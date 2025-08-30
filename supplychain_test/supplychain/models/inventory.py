from django.db import models

from .master_data import Product, TimeStampedModel


##### Inventory & Alerts

class StockTransaction(TimeStampedModel):
    """Atomic record of stock changes (receipts or issues) for real-time inventory."""
    RECEIVE = 'RECEIVE'
    ISSUE = 'ISSUE'
    TRANSACTION_CHOICES = [
        (RECEIVE, 'Receive'),
        (ISSUE, 'Issue'),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='stock_transactions'
    )
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_CHOICES)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} of {self.product}"
    


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
