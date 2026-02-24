# 04 — Data Model ERD

```mermaid
erDiagram
  Organization ||--o{ OrganizationMembership : has
  User ||--o{ OrganizationMembership : joins

  UnitOfMeasure ||--o{ Product : used_by
  Product }o--o{ Category : categorized_as
  Product }o--o{ Supplier : vendor_links
  Product }o--o{ User : assigned_users

  Destination ||--o{ Requisition : routes
  Supplier ||--o{ Requisition : requested_from
  Supplier_destination_sub_category ||--o{ Requisition : optional_subtype
  User ||--o{ Requisition : requester
  Requisition ||--o{ RequisitionItem : has
  Product ||--o{ RequisitionItem : requested_product
  Requisition ||--o{ RequisitionApproval : approval_log
  User ||--o{ RequisitionApproval : approver

  Requisition o|--|| PurchaseOrder : may_create
  Supplier ||--o{ PurchaseOrder : ordered_from
  User ||--o{ PurchaseOrder : created_by
  PurchaseOrder ||--o{ PurchaseOrderItem : has
  Product ||--o{ PurchaseOrderItem : ordered_product
  PurchaseOrder ||--o{ PurchaseOrderApproval : approval_log
  User ||--o{ PurchaseOrderApproval : approver

  PurchaseOrder ||--o{ Receiving : receives
  User ||--o{ Receiving : received_by
  User ||--o{ Receiving : reviewed_by
  User ||--o{ Receiving : sent_to_coo_by
  User ||--o{ Receiving : coo_decision_by
  Receiving ||--o{ ReceivingItem : has
  PurchaseOrderItem ||--o{ ReceivingItem : actuals_for
  ReceivingItem ||--o{ InvoiceLineApproval : line_decisions
  User ||--o{ InvoiceLineApproval : accountant

  PurchaseOrder ||--|| Payment : one_payment
  User ||--o{ Payment : created_by
  User ||--o{ Payment : processed_by

  Product ||--o{ StockTransaction : movement
  User ||--o{ StockTransaction : actor
  Product ||--o{ LowStockAlert : alerts
  User ||--o{ LowStockAlert : acknowledged_by
  User ||--|| Profile : phone_profile
```

## Constraints and indexes highlights
- Unique membership: `(user, organization)`.
- Product uniqueness: `(Lower(name), uom)` via `uniq_product_sku` constraint name.
- RequisitionItem uniqueness: `(requisition, product)`.
- One payment per PO and one receiving per PO unique constraints.
- Stock idempotency: unique `(transaction_type, source_type, source_id, product)`.
