from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Organization, OrganizationMembership
from supplychain.models.master_data import Destination, Supplier_destination_sub_category, UnitOfMeasure, Product
from supplychain.models.requisition import Requisition

User = get_user_model()


@override_settings(
    APP_BASE_URL="https://app.example.com",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class AccountOnboardingTests(TestCase):
    def test_signup_creates_owner_membership_and_logs_in(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "organization_name": "Acme Inc",
                "email": "owner@acme.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("supplychain:dashboard"))
        user = User.objects.get(email="owner@acme.com")
        membership = OrganizationMembership.objects.get(user=user)
        self.assertEqual(membership.role, OrganizationMembership.OWNER)
        self.assertEqual(membership.organization.name, "Acme Inc")

    def test_invite_adds_user_to_same_organization(self):
        owner = User.objects.create_user(username="owner", email="owner@acme.com", password="pw")
        org = Organization.objects.create(name="Acme Inc")
        OrganizationMembership.objects.create(user=owner, organization=org, role=OrganizationMembership.OWNER)

        ops_group = Group.objects.create(name="Ops")

        self.client.force_login(owner)
        session = self.client.session
        session["active_organization_id"] = org.id
        session.save()

        response = self.client.post(
            reverse("accounts:invite_user"),
            {"email": "staff@acme.com", "groups": [ops_group.id]},
        )

        self.assertRedirects(response, reverse("accounts:invite_done"))
        invited = User.objects.get(email="staff@acme.com")
        self.assertTrue(
            OrganizationMembership.objects.filter(
                user=invited,
                organization=org,
                role=OrganizationMembership.MEMBER,
            ).exists()
        )
        self.assertIn(ops_group, invited.groups.all())
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="id", GOOGLE_OAUTH_CLIENT_SECRET="secret")
    @patch("accounts.views.requests.get")
    @patch("accounts.views.requests.post")
    def test_google_callback_requires_org_setup_for_new_user(self, mock_post, mock_get):
        session = self.client.session
        session["google_oauth_state"] = "state123"
        session.save()

        mock_post.return_value = Mock(ok=True)
        mock_post.return_value.json.return_value = {"access_token": "token"}

        mock_get.return_value = Mock(ok=True)
        mock_get.return_value.json.return_value = {"email": "google-user@example.com"}

        response = self.client.get(
            reverse("accounts:google_callback"),
            {"state": "state123", "code": "auth-code"},
        )

        self.assertRedirects(response, reverse("accounts:organization_setup"))
        user = User.objects.get(email="google-user@example.com")
        self.assertFalse(user.organization_memberships.exists())


class DashboardOrganizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.destination, _ = Destination.objects.get_or_create(name=Destination.PURCHASE)
        cls.subcat, _ = Supplier_destination_sub_category.objects.get_or_create(
            name=Supplier_destination_sub_category.CONSUMABLES
        )
        cls.uom, _ = UnitOfMeasure.objects.get_or_create(code="EA", defaults={"name": "Each"})
        cls.product, _ = Product.objects.get_or_create(name="Pen", defaults={"unit_cost": "1.00", "uom": cls.uom})

    def test_dashboard_counts_only_active_organization_requests(self):
        user = User.objects.create_user(username="user", password="pw")
        teammate = User.objects.create_user(username="team", password="pw")
        outsider = User.objects.create_user(username="other", password="pw")

        org_a = Organization.objects.create(name="Org A")
        org_b = Organization.objects.create(name="Org B")

        OrganizationMembership.objects.create(user=user, organization=org_a, role=OrganizationMembership.OWNER)
        OrganizationMembership.objects.create(user=teammate, organization=org_a, role=OrganizationMembership.MEMBER)
        OrganizationMembership.objects.create(user=outsider, organization=org_b, role=OrganizationMembership.OWNER)

        Requisition.objects.create(
            requester=user,
            destination=self.destination,
            Supplier_destination_sub_category=self.subcat,
            notes="mine",
            evidence="requisition_evidence/test1.txt",
        )
        Requisition.objects.create(
            requester=teammate,
            destination=self.destination,
            Supplier_destination_sub_category=self.subcat,
            notes="teammate",
            evidence="requisition_evidence/test2.txt",
        )
        Requisition.objects.create(
            requester=outsider,
            destination=self.destination,
            Supplier_destination_sub_category=self.subcat,
            notes="other-org",
            evidence="requisition_evidence/test3.txt",
        )

        self.client.force_login(user)
        session = self.client.session
        session["active_organization_id"] = org_a.id
        session.save()

        response = self.client.get(reverse("supplychain:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["user_reqs_count"], 1)
        self.assertContains(response, "Organization: <strong>Org A</strong>", html=True)
