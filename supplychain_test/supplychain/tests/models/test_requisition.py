"""Requisition model tests.

Covers Destination choices, Requisition defaults and string output,
RequisitionItem cascade behavior, and RequisitionApproval validation.
These tests ensure choice validation, protect/cascade delete semantics,
and formatted string outputs used across the UI.
"""

from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from model_bakery import baker

from .helpers import (
    make_destination, make_requisition, make_product, make_user
)

from supplychain.models import Destination, Requisition, RequisitionItem, RequisitionApproval


class DestinationModelTests(TestCase):
    def test_str_returns_humanized_choice(self):
        d = make_destination(Destination.PURCHASE)
        self.assertEqual(str(d), "PURCHASE")

    def test_invalid_choice_rejected_by_full_clean(self):
        d = Destination(name="NOT_A_REAL_CHOICE")
        with self.assertRaises(ValidationError):
            d.full_clean()


class RequisitionModelTests(TestCase):
    def test_defaults_and_str_and_destination_display(self):
        user = make_user()
        dest = make_destination(Destination.STORE)
        r = make_requisition(requester=user, destination=dest)
        self.assertEqual(r.status, Requisition.PENDING)
        self.assertFalse(r.urgent)
        self.assertIn("Requisition #", str(r))
        self.assertEqual(r.get_destination_display(), "STORE")

    def test_destination_protects_from_deletion(self):
        dest = make_destination(Destination.PURCHASE)
        make_requisition(destination=dest)
        with self.assertRaises(ProtectedError):
            dest.delete()


class RequisitionItemModelTests(TestCase):
    def test_str(self):
        r = make_requisition()
        p = make_product(name="Rice")
        item = baker.make(RequisitionItem, requisition=r, product=p, quantity=1.25)
        self.assertEqual(str(item), "1.25 x Rice")

    def test_requisition_delete_cascades_items(self):
        r = make_requisition()
        baker.make(RequisitionItem, requisition=r)
        r.delete()
        self.assertEqual(RequisitionItem.objects.count(), 0)


class RequisitionApprovalModelTests(TestCase):
    def test_valid_action_choices(self):
        r = make_requisition()
        approver = make_user()
        ra = baker.make(RequisitionApproval, requisition=r, approver=approver, action=Requisition.APPROVED)
        self.assertEqual(ra.action, Requisition.APPROVED)

    def test_invalid_action_full_clean_raises(self):
        ra = baker.prepare(RequisitionApproval, action="BOGUS")
        with self.assertRaises(ValidationError):
            ra.full_clean()
