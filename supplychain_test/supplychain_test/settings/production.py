from .base import *
import os
import dj_database_url

from storages.backends.s3boto3 import S3Boto3Storage


# Production settings for Render
SECRET_KEY = os.environ["SECRET_KEY"]
DEBUG = os.environ.get("DEBUG", "0") == "1"
ALLOWED_HOSTS = [os.environ.get("RENDER_EXTERNAL_HOSTNAME", "127.0.0.1")]

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ["DATABASE_URL"],
        conn_max_age=600,
        conn_health_checks=True,
    )
}

STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"



# Set the required AWS credentials
AWS_ACCESS_KEY_ID = 'your-access-key-id'
AWS_SECRET_ACCESS_KEY = 'your-secret-access-key'
AWS_STORAGE_BUCKET_NAME = 'your-bucket-name'
AWS_S3_REGION_NAME = 'your-region-name'  # e.g. us-west-2

# Optional: Set custom domain for static and media files
# AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'

# Set the static and media files locations
STATICFILES_LOCATION = 'static'
MEDIAFILES_LOCATION = 'media'

# Define custom storage classes for static and media files
class StaticStorage(S3Boto3Storage):
    location = STATICFILES_LOCATION

class MediaStorage(S3Boto3Storage):
    location = MEDIAFILES_LOCATION
    file_overwrite = False

# Configure static and media files storage
STATICFILES_STORAGE = 'your_app_name.settings.StaticStorage'
DEFAULT_FILE_STORAGE = 'your_app_name.settings.MediaStorage'

# Set static and media URLs
STATIC_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{STATICFILES_LOCATION}/'
MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{MEDIAFILES_LOCATION}/'


