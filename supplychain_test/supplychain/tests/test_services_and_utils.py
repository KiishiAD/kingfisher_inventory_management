from decimal import Decimal
from unittest.mock import Mock, patch

import pandas as pd
from django.test import TestCase
from django.utils import timezone
from model_bakery import baker

from supplychain.models import (
    Category,
    Destination,
    LowStockAlert,
    Payment,
    Product,
    PurchaseOrder,
    PurchaseOrderApproval,
    PurchaseOrderItem,
    Receiving,
    ReceivingItem,
    RequisitionApproval,
    RequisitionItem,
    StockTransaction,
    Supplier,
    UnitOfMeasure,
)
from supplychain.services import inventory as inv
from supplychain.services.uploads import product_bulk_upload as bulk
from supplychain import utils
from supplychain.templatetags.status_tags import status_badge
from supplychain.tests.models.helpers import make_product, make_requisition, make_user, make_po


class InventoryServiceTests(TestCase):
    def test_on_hand_and_low_stock_lifecycle(self):
        product = make_product(low_stock_threshold=Decimal("5.00"))
        baker.make(StockTransaction, product=product, transaction_type=StockTransaction.RECEIVE, quantity=Decimal("10.00"))
        baker.make(StockTransaction, product=product, transaction_type=StockTransaction.ISSUE, quantity=Decimal("7.00"))
        baker.make(StockTransaction, product=product, transaction_type=StockTransaction.ADJUST_OUT, quantity=Decimal("1.00"))

        self.assertEqual(inv.on_hand(product.id), Decimal("2"))
        inv.evaluate_low_stock(product.id)
        alert = LowStockAlert.objects.get(product=product, resolved_at__isnull=True)
        self.assertEqual(alert.threshold, Decimal("5.00"))

        product.low_stock_threshold = Decimal("3.00")
        product.save(update_fields=["low_stock_threshold"])
        inv.evaluate_low_stock(product.id)
        alert.refresh_from_db()
        self.assertEqual(alert.threshold, Decimal("3.00"))

        baker.make(StockTransaction, product=product, transaction_type=StockTransaction.ADJUST_IN, quantity=Decimal("10.00"))
        inv.evaluate_low_stock(product.id)
        alert.refresh_from_db()
        self.assertIsNotNone(alert.resolved_at)

    def test_evaluate_low_stock_ignores_null_threshold(self):
        product = make_product(low_stock_threshold=None)
        inv.evaluate_low_stock(product.id)
        self.assertFalse(LowStockAlert.objects.exists())

    def test_record_receiving_as_stock_only_when_reviewed_and_idempotent(self):
        po = make_po()
        product = make_product()
        item = baker.make(PurchaseOrderItem, purchase_order=po, product=product, quantity=Decimal("3.00"), unit_cost=Decimal("2.00"))
        receiving = baker.make(Receiving, purchase_order=po, status=Receiving.PENDING)
        baker.make(ReceivingItem, receiving=receiving, po_item=item, actual_quantity=Decimal("4.00"))

        inv.record_receiving_as_stock(receiving.id)
        self.assertFalse(StockTransaction.objects.exists())

        receiving.status = Receiving.REVIWED
        receiving.save(update_fields=["status"])
        inv.record_receiving_as_stock(receiving.id)
        inv.record_receiving_as_stock(receiving.id)
        txn = StockTransaction.objects.get(product=product, source_type=StockTransaction.SRC_RECEIVING)
        self.assertEqual(txn.quantity, Decimal("4.00"))

    def test_record_store_requisition_issue_only_for_approved_store(self):
        user = make_user()
        product = make_product()
        store = Destination.objects.get_or_create(name=Destination.STORE)[0]
        purchase = Destination.objects.get_or_create(name=Destination.PURCHASE)[0]
        req = make_requisition(requester=user, destination=purchase, status="PENDING")
        RequisitionItem.objects.create(requisition=req, product=product, quantity=Decimal("2.00"))

        inv.record_store_requisition_issue(req.id, user.id)
        self.assertFalse(StockTransaction.objects.exists())

        req.destination = store
        req.status = "APPROVED"
        req.save(update_fields=["destination", "status"])
        inv.record_store_requisition_issue(req.id, user.id)
        txn = StockTransaction.objects.get(product=product, source_type=StockTransaction.SRC_REQUISITION)
        self.assertEqual(txn.transaction_type, StockTransaction.ISSUE)
        self.assertEqual(txn.quantity, Decimal("2.00"))


class ProductBulkUploadServiceTests(TestCase):
    def test_small_helpers(self):
        df = pd.DataFrame({" Name ": [" Widget "], "UOM Code": ["EA"]})
        self.assertEqual(list(bulk._norm_cols(df).columns), ["name", "uom_code"])
        self.assertEqual(bulk._split("a, b,,"), ["a", "b"])
        self.assertEqual(bulk._split(pd.NA), [])
        self.assertEqual(bulk._dec_required("1.25", "price"), Decimal("1.25"))
        with self.assertRaisesMessage(ValueError, "required"):
            bulk._dec_required("", "price")
        with self.assertRaisesMessage(ValueError, "valid number"):
            bulk._dec_required("x", "price")
        self.assertEqual(bulk._str_optional(pd.NA), "")
        self.assertEqual(bulk._norm_name("  A   B  "), "A B")

    def test_get_or_create_uom_rules(self):
        uom = UnitOfMeasure.objects.create(code="TSTKG", name="TSTKG")
        same = bulk._get_or_create_uom("TSTKG", "TestKilogram")
        same.refresh_from_db()
        self.assertEqual(same, uom)
        self.assertEqual(same.name, "TestKilogram")

        UnitOfMeasure.objects.create(code="TSTL", name="TestLitre")
        with self.assertRaisesMessage(ValueError, "already exists"):
            bulk._get_or_create_uom("LTR", "TestLitre")

    def test_import_products_df_create_update_lists_stock_and_errors(self):
        actor = make_user(email="actor@example.com")
        assigned = make_user(email="person@example.com")
        df = pd.DataFrame([
            {
                "sku": "SKU-1",
                "name": "Widget",
                "description": "Useful",
                "unit_cost": "3.50",
                "uom_code": "EA",
                "uom_name": "Each",
                "stock_level": "5",
                "categories": "Consumables, Office",
                "vendors": "Acme, Best",
                "assigned_users": assigned.email,
            },
            {"name": "", "unit_cost": "4.00", "uom_code": "EA", "stock_level": "1"},
            {"name": "Bad Stock", "unit_cost": "4.00", "uom_code": "EA", "stock_level": "-1"},
        ])

        result = bulk.import_products_df(df, actor=actor, upload_id=99)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["inventory_adjusted"], 1)
        self.assertEqual(len(result["errors"]), 2)
        product = Product.objects.get(sku="SKU-1")
        self.assertEqual(product.name, "Widget")
        self.assertEqual(set(product.categories.values_list("name", flat=True)), {"Consumables", "Office"})
        self.assertEqual(set(product.vendors.values_list("name", flat=True)), {"Acme", "Best"})
        self.assertEqual(list(product.assigned_users.values_list("email", flat=True)), [assigned.email])
        self.assertEqual(bulk._current_stock(product.id), Decimal("5"))

        update = bulk.import_products_df(
            pd.DataFrame([{"sku": "SKU-1", "name": "Widget Pro", "unit_cost": "4.00", "uom_code": "EA", "stock_level": "2"}]),
            actor=actor,
            upload_id=100,
        )
        product.refresh_from_db()
        self.assertEqual(update["updated"], 1)
        self.assertEqual(product.name, "Widget Pro")
        self.assertEqual(bulk._current_stock(product.id), Decimal("2"))

    def test_import_products_missing_upload_columns_and_duplicate_without_sku(self):
        with self.assertRaisesMessage(ValueError, "upload reference"):
            bulk.import_products_df(pd.DataFrame())
        with self.assertRaisesMessage(ValueError, "Missing required"):
            bulk.import_products_df(pd.DataFrame({"name": ["x"]}), upload_id=1)

        uom = UnitOfMeasure.objects.create(code="TSTEA", name="TestEach")
        Product.objects.create(name="Known", uom=uom, unit_cost=Decimal("1.00"))
        result = bulk.import_products_df(
            pd.DataFrame([{"name": "Known", "unit_cost": "1", "uom_code": "TSTEA", "stock_level": "0"}]),
            upload_id=2,
        )
        self.assertIn("Product already exists", result["errors"][0]["message"])


class WorkflowUtilsTests(TestCase):
    def test_generate_po_for_requisition_single_supplier_and_existing(self):
        user = make_user()
        supplier = baker.make(Supplier, name="Vendor")
        product = make_product(unit_cost=Decimal("7.25"))
        req = make_requisition(requester=user, destination=Destination.objects.get_or_create(name=Destination.PURCHASE)[0], supplier=supplier, status="APPROVED")
        RequisitionItem.objects.create(requisition=req, product=product, quantity=Decimal("3.00"))

        po = utils.generate_po_for_requisition(req, created_by=user)
        self.assertEqual(po.supplier, supplier)
        self.assertEqual(po.items.get().unit_cost, Decimal("7.25"))
        self.assertEqual(utils.generate_po_for_requisition(req, created_by=user), po)

    def test_generate_po_for_requisition_vendor_fallback_and_missing_supplier(self):
        user = make_user()
        vendor = baker.make(Supplier)
        product = make_product()
        product.vendors.add(vendor)
        req = make_requisition(requester=user, destination=Destination.objects.get_or_create(name=Destination.PURCHASE)[0], status="APPROVED")
        RequisitionItem.objects.create(requisition=req, product=product, quantity=Decimal("1.00"))
        self.assertEqual(utils.generate_po_for_requisition(req, user).supplier, vendor)

        req2 = make_requisition(requester=user, destination=Destination.objects.get_or_create(name=Destination.PURCHASE)[0], status="APPROVED")
        RequisitionItem.objects.create(requisition=req2, product=make_product(), quantity=Decimal("1.00"))
        with self.assertRaisesMessage(ValueError, "has no supplier"):
            utils.generate_po_for_requisition(req2, user)

    def test_generate_receiving_for_purchase_order_idempotent(self):
        po = make_po()
        item = baker.make(PurchaseOrderItem, purchase_order=po, product=make_product(), quantity=Decimal("2.00"), unit_cost=Decimal("1.00"))
        rec = utils.generate_receiving_for_purchase_order(po)
        self.assertEqual(rec.items.get().po_item, item)
        self.assertEqual(utils.generate_receiving_for_purchase_order(po), rec)

    def test_payment_and_workitem_timelines(self):
        user = make_user()
        supplier = baker.make(Supplier)
        req = make_requisition(requester=user, supplier=supplier, destination=Destination.objects.get_or_create(name=Destination.PURCHASE)[0])
        RequisitionApproval.objects.create(requisition=req, approver=user, action="PENDING", notes="sent")
        po = baker.make(PurchaseOrder, requisition=req, supplier=supplier, created_by=user)
        PurchaseOrderApproval.objects.create(purchase_order=po, approver=user, action="APPROVED", notes="ok")
        baker.make(PurchaseOrderItem, purchase_order=po, product=make_product(), quantity=Decimal("1.00"), unit_cost=Decimal("2.00"))
        payment = baker.make(Payment, purchase_order=po, created_by=user, processed_by=user, processed_at=timezone.now(), status=Payment.PROCESSED, payment_type=Payment.CHEQUE, payment_notes="paid")
        rec = utils.generate_receiving_for_purchase_order(po)
        rec.received_at = timezone.now(); rec.received_by = user; rec.reviewed_at = timezone.now(); rec.reviewed_by = user; rec.status = Receiving.REVIWED; rec.save()
        rec.items.update(actual_quantity=Decimal("1.50"), accounting_queried=True, accounting_notes="check")

        events = utils.build_workitem_timeline(req)
        labels = [e["label"] for e in events]
        self.assertIn(f"Payment processed ({payment.get_payment_type_display()})", labels)
        self.assertTrue(any("Receiving recorded" in label for label in labels))
        self.assertEqual(utils.build_workitem_timeline_for_po(po), events)
        self.assertIn("WITHIN 0.50", utils._receiving_variance_details(rec))
        self.assertIn("Queried lines", utils._receiving_queried_lines_details(rec))
        self.assertEqual(utils._fmt2(None), "—")
        self.assertEqual(utils._fmt2("bad"), "bad")

    def test_status_badge_known_and_unknown(self):
        self.assertIn("text-bg-success", status_badge("APPROVED"))
        self.assertIn("text-bg-secondary", status_badge("CUSTOM"))
        self.assertIn("Custom", status_badge("CUSTOM"))
