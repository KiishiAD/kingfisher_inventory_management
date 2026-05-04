"""Tests for get_user_groups permission helper."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from supplychain.models import Organisation, OrganisationMembership
from supplychain.tenant_utils import get_user_groups

User = get_user_model()


class GetUserGroupsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pass")
        self.org = Organisation.objects.create(name="Acme", slug="acme")

    def test_returns_groups_for_membership_role(self):
        Group.objects.create(name="manager")
        OrganisationMembership.objects.create(
            user=self.user, organisation=self.org, role="manager"
        )
        groups = get_user_groups(self.user, self.org)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].name, "manager")

    def test_returns_groups_for_multiple_memberships_across_orgs(self):
        Group.objects.create(name="viewer")
        Group.objects.create(name="editor")
        other_org = Organisation.objects.create(name="Beta", slug="beta")
        OrganisationMembership.objects.create(
            user=self.user, organisation=self.org, role="viewer"
        )
        OrganisationMembership.objects.create(
            user=self.user, organisation=other_org, role="editor"
        )
        groups_org1 = get_user_groups(self.user, self.org)
        groups_org2 = get_user_groups(self.user, other_org)
        self.assertEqual({g.name for g in groups_org1}, {"viewer"})
        self.assertEqual({g.name for g in groups_org2}, {"editor"})

    def test_returns_empty_when_no_group_exists_for_role(self):
        OrganisationMembership.objects.create(
            user=self.user, organisation=self.org, role="nonexistent-role"
        )
        groups = get_user_groups(self.user, self.org)
        self.assertEqual(groups, [])

    def test_returns_empty_when_user_has_no_membership(self):
        groups = get_user_groups(self.user, self.org)
        self.assertEqual(groups, [])

    def test_ignores_memberships_in_other_organisations(self):
        Group.objects.create(name="admin")
        other_org = Organisation.objects.create(name="Beta", slug="beta")
        OrganisationMembership.objects.create(
            user=self.user, organisation=other_org, role="admin"
        )
        groups = get_user_groups(self.user, self.org)
        self.assertEqual(groups, [])
