import time
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from .helpers import make_uom, make_po_item, make_product
from supplychain.models import Receiving, ReceivingItem


class TimestampBehaviorTests(TestCase):
    def test_created_and_updated_auto_fields(self):
        uom = make_uom()
        self.assertIsNotNone(uom.created_at)
        self.assertIsNotNone(uom.updated_at)

    def test_updated_at_changes_on_save(self):
        uom = make_uom()
        original_updated = uom.updated_at
        time.sleep(0.01)
        uom.name = "NewName" if uom.name != "NewName" else "AnotherName"
        uom.save()
        uom.refresh_from_db()
        self.assertGreaterEqual(uom.updated_at, original_updated)
        self.assertNotEqual(uom.updated_at, original_updated)


class JSONFieldIndependenceTests(TestCase):
    def test_flagged_for_dict_is_per_instance_not_shared(self):
        poi = make_po_item()
        rec = baker.make(Receiving, purchase_order=poi.purchase_order, supplier_invoice=SimpleUploadedFile("i.pdf", b"x"))
        ri1 = baker.make(ReceivingItem, receiving=rec, po_item=poi)
        ri2 = baker.make(ReceivingItem, receiving=rec, po_item=poi)
        ri1.flagged_for["audit"] = True
        ri1.save()
        ri2.refresh_from_db()
        self.assertTrue(ri1.flagged_for.get("audit", False))
        self.assertFalse(ri2.flagged_for.get("audit", False))
