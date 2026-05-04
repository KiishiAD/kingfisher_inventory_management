"""Tests for TenantMiddleware."""
from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse

from supplychain.middleware import TenantMiddleware
from supplychain.models import Organisation, OrganisationMembership

User = get_user_model()


class TenantMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="bob", password="pass")
        self.org = Organisation.objects.create(name="Org A", slug="org-a")
        OrganisationMembership.objects.create(
            user=self.user, organisation=self.org, role="member"
        )
        self.middleware = TenantMiddleware(get_response=lambda req: None)

    def _get_request(self, user=None):
        req = self.factory.get("/")
        req.user = user or self.user
        req.session = {}
        return req

    def test_middleware_passes_organisation_from_session(self):
        """When organisation_id is set in session, request.organisation is populated."""
        req = self._get_request()
        req.session["organisation_id"] = self.org.id
        self.middleware(req)
        self.assertEqual(req.organisation, self.org)

    def test_middleware_no_organisation_when_not_in_session(self):
        """When no organisation_id in session, request.organisation is None."""
        req = self._get_request()
        self.middleware(req)
        self.assertIsNone(req.organisation)

    def test_middleware_handles_unauthenticated_user(self):
        """Anonymous users don't break the middleware."""
        req = self._get_request()
        req.user = User()  # AnonymousUser-like, not saved
        self.middleware(req)
        self.assertIsNone(req.organisation)

    def test_middleware_ignores_invalid_organisation_id(self):
        """If session org id doesn't exist in DB, request.organisation is None."""
        req = self._get_request()
        req.session["organisation_id"] = 99999
        self.middleware(req)
        self.assertIsNone(req.organisation)

    def test_middleware_attribute_set_on_every_request(self):
        """request.organisation should always be set (even if None) after middleware runs."""
        req = self._get_request()
        self.middleware(req)
        self.assertTrue(hasattr(req, "organisation"))
