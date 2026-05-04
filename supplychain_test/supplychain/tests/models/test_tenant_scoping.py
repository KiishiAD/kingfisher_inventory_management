"""Tests for organisation FK + TenantManager scoping on Product and Supplier.

S5 behaviour:
- Product and Supplier have an optional organisation FK (null=True).
- When TenantManager is active (org_id set in thread-local), querysets are
  filtered to the current organisation.
- When no org context is active, all records are returned (backward compat).
"""

from decimal import Decimal

from django.test import TestCase

from supplychain.models import Organisation, UnitOfMeasure, Supplier, Product
from supplychain.tenant_utils import (
    set_current_organisation,
    clear_current_organisation,
)


class ProductOrganisationScopingTests(TestCase):
    """Product has organisation FK and respects TenantManager."""

    def setUp(self):
        clear_current_organisation()
        self.org_a = Organisation.objects.create(name="Org A", slug="org-a")
        self.org_b = Organisation.objects.create(name="Org B", slug="org-b")
        self.uom = UnitOfMeasure.objects.create(code="UNIT", name="Unit")

    def tearDown(self):
        clear_current_organisation()

    def test_product_has_organisation_fk(self):
        """Product model has an organisation FK field."""
        field = Product._meta.get_field("organisation")
        self.assertIsNotNone(field)
        self.assertEqual(field.related_model, Organisation)

    def test_product_organisation_nullable(self):
        """Organisation FK on Product allows null."""
        field = Product._meta.get_field("organisation")
        self.assertTrue(field.null)

    def test_products_filtered_by_organisation_when_org_set(self):
        """With org context set, only that org's products are returned."""
        p_a = Product.objects.create(
            name="OrgA Product", unit_cost=Decimal("1.00"), uom=self.uom,
            organisation=self.org_a,
        )
        Product.objects.create(
            name="OrgB Product", unit_cost=Decimal("2.00"), uom=self.uom,
            organisation=self.org_b,
        )

        set_current_organisation(self.org_a)
        qs = Product.objects.all()
        self.assertIn(p_a, qs)
        self.assertEqual(qs.count(), 1)

    def test_products_return_all_when_no_org_set(self):
        """Without org context, all products are returned."""
        Product.objects.create(
            name="A", unit_cost=Decimal("1.00"), uom=self.uom,
            organisation=self.org_a,
        )
        Product.objects.create(
            name="B", unit_cost=Decimal("2.00"), uom=self.uom,
            organisation=self.org_b,
        )
        clear_current_organisation()
        self.assertEqual(Product.objects.count(), 2)

    def test_product_can_have_null_organisation(self):
        """Products can exist without an organisation (null FK)."""
        p = Product.objects.create(
            name="Global Product", unit_cost=Decimal("5.00"), uom=self.uom,
        )
        self.assertIsNone(p.organisation)
        self.assertIn(p, Product.objects.all())

    def test_products_scoped_to_correct_organisation(self):
        """Org A sees only Org A's products; Org B sees only Org B's."""
        Product.objects.create(
            name="A-Prod", unit_cost=Decimal("1.00"), uom=self.uom,
            organisation=self.org_a,
        )
        Product.objects.create(
            name="B-Prod", unit_cost=Decimal("2.00"), uom=self.uom,
            organisation=self.org_b,
        )

        set_current_organisation(self.org_a)
        names_a = set(Product.objects.values_list("name", flat=True))
        self.assertEqual(names_a, {"A-Prod"})

        set_current_organisation(self.org_b)
        names_b = set(Product.objects.values_list("name", flat=True))
        self.assertEqual(names_b, {"B-Prod"})


class SupplierOrganisationScopingTests(TestCase):
    """Supplier has organisation FK and respects TenantManager."""

    def setUp(self):
        clear_current_organisation()
        self.org_a = Organisation.objects.create(name="Org A", slug="org-a")
        self.org_b = Organisation.objects.create(name="Org B", slug="org-b")

    def tearDown(self):
        clear_current_organisation()

    def test_supplier_has_organisation_fk(self):
        """Supplier model has an organisation FK field."""
        field = Supplier._meta.get_field("organisation")
        self.assertIsNotNone(field)
        self.assertEqual(field.related_model, Organisation)

    def test_supplier_organisation_nullable(self):
        """Organisation FK on Supplier allows null."""
        field = Supplier._meta.get_field("organisation")
        self.assertTrue(field.null)

    def test_suppliers_filtered_by_organisation_when_org_set(self):
        """With org context set, only that org's suppliers are returned."""
        s_a = Supplier.objects.create(name="OrgA Supplier", organisation=self.org_a)
        Supplier.objects.create(name="OrgB Supplier", organisation=self.org_b)

        set_current_organisation(self.org_a)
        qs = Supplier.objects.all()
        self.assertIn(s_a, qs)
        self.assertEqual(qs.count(), 1)

    def test_suppliers_return_all_when_no_org_set(self):
        """Without org context, all suppliers are returned."""
        Supplier.objects.create(name="A", organisation=self.org_a)
        Supplier.objects.create(name="B", organisation=self.org_b)
        clear_current_organisation()
        self.assertEqual(Supplier.objects.count(), 2)

    def test_supplier_can_have_null_organisation(self):
        """Suppliers can exist without an organisation (null FK)."""
        s = Supplier.objects.create(name="Global Supplier")
        self.assertIsNone(s.organisation)
        self.assertIn(s, Supplier.objects.all())

    def test_suppliers_scoped_to_correct_organisation(self):
        """Org A sees only Org A's suppliers; Org B sees only Org B's."""
        Supplier.objects.create(name="A-Supplier", organisation=self.org_a)
        Supplier.objects.create(name="B-Supplier", organisation=self.org_b)

        set_current_organisation(self.org_a)
        names_a = set(Supplier.objects.values_list("name", flat=True))
        self.assertEqual(names_a, {"A-Supplier"})

        set_current_organisation(self.org_b)
        names_b = set(Supplier.objects.values_list("name", flat=True))
        self.assertEqual(names_b, {"B-Supplier"})
