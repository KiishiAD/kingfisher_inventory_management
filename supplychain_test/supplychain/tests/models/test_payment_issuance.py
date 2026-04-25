"""Payment model tests."""

from django.db import IntegrityError, transaction
from django.test import TestCase
from model_bakery import baker

from .helpers import make_po, make_user
from supplychain.models import Payment


class PaymentModelTests(TestCase):
    def test_defaults_and_str(self):
        po = make_po()
        user = make_user(username="payer")
        pay = baker.make(Payment, purchase_order=po, created_by=user, payment_type=Payment.TRANSFER)

        self.assertEqual(pay.status, Payment.PENDING)
        self.assertFalse(pay.approved_by_coo)
        self.assertIsNone(pay.processed_at)
        self.assertIn(f"Payment #{pay.id} for PO #{po.id}", str(pay))
        self.assertIn("Pending Payment", str(pay))

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
