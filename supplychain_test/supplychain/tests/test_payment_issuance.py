from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from model_bakery import baker

from .helpers import make_po, make_product, make_requisition, make_user
from supplychain.models import Payment, IssuanceRequest, IssuanceItem


class PaymentModelTests(TestCase):
    def test_defaults_and_str(self):
        po = make_po()
        pay = baker.make(Payment, purchase_order=po, payment_type=Payment.TRANSFER)
        self.assertFalse(pay.approved_by_mum)
        self.assertIn("Payment for", str(pay))
        self.assertIsNotNone(pay.processed_at)

    def test_one_to_one_uniqueness(self):
        po = make_po()
        baker.make(Payment, purchase_order=po, payment_type=Payment.CHEQUE)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                baker.make(Payment, purchase_order=po, payment_type=Payment.TRANSFER)

    def test_delete_po_cascades_payment(self):
        po = make_po()
        baker.make(Payment, purchase_order=po, payment_type=Payment.CHEQUE)
        po.delete()
        self.assertEqual(Payment.objects.count(), 0)


class IssuanceModelTests(TestCase):
    def test_issuance_request_defaults_and_str(self):
        req = make_requisition()
        ir = baker.make(IssuanceRequest, requester=req.requester, requisition=req)
        self.assertEqual(ir.status, IssuanceRequest.PENDING)
        self.assertIn("IssuanceRequest #", str(ir))

    def test_issuance_item_str(self):
        from decimal import Decimal
        ir = baker.make(IssuanceRequest, requester=make_user())
        p = make_product(name="Beans")
        ii = baker.make(IssuanceItem, issuance_request=ir, product=p, quantity=Decimal("4.00"))
        self.assertEqual(str(ii), "4.00 x Beans")
