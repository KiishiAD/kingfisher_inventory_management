# 13 — Testing and Quality

## What tests exist
- Accounts onboarding and organization context tests.
- Model tests for master data, requisition, purchase, receiving, payment, inventory.
- View tests focused on requisition paths.

## How to run tests
```bash
cd supplychain_test
python manage.py test
```

If settings require env vars, export them before running.

## What these tests cover
- Model constraints and field behavior.
- Status transitions and key business rules.
- View permission and form handling basics.

## What is still missing (recommended next tests)
1. End-to-end PO -> receiving -> payment integration tests.
2. Bulk upload error-path tests with mixed valid/invalid rows.
3. Permission matrix tests per role across all major views.

## Where in code
- Accounts tests: `supplychain_test/accounts/tests.py::AccountOnboardingTests`
- Model test helpers: `supplychain_test/supplychain/tests/models/helpers.py::make_product`
- Inventory model tests: `supplychain_test/supplychain/tests/models/test_inventory.py::StockAndAlertsModelTests`
- Requisition view tests: `supplychain_test/supplychain/tests/views/test_requisition_views.py::RequisitionViewsTestCase`
