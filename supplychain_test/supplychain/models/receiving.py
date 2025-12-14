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
            ("approve_receiving", "Can approve/deny receivings (COO)"),
            # keep your old permission if you already assigned it to groups
            ("amend_receiving", "Legacy (do not use)"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["purchase_order"], name="unique_receiving_per_purchase_order")
        ]

    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    PENDING_COO = "PENDING_COO"     # accounting sent to COO for approve/deny
    REVIWED = "REVIEWED"            # keep constant name typo; value is correct
    DENIED = "DENIED"

    # Keep QUERIED only if you already have rows in DB with this value; otherwise remove it.
    QUERIED = "QUERIED"

    STATUS_CHOICES = [
        (PENDING, "Pending Receipt"),
        (UNDER_REVIEW, "Pending Accounting Review"),
        (PENDING_COO, "Pending COO Approval"),
        (REVIWED, "Cleared for Payment"),
        (DENIED, "Denied"),
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

    # Will be set when a store/warehouse user actually records the receipt
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receivings",
        help_text="User who physically recorded the receipt of goods.",
    )

    # Actual physical receipt time (not PO approval time)
    received_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when goods were actually received.",
    )

    # Invoice upload (your template copy says 'if available', so this should be optional)
    supplier_invoice = models.FileField(
        upload_to="supplier_invoices/",
        null=True,
        blank=True,
        help_text="Supplier invoice document for this receipt (optional).",
    )

    # Accounting review audit (whole receiving)
    review_notes = models.TextField(
        blank=True,
        help_text="Optional accounting notes for the overall receiving (summary/exceptions).",
    )
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

     # Accounting “send to COO” audit
    sent_to_coo_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="receivings_sent_to_coo",
    )
    sent_to_coo_at = models.DateTimeField(null=True, blank=True)

    # COO decision audit
    coo_decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="receivings_coo_decided",
    )
    coo_decision_at = models.DateTimeField(null=True, blank=True)
    coo_decision_notes = models.TextField(blank=True)

    def __str__(self):
        return f"Receiving #{self.id} for {self.purchase_order}"

    @property
    def items_summary(self):
        """
        Human-friendly summary of items for this receiving.

        Example: "Tomatoes × 10, Cooking Oil × 5, + 2 more"
        Based on the PO items behind this receiving.
        """
        lines = []
        items = list(self.items.select_related("po_item__product"))

        for ri in items[:3]:
            product = ri.po_item.product
            product_name = getattr(product, "name", str(product))
            qty = ri.po_item.quantity  # requested qty from the PO
            lines.append(f"{product_name} × {qty}")

        extra = len(items) - 3
        if extra > 0:
            lines.append(f"+ {extra} more")

        return ", ".join(lines)

    @property
    def has_accounting_queries(self):
        return self.items.filter(accounting_queried=True).exists()


class ReceivingItem(models.Model):
    """
    Actual quantities received per PO item, with departmental flags and accounting query markers.
    """
    receiving = models.ForeignKey(
        Receiving,
        on_delete=models.CASCADE,
        related_name="items",
    )
    po_item = models.ForeignKey(
        PurchaseOrderItem,
        on_delete=models.PROTECT,
    )

    # If you want "Not recorded yet" to exist, this must be nullable.
    actual_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # Accounting exception flow: checkbox + note
    accounting_queried = models.BooleanField(
        default=False,
        help_text="Accounting marked this line as queried/incorrect.",
    )
    accounting_notes = models.TextField(
        blank=True,
        help_text="Accounting notes explaining why this line was queried.",
    )

    # Keep your existing flags for audit/other departments
    flagged_for = models.JSONField(
        default=dict,
        help_text="Keys: kitchen, store, audit, admin; values: booleans",
    )

    def __str__(self):
        qty = self.actual_quantity
        qty_str = f"{qty:.2f}" if qty is not None else "—"
        return f"{qty_str} of {self.po_item.product}"


class InvoiceLineApproval(models.Model):
    class Meta:
        permissions = [
            ("approve_invoiceline", "Can approve/deny/query invoice lines"),
        ]

    """
    Optional audit trail for line-level approval decisions.
    You can keep this even if you primarily use ReceivingItem.accounting_queried/accounting_notes for workflow.
    """
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

    approved = models.BooleanField(null=True)  # None = queried
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "Approved" if self.approved else "Denied" if self.approved is False else "Queried"
        return f"{status} {self.receiving_item} by {self.accountant}"
