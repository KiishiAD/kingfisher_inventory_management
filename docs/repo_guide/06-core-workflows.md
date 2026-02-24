# 06 — Core Workflows (Step-by-step)

This chapter explains how data actually moves through the system, like an instructor walking a whiteboard.

---

## Workflow 1: Requisition approval flow

## Human explanation
1. Requester creates requisition + line items.
2. Requisition starts as `PENDING`.
3. Approver chooses `APPROVED`, `QUERIED`, or `DENIED`.
4. If approved:
   - For `PURCHASE` destination: system generates a PO.
   - For `STORE` destination: system posts `ISSUE` stock transactions.
5. If queried: requester edits and resubmits back to pending.

## Quick visual
```text
Create requisition -> PENDING -> Approver decision
    APPROVED + PURCHASE -> create PO
    APPROVED + STORE    -> issue stock
    QUERIED             -> requester edits -> PENDING again
    DENIED              -> closed
```

## Where in code
- URLs: `supplychain/urls.py`
- Views: `RequisitionCreateView`, `RequisitionDetailView`, `RequisitionUpdateView`
- Helpers: `generate_po_for_requisition`, `record_store_requisition_issue`

---

## Workflow 2: Purchase order to receiving to payment

## Human explanation
1. Procurement creates PO (or PO comes from approved requisition).
2. COO approves PO.
3. System ensures a receiving record exists for that PO.
4. Store user records actual delivered quantities.
5. Accounting reviews lines; may deny, approve, or escalate to COO.
6. If cleared for payment:
   - pending payment row is created (if missing)
   - stock is posted as `RECEIVE` transactions
7. Finance processes payment and uploads proof.

## Quick visual
```text
PO approved
  -> Receiving exists
  -> Actual quantities entered
  -> Accounting/COO decision
  -> If approved: create/keep pending payment + post RECEIVE stock
  -> Finance marks payment PROCESSED
```

## Where in code
- PO: `PurchaseOrderDetailView`, `generate_receiving_for_purchase_order`
- Receiving: `ReceivingDetailView`
- Inventory posting: `record_receiving_as_stock`
- Payment processing: `PaymentDetailView`

---

## Workflow 3: Bulk product upload

## Human explanation
1. User uploads CSV/XLSX from operations page.
2. System validates required columns and row data.
3. Product is created/updated.
4. System computes current stock and difference to target stock.
5. System posts `ADJUST_IN` or `ADJUST_OUT` transaction.
6. Row-level errors are returned without stopping the whole file.

## Quick visual
```text
Upload file -> validate rows -> upsert product -> compute stock diff -> post adjust txn
```

## Where in code
- View: `ProductBulkUploadView`
- Service: `import_products_df`

---

## Common debugging questions
- “Why no PO created?” → check requisition destination/status.
- “Why no stock change?” → check approval path and transaction uniqueness keys.
- “Why no payment row?” → check receiving reached cleared-for-payment state.
