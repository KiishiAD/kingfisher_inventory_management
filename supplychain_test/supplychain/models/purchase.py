from django.db import models
from django.conf import settings

from .master_data import Supplier, Product
from .requisition import Requisition
from .master_data import TimeStampedModel


#### Purchase Order (PO) & Approval

class PurchaseOrder(TimeStampedModel):
    class Meta:
        permissions = [
            ("create_purchaseorder",  "Can view and generate PO drafts"),
            ("approve_purchaseorder", "Can approve/deny/query POs"),  # Only Master gets this
        ]  

    """A purchase order generated from an approved requisition or created directly, tracked through multi-stage approval."""
    DRAFT = 'DRAFT'
    PENDING_PROCUREMENT = 'PENDING_PROCUREMENT'
    PENDING_COO= 'PENDING_COO'  ##pending Chief operations approval
    APPROVED = 'APPROVED'
    DENIED = 'DENIED'
    QUERIED = 'QUERIED'
    SENT = 'SENT'
    STATUS_CHOICES = [
        (DRAFT, 'Draft'),
        (PENDING_PROCUREMENT, 'Pending Procurement'),
        (PENDING_COO, 'Pending COO Approval'),
        (APPROVED, 'Approved'),
        (DENIED, 'Denied'),
        (QUERIED, 'Queried'),
        (SENT, 'Sent to Supplier'),
    ]

    requisition = models.OneToOneField(
        Requisition,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_order'
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_purchase_orders'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"PO #{self.id} ({self.status})"
    


class PurchaseOrderItem(models.Model):
    """Line items for each purchase order, with snapshot of cost and quantity."""
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product} @ {self.unit_cost}"
    


class PurchaseOrderApproval(models.Model):
    """Audit trail of approval actions taken on a purchase order."""
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='approvals'
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='purchase_order_approvals'
    )
    action = models.CharField(
        max_length=20,
        choices=PurchaseOrder.STATUS_CHOICES
    )
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.purchase_order} {self.action} by {self.approver}"
