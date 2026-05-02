"""Test settings — uses console email backend and minimal config."""
from .base import *

DEBUG = False
SECRET_KEY = "test-secret-key-for-testing-only"

# SQLite for tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Use console email backend so tests don't need real SMTP
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "test@example.com"
SERVER_EMAIL = "test@example.com"

# Speed up tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# No real storage needed
DEFAULT_FILE_STORAGE = "django.core.files.storage.InMemoryStorage"
