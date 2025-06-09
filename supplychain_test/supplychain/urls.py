from django.urls import path, include
from .views import *

app_name = "supplychain"

urlpatterns = [
    # Dashboard route
    path("dashboard/", DashboardView.as_view(), name="dashboard"),

    # Purchase Orders
    path('purchase-orders/', PurchaseOrderListView.as_view(), name='po-list'),
    path('purchase-orders/create/', PurchaseOrderCreateView.as_view(), name='po-create'),
    path('purchase-orders/pending/', PurchaseOrderPendingListView.as_view(), name='po-pending'),

    # REQUESTER: Create a new requisition
    path('requisitions/create/', RequisitionCreateView.as_view(), name='requisition-create'),

    # REQUESTER: List all requisitions owned by the logged-in user
    path('requisitions/', RequisitionListView.as_view(), name='requisition-list'),
    # PROCUREMENT: List of pending requisitions
    path('requisitions/pending/', RequisitionPendingListView.as_view(), name='requisition-pending'),

    # DETAIL & APPROVAL: View a single requisition and show approval form
    path('requisitions/<int:pk>/', RequisitionDetailView.as_view(), name='requisition-detail'),

    # Receiving
    path('receiving/', ReceivingListView.as_view(), name='receiving-list'),
    path('receiving/record/', ReceivingRecordView.as_view(), name='receiving-record'),

    # Issuance
    path('issuance/', IssuanceListView.as_view(), name='issuance-list'),
    path('issuance/create/', IssuanceCreateView.as_view(), name='issuance-create'),
    path('issuance/pending/', IssuancePendingListView.as_view(), name='issuance-pending'),

    # Inventory
    path('inventory/levels/', InventoryLevelsView.as_view(), name='inventory-levels'),
    path('inventory/alerts/', InventoryAlertsView.as_view(), name='inventory-alerts'),

    # Payments
    path('payments/', PaymentsListView.as_view(), name='payments-list'),
]
