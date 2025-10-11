# filepath: /workspaces/kingfisher_inventory_management/supplychain_test/supplychain/tests/models/test_master_data.py
"""Tests for master data models: UnitOfMeasure, Category, Supplier, Product.

These tests validate string representations, uniqueness constraints,
many-to-many behavior, and foreign-key delete protection semantics.
"""

from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.contrib.auth import get_user_model
from django.test import TestCase

# import actual models from master_data
from supplychain.models.master_data import (
    UnitOfMeasure,
    Category,
    Supplier,
    Product,
    Profile,
)

User = get_user_model()


class UnitOfMeasureModelTests(TestCase):
    def test_str_returns_name_and_code(self):
        uom = UnitOfMeasure.objects.create(code="KG", name="Kilogram")
        self.assertEqual(str(uom), "Kilogram (KG)")

    def test_unique_code_and_name_enforced(self):
        UnitOfMeasure.objects.create(code="L", name="Liter")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UnitOfMeasure.objects.create(code="L", name="SomethingElse")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UnitOfMeasure.objects.create(code="XX", name="Liter")


class CategoryModelTests(TestCase):
    def test_str(self):
        c = Category.objects.create(name="Beverages")
        self.assertEqual(str(c), "Beverages")

    def test_unique_name(self):
        Category.objects.create(name="Staples")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(name="Staples")


class SupplierModelTests(TestCase):
    def test_str(self):
        s = Supplier.objects.create(name="Acme Trading")
        self.assertEqual(str(s), "Acme Trading")

    def test_blank_fields_allowed(self):
        s = Supplier.objects.create(name="Blank Co", contact_email="", phone_number="", address="")
        self.assertEqual(s.contact_email, "")
        self.assertEqual(s.phone_number, "")
        self.assertEqual(s.address, "")


class ProductModelTests(TestCase):
    def test_str(self):
        uom = UnitOfMeasure.objects.create(code="UNIT", name="Unit")
        p = Product.objects.create(name="Tomatoes", unit_cost=Decimal("1.23"), uom=uom)
        self.assertEqual(str(p), "Tomatoes")

    def test_m2m_additions_and_no_duplicates(self):
        uom = UnitOfMeasure.objects.create(code="U1", name="Unit1")
        p = Product.objects.create(name="Sample Product", unit_cost=Decimal("2.00"), uom=uom)

        c1 = Category.objects.create(name="Veg")
        c2 = Category.objects.create(name="Fruit")
        v1 = Supplier.objects.create(name="S1")
        v2 = Supplier.objects.create(name="S2")
        u1 = User.objects.create_user(username="u1", password="pass")
        u2 = User.objects.create_user(username="u2", password="pass")

        p.categories.add(c1, c2, c1)
        p.vendors.add(v1, v2, v2)
        p.assigned_users.add(u1, u2, u2)

        self.assertEqual(p.categories.count(), 2)
        self.assertEqual(p.vendors.count(), 2)
        self.assertEqual(p.assigned_users.count(), 2)

    def test_cannot_delete_uom_when_product_exists(self):
        uom = UnitOfMeasure.objects.create(code="DEL", name="DeleteMe")
        Product.objects.create(name="ProtectedProd", unit_cost=Decimal("3.00"), uom=uom)
        with self.assertRaises(ProtectedError):
            uom.delete()


class ProfileModelTests(TestCase):
    def test_create_profile_and_str(self):
        user = User.objects.create_user(username="alice", password="pass")
        profile = Profile.objects.create(user=user, phone_number="+15551234567")
        # relation
        self.assertEqual(profile.user, user)
        self.assertEqual(user.profile, profile)
        # string representation
        self.assertEqual(str(profile), f"Profile of {user.username}")

    def test_phone_number_optional(self):
        user = User.objects.create_user(username="bob", password="pass")
        profile = Profile.objects.create(user=user, phone_number="")
        self.assertEqual(profile.phone_number, "")
        self.assertTrue(hasattr(profile, "user"))
        self.assertEqual(profile.user.username, "bob")

    def test_one_to_one_enforces_uniqueness(self):
        user = User.objects.create_user(username="carol", password="pass")
        Profile.objects.create(user=user, phone_number="123")
        with self.assertRaises(IntegrityError):
            # creating a second Profile for the same user should fail
            Profile.objects.create(user=user, phone_number="456")