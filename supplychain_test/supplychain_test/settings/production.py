import os
from storages.backends.s3boto3 import S3Boto3Storage

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
