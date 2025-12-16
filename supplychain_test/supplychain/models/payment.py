# supplychain/models/payment.py  (or wherever your Payment model currently lives)

from django.db import models
from django.conf import settings

from .purchase import PurchaseOrder
from .master_data import TimeStampedModel


class Payment(TimeStampedModel):
    class Meta:
        permissions = [
            ("process_payment", "Can create and finalize payments"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_order"],
                name="unique_payment_per_purchase_order",
            )
        ]

    # Status
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (PENDING, "Pending Payment"),
        (PROCESSED, "Processed"),
        (CANCELLED, "Cancelled"),
    ]

    # Method
    CHEQUE = "CHEQUE"
    TRANSFER = "TRANSFER"
    CASH = "CASH"
    CARD = "CARD"

    PAYMENT_CHOICES = [
        (CHEQUE, "Cheque"),
        (TRANSFER, "Bank Transfer"),
        (CASH, "Cash"),
        (CARD, "Card Payment"),
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

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_created",
    )

    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_processed",
    )

    approved_by_coo= models.BooleanField(default=False)

    # Allow auto-created payment to exist before method chosen
    payment_type = models.CharField(
        max_length=10,
        choices=PAYMENT_CHOICES,
        null=True,
        blank=True,
    )

    # Optional method metadata (use what you need; leave blank otherwise)
    bank_name = models.CharField(max_length=120, blank=True)
    transfer_reference = models.CharField(max_length=120, blank=True)
    cheque_number = models.CharField(max_length=60, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)

    payment_notes = models.TextField(blank=True)

    payment_proof = models.FileField(
        upload_to="payment_proofs/",
        null=True,
        blank=True,
    )

    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment #{self.id} for PO #{self.purchase_order_id} ({self.get_status_display()})"
