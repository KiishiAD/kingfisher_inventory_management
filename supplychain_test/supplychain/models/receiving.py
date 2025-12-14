# supplychain/models.py  (or wherever these classes currently live)

from decimal import Decimal
from django.db import models
from django.conf import settings

from .purchase import PurchaseOrder, PurchaseOrderItem
from .master_data import TimeStampedModel


# supplychain/models/receiving.py (or wherever yours currently is)

from decimal import Decimal
from django.db import models
from django.conf import settings
from .purchase import PurchaseOrder, PurchaseOrderItem
from .master_data import TimeStampedModel


class Receiving(TimeStampedModel):
    class Meta:
        permissions = [
            ("record_receiving", "Can record goods receipt and upload invoice"),
            ("review_receiving", "Can perform accounting review on receivings"),
            ("amend_receiving",  "Can amend receivings after accounting query (COO)"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order"],
                name="unique_receiving_per_purchase_order"
            )
        ]

    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    QUERIED = "QUERIED"

    # keep your typo constant name to avoid breaking other places
    REVIWED = "REVIEWED"

    STATUS_CHOICES = [
        (PENDING, "Pending Receipt"),
        (UNDER_REVIEW, "Pending Accounting Review"),
        (QUERIED, "Queried (Needs COO Amendment)"),
        (REVIWED, "Reviewed and Cleared for Payment"),
    ]

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="receivings",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receivings",
    )
    received_at = models.DateTimeField(null=True, blank=True)

    # keep as-is if you want it mandatory at entry time, but your UI text says “if available”
    # recommended: blank=True (optional)
    supplier_invoice = models.FileField(
        upload_to="supplier_invoices/",
        null=True,
        blank=True,
        help_text="Supplier invoice document for this receipt (optional).",
    )

    # overall accounting review note + audit
    review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receivings_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # COO amendment audit (optional but useful)
    amendment_notes = models.TextField(blank=True)
    amended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receivings_amended",
    )
    amended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Receiving #{self.id} for {self.purchase_order}"

    @property
    def has_accounting_queries(self):
        return self.items.filter(accounting_queried=True).exists()


class ReceivingItem(models.Model):
    receiving = models.ForeignKey(Receiving, on_delete=models.CASCADE, related_name="items")
    po_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.PROTECT)

    # if you truly want “Not recorded yet”, it must be nullable
    actual_quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # accounting “query this line” + note
    accounting_queried = models.BooleanField(default=False)
    accounting_notes = models.TextField(blank=True)

    flagged_for = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.actual_quantity} of {self.po_item.product}"



class InvoiceLineApproval(models.Model):
    class Meta:
        permissions = [
            ("approve_invoiceline", "Can approve/deny/query invoice lines"),
        ]

    receiving_item = models.ForeignKey(
        ReceivingItem,
        on_delete=models.CASCADE,
        related_name="invoice_approvals",
    )
    accountant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="invoice_line_approvals",
    )

    # Keep for audit trail if you want to log every decision;
    # not required for the minimal queried/cleared workflow.
    approved = models.BooleanField(null=True)  # None = queried
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "Approved" if self.approved else "Denied" if self.approved is False else "Queried"
        return f"{status} {self.receiving_item} by {self.accountant}"
