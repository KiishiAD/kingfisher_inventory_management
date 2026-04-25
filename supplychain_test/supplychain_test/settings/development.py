from .base import *
import os

# Development settings
DEBUG = True
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

from urllib.parse import urlparse

# Codespaces: automatically build the forwarded URL for port 8000
CODESPACE_NAME = os.environ.get("CODESPACE_NAME")
PORT_FWD_DOMAIN = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")

if CODESPACE_NAME and PORT_FWD_DOMAIN:
    # Example: https://<codespace>-8000.<domain>
    APP_BASE_URL = f"https://{CODESPACE_NAME}-8000.{PORT_FWD_DOMAIN}"
else:
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8000").rstrip("/")

APP_BASE_URL = APP_BASE_URL.rstrip("/")

u = urlparse(APP_BASE_URL)


ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "ideal-tribble-rxjvjr4xggx2x4wg.github.dev",
]

CSRF_TRUSTED_ORIGINS = [
    "https://ideal-tribble-rxjvjr4xggx2x4wg.github.dev",
    "https://localhost:8000",

]


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.hostinger.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "dev@example.com")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
SERVER_EMAIL = EMAIL_HOST_USER
APP_BASE_URL = os.environ.get("APP_BASE_URL", APP_BASE_URL).rstrip("/")