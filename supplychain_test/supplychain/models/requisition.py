from django.db import models
from django.conf import settings

from .master_data import Supplier_destination_sub_category, Destination, Product, TimeStampedModel


#### Requisition & Approval

class Requisition(TimeStampedModel):
    class Meta:
        permissions = [
            ("submit_requisition",   "Can submit and view requisitions"),
            ("approve_requisition",  "Can approve/deny/query requisitions"),
            ("view_all_requisitions", "Can view all requisitions"),
        ]
           

    """A request for products, submitted by a user and tracked through approval."""
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
        related_name='requisitions'
    )

    Supplier_destination_sub_category = models.ForeignKey(
        Supplier_destination_sub_category,
        on_delete=models.PROTECT,
        related_name="requisitions",
        verbose_name="Supplier Sub-Category",
        null=True,
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    destination = models.ForeignKey(
        Destination,
        on_delete=models.PROTECT,
        related_name='requisitions'
    )
    notes = models.TextField(blank=True)
    evidence = models.FileField(upload_to='requisition_evidence/', blank=True)
    urgent = models.BooleanField(default=False)

    def __str__(self):
        return f"Requisition #{self.id} by {self.requester}"

    def get_destination_display(self):
        return self.destination.get_name_display()
    

class RequisitionItem(models.Model):
    """Line items for each requisition, linking to products and quantities."""
    requisition = models.ForeignKey(
        Requisition,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product}"



class RequisitionApproval(models.Model):
    """Audit trail of approval actions taken on a requisition."""
    requisition = models.ForeignKey(
        Requisition,
        on_delete=models.CASCADE,
        related_name='approvals'
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='requisition_approvals'
    )
    action = models.CharField(
        max_length=10,
        choices=Requisition.STATUS_CHOICES
    )
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.requisition} {self.action} by {self.approver}"
