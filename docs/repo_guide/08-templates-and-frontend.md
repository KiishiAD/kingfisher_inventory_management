# 08 — Templates and Frontend

## Base templates
- `templates/base.html`: main authenticated shell, nav, section highlighting, dropdown ops links.
- `templates/base_login.html`: auth shell for login/signup/reset pages.

## Feature templates
- Requisition pages (`create`, `list`, `all`, `pending`, `detail`, `update`).
- PO pages (`create`, `list`, `pending`, `detail`, `update`).
- Receiving (`list`, `detail`) with mode-driven form rendering.
- Payments (`list`, `detail`).
- Inventory (`list`, `detail`, `low_stock`, `movement_report`).
- Operations (`product_bulk_upload`).

## Inheritance pattern
Most supplychain templates do `{% extends "base.html" %}` and use `section` context for active menu state.
Auth templates extend `base_login.html`.

## Static pipeline
- Global stylesheet at `static/css/styles.css`.
- Bootstrap, Bootstrap Icons, Select2 loaded via CDN in `base.html`.
- WhiteNoise serves static assets; production uses compressed manifest storage.

> Tip: This frontend is server-rendered-first. JavaScript is mostly enhancement (search/select widgets), not SPA routing.
