# 04 — Data Model ERD

This section gives you two views:
1. A **Mermaid ERD** (for tools that support it).
2. A **plain-English relationship map** (for first-glance understanding).

---

## ERD (Mermaid)

```mermaid
erDiagram
  ORG ||--o{ ORG_MEMBERSHIP : has
  USER ||--o{ ORG_MEMBERSHIP : belongs_to

  UOM ||--o{ PRODUCT : unit_for
  PRODUCT }o--o{ CATEGORY : tagged_with
  PRODUCT }o--o{ SUPPLIER : vendor_link
  PRODUCT }o--o{ USER : assigned_to

  DESTINATION ||--o{ REQUISITION : routes
  SUPPLIER ||--o{ REQUISITION : optional_supplier
  SUPPLIER_SUBCATEGORY ||--o{ REQUISITION : optional_subcategory
  USER ||--o{ REQUISITION : requester
  REQUISITION ||--o{ REQUISITION_ITEM : has
  PRODUCT ||--o{ REQUISITION_ITEM : requested
  REQUISITION ||--o{ REQUISITION_APPROVAL : audited_by
  USER ||--o{ REQUISITION_APPROVAL : actor

  REQUISITION o|--|| PURCHASE_ORDER : may_create
  SUPPLIER ||--o{ PURCHASE_ORDER : supplier
  USER ||--o{ PURCHASE_ORDER : created_by
  PURCHASE_ORDER ||--o{ PURCHASE_ORDER_ITEM : has
  PRODUCT ||--o{ PURCHASE_ORDER_ITEM : ordered
  PURCHASE_ORDER ||--o{ PURCHASE_ORDER_APPROVAL : audited_by
  USER ||--o{ PURCHASE_ORDER_APPROVAL : actor

  PURCHASE_ORDER ||--o{ RECEIVING : has
  RECEIVING ||--o{ RECEIVING_ITEM : has
  PURCHASE_ORDER_ITEM ||--o{ RECEIVING_ITEM : references
  RECEIVING_ITEM ||--o{ INVOICE_LINE_APPROVAL : has
  USER ||--o{ INVOICE_LINE_APPROVAL : accountant

  PURCHASE_ORDER ||--|| PAYMENT : one_to_one
  USER ||--o{ PAYMENT : created_by
  USER ||--o{ PAYMENT : processed_by

  PRODUCT ||--o{ STOCK_TXN : movements
  USER ||--o{ STOCK_TXN : created_by
  PRODUCT ||--o{ LOW_STOCK_ALERT : triggers
  USER ||--o{ LOW_STOCK_ALERT : acknowledged_by

  USER ||--|| PROFILE : has
```

---

## Relationship map (quick human read)

```text
Organization
  └─< OrganizationMembership >─ User

Product master data
  UOM ──< Product >── Category
                 └── Supplier (vendors)
                 └── User (assigned users)

Procurement chain
  Requisition ──< RequisitionItem
      └──< RequisitionApproval
      └──(0..1) PurchaseOrder ──< PurchaseOrderItem
                                 └──< PurchaseOrderApproval
                                 └──(1) Payment
                                 └──(1) Receiving ──< ReceivingItem
                                                     └──< InvoiceLineApproval

Inventory chain
  Product ──< StockTransaction
  Product ──< LowStockAlert
```

---

## Constraint highlights
- Unique membership per user/org.
- Unique requisition line per product per requisition.
- Unique payment per PO.
- Unique receiving per PO.
- Unique stock transaction per `(type, source_type, source_id, product)` for idempotency.

> Gotcha: Mermaid ER rendering can vary by Markdown engine. If your preview breaks, rely on the relationship map above (same logic, no parser dependency).
