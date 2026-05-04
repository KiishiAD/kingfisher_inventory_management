"""Tests for Organisation and OrganisationMembership models."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import TestCase, RequestFactory
from django.test.utils import override_settings

from supplychain.models import Organisation, OrganisationMembership

User = get_user_model()


class OrganisationModelTests(TestCase):
    def test_create_organisation(self):
        org = Organisation.objects.create(name="Test Org", slug="test-org")
        self.assertEqual(org.name, "Test Org")
        self.assertEqual(org.slug, "test-org")
        self.assertTrue(org.is_active)
        self.assertIsNotNone(org.created_at)

    def test_str(self):
        org = Organisation.objects.create(name="Acme Corp", slug="acme")
        self.assertEqual(str(org), "Acme Corp")

    def test_default_is_active(self):
        org = Organisation.objects.create(name="Default Active", slug="default-active")
        self.assertTrue(org.is_active)

    def test_unique_slug_enforced(self):
        Organisation.objects.create(name="First", slug="duplicate")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Organisation.objects.create(name="Second", slug="duplicate")

    def test_can_have_inactive_organisation(self):
        org = Organisation.objects.create(
            name="Inactive Org", slug="inactive", is_active=False
        )
        self.assertFalse(org.is_active)


class OrganisationMembershipModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pass")
        self.org = Organisation.objects.create(name="Acme", slug="acme")
        self.role = "manager"

    def test_create_membership(self):
        membership = OrganisationMembership.objects.create(
            user=self.user, organisation=self.org, role=self.role
        )
        self.assertEqual(membership.user, self.user)
        self.assertEqual(membership.organisation, self.org)
        self.assertEqual(membership.role, self.role)

    def test_unique_together_user_organisation(self):
        OrganisationMembership.objects.create(
            user=self.user, organisation=self.org, role="member"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrganisationMembership.objects.create(
                    user=self.user, organisation=self.org, role="admin"
                )

    def test_user_can_join_multiple_organisations(self):
        org2 = Organisation.objects.create(name="Beta", slug="beta")
        OrganisationMembership.objects.create(
            user=self.user, organisation=self.org, role="member"
        )
        OrganisationMembership.objects.create(
            user=self.user, organisation=org2, role="admin"
        )
        self.assertEqual(self.user.organisationmembership_set.count(), 2)

    def test_membership_str(self):
        membership = OrganisationMembership.objects.create(
            user=self.user, organisation=self.org, role="viewer"
        )
        expected = f"alice is viewer of Acme"
        self.assertEqual(str(membership), expected)
