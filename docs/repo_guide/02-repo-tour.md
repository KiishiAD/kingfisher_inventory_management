# 02 — Repository Tour

This page is your map. If you are new, keep this open while reading code.

## Top-level folders and files
- `supplychain_test/` — Django project root (contains `manage.py`).
- `Dockerfile`, `docker-compose.yml`, `Caddyfile` — deployment/infrastructure.
- `requirements-dev.txt`, `requirements-prod.txt` — dependency sets.

## Django project layout
- `supplychain_test/supplychain_test/` — project config (settings, root URLs, ASGI/WSGI).
- `supplychain_test/accounts/` — account + organization app.
- `supplychain_test/supplychain/` — business domain app.
- `supplychain_test/templates/` — shared templates.
- `supplychain_test/static/` — global CSS/static files.
- `supplychain_test/media/` — uploaded files in development.

## How a request moves through folders
First, `urls.py` chooses a view.
Then the view validates forms and calls model/services.
Then a template is rendered.

```text
supplychain_test/supplychain_test/urls.py
  -> accounts/views.py or supplychain/views/*.py
  -> forms.py + services/utils + models/*
  -> templates/*
```

## Where to look for common tasks
- Add a new page: `supplychain/urls.py` + `supplychain/views/*` + template file.
- Add a new business field: `supplychain/models/*` + migration + forms + templates.
- Change role checks: `PermissionRequiredMixin` in views + Django permissions on models.

## Where in code
- Root URL config: `supplychain_test/supplychain_test/urls.py::urlpatterns`
- App URL configs: `supplychain_test/accounts/urls.py::urlpatterns`, `supplychain_test/supplychain/urls.py::urlpatterns`
- Model export surface: `supplychain_test/supplychain/models/__init__.py::__all__`
