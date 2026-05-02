from django.contrib import admin
from django.test import TestCase
from django.utils import timezone

from supplychain.models import Receiving, ReceivingWorkflowHistory
from supplychain.services.receiving_history import get_receiving_timeline

from .models.helpers import make_po, make_po_item, make_user


class ReceivingWorkflowHistoryTests(TestCase):
    def make_receiving(self):
        po = make_po()
        po_item = make_po_item(purchase_order=po)
        receiving = Receiving.objects.create(purchase_order=po)
        receiving.items.create(po_item=po_item, actual_quantity=po_item.quantity)
        return receiving

    def test_persisted_history_orders_by_occurrence_and_snapshot_actor(self):
        receiving = self.make_receiving()
        actor = make_user(first_name="Ada", last_name="Lovelace", username="ada")
        later = timezone.now()
        earlier = later - timezone.timedelta(minutes=5)

        ReceivingWorkflowHistory.objects.create_event(
            receiving=receiving,
            action_type=ReceivingWorkflowHistory.ACTION_ACCOUNTING_APPROVED,
            label="Receiving approved by accounting (cleared for payment)",
            details="Payment ready for processing.",
            actor=actor,
            occurred_at=later,
            idempotency_key="clearance",
            metadata={"payment": {"created": True}},
        )
        ReceivingWorkflowHistory.objects.create_event(
            receiving=receiving,
            action_type=ReceivingWorkflowHistory.ACTION_GOODS_RECEIVED,
            label="Receiving recorded (goods received)",
            details="All received quantities match the PO.",
            actor=actor,
            occurred_at=earlier,
            idempotency_key="goods",
        )

        events = list(get_receiving_timeline(receiving))

        self.assertEqual([event["label"] for event in events], [
            "Receiving recorded (goods received)",
            "Receiving approved by accounting (cleared for payment)",
        ])
        self.assertEqual(events[0]["who"], actor)
        self.assertEqual(events[0]["actor_display"], "Ada Lovelace")
        self.assertEqual(events[0]["source"], "persisted")
        self.assertNotIn("metadata", events[1])

    def test_history_event_idempotency_reuses_existing_event(self):
        receiving = self.make_receiving()
        occurred_at = timezone.now()

        first = ReceivingWorkflowHistory.objects.create_event(
            receiving=receiving,
            action_type=ReceivingWorkflowHistory.ACTION_GOODS_RECEIVED,
            label="Receiving recorded (goods received)",
            details="First details",
            occurred_at=occurred_at,
            idempotency_key="same-key",
        )
        second = ReceivingWorkflowHistory.objects.create_event(
            receiving=receiving,
            action_type=ReceivingWorkflowHistory.ACTION_GOODS_RECEIVED,
            label="Receiving recorded (goods received)",
            details="Changed details should not overwrite append-only event",
            occurred_at=occurred_at,
            idempotency_key="same-key",
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ReceivingWorkflowHistory.objects.filter(receiving=receiving).count(), 1)
        self.assertEqual(first.details, "First details")

    def test_reader_falls_back_to_derived_audit_fields_when_no_persisted_history(self):
        receiving = self.make_receiving()
        actor = make_user(username="receiver")
        receiving.received_by = actor
        receiving.received_at = timezone.now()
        receiving.status = Receiving.UNDER_REVIEW
        receiving.save()

        events = list(get_receiving_timeline(receiving))

        self.assertTrue(any(event["label"] == "Receiving recorded (goods received)" for event in events))
        self.assertTrue(all(event["source"] == "derived" for event in events))

    def test_workflow_history_admin_is_read_only(self):
        model_admin = admin.site._registry[ReceivingWorkflowHistory]
        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None))
