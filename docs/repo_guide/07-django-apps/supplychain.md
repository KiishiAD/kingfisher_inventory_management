# Supplychain App

## What this app is for
The `supplychain` app is the business engine of this repository.
It handles requisitions, purchase approvals, receiving, payments, and inventory tracking.

## Who uses it
- Requesters
- Procurement officers
- Approvers (including COO-level steps)
- Accounting/finance
- Store/warehouse users

## Step-by-step business story
First, requester creates requisition.
Then approver decision triggers PO creation or stock issue.
Then PO approval enables receiving.
Then receiving review enables payment.
Finally inventory and payment records give audit trace.

## URL sections
- Dashboard
- Requisitions
- Purchase orders
- Receiving
- Inventory
- Payments
- Product bulk upload

## Core model groups
- Master data: product/supplier/category/UOM
- Procurement: requisition + purchase order + approvals
- Fulfillment/finance: receiving + payment
- Inventory: stock transactions + low stock alerts

## Services and utility modules
- Inventory posting service
- Notifications (email/SMS)
- Product upload importer
- Timeline builders and orchestration helpers

## Where in code
- URL map: `supplychain_test/supplychain/urls.py::urlpatterns`
- Dashboard: `supplychain_test/supplychain/views/dashboard_views.py::DashboardView`
- Requisition flow: `supplychain_test/supplychain/views/requisition_views.py::RequisitionDetailView`
- PO flow: `supplychain_test/supplychain/views/purchaseorder_views.py::PurchaseOrderDetailView`
- Receiving flow: `supplychain_test/supplychain/views/receiving_views.py::ReceivingDetailView`
- Payment flow: `supplychain_test/supplychain/views/payments_views.py::PaymentDetailView`
- Bulk upload: `supplychain_test/supplychain/services/uploads/product_bulk_upload.py::import_products_df`
- Inventory services: `supplychain_test/supplychain/services/inventory.py::record_receiving_as_stock`
- Model exports: `supplychain_test/supplychain/models/__init__.py::__all__`
