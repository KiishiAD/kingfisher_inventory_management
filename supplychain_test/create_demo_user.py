"""Create or refresh the isolated public-demo administrator account."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "supplychain_test.settings")
os.environ.setdefault("DJANGO_ENV", "demo")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

username = os.getenv("DEMO_USERNAME", "demo")
password = os.environ["DEMO_PASSWORD"]
email = os.getenv("DEMO_EMAIL", "demo@kingfisher.local")

User = get_user_model()
user, _ = User.objects.get_or_create(username=username)
user.email = email
user.is_active = True
user.is_staff = True
user.is_superuser = True
user.set_password(password)
user.save()

print(f"Demo administrator ready: {username}")
