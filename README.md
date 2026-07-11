# Kingfisher Supply Chain System

Kingfisher is an open-source Django application for procurement, inventory, receiving, supplier, payment, and approval workflows in small and medium-sized organisations.

## Features

- Role-based access for requesters, approvers, procurement, finance, and store teams
- Requisition and purchase-order approval workflows
- Supplier and product catalogue management
- Goods receiving and inventory issuance
- Invoice and payment tracking
- Email and optional SMS notifications
- PDF exports, audit trails, and operational dashboards

## Quick start with Docker

Requirements: Docker and Docker Compose.

```bash
git clone https://github.com/KiishiAD/kingfisher_inventory_management.git
cd kingfisher_inventory_management
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8000`.

Create an administrator account in a second terminal:

```bash
docker compose exec web python manage.py createsuperuser
```

The Docker development setup uses SQLite and prints outgoing emails to the container console, so no database or SMTP account is required.

## Local Python setup

Requirements: Python 3.12 or newer.

```bash
git clone https://github.com/KiishiAD/kingfisher_inventory_management.git
cd kingfisher_inventory_management
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
cd supplychain_test
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The default settings module selects the development configuration unless `DJANGO_ENV` is changed.

## Configuration

All environment variables are documented in `.env.example`. The useful defaults are:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_ENV` | `development` | Selects development, testing, or production settings |
| `SECRET_KEY` | unsafe local value | Django signing key; replace outside local development |
| `APP_BASE_URL` | `http://localhost:8000` | Public application URL |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated Django hosts |
| `EMAIL_BACKEND` | console backend | Prints local emails instead of requiring SMTP |
| `TEXTBELT_API_KEY` | `textbelt` | Optional SMS integration test key |

Never commit a populated `.env` file or production credentials.

## Running tests

```bash
cd supplychain_test
DJANGO_ENV=testing python manage.py test
```

## Production notes

The included Compose file is intentionally optimised for local evaluation. A production deployment should use a strong `SECRET_KEY`, PostgreSQL, HTTPS, restricted hosts/origins, persistent media storage, a real email provider, and the production settings module.

## Project structure

```text
.
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── supplychain_test/
    ├── manage.py
    ├── accounts/
    ├── supplychain/
    └── supplychain_test/settings/
```

## Contributing

Issues and pull requests are welcome. For substantial changes, open an issue first so the proposed behaviour and scope can be discussed. Keep credentials and organisation-specific data out of commits, add tests for behavioural changes, and run the test suite before submitting a pull request.

## License

Released under the MIT License. See `LICENSE`.
