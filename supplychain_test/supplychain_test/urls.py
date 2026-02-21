from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from accounts.views import auth_landing

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("supplychain/", include("supplychain.urls")),
    path("accounts/login/", auth_landing, name="login"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", RedirectView.as_view(url="accounts/login/", permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
