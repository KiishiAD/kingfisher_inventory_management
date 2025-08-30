from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from model_bakery import baker

from .helpers import (
    make_uom, make_category, make_supplier, make_product, make_user
)


class UnitOfMeasureModelTests:
    pass


from django.test import TestCase


class UnitOfMeasureModelTests(TestCase):
    def test_str_returns_name_and_code(self):
        uom = make_uom(code="KG", name="Kilogram")
        self.assertEqual(str(uom), "Kilogram (KG)")

    def test_unique_code_and_name_enforced(self):
        make_uom(code="L", name="Liter")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_uom(code="L", name="SomethingElse")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_uom(code="XX", name="Liter")


class CategoryModelTests(TestCase):
    def test_str(self):
        c = make_category(name="Beverages")
        self.assertEqual(str(c), "Beverages")

    def test_unique_name(self):
        make_category(name="Staples")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_category(name="Staples")


class SupplierModelTests(TestCase):
    def test_str(self):
        s = make_supplier(name="Acme Trading")
        self.assertEqual(str(s), "Acme Trading")

    def test_blank_fields_allowed(self):
        s = make_supplier(contact_email="", phone_number="", address="")
        self.assertEqual(s.contact_email, "")
        self.assertEqual(s.phone_number, "")
        self.assertEqual(s.address, "")


class ProductModelTests(TestCase):
    def test_str(self):
        p = make_product(name="Tomatoes")
        self.assertEqual(str(p), "Tomatoes")

    def test_m2m_additions_and_no_duplicates(self):
        p = make_product()
        c1, c2 = make_category(name="Veg"), make_category(name="Fruit")
        v1, v2 = make_supplier(name="S1"), make_supplier(name="S2")
        u1, u2 = make_user(username="u1"), make_user(username="u2")
        p.categories.add(c1, c2, c1)
        p.vendors.add(v1, v2, v2)
        p.assigned_users.add(u1, u2, u2)
        self.assertEqual(p.categories.count(), 2)
        self.assertEqual(p.vendors.count(), 2)
        self.assertEqual(p.assigned_users.count(), 2)

    def test_cannot_delete_uom_when_product_exists(self):
        from .helpers import make_uom
        uom = make_uom()
        make_product(uom=uom)
        with self.assertRaises(ProtectedError):
            uom.delete()
