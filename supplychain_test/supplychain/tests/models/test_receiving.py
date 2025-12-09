"""Receiving and invoice-line tests.

Tests ensure supplier invoice files are handled, Receiving/ReceivingItem
string formatting is correct, deletion protections when receipts exist are
enforced, and InvoiceLineApproval string variants reflect approval state.
_MediaRootMixin provides a temporary MEDIA_ROOT so uploaded files do not
pollute the real media directory.
"""

import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from model_bakery import baker

from .helpers import make_po_item, make_po, make_user
from supplychain.models import Receiving, ReceivingItem, PurchaseOrder, PurchaseOrderItem, InvoiceLineApproval


class _MediaRootMixin:
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
        po = make_po()
        user = make_user()
        upload = SimpleUploadedFile("invoice.pdf", b"pdf-bytes")
        rec = baker.make(Receiving, purchase_order=po, received_by=user, supplier_invoice=upload)
        self.assertTrue(os.path.exists(rec.supplier_invoice.path))
        self.assertIn("Receiving #", str(rec))
        self.assertIsNone(rec.received_at)

    def test_receivingitem_str_and_flags_default(self):
        poi = make_po_item()
        upload = SimpleUploadedFile("invoice.pdf", b"abc")
        rec = baker.make(Receiving, purchase_order=poi.purchase_order, supplier_invoice=upload)
        ri = baker.make(ReceivingItem, receiving=rec, po_item=poi, actual_quantity=1.25)
        self.assertEqual(str(ri), f"1.25 of {poi.product}")
        self.assertIsInstance(ri.flagged_for, dict)

    def test_delete_po_cascades_po_items_when_no_receipts(self):
        poi = make_po_item()
        po = poi.purchase_order
        po.delete()
        self.assertEqual(PurchaseOrder.objects.count(), 0)
        self.assertEqual(PurchaseOrderItem.objects.count(), 0)

    def test_delete_po_blocked_if_receivingitems_exist(self):
        poi = make_po_item()
        upload = SimpleUploadedFile("invoice.pdf", b"data")
        rec = baker.make(Receiving, purchase_order=poi.purchase_order, supplier_invoice=upload)
        baker.make(ReceivingItem, receiving=rec, po_item=poi)
        with self.assertRaises(ProtectedError):
            poi.purchase_order.delete()

    def test_cannot_delete_po_item_if_receivingitem_exists(self):
        poi = make_po_item()
        upload = SimpleUploadedFile("invoice.pdf", b"data")
        rec = baker.make(Receiving, purchase_order=poi.purchase_order, supplier_invoice=upload)
        baker.make(ReceivingItem, receiving=rec, po_item=poi)
        with self.assertRaises(ProtectedError):
            poi.delete()


class InvoiceLineApprovalModelTests(TestCase):
    def test_str_variants(self):
        poi = make_po_item()
        ri = baker.make(ReceivingItem, receiving=baker.make(Receiving, purchase_order=poi.purchase_order, supplier_invoice=SimpleUploadedFile("i.pdf", b"x")), po_item=poi)
        acc = make_user()
        a1 = baker.make(InvoiceLineApproval, receiving_item=ri, accountant=acc, approved=True)
        a2 = baker.make(InvoiceLineApproval, receiving_item=ri, accountant=acc, approved=False)
        a3 = baker.make(InvoiceLineApproval, receiving_item=ri, accountant=acc, approved=None)
        self.assertTrue(str(a1).startswith("Approved "))
        self.assertTrue(str(a2).startswith("Denied "))
        self.assertTrue(str(a3).startswith("Queried "))
