# 02 — Repository Tour

## Top-level
- `Dockerfile`, `docker-compose.yml`, `Caddyfile`: container + reverse proxy deployment.
- `requirements-*.txt`: dependency sets.
- `supplychain_test/`: Django project root (`manage.py` here).

## Django project tree
- `supplychain_test/supplychain_test/`: project config (settings, root urls, wsgi/asgi).
- `supplychain_test/accounts/`: org/user onboarding app.
- `supplychain_test/supplychain/`: procurement + inventory core app.
- `supplychain_test/templates/`: shared templates (base/login/auth).
- `supplychain_test/static/`: global static assets (`css/styles.css`).
- `supplychain_test/media/`: uploaded files in dev.

## App surface inventory
- **Models:** `accounts/models.py`, `supplychain/models/*`.
- **Views:** `accounts/views.py`, `supplychain/views/*`.
- **Forms:** `accounts/forms.py`, `supplychain/forms.py`.
- **Admin:** `supplychain/admin.py`.
- **Services/utilities:** `supplychain/services/*`, `supplychain/utils.py`.
- **Templatetags:** `supplychain/templatetags/status_tags.py`.
- **Tests:** `accounts/tests.py`, `supplychain/tests/*`.
