# 06 — Core Workflows

This is the “follow the ball” chapter.

---

## Workflow A: Requisition lifecycle

### Mermaid
```mermaid
flowchart TD
    A[Requester submits requisition]
    B[Status PENDING]
    C{Approver decision}
    D[APPROVED PURCHASE]
    E[APPROVED STORE]
    F[QUERIED]
    G[DENIED]
    H[Generate Purchase Order]
    I[Create ISSUE stock transactions]
    J[Requester updates and resubmits]

    A --> B
    B --> C
    C --> D --> H
    C --> E --> I
    C --> F --> J --> B
    C --> G
```

### ASCII fallback
```text
Requester -> PENDING -> Approver decides
   |- APPROVED + PURCHASE -> create PO
   |- APPROVED + STORE    -> issue stock
   |- QUERIED             -> requester edits -> back to PENDING
   |- DENIED              -> stop
```

### What this means in practice
1. User submits requisition and line items.
2. Approver action writes `RequisitionApproval` history.
3. If approved:
   - `PURCHASE` destination triggers PO generation.
   - `STORE` destination triggers inventory issue transactions.

---

## Workflow B: Purchase Order to Receiving to Payment

### Mermaid
```mermaid
sequenceDiagram
    participant COO as COO Approver
    participant POV as PurchaseOrderDetailView
    participant UTIL as Utils
    participant RV as ReceivingDetailView
    participant INV as InventoryService
    participant PAY as Payment

    COO->>POV: Approve PO
    POV->>UTIL: generate_receiving_for_purchase_order
    RV->>RV: Store records actual received quantities
    RV->>RV: Accounting reviews and decides
    alt cleared for payment
      RV->>PAY: get_or_create pending payment
      RV->>INV: record_receiving_as_stock
    end
```

### ASCII fallback
```text
COO approves PO
   -> receiving record exists
   -> store enters actual quantities
   -> accounting/COO decision
   -> if approved: payment becomes actionable + stock RECEIVE posted
```

---

## Workflow C: Bulk product upload

### Mermaid
```mermaid
flowchart LR
    FILE[CSV or XLSX] --> VIEW[ProductBulkUploadView]
    VIEW --> IMPORT[import_products_df]
    IMPORT --> PROD[Create or update products]
    IMPORT --> TXN[Create ADJUST_IN or ADJUST_OUT transactions]
    TXN --> STOCK[Updated computed stock]
```

### Quick notes
- Upload uses one `upload_id` batch reference.
- Each row is validated and errors are reported per row.
- Stock is set by **difference** from current on-hand.

---

## Why these diagrams matter
- They mirror where status transitions and side-effects happen.
- They make it easy to debug “why wasn’t stock/payment created?”.
