# 06 — Core Workflows (Step-by-step)

This chapter follows one request from creation to payment and inventory effects.

## Workflow 1: Requisition lifecycle

### Plain-English walkthrough
First, a requester creates a requisition with line items.
Then the requisition waits in `PENDING`.
Then an approver chooses approved, queried, or denied.
Because destination controls downstream behavior, approved requisitions split:
- `PURCHASE` creates a purchase order.
- `STORE` posts stock issue transactions.

### Mermaid
```mermaid
flowchart TD
  CREATE[Requester submits requisition]
  PENDING[Status pending]
  DECIDE{Approver decision}
  APPROVE_PURCHASE[Approved purchase]
  APPROVE_STORE[Approved store]
  QUERY[Queried]
  DENY[Denied]
  CREATE_PO[Generate purchase order]
  ISSUE_STOCK[Create issue stock transactions]
  RESUBMIT[Requester updates and resubmits]

  CREATE --> PENDING --> DECIDE
  DECIDE --> APPROVE_PURCHASE --> CREATE_PO
  DECIDE --> APPROVE_STORE --> ISSUE_STOCK
  DECIDE --> QUERY --> RESUBMIT --> PENDING
  DECIDE --> DENY
```

### Text fallback
```text
Requester submits requisition
  -> status becomes pending
  -> approver decides:
     - approved + purchase: create purchase order
     - approved + store: post issue stock transactions
     - queried: requester edits and resubmits to pending
     - denied: workflow ends
```

### Where in code
- URL routes: `supplychain_test/supplychain/urls.py::urlpatterns`
- Create/update/detail views: `supplychain_test/supplychain/views/requisition_views.py::RequisitionCreateView`, `supplychain_test/supplychain/views/requisition_views.py::RequisitionUpdateView`, `supplychain_test/supplychain/views/requisition_views.py::RequisitionDetailView`
- Side effects: `supplychain_test/supplychain/utils.py::generate_po_for_requisition`, `supplychain_test/supplychain/services/inventory.py::record_store_requisition_issue`

---

## Workflow 2: PO to receiving to payment (flowchart)

### Plain-English walkthrough
First, procurement creates or receives a PO from approved requisition.
Then COO approves the PO.
Then the system ensures receiving lines exist.
Then receiving is recorded and reviewed.
If the review clears payment, stock is posted as receive movements and a pending payment record exists.
Finally finance processes the payment.

### Mermaid
```mermaid
flowchart TD
  PO_CREATED[PO created]
  COO_APPROVAL[COO approves PO]
  RECEIVING_READY[Receiving record exists]
  ENTRY[Store records actual quantities]
  REVIEW[Accounting review]
  COO_REVIEW[COO exception decision if needed]
  CLEAR[Cleared for payment]
  STOCK_POST[Post receive stock transactions]
  PAYMENT_PENDING[Ensure pending payment]
  PAYMENT_DONE[Finance processes payment]

  PO_CREATED --> COO_APPROVAL --> RECEIVING_READY --> ENTRY --> REVIEW
  REVIEW --> COO_REVIEW --> CLEAR
  REVIEW --> CLEAR
  CLEAR --> STOCK_POST
  CLEAR --> PAYMENT_PENDING --> PAYMENT_DONE
```

### Text fallback
```text
PO created -> COO approval -> receiving exists
-> store entry -> accounting review
-> optional COO exception decision
-> if cleared: post receive stock + ensure pending payment
-> finance processes payment
```

### Where in code
- PO decision: `supplychain_test/supplychain/views/purchaseorder_views.py::PurchaseOrderDetailView`
- Receiving orchestration: `supplychain_test/supplychain/views/receiving_views.py::ReceivingDetailView`
- Receiving generation: `supplychain_test/supplychain/utils.py::generate_receiving_for_purchase_order`
- Stock posting: `supplychain_test/supplychain/services/inventory.py::record_receiving_as_stock`
- Payment processing: `supplychain_test/supplychain/views/payments_views.py::PaymentDetailView`

---

## Workflow 3: PO to receiving to payment (sequence)

### Mermaid
```mermaid
sequenceDiagram
  participant PROC as Procurement user
  participant PVIEW as Purchase order view
  participant RVIEW as Receiving view
  participant INV as Inventory service
  participant PAY as Payment view

  PROC->>PVIEW: Approve purchase order path completes
  PVIEW->>RVIEW: Ensure receiving record exists
  PROC->>RVIEW: Enter actual quantities and invoice
  RVIEW->>INV: Post receive stock when cleared
  RVIEW->>PAY: Ensure pending payment
  PROC->>PAY: Process payment with proof
```

### Text fallback
```text
Procurement/approver action
  -> receiving screen has lines to fill
  -> receiving review clears payment
  -> inventory receive transactions are posted
  -> payment is processed
```

## Workflow 4: Bulk product upload

### Plain-English walkthrough
First, user uploads CSV/XLSX.
Then each row is validated.
Then product records are created/updated.
Because stock is event-based, the importer computes difference from current stock and writes adjustment transactions.

### Where in code
- Upload endpoint: `supplychain_test/supplychain/views/product_bulk_upload_views.py::ProductBulkUploadView`
- Import service: `supplychain_test/supplychain/services/uploads/product_bulk_upload.py::import_products_df`
