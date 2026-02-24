# 09 — Admin and Operations

## What Django admin is used for here
Admin is the back-office control panel for data maintenance and auditing.

## How staff should use it
First, maintain master data (products, suppliers, categories, UOM).
Then inspect workflow records (requisition approvals, PO approvals, receiving, payments).
Then audit inventory events and low-stock alerts.

## Operational pages outside admin
- Product bulk upload UI
- Team invite page

## Notification operations
The app can notify users by email and SMS from service modules.

## Where in code
- Admin registrations: `supplychain_test/supplychain/admin.py::ProductAdmin` (and sibling admin classes)
- Admin route: `supplychain_test/supplychain_test/urls.py::urlpatterns`
- Product bulk upload view: `supplychain_test/supplychain/views/product_bulk_upload_views.py::ProductBulkUploadView`
- Email notifications: `supplychain_test/supplychain/services/notifications/email_notifications.py::notify_requisition_approved_to_all`
- SMS notifications: `supplychain_test/supplychain/services/notifications/sms_notifications.py::notify_requisition_approved_to_all`
