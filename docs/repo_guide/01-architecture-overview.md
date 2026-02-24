# 01 — Architecture Overview

## High-level architecture
```mermaid
flowchart LR
  Browser --> Django["Django app
(supplychain_test)"]
  Django --> Views["Class/Function Views"]
  Views --> Forms["Django Forms/Formsets"]
  Views --> Utils["utils.py + services/*"]
  Forms --> Models["accounts + supplychain models"]
  Utils --> Models
  Models --> DB[(SQLite dev / Postgres prod)]
  Django --> Templates["Django templates"]
  Django --> Static["WhiteNoise static files"]
  Django --> Email["SMTP"]
  Django --> SMS["Textbelt API"]
  Django --> S3["S3 media in production"]
```

## Main packages
- `accounts`: organization onboarding, invite flow, optional Google OAuth.
- `supplychain`: procurement/inventory/payment domain.
- `supplychain_test/settings`: env-specific settings split.

## Request path pattern
`urls.py` → view class/function → form/formset validation → model write/read → template render.

## Notable design traits
- Most workflows are server-rendered pages (no DRF API layer).
- Workflow state is represented in model `status` fields.
- Timeline/event rendering is centralized in `supplychain/utils.py`.
- Inventory stock is event-sourced from `StockTransaction` rows (signed quantities).
