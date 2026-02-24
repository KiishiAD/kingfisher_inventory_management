# 13 — Testing and Quality

## Test structure
- `accounts/tests.py`: onboarding + dashboard org context tests.
- `supplychain/tests/models/*`: model constraints/behavior by domain.
- `supplychain/tests/views/test_requisition_views.py`: requisition view behavior.

## Running tests
```bash
cd supplychain_test
python manage.py test
```

## Coverage themes
- Product and stock transaction invariants.
- Requisition / PO / receiving / payment model rules.
- Timestamp and JSON field behavior.
- Core requisition page permissions and posting paths.
