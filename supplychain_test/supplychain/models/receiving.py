from django.db import models
from django.conf import settings

from .purchase import PurchaseOrder, PurchaseOrderItem
from .master_data import TimeStampedModel


#### Receiving & Invoice Processing


from django.db import models
from django.conf import settings

from .purchase import PurchaseOrder, PurchaseOrderItem
from .master_data import TimeStampedModel


class Receiving(TimeStampedModel):
    class Meta:
        permissions = [
            ("record_receiving", "Can record goods receipt and upload invoice"),
        ]

    # Status constants
    PENDING = "PENDING"              # PO approved, waiting for physical receipt
    UNDER_REVIEW = "UNDER_REVIEW"    # Goods received, accounting doing three-way check         # Three-way check completed, cleared for payment
    REVIWED = "REVIEWED"              # Three-way check completed, cleared for payment

    STATUS_CHOICES = [
        (PENDING, "Pending Receipt"),
        (UNDER_REVIEW, "Pending Accounting Review"),
        (REVIWED, "Reviewed and Cleared for Payment"),
    ]

    """Tracks physical receipt of goods against a Purchase Order, with supplier invoice."""
    purchase_order = models.OneToOneField(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='receivings',
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
        related_name='receivings',
        help_text="User who physically recorded the receipt of goods.",
    )

    # Actual physical receipt time (not PO approval time)
    received_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when goods were actually received.",
    )

    # Invoice can be uploaded later by receiving/accounting
    supplier_invoice = models.FileField(
        upload_to='supplier_invoices/',
        null=True,
        blank=False,
        help_text="Supplier invoice document for this receipt (optional).",
    )

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


class ReceivingItem(models.Model):
    """Actual quantities received per PO item, with departmental flags for audit."""
    receiving = models.ForeignKey(
        Receiving,
        on_delete=models.CASCADE,
        related_name='items'
    )
    po_item = models.ForeignKey(
        PurchaseOrderItem,
        on_delete=models.PROTECT
    )
    actual_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    flagged_for = models.JSONField(
        default=dict,
        help_text="Keys: kitchen, store, audit, admin; values: booleans"
    )

    def __str__(self):
        return f"{self.actual_quantity} of {self.po_item.product}"
    

class InvoiceLineApproval(models.Model):
    class Meta:
        permissions = [
            ("approve_invoiceline",   "Can approve/deny/query invoice lines"),
        ]

    """Accountant sign-off on individual invoice lines, tying back to a ReceivingItem."""
    receiving_item = models.ForeignKey(
        ReceivingItem,
        on_delete=models.CASCADE,
        related_name='invoice_approvals'
    )
    accountant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invoice_line_approvals'
    )
    approved = models.BooleanField(null=True)  # None = queried
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = 'Approved' if self.approved else 'Denied' if self.approved is False else 'Queried'
        return f"{status} {self.receiving_item} by {self.accountant}"
