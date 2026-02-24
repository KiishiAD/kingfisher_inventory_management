# 10 — Settings and Environments

## How settings are split
First, Django loads `settings/__init__.py`.
Then that module chooses `development.py` or `production.py` by `DJANGO_ENV`.
Because production is strict, missing required env vars raise runtime errors early.

## Environment files
- `base.py`: shared config
- `development.py`: local defaults (SQLite, debug, SMTP env usage)
- `production.py`: Postgres, WhiteNoise static root, S3 media, stricter validation

## Key configuration topics
- Security: secret key, hosts, CSRF origins
- Sessions: short sliding session timeout
- Static/media: local in dev, S3 media in prod
- Email: SMTP settings
- OAuth: optional Google credentials
- Logging: production logger config

## Where in code
- Loader: `supplychain_test/supplychain_test/settings/__init__.py::env`
- Shared settings: `supplychain_test/supplychain_test/settings/base.py::MIDDLEWARE`
- Dev database/email: `supplychain_test/supplychain_test/settings/development.py::DATABASES`, `supplychain_test/supplychain_test/settings/development.py::EMAIL_HOST_USER`
- Prod env checks: `supplychain_test/supplychain_test/settings/production.py::SECRET_KEY`, `supplychain_test/supplychain_test/settings/production.py::DATABASES`
- S3 media setup: `supplychain_test/supplychain_test/settings/production.py::MediaStorage`
