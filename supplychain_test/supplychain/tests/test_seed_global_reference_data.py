from io import StringIO
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from supplychain.models import UnitOfMeasure, Category, Product


class SeedGlobalReferenceDataTest(TestCase):
    """Behavioural tests for the seed_global_reference_data management command."""

    def test_creates_all_expected_uoms(self):
        call_command("seed_global_reference_data", stdout=StringIO())
        codes = set(UnitOfMeasure.objects.values_list("code", flat=True))
        expected = {"kg", "g", "L", "mL", "pcs", "box", "carton"}
        self.assertEqual(codes, expected)

    def test_creates_all_expected_categories(self):
        call_command("seed_global_reference_data", stdout=StringIO())
        names = set(Category.objects.values_list("name", flat=True))
        expected = {"Produce", "Meat", "Dairy", "Dry Goods", "Beverages", "Cleaning", "Supplies"}
        self.assertEqual(names, expected)

    def test_is_idempotent_when_run_twice(self):
        call_command("seed_global_reference_data", stdout=StringIO())
        call_command("seed_global_reference_data", stdout=StringIO())
        self.assertEqual(UnitOfMeasure.objects.count(), 7)
        self.assertEqual(Category.objects.count(), 7)

    def test_seeded_uom_can_be_used_by_any_product(self):
        call_command("seed_global_reference_data", stdout=StringIO())
        kg = UnitOfMeasure.objects.get(code="kg")
        product = Product.objects.create(
            name="Test Product",
            uom=kg,
            unit_cost=Decimal("10.00"),
        )
        self.assertEqual(product.uom, kg)

    def test_seeded_category_can_be_assigned_to_product(self):
        call_command("seed_global_reference_data", stdout=StringIO())
        dairy = Category.objects.get(name="Dairy")
        kg = UnitOfMeasure.objects.get(code="kg")
        product = Product.objects.create(
            name="Cheese",
            uom=kg,
            unit_cost=Decimal("5.00"),
        )
        product.categories.add(dairy)
        self.assertIn(dairy, product.categories.all())
