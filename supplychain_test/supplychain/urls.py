from django.urls import path, include


urlpatterns = [
    # Dashboard route
    path("dashboard/", views.dashboard, name="dashboard"),
    
]

