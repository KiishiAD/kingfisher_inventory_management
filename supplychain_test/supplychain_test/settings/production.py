from .base import *
import os
import dj_database_url
from storages.backends.s3boto3 import S3Boto3Storage

# --- Database (required in production) ---
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing/empty in production settings")

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}


# Keep Whitenoise for static
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_URL = "/static/"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# --- S3: MEDIA only (uploads) ---
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "")

MEDIAFILES_LOCATION = "media"

class MediaStorage(S3Boto3Storage):
    location = MEDIAFILES_LOCATION
    file_overwrite = False

DEFAULT_FILE_STORAGE = "supplychain_test.settings.production.MediaStorage"

# If your bucket is PRIVATE, keep signed URLs enabled (default True).
# If your bucket is PUBLIC and you don't want signed URLs, uncomment:
# AWS_QUERYSTRING_AUTH = False

MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{MEDIAFILES_LOCATION}/"
