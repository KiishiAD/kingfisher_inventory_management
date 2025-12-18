from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("invite/", views.invite_user, name="invite_user"),
    path("invite/done/", views.invite_done, name="invite_done"),
]
