# 15 — Glossary

- **Requisition**: Internal request for goods/services.
- **Destination**: Requisition target (`PURCHASE` external supplier, `STORE` internal issue).
- **PO (Purchase Order)**: Formal supplier order generated from approved requisition.
- **Receiving**: Goods receipt record tied to PO.
- **Three-way match (loosely)**: PO lines vs received quantities vs invoice evidence.
- **COO approval**: Executive step for PO decisions and receiving exceptions.
- **StockTransaction**: Atomic inventory movement event.
- **LowStockAlert**: Trigger when on-hand < product threshold.
- **OrganizationMembership role**: owner/admin/member authorization within org context.

## What’s next for a beginner
1. Run local app and create one requisition end-to-end.
2. Inspect generated DB rows in admin.
3. Read `supplychain/views/*` side-by-side with templates.
4. Add one tiny test to understand app conventions.
