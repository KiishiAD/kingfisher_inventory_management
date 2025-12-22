# supplychain_test/settings/production.py
from .base import *  # noqa
import os
import dj_database_url

APP_BASE_URL = os.getenv("APP_BASE_URL", "").strip().rstrip("/")


#To enable tracebacks in production logs
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        # Optional: log your app too
        "supplychain": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}



def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "t", "yes", "y", "on")


def env_list(name: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, "").split(",") if x.strip()]


def env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    return int(v)


# --------------------
# Core required config
# --------------------
DJANGO_ENV = os.getenv("DJANGO_ENV", "production").strip()

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is required in production")

DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS is required (comma-separated)")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# --------------------
# Database (required)
# --------------------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required in production")

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# --------------------
# Static (on droplet via WhiteNoise)
# --------------------
STATIC_URL = "/static/"
STATIC_ROOT = "/vol/web/static"



# Django 5+ preferred storage config
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Optional: if you still rely on the legacy setting anywhere
# STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# --------------------
# Media / uploads (S3 only)
# --------------------
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "").strip()
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "").strip()

USE_S3_MEDIA = all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME])

if USE_S3_MEDIA:
    from storages.backends.s3boto3 import S3Boto3Storage

    MEDIAFILES_LOCATION = "media"

    class MediaStorage(S3Boto3Storage):
        location = MEDIAFILES_LOCATION
        file_overwrite = False

    # Django 5+ default file storage backend
    STORAGES["default"] = {"BACKEND": "supplychain_test.settings.production.MediaStorage"}

    # S3 URL for uploaded media
    MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{MEDIAFILES_LOCATION}/"
else:
    # If you truly require S3 in production, fail fast:
    raise RuntimeError(
        "S3 media is not configured. Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME."
    )

# --------------------
# Email (SMTP)
# --------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = os.getenv("EMAIL_HOST", "").strip()
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or "noreply@localhost"

# Optional: fail fast if email is required in prod
# if not EMAIL_HOST or not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
#     raise RuntimeError("Email SMTP is not fully configured in production")
