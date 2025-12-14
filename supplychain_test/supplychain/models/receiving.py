# supplychain/models.py  (or wherever these classes currently live)

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
                name="unique_receiving_per_purchase_order",
            )
        ]

    # Status constants
    PENDING = "PENDING"              # PO approved, waiting for store/warehouse entry
    UNDER_REVIEW = "UNDER_REVIEW"    # Receiving entered, accounting review in progress
    QUERIED = "QUERIED"              # Accounting found issues; COO must amend
    REVIEWED = "REVIEWED"            # Accounting cleared; can proceed to payment

    STATUS_CHOICES = [
        (PENDING, "Pending Receipt"),
        (UNDER_REVIEW, "Pending Accounting Review"),
        (QUERIED, "Queried (Needs COO Amendment)"),
        (REVIEWED, "Reviewed and Cleared for Payment"),
    ]

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="receivings",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
    )

    # Receiving stage (store/warehouse)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receivings",
        help_text="User who physically recorded the receipt of goods.",
    )
    received_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when goods were actually received.",
    )

    # Invoice is optional (your UI says 'if available')
    supplier_invoice = models.FileField(
        upload_to="supplier_invoices/",
        null=True,
        blank=True,
        help_text="Supplier invoice document for this receipt (optional).",
    )

    # Accounting review audit (whole receiving)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receivings_reviewed",
        help_text="Accountant who cleared/queried this receiving.",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when accounting completed review (cleared or queried).",
    )
    review_notes = models.TextField(
        blank=True,
        help_text="Optional accounting notes for the overall receiving.",
    )

    # COO amendment audit
    amended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receivings_amended",
        help_text="COO who amended the receiving after query.",
    )
    amended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when COO amended this receiving after query.",
    )
    amendment_notes = models.TextField(
        blank=True,
        help_text="Optional COO notes for amendments made after query.",
    )

    def __str__(self):
        return f"Receiving #{self.id} for {self.purchase_order}"

    @property
    def has_accounting_queries(self) -> bool:
        return self.items.filter(accounting_queried=True).exists()

    @property
    def is_clear_for_payment(self) -> bool:
        return self.status == self.REVIEWED

    @property
    def items_summary(self):
        lines = []
        items = list(self.items.select_related("po_item__product"))

        for ri in items[:3]:
            product = ri.po_item.product
            product_name = getattr(product, "name", str(product))
            qty = ri.po_item.quantity
            lines.append(f"{product_name} × {qty}")

        extra = len(items) - 3
        if extra > 0:
            lines.append(f"+ {extra} more")

        return ", ".join(lines)


class ReceivingItem(models.Model):
    receiving = models.ForeignKey(
        Receiving,
        on_delete=models.CASCADE,
        related_name="items",
    )
    po_item = models.ForeignKey(
        PurchaseOrderItem,
        on_delete=models.PROTECT,
    )

    # Must be nullable to support "Not recorded yet" properly
    actual_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # Exception-driven accounting line review (checkbox = "Query this line")
    accounting_queried = models.BooleanField(
        default=False,
        help_text="Accounting marked this line as queried/incorrect.",
    )
    accounting_notes = models.TextField(
        blank=True,
        help_text="Accounting notes for why this line was queried.",
    )

    # Keep your existing flags for other departments
    flagged_for = models.JSONField(
        default=dict,
        help_text="Keys: kitchen, store, audit, admin; values: booleans",
    )

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
