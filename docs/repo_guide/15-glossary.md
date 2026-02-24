# 15 — Glossary

- **Requisition**: Internal request for goods/services before procurement action.
- **Destination**: Whether requisition is for external purchase or internal store issue.
- **Purchase Order (PO)**: Supplier-facing order document linked to requisition context.
- **Receiving**: Recorded evidence of what was physically delivered for a PO.
- **Payment**: Finance record that a PO has been processed/settled.
- **StockTransaction**: Atomic event that changes stock up/down.
- **LowStockAlert**: Warning record when computed on-hand drops below threshold.
- **OrganizationMembership**: User role assignment inside an organization.

## What’s next for beginners
1. Run the app locally and create one requisition.
2. Follow it through approval to PO, receiving, and payment pages.
3. Inspect created rows in Django admin.
4. Read the related view and model classes side-by-side.

## Where in code
- Domain object exports: `supplychain_test/supplychain/models/__init__.py::__all__`
- Timeline building helpers: `supplychain_test/supplychain/utils.py::build_workitem_timeline_for_po`
