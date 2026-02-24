# 03 — Domain Model

This section is the “what exists in the database and why” map.

## End-to-end business chain

`Organization/User` → `Requisition` → `PurchaseOrder` → `Receiving` → `Payment` + `StockTransaction`/`LowStockAlert`

---

## Accounts models

### `accounts/models.py::Organization`
- `name` (CharField, unique)
- `created_at` (auto add)

**Meaning:** top-level business entity users belong to.

### `accounts/models.py::OrganizationMembership`
- `user` (FK → `AUTH_USER_MODEL`, CASCADE, related `organization_memberships`)
- `organization` (FK → `Organization`, CASCADE, related `memberships`)
- `role` (`owner|admin|member`)
- `created_at`

**Constraint:** unique `(user, organization)` via `uniq_user_organization_membership`.

---

## Master data models (`supplychain/models/master_data.py`)

### `TimeStampedModel` (abstract)
- `created_at`, `updated_at`

### `UnitOfMeasure`
- `code` unique
- `name` unique

### `Category`
- `name` unique

### `Supplier`
- `name`
- `contact_email`, `phone_number`, `address` optional

### `Supplier_destination_sub_category`
- `name` choice (`CONSUMABLES`, `SERVICES`), unique, nullable

### `Product`
- `sku` unique (auto-generated if blank)
- `name`, `description`, `unit_cost`
- `uom` (FK → `UnitOfMeasure`, PROTECT, related `products`)
- `categories` (M2M → `Category`)
- `vendors` (M2M → `Supplier`)
- `assigned_users` (M2M → user, related `managed_products`)
- `low_stock_threshold` optional decimal, min 0 validator

**Constraint:** unique on `Lower(name)` + `uom` (`uniq_product_sku`).

### `Destination`
- `name` unique choice (`PURCHASE`, `STORE`)

### `Profile`
- `user` (OneToOne → user, related `profile`)
- `phone_number`

---

## Requisition models (`supplychain/models/requisition.py`)

### `Requisition`
- `requester` (FK user)
- `supplier` (FK Supplier, optional)
- `Supplier_destination_sub_category` (FK optional)
- `status` (`PENDING|APPROVED|DENIED|QUERIED`)
- `destination` (FK Destination)
- `notes`, `evidence` (required file), `urgent`
- timestamp fields from abstract base

### `RequisitionItem`
- `requisition` (FK Requisition, related `items`)
- `product` (FK Product, PROTECT)
- `quantity`

**Constraint:** unique `(requisition, product)` (`uniq_requisition_product`).

### `RequisitionApproval`
- `requisition` (FK, related `approvals`)
- `approver` (FK user, nullable SET_NULL)
- `action` (same choices as requisition status)
- `notes`, `timestamp`

---

## Purchase models (`supplychain/models/purchase.py`)

### `PurchaseOrder`
- `requisition` (OneToOne → Requisition, nullable, related `purchase_order`)
- `supplier` (FK Supplier)
- `created_by` (FK user)
- `status` (`PENDING_COO|APPROVED|DENIED|QUERIED`)
- `sent_at`

**Business validation (`clean`)**: PO supplier must match linked requisition supplier.

### `PurchaseOrderItem`
- `purchase_order` (FK, related `items`)
- `product` (FK Product)
- `quantity`, `unit_cost`
- computed `line_total`

### `PurchaseOrderApproval`
- `purchase_order` (FK, related `approvals`)
- `approver` (FK user)
- `action` (PO status choice)
- `notes`, `timestamp`

---

## Receiving models (`supplychain/models/receiving.py`)

### `Receiving`
- `purchase_order` (FK PurchaseOrder, related `receivings`)
- `status` (`PENDING|UNDER_REVIEW|PENDING_COO|REVIWED|DENIED`)
- `received_by`, `received_at`
- `supplier_invoice` file optional
- accounting/COO audit fields (`review_notes`, `reviewed_by`, `reviewed_at`, `sent_to_coo_*`, `coo_decision_*`)

**Constraint:** unique `purchase_order` (`unique_receiving_per_purchase_order`).

### `ReceivingItem`
- `receiving` (FK, related `items`)
- `po_item` (FK PurchaseOrderItem)
- `actual_quantity` nullable
- `accounting_queried`, `accounting_notes`
- `flagged_for` JSON

### `InvoiceLineApproval`
- `receiving_item` (FK, related `invoice_approvals`)
- `accountant` (FK user)
- `approved` nullable bool (`None` means queried)
- `notes`, `timestamp`

---

## Payment + inventory models

### `supplychain/models/payment.py::Payment`
- `purchase_order` (OneToOne → PO, related `payment`)
- `status` (`PENDING|PROCESSED|CANCELLED`)
- `created_by`, `processed_by`, `processed_at`
- `approved_by_coo` bool
- payment method fields (`payment_type`, `bank_name`, `transfer_reference`, etc.)
- `payment_notes`, `payment_proof`

**Constraint:** unique payment per PO (`unique_payment_per_purchase_order`).

### `supplychain/models/inventory.py::StockTransaction`
- `product` (FK Product, PROTECT)
- `transaction_type` (`RECEIVE|ISSUE|ADJUST_IN|ADJUST_OUT`)
- `quantity` (min 0)
- `source_type` (`REQUISITION|RECEIVING|STOCKTAKE|BULK_UPLOAD`)
- `source_id` (integer correlation id)
- `created_by`, `note`

**Constraint:** unique `(transaction_type, source_type, source_id, product)` to ensure idempotent posting.

### `LowStockAlert`
- `product` FK
- `threshold` snapshot
- `triggered_at`, `resolved_at`
- `acknowledged`, `acknowledged_by`, `acknowledged_at`

---

## Relationship direction and workflow meaning
- One org has many memberships; one user can belong to many orgs.
- One requisition has many requisition items and approvals.
- A requisition can have at most one PO (model OneToOne), though utility code still contains legacy multi-supplier grouping logic.
- One PO has many PO items and approvals.
- One PO has one receiving lifecycle record and one payment record (enforced by unique constraints/OneToOne payment).
- Inventory is not stored as a mutable stock field; current stock is computed from transaction sums.

> Tip: Think of this project as **workflow-state models + append-only audit/event rows**.
