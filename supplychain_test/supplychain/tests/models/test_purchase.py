"""Purchase order model tests.

Validates PurchaseOrder and PurchaseOrderItem behavior: defaults and
string formatting, delete-protection for suppliers/products, and
validation of approval actions.
"""

from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from model_bakery import baker

from .helpers import make_supplier, make_po, make_requisition
from .helpers import make_product, make_po_item

from supplychain.models import PurchaseOrder, PurchaseOrderItem, PurchaseOrderApproval


class PurchaseOrderModelTests(TestCase):
    def test_defaults_and_str(self):
        po = make_po(status=PurchaseOrder.DRAFT)
        self.assertEqual(po.status, PurchaseOrder.DRAFT)
        self.assertIn("PO #", str(po))

    def test_supplier_protects_from_deletion(self):
        supplier = make_supplier()
        baker.make(PurchaseOrder, supplier=supplier)
        with self.assertRaises(ProtectedError):
            supplier.delete()

    def test_delete_requisition_sets_po_requisition_to_null(self):
        req = make_requisition()
        po = make_po(requisition=req)
        req.delete()
        po.refresh_from_db()
        self.assertIsNone(po.requisition)


class PurchaseOrderItemModelTests(TestCase):
    def test_str(self):
        from decimal import Decimal
        p = make_product(name="Sugar")
        poi = make_po_item(product=p, quantity=Decimal("7.00"), unit_cost=Decimal("2.50"))
        self.assertEqual(str(poi), "7.00 x Sugar @ 2.50")

    def test_cannot_delete_product_if_referenced_by_po_item(self):
        p = make_product()
        make_po_item(product=p)
        with self.assertRaises(ProtectedError):
            p.delete()


class PurchaseOrderApprovalModelTests(TestCase):
    def test_invalid_action_full_clean_raises(self):
        poa = baker.prepare(PurchaseOrderApproval, action="NOT_VALID")
        with self.assertRaises(Exception):
            poa.full_clean()
