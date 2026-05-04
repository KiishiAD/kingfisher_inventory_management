from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from django.db.models.functions import Lower

from supplychain.tenant_utils import TenantManager


### Master Data

class TimeStampedModel(models.Model):
    """This abstract class provides two timestamp fields that will automatically record when any inheriting record is created and last updated, ensuring consistent audit fields across all models."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UnitOfMeasure(TimeStampedModel):
    code = models.CharField(max_length=10, unique=True)
    # name holds the full unit name (e.g. “Kilogram”, “Liter”) and must be unique so each UnitOfMeasure appears only once
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Category(TimeStampedModel):
    # name holds the category title and must be unique so each category appears only once
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Supplier(TimeStampedModel):
    objects = TenantManager()

    organisation = models.ForeignKey(
        "Organisation",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name
    

class Supplier_destination_sub_category(models.Model):
    CONSUMABLES = "CONSUMABLES"
    SERVICES = "SERVICES"
    SUBCATEGORY_CHOICES = [
        (CONSUMABLES, "CONSUMABLES"),
        (SERVICES, "SERVICES"),
    ]
    name = models.CharField(
        max_length=20,
        choices=SUBCATEGORY_CHOICES,
        unique=True,
        null=True,
        blank = True
    )
    

    def __str__(self):
        return self.get_name_display()



class Product(TimeStampedModel):
    class Meta:
        permissions = [
            ("bulk_upload_products", "Can bulk upload products"),
        ]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "uom",
                name="uniq_product_sku",
            )
        ]

    objects = TenantManager()

    organisation = models.ForeignKey(
        "Organisation",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    # allow blank so the model can generate it; keep unique + non-null in DB
    sku = models.CharField(max_length=64, unique=True, blank=True)

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    uom = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name="products")
    categories = models.ManyToManyField(Category, blank=True)
    vendors = models.ManyToManyField(Supplier, blank=True)
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="managed_products",
    )
    low_stock_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="If set, create an alert when on-hand stock drops below this value."
    )

    def save(self, *args, **kwargs):
        if not self.sku:
            base = slugify(self.name)[:40] or "product"
            self.sku = f"{base}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Destination(models.Model):
    """Possible requisition destinations (Supplier vs Store)."""

    PURCHASE = "PURCHASE"
    STORE = "STORE"
    DESTINATION_CHOICES = [
        (PURCHASE, "PURCHASE"),
        (STORE, "STORE"),
    ]

    name = models.CharField(max_length=10, choices=DESTINATION_CHOICES, unique=True)

    def __str__(self):
        return self.get_name_display()
    

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"Profile of {self.user.username}"