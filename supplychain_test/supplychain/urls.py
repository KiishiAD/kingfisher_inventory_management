from django.urls import path, include
from .views import *

app_name = "supplychain"

urlpatterns = [
    # Dashboard route
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    
    # REQUESTER: Create a new requisition
    path('requisitions/create/', RequisitionCreateView.as_view(), name='requisition-create'),

    # REQUESTER: List all requisitions owned by the logged-in user
    path('requisitions/', RequisitionListView.as_view(), name='requisition-list'
    ),
    # PROCUREMENT: List of pending requisitions
    path('requisitions/pending/', RequisitionPendingListView.as_view(), name='requisition-pending'),
    
    # DETAIL & APPROVAL: View a single requisition and show approval form
    path('requisitions/<int:pk>/', RequisitionDetailView.as_view(), name='requisition-detail'
    ),


    
]

