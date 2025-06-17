# kingfisher_inventory_management
Official repo for the inventory management app

## Setup

1. Install Django (and any other dependencies) using pip:
```bash
pip install django
```
2. Apply database migrations before starting the server:
```bash
python supplychain_test/manage.py migrate
```

The SQLite database file is located at `supplychain_test/db.sqlite3`.

3. Ensure the `DJANGO_ENV` variable is set to `development` (the default). Then
   start the development server:
```bash
export DJANGO_ENV=development  # optional, defaults to development
python supplychain_test/manage.py runserver
```
