# 00 — Quickstart

This chapter helps a new developer get the app running and understand what they are seeing.

## What this project is
This is a Django web app with two Django apps:
- `accounts` for login, organization setup, and invites.
- `supplychain` for requisitions, purchase orders, receiving, payment, and inventory.

## Prerequisites
- Python 3.12+
- pip
- SQLite (default development database)

## First run (step-by-step)
1. Open a terminal in this repository.
2. Enter the Django project directory.
3. Create and activate a virtual environment.
4. Install dependencies.
5. Run migrations.
6. Create an admin account.
7. Start the server.

```bash
cd supplychain_test
python -m venv .venv
source .venv/bin/activate
pip install -r ../requirements-dev.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then open: `http://127.0.0.1:8000/`.

## Environment variables you should set
- `DJANGO_ENV` (`development` or `production`).
- `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` (required by development settings).
- `APP_BASE_URL` (used to build invite/reset links).

## What you should do after startup
1. Visit `/accounts/login/`.
2. Create an organization owner account on signup.
3. Open the dashboard.
4. Create one requisition so you can trace the full workflow.

## Where in code
- Project entry: `supplychain_test/manage.py::main`
- Settings loader: `supplychain_test/supplychain_test/settings/__init__.py::env`
- Dev email env requirement: `supplychain_test/supplychain_test/settings/development.py::EMAIL_HOST_USER`
- Login redirect: `supplychain_test/supplychain_test/settings/base.py::LOGIN_REDIRECT_URL`
