"""Shared test helpers for supplychain model tests.

This module contains factory helper functions (using model_bakery) that
produce model instances with sensible defaults. Tests import these helpers
to keep setup consistent and to ensure Decimal usage where string
formatting is asserted.

Helpers:
- make_user, make_uom, make_category, make_supplier, make_product,
  make_destination, make_requisition, make_po, make_po_item

Use these to create objects in tests instead of repeating model_bakery calls.
"""

from decimal import Decimal
import os
import shutil
import tempfile
import time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings

from model_bakery import baker

from supplychain.models import (
    UnitOfMeasure,
    Category,
    Supplier,
    Product,
    Destination,
    Requisition,
    RequisitionItem,
    RequisitionApproval,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderApproval,
    Receiving,
    ReceivingItem,
    InvoiceLineApproval,
    Payment,
    StockTransaction,
    LowStockAlert,
    Profile,
)


# test helpers (shared across modular tests)
User = get_user_model()


def make_user(**kwargs):
    return baker.make(User, **kwargs)


def make_uom(**kwargs):
    return baker.make(UnitOfMeasure, **kwargs)


def make_category(**kwargs):
    return baker.make(Category, **kwargs)


def make_supplier(**kwargs):
    return baker.make(Supplier, **kwargs)


def make_product(**kwargs):
    defaults = {
        "uom": make_uom(),
        "unit_cost": Decimal("10.00"),
    }
    defaults.update(kwargs)
    return baker.make(Product, **defaults)


def make_destination(name=Destination.STORE):
    obj, _ = Destination.objects.get_or_create(name=name)
    return obj


def make_requisition(**kwargs):
    defaults = {
        "requester": make_user(),
        "destination": make_destination(),
    }
    defaults.update(kwargs)
    return baker.make(Requisition, **defaults)


def make_po(**kwargs):
    defaults = {
        "supplier": make_supplier(),
        "created_by": make_user(),
    }
    defaults.update(kwargs)
    return baker.make(PurchaseOrder, **defaults)


def make_po_item(**kwargs):
    defaults = {
        "purchase_order": make_po(),
        "product": make_product(),
        "quantity": Decimal("2.00"),
        "unit_cost": Decimal("5.00"),
    }
    defaults.update(kwargs)
    return baker.make(PurchaseOrderItem, **defaults)
