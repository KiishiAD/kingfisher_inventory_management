# 14 — Troubleshooting

## 1) Login/invite links are wrong
**Symptom:** invite/reset emails point to wrong host.

**Fix:** set `APP_BASE_URL` correctly for your environment.

**Where in code:** `supplychain_test/accounts/views.py::_send_set_password_email`

## 2) Google login fails
**Symptom:** redirect or token exchange errors.

**Fix:** verify client id/secret and callback URL match configured provider values.

**Where in code:** `supplychain_test/accounts/views.py::google_start`, `supplychain_test/accounts/views.py::google_callback`

## 3) Production start crashes early
**Symptom:** runtime errors during boot.

**Fix:** provide required `SECRET_KEY`, `DATABASE_URL`, and S3 variables.

**Where in code:** `supplychain_test/supplychain_test/settings/production.py::SECRET_KEY`, `supplychain_test/supplychain_test/settings/production.py::DATABASE_URL`

## 4) Receiving looks locked
**Symptom:** cannot edit a receiving record.

**Fix:** check status and COO decision fields; finalized records are intentionally immutable.

**Where in code:** `supplychain_test/supplychain/views/receiving_views.py::ReceivingDetailView`

## 5) Inventory totals seem wrong
**Symptom:** on-hand does not match expectation.

**Fix:** verify stock movement signs and source postings.

**Where in code:** `supplychain_test/supplychain/views/inventory_views.py::_signed_case_for_txn_queryset`, `supplychain_test/supplychain/services/inventory.py::record_receiving_as_stock`
