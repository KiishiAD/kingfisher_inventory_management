"""Inventory tests for StockTransaction and LowStockAlert.

Verifies string formatting for transactions (Decimal-aware), deletion
protections while transactions exist, and default/formatting behavior for
low-stock alerts.
"""

from decimal import Decimal
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from model_bakery import baker

from .helpers import make_product, make_po_item
from supplychain.models import StockTransaction, LowStockAlert


class StockAndAlertsModelTests(TestCase):
    def test_stock_transaction_str_and_protect(self):
        p = make_product(name="Oil")
        st = baker.make(StockTransaction, product=p, transaction_type=StockTransaction.RECEIVE, quantity=Decimal("9.00"))
        self.assertEqual(str(st), f"RECEIVE 9.00 of {p}")
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError):
            p.delete()

    def test_low_stock_alert_defaults_and_str(self):
        p = make_product(name="Flour")
        alert = baker.make(LowStockAlert, product=p, threshold=Decimal("2.50"))
        self.assertFalse(alert.acknowledged)
        self.assertIn("Low stock alert for", str(alert))
