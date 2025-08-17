"""
Place this file at: supplychain/tests/test_models.py

Prereqs:
  pip install model-bakery
Run:
  python manage.py test supplychain

Notes:
- Uses AAA pattern (Arrange–Act–Assert)
- Uses model_bakery to avoid repetitive setup
- Exercises uniques, choices validation, M2M ops, on_delete behaviors (CASCADE/PROTECT/SET_NULL), FileFields, JSONField, timestamps
- Adjusted to avoid UNIQUE errors from preloaded Destination rows
- Adjusted tests to reflect PROTECT chain from ReceivingItem -> PurchaseOrderItem -> PurchaseOrder
"""

from decimal import Decimal
import os
import shutil
import tempfile
import time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings

from model_bakery import baker

from supplychain.models import (
    UnitOfMeasure,
    Category,
    Supplier,
    Product,
    Destination,
    Requisition,
    RequisitionItem,
    RequisitionApproval,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderApproval,
    Receiving,
    ReceivingItem,
    InvoiceLineApproval,
    Payment,
    IssuanceRequest,
    IssuanceItem,
    StockTransaction,
    LowStockAlert,
)


# -----------------------------
# Helpers
# -----------------------------

User = get_user_model()


def make_user(**kwargs):
    """Create a user with sane defaults via bakery."""
    return baker.make(User, **kwargs)


def make_uom(**kwargs):
    return baker.make(UnitOfMeasure, **kwargs)


def make_category(**kwargs):
    return baker.make(Category, **kwargs)


def make_supplier(**kwargs):
    return baker.make(Supplier, **kwargs)


def make_product(**kwargs):
    defaults = {
        "uom": make_uom(),
        "unit_cost": Decimal("10.00"),
    }
    defaults.update(kwargs)
    return baker.make(Product, **defaults)


def make_destination(name=Destination.STORE):
    # Some environments preload Destination rows via data migrations.
    # Use get_or_create to avoid UNIQUE errors on the `name` field.
    obj, _ = Destination.objects.get_or_create(name=name)
    return obj


def make_requisition(**kwargs):
    defaults = {
        "requester": make_user(),
        "destination": make_destination(),
    }
    defaults.update(kwargs)
    return baker.make(Requisition, **defaults)


def make_po(**kwargs):
    defaults = {
        "supplier": make_supplier(),
        "created_by": make_user(),
    }
    defaults.update(kwargs)
    return baker.make(PurchaseOrder, **defaults)


def make_po_item(**kwargs):
    defaults = {
        "purchase_order": make_po(),
        "product": make_product(),
        "quantity": Decimal("2.00"),
        "unit_cost": Decimal("5.00"),
    }
    defaults.update(kwargs)
    return baker.make(PurchaseOrderItem, **defaults)


# -----------------------------
# Master Data
# -----------------------------

class UnitOfMeasureModelTests(TestCase):
    def test_str_returns_name_and_code(self):
        # Arrange
        uom = make_uom(code="KG", name="Kilogram")
        # Act
        s = str(uom)
        # Assert
        self.assertEqual(s, "Kilogram (KG)")

    def test_unique_code_and_name_enforced(self):
        # Arrange
        make_uom(code="L", name="Liter")
        # Act + Assert: duplicate code
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_uom(code="L", name="SomethingElse")
        # Act + Assert: duplicate name
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_uom(code="XX", name="Liter")


class CategoryModelTests(TestCase):
    def test_str(self):
        # Arrange
        c = make_category(name="Beverages")
        # Act
        s = str(c)
        # Assert
        self.assertEqual(s, "Beverages")

    def test_unique_name(self):
        # Arrange
        make_category(name="Staples")
        # Act + Assert
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_category(name="Staples")


class SupplierModelTests(TestCase):
    def test_str(self):
        # Arrange
        s = make_supplier(name="Acme Trading")
        # Act
        text = str(s)
        # Assert
        self.assertEqual(text, "Acme Trading")

    def test_blank_fields_allowed(self):
        # Arrange
        s = make_supplier(contact_email="", phone_number="", address="")
        # Act + Assert
        self.assertEqual(s.contact_email, "")
        self.assertEqual(s.phone_number, "")
        self.assertEqual(s.address, "")


class ProductModelTests(TestCase):
    def test_str(self):
        # Arrange
        p = make_product(name="Tomatoes")
        # Act
        s = str(p)
        # Assert
        self.assertEqual(s, "Tomatoes")

    def test_m2m_additions_and_no_duplicates(self):
        # Arrange
        p = make_product()
        c1, c2 = make_category(name="Veg"), make_category(name="Fruit")
        v1, v2 = make_supplier(name="S1"), make_supplier(name="S2")
        u1, u2 = make_user(username="u1"), make_user(username="u2")
        # Act
        p.categories.add(c1, c2, c1)  # duplicate add
        p.vendors.add(v1, v2, v2)      # duplicate add
        p.assigned_users.add(u1, u2, u2)
        # Assert
        self.assertEqual(p.categories.count(), 2)
        self.assertEqual(p.vendors.count(), 2)
        self.assertEqual(p.assigned_users.count(), 2)

    def test_cannot_delete_uom_when_product_exists(self):
        # Arrange
        uom = make_uom()
        make_product(uom=uom)
        # Act + Assert
        with self.assertRaises(ProtectedError):
            uom.delete()


# -----------------------------
# Requisition & Approvals
# -----------------------------

class DestinationModelTests(TestCase):
    def test_str_returns_humanized_choice(self):
        # Arrange
        d = make_destination(Destination.SUPPLIER)
        # Act
        s = str(d)
        # Assert
        self.assertEqual(s, "Supplier")

    def test_invalid_choice_rejected_by_full_clean(self):
        # Arrange
        d = Destination(name="NOT_A_REAL_CHOICE")
        # Act + Assert
        with self.assertRaises(ValidationError):
            d.full_clean()  # choices enforced at validation time


class RequisitionModelTests(TestCase):
    def test_defaults_and_str_and_destination_display(self):
        # Arrange
        user = make_user()
        dest = make_destination(Destination.STORE)
        # Act
        r = make_requisition(requester=user, destination=dest)
        # Assert
        self.assertEqual(r.status, Requisition.PENDING)
        self.assertFalse(r.urgent)
        self.assertIn("Requisition #", str(r))
        self.assertEqual(r.get_destination_display(), "Store")

    def test_destination_protects_from_deletion(self):
        # Arrange
        dest = make_destination(Destination.SUPPLIER)
        make_requisition(destination=dest)
        # Act + Assert
        with self.assertRaises(ProtectedError):
            dest.delete()


class RequisitionItemModelTests(TestCase):
    def test_str(self):
        # Arrange
        r = make_requisition()
        p = make_product(name="Rice")
        item = baker.make(RequisitionItem, requisition=r, product=p, quantity=Decimal("3.50"))
        # Act
        s = str(item)
        # Assert
        self.assertEqual(s, "3.50 x Rice")

    def test_requisition_delete_cascades_items(self):
        # Arrange
        r = make_requisition()
        baker.make(RequisitionItem, requisition=r)
        # Act
        r.delete()
        # Assert
        self.assertEqual(RequisitionItem.objects.count(), 0)


class RequisitionApprovalModelTests(TestCase):
    def test_valid_action_choices(self):
        # Arrange
        r = make_requisition()
        approver = make_user()
        # Act
        ra = baker.make(RequisitionApproval, requisition=r, approver=approver, action=Requisition.APPROVED)
        # Assert
        self.assertEqual(ra.action, Requisition.APPROVED)

    def test_invalid_action_full_clean_raises(self):
        # Arrange
        ra = baker.prepare(RequisitionApproval, action="BOGUS")
        # Act + Assert
        with self.assertRaises(ValidationError):
            ra.full_clean()


# -----------------------------
# Purchase Orders & Approvals
# -----------------------------

class PurchaseOrderModelTests(TestCase):
    def test_defaults_and_str(self):
        # Arrange
        po = make_po(status=PurchaseOrder.DRAFT)
        # Act
        s = str(po)
        # Assert
        self.assertEqual(po.status, PurchaseOrder.DRAFT)
        self.assertIn("PO #", s)

    def test_supplier_protects_from_deletion(self):
        # Arrange
        supplier = make_supplier()
        baker.make(PurchaseOrder, supplier=supplier)
        # Act + Assert
        with self.assertRaises(ProtectedError):
            supplier.delete()

    def test_delete_requisition_sets_po_requisition_to_null(self):
        # Arrange
        req = make_requisition()
        po = make_po(requisition=req)
        # Act
        req.delete()
        po.refresh_from_db()
        # Assert
        self.assertIsNone(po.requisition)


class PurchaseOrderItemModelTests(TestCase):
    def test_str(self):
        # Arrange
        p = make_product(name="Sugar")
        poi = make_po_item(product=p, quantity=Decimal("7.00"), unit_cost=Decimal("2.50"))
        # Act
        s = str(poi)
        # Assert
        self.assertEqual(s, "7.00 x Sugar @ 2.50")

    def test_cannot_delete_product_if_referenced_by_po_item(self):
        # Arrange
        p = make_product()
        make_po_item(product=p)
        # Act + Assert
        with self.assertRaises(ProtectedError):
            p.delete()


class PurchaseOrderApprovalModelTests(TestCase):
    def test_invalid_action_full_clean_raises(self):
        # Arrange
        poa = baker.prepare(PurchaseOrderApproval, action="NOT_VALID")
        # Act + Assert
        with self.assertRaises(ValidationError):
            poa.full_clean()


# -----------------------------
# Receiving & Invoice Processing
# -----------------------------

class _MediaRootMixin:
    """Provide a per-class temporary MEDIA_ROOT for FileField tests."""
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_dir = tempfile.mkdtemp(prefix="test_media_")
        cls._override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)
        super().tearDownClass()


class ReceivingModelTests(_MediaRootMixin, TestCase):
    def test_receiving_requires_invoice_file_and_str(self):
        # Arrange
        po = make_po()
        user = make_user()
        upload = SimpleUploadedFile("invoice.pdf", b"pdf-bytes")
        # Act
        rec = baker.make(Receiving, purchase_order=po, received_by=user, supplier_invoice=upload)
        # Assert
        self.assertTrue(os.path.exists(rec.supplier_invoice.path))
        self.assertIn("Receiving #", str(rec))
        self.assertIsNotNone(rec.received_at)

    def test_receivingitem_str_and_flags_default(self):
        # Arrange
        poi = make_po_item()
        upload = SimpleUploadedFile("invoice.pdf", b"abc")
        rec = baker.make(Receiving, purchase_order=poi.purchase_order, supplier_invoice=upload)
        # Act
        ri = baker.make(ReceivingItem, receiving=rec, po_item=poi, actual_quantity=Decimal("1.25"))
        # Assert
        self.assertEqual(str(ri), f"1.25 of {poi.product}")
        self.assertIsInstance(ri.flagged_for, dict)

    def test_delete_po_cascades_po_items_when_no_receipts(self):
        # Arrange
        poi = make_po_item()
        po = poi.purchase_order
        # Act
        po.delete()
        # Assert
        self.assertEqual(PurchaseOrder.objects.count(), 0)
        self.assertEqual(PurchaseOrderItem.objects.count(), 0)

    def test_delete_po_blocked_if_receivingitems_exist(self):
        # Arrange
        poi = make_po_item()
        upload = SimpleUploadedFile("invoice.pdf", b"data")
        rec = baker.make(Receiving, purchase_order=poi.purchase_order, supplier_invoice=upload)
        baker.make(ReceivingItem, receiving=rec, po_item=poi)
        # Act + Assert
        with self.assertRaises(ProtectedError):
            poi.purchase_order.delete()

    def test_cannot_delete_po_item_if_receivingitem_exists(self):
        # Arrange
        poi = make_po_item()
        upload = SimpleUploadedFile("invoice.pdf", b"data")
        rec = baker.make(Receiving, purchase_order=poi.purchase_order, supplier_invoice=upload)
        baker.make(ReceivingItem, receiving=rec, po_item=poi)
        # Act + Assert
        with self.assertRaises(ProtectedError):
            poi.delete()


class InvoiceLineApprovalModelTests(TestCase):
    def test_str_variants(self):
        # Arrange
        poi = make_po_item()
        ri = baker.make(ReceivingItem, receiving=baker.make(Receiving, purchase_order=poi.purchase_order, supplier_invoice=SimpleUploadedFile("i.pdf", b"x")), po_item=poi)
        acc = make_user()

        # Act
        a1 = baker.make(InvoiceLineApproval, receiving_item=ri, accountant=acc, approved=True)
        a2 = baker.make(InvoiceLineApproval, receiving_item=ri, accountant=acc, approved=False)
        a3 = baker.make(InvoiceLineApproval, receiving_item=ri, accountant=acc, approved=None)

        # Assert
        self.assertTrue(str(a1).startswith("Approved "))
        self.assertTrue(str(a2).startswith("Denied "))
        self.assertTrue(str(a3).startswith("Queried "))


# -----------------------------
# Payment
# -----------------------------

class PaymentModelTests(_MediaRootMixin, TestCase):
    def test_defaults_and_str(self):
        # Arrange
        po = make_po()
        pay = baker.make(Payment, purchase_order=po, payment_type=Payment.TRANSFER)
        # Act
        s = str(pay)
        # Assert
        self.assertFalse(pay.approved_by_mum)
        self.assertIn("Payment for", s)
        self.assertIsNotNone(pay.processed_at)

    def test_one_to_one_uniqueness(self):
        # Arrange
        po = make_po()
        baker.make(Payment, purchase_order=po, payment_type=Payment.CHEQUE)
        # Act + Assert
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                baker.make(Payment, purchase_order=po, payment_type=Payment.TRANSFER)

    def test_delete_po_cascades_payment(self):
        # Arrange
        po = make_po()
        baker.make(Payment, purchase_order=po, payment_type=Payment.CHEQUE)
        # Act
        po.delete()
        # Assert
        self.assertEqual(Payment.objects.count(), 0)


# -----------------------------
# Issuance
# -----------------------------

class IssuanceModelTests(TestCase):
    def test_issuance_request_defaults_and_str(self):
        # Arrange
        req = make_requisition()
        # Act
        ir = baker.make(IssuanceRequest, requester=req.requester, requisition=req)
        # Assert
        self.assertEqual(ir.status, IssuanceRequest.PENDING)
        self.assertIn("IssuanceRequest #", str(ir))

    def test_issuance_item_str(self):
        # Arrange
        ir = baker.make(IssuanceRequest, requester=make_user())
        p = make_product(name="Beans")
        # Act
        ii = baker.make(IssuanceItem, issuance_request=ir, product=p, quantity=Decimal("4.00"))
        # Assert
        self.assertEqual(str(ii), "4.00 x Beans")


# -----------------------------
# Inventory & Alerts
# -----------------------------

class StockAndAlertsModelTests(TestCase):
    def test_stock_transaction_str_and_protect(self):
        # Arrange
        p = make_product(name="Oil")
        st = baker.make(StockTransaction, product=p, transaction_type=StockTransaction.RECEIVE, quantity=Decimal("9.00"))
        # Act
        s = str(st)
        # Assert
        self.assertEqual(s, f"RECEIVE 9.00 of {p}")
        # PROTECT: cannot delete product while transactions exist
        with self.assertRaises(ProtectedError):
            p.delete()

    def test_low_stock_alert_defaults_and_str(self):
        # Arrange
        p = make_product(name="Flour")
        # Act
        alert = baker.make(LowStockAlert, product=p, threshold=Decimal("2.50"))
        # Assert
        self.assertFalse(alert.acknowledged)
        self.assertIn("Low stock alert for", str(alert))


# -----------------------------
# Cross-cutting: timestamps & JSONField behavior
# -----------------------------

class TimestampBehaviorTests(TestCase):
    def test_created_and_updated_auto_fields(self):
        # Arrange
        uom = make_uom()
        # Act + Assert
        self.assertIsNotNone(uom.created_at)
        self.assertIsNotNone(uom.updated_at)

    def test_updated_at_changes_on_save(self):
        # Arrange
        uom = make_uom()
        original_updated = uom.updated_at
        time.sleep(0.01)  # ensure clock tick
        uom.name = "NewName" if uom.name != "NewName" else "AnotherName"
        uom.save()
        # Act
        uom.refresh_from_db()
        # Assert
        self.assertGreaterEqual(uom.updated_at, original_updated)
        self.assertNotEqual(uom.updated_at, original_updated)


class JSONFieldIndependenceTests(TestCase):
    def test_flagged_for_dict_is_per_instance_not_shared(self):
        # Arrange
        poi = make_po_item()
        rec = baker.make(Receiving, purchase_order=poi.purchase_order, supplier_invoice=SimpleUploadedFile("i.pdf", b"x"))
        ri1 = baker.make(ReceivingItem, receiving=rec, po_item=poi)
        ri2 = baker.make(ReceivingItem, receiving=rec, po_item=poi)
        # Act
        ri1.flagged_for["audit"] = True
        ri1.save()
        ri2.refresh_from_db()
        # Assert
        self.assertTrue(ri1.flagged_for.get("audit", False))
        self.assertFalse(ri2.flagged_for.get("audit", False))
