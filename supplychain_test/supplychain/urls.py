from django.urls import path, include

from .views.dashboard_views import DashboardView
from .views.requisition_views import (
    RequisitionCreateView,
    RequisitionListView,
    RequisitionPendingListView,
    RequisitionAllListView,
    RequisitionDetailView,
    RequisitionUpdateView,
)
from .views.purchaseorder_views import (
    PurchaseOrderListView,
    PurchaseOrderCreateView,
    PurchaseOrderPendingListView,
    PurchaseOrderDetailView,
    PurchaseOrderUpdateView,
)
from .views.receiving_views import (ReceivingListView, ReceivingDetailView
                                    
)
from .views.inventory_views import InventoryLevelsView, InventoryAlertsView
from .views.payments_views import PaymentsListView

app_name = "supplychain"

urlpatterns = [
    # Dashboard route
    path("dashboard/", DashboardView.as_view(), name="dashboard"),

    # Purchase Orders
    path('purchase-orders/', PurchaseOrderListView.as_view(), name='po-list'),
    path('purchase-orders/create/', PurchaseOrderCreateView.as_view(), name='po-create'),
    path('purchase-orders/pending/', PurchaseOrderPendingListView.as_view(), name='po-pending'),
    path('purchase-orders/<int:pk>/', PurchaseOrderDetailView.as_view(), name='po-detail'),
    path("purchase-orders/<int:pk>/update/", PurchaseOrderUpdateView.as_view(), name="po-update"),

    # REQUESTER: Create a new requisition
    path('requisitions/create/', RequisitionCreateView.as_view(), name='requisition-create'),

    # REQUESTER: List all requisitions owned by the logged-in user
    path('requisitions/', RequisitionListView.as_view(), name='requisition-list'),
    # MANAGEMENT: View all requisitions
    path('requisitions/all/', RequisitionAllListView.as_view(), name='requisition-all'),
    # PROCUREMENT: List of pending requisitions
    path('requisitions/pending/', RequisitionPendingListView.as_view(), name='requisition-pending'),

    # Update queried requisition
    path('requisitions/<int:pk>/update/', RequisitionUpdateView.as_view(), name='requisition-update'),

    # DETAIL & APPROVAL: View a single requisition and show approval form
    path('requisitions/<int:pk>/', RequisitionDetailView.as_view(), name='requisition-detail'),

    # Receiving
    path('receiving/', ReceivingListView.as_view(), name='receiving-list'),
    path('receiving/<int:pk>/', ReceivingDetailView.as_view(), name='receiving-detail'),

    # Inventory
    path('inventory/levels/', InventoryLevelsView.as_view(), name='inventory-levels'),
    path('inventory/alerts/', InventoryAlertsView.as_view(), name='inventory-alerts'),

    # Payments
    path('payments/', PaymentsListView.as_view(), name='payments-list'),
]
