from django.db import models
from django.conf import settings

from .purchase import PurchaseOrder
from .requisition import Requisition
from .master_data import Product, TimeStampedModel


#### Payment

class Payment(TimeStampedModel):
    class Meta:
        permissions = [
            ("process_payment",       "Can create and finalize payments"),
        ]

    """Final payment record for a Purchase Order, capturing type, notes, proof, and approval."""
    CHEQUE = 'CHEQUE'
    TRANSFER = 'TRANSFER'
    PAYMENT_CHOICES = [
        (CHEQUE, 'Cheque'),
        (TRANSFER, 'Bank Transfer'),
    ]

    purchase_order = models.OneToOneField(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='payment'
    )
    approved_by_mum = models.BooleanField(default=False)
    payment_type = models.CharField(max_length=10, choices=PAYMENT_CHOICES)
    payment_notes = models.TextField(blank=True)
    payment_proof = models.FileField(upload_to='payment_proofs/', blank=True)
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for {self.purchase_order} via {self.payment_type}"



class IssuanceRequest(TimeStampedModel):
    class Meta:
        permissions = [
            ("submit_issuance",       "Can submit and view issuance requests"),
            ("approve_issuance",      "Can approve/deny/query internal issuance"),
        ]

    """Internal stock issuance request from store to kitchen, with approval workflow."""
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    DENIED = 'DENIED'
    QUERIED = 'QUERIED'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (DENIED, 'Denied'),
        (QUERIED, 'Queried'),
    ]

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='issuance_requests'
    )
    requisition = models.OneToOneField(
        'Requisition',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issuance_request'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    issue_slip = models.FileField(upload_to='issue_slips/', blank=True)

    def __str__(self):
        return f"IssuanceRequest #{self.id} by {self.requester}"


class IssuanceItem(models.Model):
    """Products and quantities for each internal issuance request."""
    issuance_request = models.ForeignKey(
        IssuanceRequest,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product}"
