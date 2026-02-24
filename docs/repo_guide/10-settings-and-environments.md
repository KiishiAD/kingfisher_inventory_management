# 10 — Settings and Environments

## Settings split
- `settings/base.py` — shared app config, middleware, templates, static/media defaults.
- `settings/development.py` — DEBUG=True, SQLite, dev email creds.
- `settings/production.py` — strict env checks, Postgres URL parsing, WhiteNoise + S3 media.
- `settings/__init__.py` chooses by `DJANGO_ENV`.

## Security-ish defaults
- Session age 15 minutes, sliding expiry.
- `SECRET_KEY` mandatory in prod.
- `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` environment-driven in prod.

## Storage
- Static: WhiteNoise manifest storage + `STATIC_ROOT=/vol/web/static` in prod.
- Media: forced S3 in prod (`USE_S3_MEDIA` validation).

## Email + OAuth
- SMTP settings expected from env vars.
- Google OAuth client id/secret optional; if absent, flow warns and falls back.
