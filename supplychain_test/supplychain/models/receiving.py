from django.db import models
from django.conf import settings

from .purchase import PurchaseOrder, PurchaseOrderItem
from .master_data import TimeStampedModel


#### Receiving & Invoice Processing


class Receiving(TimeStampedModel):
    class Meta:
        permissions = [
            ("record_receiving",      "Can record goods receipt and upload invoice"),
        ]

    """Tracks physical receipt of goods against a Purchase Order, with supplier invoice."""
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='receivings'
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='receivings'
    )
    received_at = models.DateTimeField(auto_now_add=True)
    supplier_invoice = models.FileField(upload_to='supplier_invoices/')

    def __str__(self):
        return f"Receiving #{self.id} for {self.purchase_order}"
    

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
