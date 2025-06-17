"""Settings loader dispatching on DJANGO_ENV"""
import os

env = os.environ.get("DJANGO_ENV", "development").lower()

if env == "production":
    from .production import *  # noqa
else:
    from .development import *  # noqa
