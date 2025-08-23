from django.contrib import admin
from .models import (
    UnitOfMeasure, Category, Supplier, Product,
    Requisition, RequisitionItem, RequisitionApproval,
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderApproval,
    Receiving, ReceivingItem, InvoiceLineApproval,
    Payment,
    IssuanceRequest, IssuanceItem,
    StockTransaction, LowStockAlert, Supplier_destination_sub_category,Destination
)

# Master Data
@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_email', 'phone_number')
    search_fields = ('name',)

@admin.register(Supplier_destination_sub_category)
class SupplierDestinationSubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit_cost', 'uom')
    list_filter = ('uom',)
    search_fields = ('name',)
    filter_horizontal = ('categories', 'vendors', 'assigned_users')

# Requisition & Approval
@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = ('id', 'requester', 'status', 'destination', 'urgent', 'created_at')
    list_filter = ('status', 'destination', 'urgent', 'created_at')

@admin.register(RequisitionItem)
class RequisitionItemAdmin(admin.ModelAdmin):
    list_display = ('requisition', 'product', 'quantity')
    list_filter = ('product',)

@admin.register(RequisitionApproval)
class RequisitionApprovalAdmin(admin.ModelAdmin):
    list_display = ('requisition', 'approver', 'action', 'timestamp')
    list_filter = ('action',)

# Purchase Order & Approval
@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'supplier', 'created_by')

@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'product', 'quantity', 'unit_cost')
    list_filter = ('product',)

@admin.register(PurchaseOrderApproval)
class PurchaseOrderApprovalAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'approver', 'action', 'timestamp')
    list_filter = ('action',)

# Receiving & Invoice Processing
@admin.register(Receiving)
class ReceivingAdmin(admin.ModelAdmin):
    list_display = ('id', 'purchase_order', 'received_by', 'received_at')

@admin.register(ReceivingItem)
class ReceivingItemAdmin(admin.ModelAdmin):
    list_display = ('receiving', 'po_item', 'actual_quantity')
    list_filter = ('po_item__product',)

@admin.register(InvoiceLineApproval)
class InvoiceLineApprovalAdmin(admin.ModelAdmin):
    list_display = ('receiving_item', 'accountant', 'approved', 'timestamp')
    list_filter = ('approved',)

# Payment
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'payment_type', 'approved_by_mum', 'processed_at')
    list_filter = ('payment_type', 'approved_by_mum')

# Store Issuance
@admin.register(IssuanceRequest)
class IssuanceRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'requester', 'status', 'created_at')
    list_filter = ('status',)

@admin.register(IssuanceItem)
class IssuanceItemAdmin(admin.ModelAdmin):
    list_display = ('issuance_request', 'product', 'quantity')
    list_filter = ('product',)

# Inventory & Alerts
@admin.register(StockTransaction)
class StockTransactionAdmin(admin.ModelAdmin):
    list_display = ('product', 'transaction_type', 'quantity', 'timestamp')
    list_filter = ('transaction_type', 'product')

@admin.register(LowStockAlert)
class LowStockAlertAdmin(admin.ModelAdmin):
    list_display = ('product', 'threshold', 'triggered_at', 'acknowledged')
    list_filter = ('acknowledged',)
