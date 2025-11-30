from django.db import models
from django.conf import settings
from decimal import Decimal

from .master_data import Supplier, Product
from .requisition import Requisition
from .master_data import TimeStampedModel


class PurchaseOrder(TimeStampedModel):
    class Meta:
        permissions = [
            ("create_purchaseorder",  "Can view and generate PO drafts"),
            ("approve_purchaseorder", "Can approve/deny/query POs"),
        ]

    # --- Simplified, aligned status machine ---
    PENDING_COO = "PENDING_COO"        # waiting for COO decision
    APPROVED    = "APPROVED"           # COO approved
    DENIED      = "DENIED"
    QUERIED     = "QUERIED"

    STATUS_CHOICES = [
        (PENDING_COO, "Pending COO Approval"),
        (APPROVED,    "Approved"),
        (DENIED,      "Denied"),
        (QUERIED,     "Queried"),
    ]

    requisition = models.OneToOneField(
        Requisition,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_order",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_purchase_orders",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING_COO,  # new POs go straight into COO queue
    )
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

    @property
    def line_total(self) -> Decimal:
        """Quantity × unit_cost for this line."""
        if self.quantity is None or self.unit_cost is None:
            return Decimal("0")
        return self.quantity * self.unit_cost

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
