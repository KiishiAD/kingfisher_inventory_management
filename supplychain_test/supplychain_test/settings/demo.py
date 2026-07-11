"""Safe public-demo settings for Render.

This environment intentionally keeps production.py strict and unchanged. It uses
Render Postgres when DATABASE_URL is present, serves static files with WhiteNoise,
and falls back to local media storage and console email for evaluation deployments.
"""

import os

import dj_database_url

from .development import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]

render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
APP_BASE_URL = (
    f"https://{render_hostname}"
    if render_hostname
    else os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
)

ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".onrender.com"]
if render_hostname:
    ALLOWED_HOSTS.append(render_hostname)

CSRF_TRUSTED_ORIGINS = ["https://*.onrender.com"]
if APP_BASE_URL.startswith(("http://", "https://")):
    CSRF_TRUSTED_ORIGINS.append(APP_BASE_URL)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
