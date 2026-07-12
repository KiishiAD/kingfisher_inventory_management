from .base import *
import os
from urllib.parse import urlparse

# Safe, portable development defaults. Override any value through environment variables.
DEBUG = os.getenv("DEBUG", "true").lower() in {"1", "true", "yes", "on"}
SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-development-key-change-me")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")

parsed_url = urlparse(APP_BASE_URL)
configured_hosts = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
if parsed_url.hostname and parsed_url.hostname not in configured_hosts:
    configured_hosts.append(parsed_url.hostname)
ALLOWED_HOSTS = configured_hosts

configured_origins = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
if parsed_url.scheme in {"http", "https"} and parsed_url.netloc:
    configured_origins.append(f"{parsed_url.scheme}://{parsed_url.netloc}")
CSRF_TRUSTED_ORIGINS = sorted(set(configured_origins))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Console email makes the app usable locally without external SMTP credentials.
# Set EMAIL_BACKEND and SMTP variables to use a real mail service.
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").lower() in {"1", "true", "yes", "on"}
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "noreply@localhost")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
