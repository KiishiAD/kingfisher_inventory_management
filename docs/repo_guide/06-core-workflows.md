# 06 — Core Workflows

## 1) Requisition lifecycle
```mermaid
flowchart TD
  A[Requester creates requisition] --> B[Status PENDING]
  B --> C{Approver decision}
  C -->|APPROVED + PURCHASE| D[Generate PurchaseOrder]
  C -->|APPROVED + STORE| E[Create ISSUE StockTransaction]
  C -->|QUERIED| F[Requester updates & resubmits]
  C -->|DENIED| G[Closed]
  F --> B
```

Path: `supplychain/urls.py` → `Requisition*View` → `RequisitionForm + RequisitionItemFormSet` → models.

## 2) Purchase → Receiving → Payment
```mermaid
sequenceDiagram
  participant PO as PurchaseOrderDetailView
  participant U as utils.generate_receiving_for_purchase_order
  participant R as ReceivingDetailView
  participant I as inventory service
  participant P as Payment

  PO->>PO: COO approves PO
  PO->>U: create Receiving + ReceivingItems
  R->>R: store entry records actual qty + invoice
  R->>R: accounting review/COO review
  alt approved for payment
    R->>P: get_or_create pending payment
    R->>I: record_receiving_as_stock()
  end
```

## 3) Bulk product upload workflow
- Upload CSV/XLSX in `ProductBulkUploadView`.
- `import_products_df` validates columns, upserts products, assigns categories/vendors/users.
- Calculates stock diff and writes ADJUST_IN/ADJUST_OUT transactions with shared `upload_id`.
