# 08 — Templates and Frontend

## What this layer does
This project is server-rendered Django UI.
Views prepare data, templates render pages, CSS styles the interface.

## Template inheritance (how pages are built)
First, shared layout comes from `base.html` (authenticated) or `base_login.html` (auth pages).
Then feature templates extend one base and fill blocks like title/content.
Because each view passes `section`, navigation highlights the current area.

## Main template families
- Auth pages: login, signup, password reset
- Requisitions: create/list/detail/update/pending/all
- Purchase orders: create/list/detail/update/pending
- Receiving: list/detail (mode-specific controls)
- Payments: list/detail
- Inventory: list/detail/low-stock/movement
- Operations: product bulk upload

## User journey through pages
1. Login/signup screen.
2. Dashboard overview.
3. Create requisition.
4. Follow PO, receiving, and payment pages depending on role.
5. Use inventory pages for stock visibility.

## Static assets pipeline
- CSS lives in `static/css/styles.css`.
- Bootstrap, icons, and Select2 are loaded in base templates.
- WhiteNoise serves static files; production uses compressed manifest storage.

## Where in code
- Base templates: `supplychain_test/templates/base.html`, `supplychain_test/templates/base_login.html`
- Auth template routing: `supplychain_test/supplychain_test/urls.py::urlpatterns`
- Template engine setup: `supplychain_test/supplychain_test/settings/base.py::TEMPLATES`
- Global CSS: `supplychain_test/static/css/styles.css`
