from django.db import models
from django.conf import settings
from django.db import models


### Master Data

class TimeStampedModel(models.Model):
    """This abstract class provides two timestamp fields that will automatically record when any inheriting record is created and last updated, ensuring consistent audit fields across all models."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UnitOfMeasure(TimeStampedModel):
    code = models.CharField(max_length=10, unique=True)
    # name holds the full unit name (e.g. “Kilogram”, “Liter”) and must be unique so each UnitOfMeasure appears only once
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
      return f"{self.name} ({self.code})"


class Category(TimeStampedModel):
    # name holds the category title and must be unique so each category appears only once
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=200)
    contact_email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    uom = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name="products")
    categories = models.ManyToManyField(Category, blank=True)
    vendors = models.ManyToManyField(Supplier, blank=True)
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='managed_products'
    )

    def __str__(self):
        return self.name


class Destination(models.Model):
    """Possible requisition destinations (Supplier vs Store)."""

    SUPPLIER = "SUPPLIER"
    STORE = "STORE"
    DESTINATION_CHOICES = [
        (SUPPLIER, "Supplier"),
        (STORE, "Store"),
    ]

    name = models.CharField(max_length=10, choices=DESTINATION_CHOICES, unique=True)

    def __str__(self):
        return self.get_name_display()




#### Requisition & Approval

class Requisition(TimeStampedModel):
    class Meta:
           permissions = [
            ("submit_requisition",   "Can submit and view requisitions"),
            ("approve_requisition",  "Can approve/deny/query requisitions"),
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






