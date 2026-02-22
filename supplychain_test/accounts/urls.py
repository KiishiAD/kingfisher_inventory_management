from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("google/start/", views.google_start, name="google_start"),
    path("google/callback/", views.google_callback, name="google_callback"),
    path("organization/setup/", views.organization_setup, name="organization_setup"),
    path("invite/", views.invite_user, name="invite_user"),
    path("invite/done/", views.invite_done, name="invite_done"),
]
