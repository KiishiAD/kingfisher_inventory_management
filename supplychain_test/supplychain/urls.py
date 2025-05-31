from django.urls import path, include
from .views import *

app_name = "supplychain"

urlpatterns = [
    # Dashboard route
    path("dashboard/", DashboardView.as_view(), name="dashboard"),

    
]

