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

    '''Final payment status choices'''

    """Final payment record for a received item, capturing type, notes, proof, and approval."""
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


