"""
Tests for ReceivingWorkflowService — the single source of truth for
Receiving workflow state transitions.

Issue #33 — Normal clearance path (no COO required).
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from supplychain.models import Receiving, ReceivingWorkflowHistory, Payment
from supplychain.services.receiving_workflow_service import (
    ReceivingWorkflowService,
    ReceivingNotFoundError,
    InvalidStatusTransitionError,
)
from .models.helpers import make_po, make_po_item, make_user


class ReceivingWorkflowServiceTestCase(TestCase):
    """Tests for ReceivingWorkflowService.clear_for_payment (issue #33)."""

    def setUp(self):
        self.user = make_user(username="accountant")
        self.po = make_po()
        self.po_item = make_po_item(purchase_order=self.po)

    def _make_receiving(self, status=Receiving.UNDER_REVIEW):
        receiving = Receiving.objects.create(purchase_order=self.po, status=status)
        receiving.items.create(po_item=self.po_item, actual_quantity=self.po_item.quantity)
        return receiving

    def test_clear_for_payment_transitions_to_reviewed(self):
        receiving = self._make_receiving(status=Receiving.UNDER_REVIEW)
        with patch(
            "supplychain.services.receiving_workflow_service.record_receiving_as_stock"
        ):
            result = ReceivingWorkflowService.clear_for_payment(receiving.pk, self.user)
        self.assertEqual(result.status, Receiving.REVIWED)

    def test_clear_for_payment_records_accounting_approval(self):
        receiving = self._make_receiving(status=Receiving.UNDER_REVIEW)
        with patch(
            "supplychain.services.receiving_workflow_service.record_receiving_as_stock"
        ):
            ReceivingWorkflowService.clear_for_payment(receiving.pk, self.user)
        event = receiving.workflow_history.filter(
            action_type=ReceivingWorkflowHistory.ACTION_ACCOUNTING_APPROVED,
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.actor, self.user)

    def test_clear_for_payment_posts_stock(self):
        receiving = self._make_receiving(status=Receiving.UNDER_REVIEW)
        with patch(
            "supplychain.services.receiving_workflow_service.record_receiving_as_stock"
        ) as mock_stock:
            ReceivingWorkflowService.clear_for_payment(receiving.pk, self.user)
            mock_stock.assert_called_once_with(receiving.pk, self.user.pk)

    def test_clear_for_payment_idempotent(self):
        receiving = self._make_receiving(status=Receiving.UNDER_REVIEW)
        with patch(
            "supplychain.services.receiving_workflow_service.record_receiving_as_stock"
        ):
            r1 = ReceivingWorkflowService.clear_for_payment(receiving.pk, self.user)
            r2 = ReceivingWorkflowService.clear_for_payment(receiving.pk, self.user)
        self.assertEqual(r1.pk, r2.pk)
        self.assertEqual(r1.status, Receiving.REVIWED)

    def test_clear_for_payment_raises_on_pending(self):
        receiving = self._make_receiving(status=Receiving.PENDING)
        with self.assertRaises(InvalidStatusTransitionError):
            ReceivingWorkflowService.clear_for_payment(receiving.pk, self.user)

    def test_clear_for_payment_idempotent_on_reviewed(self):
        """Calling clear_for_payment on an already-reviewed receiving is a no-op."""
        receiving = self._make_receiving(status=Receiving.REVIWED)
        with patch(
            "supplychain.services.receiving_workflow_service.record_receiving_as_stock"
        ):
            result = ReceivingWorkflowService.clear_for_payment(receiving.pk, self.user)
        self.assertEqual(result.status, Receiving.REVIWED)

    def test_clear_for_payment_raises_on_denied(self):
        receiving = self._make_receiving(status=Receiving.DENIED)
        with self.assertRaises(InvalidStatusTransitionError):
            ReceivingWorkflowService.clear_for_payment(receiving.pk, self.user)

    def test_clear_for_payment_not_found(self):
        with self.assertRaises(ReceivingNotFoundError):
            ReceivingWorkflowService.clear_for_payment(9999, self.user)

    def test_clear_for_payment_creates_payment(self):
        receiving = self._make_receiving(status=Receiving.UNDER_REVIEW)
        with patch(
            "supplychain.services.receiving_workflow_service.record_receiving_as_stock"
        ):
            ReceivingWorkflowService.clear_for_payment(receiving.pk, self.user)
        # Payment uses OneToOneField on purchase_order
        self.assertTrue(hasattr(receiving.purchase_order, 'payment'))
        self.assertEqual(receiving.purchase_order.payment.status, Payment.PENDING)
