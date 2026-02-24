# 12 — Background Jobs

## Finding
No Celery worker, RQ worker, or cron scheduler integration is configured in this repository.

## Evidence
- No Celery/RQ app in installed apps or settings modules.
- No worker service in `docker-compose.yml`.
- Workflow side effects run inline inside view/service code.

## What runs instead
- Email and SMS notifications run synchronously.
- Requisition notification dispatch is deferred until commit with `transaction.on_commit`.

## Where in code
- Notification calls from requisition approval: `supplychain_test/supplychain/views/requisition_views.py::RequisitionDetailView`
- Email notifier: `supplychain_test/supplychain/services/notifications/email_notifications.py::notify_requisition_approved_to_all`
- SMS notifier: `supplychain_test/supplychain/services/notifications/sms_notifications.py::notify_requisition_approved_to_all`
- Deferred callback primitive: `supplychain_test/supplychain/views/requisition_views.py::transaction.on_commit`
