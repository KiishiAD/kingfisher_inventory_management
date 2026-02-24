# Supplychain App

## Purpose
Main business app for procurement, receiving, finance handoff, and inventory analytics.

## URL namespaces (from `supplychain/urls.py`)
- Dashboard: `/supplychain/dashboard/`
- Requisitions: create/list/all/pending/detail/update
- Purchase Orders: list/create/pending/detail/update
- Receiving: list/detail
- Inventory: list/low-stock/movement/detail
- Payments: list/detail
- Operations: product bulk upload

## Key models inside this app
- Master data: `UnitOfMeasure`, `Category`, `Supplier`, `Product`, `Destination`, `Profile`
- Procurement: `Requisition`, `RequisitionItem`, `RequisitionApproval`, `PurchaseOrder`, `PurchaseOrderItem`, `PurchaseOrderApproval`
- Fulfillment/finance: `Receiving`, `ReceivingItem`, `InvoiceLineApproval`, `Payment`
- Inventory: `StockTransaction`, `LowStockAlert`

## Forms and formsets
- Requisition: header + inline item formset + approval form + filter form.
- PO: header + inline item formset + approval form + filter form.
- Receiving: entry form, item entry formset, accounting review formset, COO decision form.
- Payment processing form with method-specific validation.
- Product bulk upload file form.

## View modules
- `dashboard_views.py`: role-aware dashboard counts.
- `requisition_views.py`: creation, approval, stock checks for STORE destination, auto PO generation.
- `purchaseorder_views.py`: manual PO create/edit + COO approval + auto receiving creation.
- `receiving_views.py`: mode-based state machine (entry/accounting/COO/readonly).
- `payments_views.py`: list + process pending payment.
- `inventory_views.py`: computed on-hand list, low-stock dashboard, movement report.
- `product_bulk_upload_views.py`: spreadsheet ingest UI.

## Templates
- `templates/supplychain/dashboard.html`
- `templates/supplychain/requisitions/*.html`
- `templates/supplychain/purchase_orders/*.html`
- `templates/supplychain/receiving/*.html`
- `templates/supplychain/payments/*.html`
- `templates/supplychain/inventory/*.html`
- `templates/supplychain/operations/product_bulk_upload.html`

## Services/utilities used by this app
- `services/inventory.py`: inventory posting + low-stock evaluation.
- `services/uploads/product_bulk_upload.py`: DataFrame-driven product import/upsert + stock adjustment.
- `services/notifications/*`: requisition approval/denial fanout.
- `utils.py`: PO/receiving generation, timeline builders, orchestration helpers.

## Cross-app interactions
- Reads org context indirectly via authenticated users and dashboard membership filtering (`accounts.OrganizationMembership`).
- Uses Django auth users/groups/permissions for role access.
