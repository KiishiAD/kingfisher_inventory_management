"""Settings loader dispatching on DJANGO_ENV."""

import os

env = os.environ.get("DJANGO_ENV", "development").lower()

if env == "production":
    from .production import *  # noqa
elif env == "demo":
    from .demo import *  # noqa
elif env == "testing":
    from .testing import *  # noqa
else:
    from .development import *  # noqa
