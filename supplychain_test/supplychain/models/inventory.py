from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from .master_data import Product, TimeStampedModel


##### Inventory & Alerts

class StockTransaction(TimeStampedModel):
    RECEIVE = "RECEIVE"
    ISSUE = "ISSUE"
    ADJUST = "ADJUST"
    TRANSACTION_CHOICES = [
        (RECEIVE, "Receive"),
        (ISSUE, "Issue"),
        (ADJUST, "Adjust"),
    ]

    SRC_REQUISITION = "REQUISITION"
    SRC_RECEIVING = "RECEIVING"
    SRC_STOCKTAKE = "STOCKTAKE"
    SOURCE_CHOICES = [
        (SRC_REQUISITION, "Requisition"),
        (SRC_RECEIVING, "Receiving"),
        (SRC_STOCKTAKE, "Stocktake"),
    ]

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_transactions")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_CHOICES)

    quantity = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_id = models.PositiveIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_transactions"
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transaction_type", "source_type", "source_id", "product"],
                name="uniq_stocktxn_per_source_product",
            )
        ]

class LowStockAlert(TimeStampedModel):
    class Meta:
        permissions = [
            ("acknowledge_lowstock",  "Can acknowledge low-stock alerts"),
        ]
    """Alerts when stock falls below a configured threshold, with acknowledgement tracking."""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='low_stock_alerts'
    )
    threshold = models.DecimalField(max_digits=10, decimal_places=2)
    triggered_at = models.DateTimeField(auto_now_add=True)
    acknowledged = models.BooleanField(default=False)

    def __str__(self):
        return f"Low stock alert for {self.product} at {self.triggered_at}"
