# 00 — Quickstart

## Prerequisites
- Python 3.12+
- pip
- SQLite (default dev DB)

## Install and run
```bash
cd supplychain_test
python -m venv .venv
source .venv/bin/activate
pip install -r ../requirements-dev.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

App URL: `http://127.0.0.1:8000/`

## Important environment variables
- `DJANGO_ENV` (`development`/`production`) via `supplychain_test/settings/__init__.py`.
- `SECRET_KEY`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (dev file expects these).
- `APP_BASE_URL` for password invite/reset links.

## First login path
1. Visit `/accounts/login/`.
2. Sign up organization owner or use existing user.
3. Use dashboard links for requisitions, POs, receiving, payment, inventory.

> Gotcha: Session expiry is 15 minutes with sliding refresh (`SESSION_COOKIE_AGE`, `SESSION_SAVE_EVERY_REQUEST`).
