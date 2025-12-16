# supplychain/models/payment.py  (or wherever your Payment model lives)

from django.db import models
from django.conf import settings

from .purchase import PurchaseOrder
from .master_data import TimeStampedModel


class Payment(TimeStampedModel):
    """
    Payment workflow for a Purchase Order.

    Created automatically when a Receiving is cleared for payment.
    Then later finalized by a user with process_payment permission.
    """

    class Meta:
        permissions = [
            ("process_payment", "Can create and finalize payments"),
        ]

    # ---- Status ----
    PENDING = "PENDING"       # created, waiting to be processed
    PROCESSED = "PROCESSED"   # paid
    CANCELLED = "CANCELLED"   # optional, if you ever void a payment

    STATUS_CHOICES = [
        (PENDING, "Pending Payment"),
        (PROCESSED, "Processed"),
        (CANCELLED, "Cancelled"),
    ]

    # ---- Payment types (optional until processed) ----
    CHEQUE = "CHEQUE"
    TRANSFER = "TRANSFER"
    PAYMENT_CHOICES = [
        (CHEQUE, "Cheque"),
        (TRANSFER, "Bank Transfer"),
    ]

    purchase_order = models.OneToOneField(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="payment",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
    )

    # who/when created (for audit trail)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_created",
    )

    # approval bit you already had
    approved_by_mum = models.BooleanField(default=False)

    # type/details recorded when actually processing payment
    payment_type = models.CharField(
        max_length=10,
        choices=PAYMENT_CHOICES,
        null=True,
        blank=True,
    )
    payment_notes = models.TextField(blank=True)
    payment_proof = models.FileField(upload_to="payment_proofs/", blank=True)

    # who/when processed (do NOT auto-set on creation)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_processed",
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        pt = self.payment_type or "—"
        return f"Payment for PO #{self.purchase_order_id} ({self.status}) via {pt}"
