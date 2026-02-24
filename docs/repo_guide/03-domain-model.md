# 03 — Domain Model (Instructor Version)

If one line in this guide should stick in your head, it is this:

> The app tracks a request from “we need something” all the way to “it was bought, received, paid, and inventory was updated.”

## That vague chain, translated into normal English

Old short form:
`Organization/User → Requisition → PurchaseOrder → Receiving → Payment + StockTransaction/LowStockAlert`

Plain-English version:
1. A **user** belongs to an **organization**.
2. That user creates a **requisition** (a request for goods/services).
3. If approved for supplier purchase, the system creates a **purchase order (PO)**.
4. When goods arrive, staff record a **receiving** entry (what actually arrived).
5. Finance processes a **payment** for the PO.
6. Inventory movement is written as **stock transactions** (receive/issue/adjust).
7. If stock drops too low, a **low stock alert** is created.

---

## Quick role of each core model

| Model | What it represents | Why it exists |
|---|---|---|
| `Organization` | Business account/tenant | Groups users and activity by business |
| `OrganizationMembership` | User↔organization link + role | Controls owner/admin/member org permissions |
| `Requisition` | Internal request | Entry point for procurement/store workflows |
| `PurchaseOrder` | Formal order to supplier | Tracks procurement approval and spending |
| `Receiving` | What was physically received | Verifies PO vs delivered quantities |
| `Payment` | Finance settlement of PO | Tracks method/status/proof of payment |
| `StockTransaction` | Inventory event row | Source of truth for on-hand stock |
| `LowStockAlert` | Threshold breach event | Signals replenishment needs |

---

## Model details (by module)

## Accounts models

### `accounts/models.py::Organization`
- `name` (unique)
- `created_at`

### `accounts/models.py::OrganizationMembership`
- `user` (FK user)
- `organization` (FK organization)
- `role` (`owner|admin|member`)
- `created_at`

Constraint: unique `(user, organization)`.

---

## Master data (`supplychain/models/master_data.py`)

### `TimeStampedModel` (abstract)
- `created_at`, `updated_at`

### `UnitOfMeasure`
- `code` unique
- `name` unique

### `Category`
- `name` unique

### `Supplier`
- `name`, optional contact fields

### `Supplier_destination_sub_category`
- optional enum-like subcategory (`CONSUMABLES`, `SERVICES`)

### `Product`
- `sku` unique, auto-generated if blank
- `name`, `description`, `unit_cost`
- `uom` FK
- M2M: `categories`, `vendors`, `assigned_users`
- `low_stock_threshold` optional

Constraint: unique on `Lower(name)` + `uom`.

### `Destination`
- choice: `PURCHASE` or `STORE` (unique)

### `Profile`
- one-to-one user profile (phone number)

---

## Requisition models (`supplychain/models/requisition.py`)

### `Requisition`
- who requested (`requester`)
- optional supplier/subcategory
- status: `PENDING|APPROVED|DENIED|QUERIED`
- destination (`PURCHASE` vs `STORE`)
- notes/evidence/urgent

### `RequisitionItem`
- line item: requisition + product + quantity
- unique `(requisition, product)`

### `RequisitionApproval`
- audit trail of approval decisions and notes

---

## Purchase models (`supplychain/models/purchase.py`)

### `PurchaseOrder`
- optional one-to-one link to requisition
- supplier, creator, status
- status: `PENDING_COO|APPROVED|DENIED|QUERIED`

Business rule: supplier must match requisition supplier when linked.

### `PurchaseOrderItem`
- product, quantity, unit_cost, computed line total

### `PurchaseOrderApproval`
- approval audit rows for PO decisions

---

## Receiving models (`supplychain/models/receiving.py`)

### `Receiving`
- linked to PO
- lifecycle status (`PENDING`, `UNDER_REVIEW`, `PENDING_COO`, `REVIWED`, `DENIED`)
- entry/review/COO audit fields
- optional supplier invoice upload

Constraint: one receiving per PO.

### `ReceivingItem`
- per-PO-line actual quantity + accounting flags/notes

### `InvoiceLineApproval`
- optional line-level accounting decision trail

---

## Payment + inventory models

### `Payment`
- one-to-one with PO
- status: `PENDING|PROCESSED|CANCELLED`
- method fields, notes, proof, actor timestamps

Constraint: one payment per PO.

### `StockTransaction`
- signed inventory movement events (`RECEIVE/ISSUE/ADJUST_IN/ADJUST_OUT`)
- tracks source type + source id for idempotent posting

Constraint: unique per `(transaction_type, source_type, source_id, product)`.

### `LowStockAlert`
- alert snapshot with threshold + acknowledgment/resolution state

---

## Relationship meaning (what to remember)
- Requisition = demand request.
- PurchaseOrder = external buy action for approved purchase demand.
- Receiving = what actually arrived, reviewed before payment.
- Payment = finance completion step.
- StockTransaction = real inventory truth; on-hand is computed from these rows.

> Think of workflow models as the “business story”, and transaction/audit models as the “evidence trail”.
