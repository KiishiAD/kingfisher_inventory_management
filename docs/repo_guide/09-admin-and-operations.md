# 09 — Admin and Operations

## Django admin
`/admin/` is enabled and all supplychain models are registered in `supplychain/admin.py` with practical `list_display`, `list_filter`, and searches.

### Staff usage ideas
- Manage master data (`Product`, `Supplier`, `Category`, `UOM`).
- Inspect lifecycle records (`RequisitionApproval`, `PurchaseOrderApproval`, `Receiving`, `Payment`).
- Audit inventory via `StockTransaction` and `LowStockAlert`.

## Operational tasks
- Product bulk upload UI: `/supplychain/operations/products/bulk-upload/`.
- Invite users via `/accounts/invite/` (owner/admin org members).

## Notifications
- Email via SMTP (`services/notifications/email_notifications.py`).
- SMS via Textbelt (`services/notifications/sms_notifications.py`).
