# Receiving Workflow Architecture — Issue Drafts

Source PRD: `docs/prd-receiving-workflow-architecture.md`

These drafts are ready to publish to `KiishiAD/kingfisher_inventory_management` with label `needs-triage` once the GitHub token has Issues read/write access.

---

## 1. Persist Receiving workflow history for existing audit timeline

Labels: `needs-triage`

## What to build

Introduce first-class Receiving workflow history for the existing audit timeline. This slice should create persisted history for Receiving records, backfill simple historical events from existing audit fields, register the history read-only in admin, and make Receiving detail/PDF history prefer persisted events with derived fallback.

## Acceptance criteria

- [ ] Receiving workflow history is persisted with controlled action type, label, details, nullable actor, actor display snapshot, occurred-at timestamp, idempotency key, and hidden metadata.
- [ ] Historical Receiving records are backfilled idempotently from existing audit fields with simple visible events only.
- [ ] Receiving history is registered read-only in Django admin for inspection/debugging.
- [ ] Receiving history/timeline read logic lives in a Receiving-focused reader/helper rather than general utilities.
- [ ] Receiving detail page and PDF prefer persisted workflow history and fall back to derived audit-field events when persisted history is missing.
- [ ] Fallback source is internally detectable for tests/debugging without showing a confusing client-facing legacy marker.
- [ ] Tests cover model/history ordering, backfill idempotency, admin read-only behavior where practical, persisted rendering, and fallback rendering.

## Blocked by

None - can start immediately

---

## 2. Route normal accounting clearance through Receiving workflow service

Labels: `needs-triage`

## What to build

Move the non-COO accounting approval path into named Receiving workflow service actions. The existing business timing must remain unchanged: when Receiving clears for payment, inventory is posted and pending payment is prepared. This slice should prove the core workflow architecture on the shortest clearance path.

## Acceptance criteria

- [ ] Normal accounting approval delegates to the Receiving workflow service instead of directly mutating Receiving status/audit fields in the view.
- [ ] The workflow action reloads and locks the Receiving row inside an atomic transaction before enforcing invariants or applying side effects.
- [ ] Clearing for payment preserves current status values and current timing for stock posting and pending payment preparation.
- [ ] Inventory posting is idempotent per Receiving and cannot duplicate stock movements on retry.
- [ ] Payment preparation is idempotent per Receiving and cannot create duplicate pending payments on retry.
- [ ] The clearance workflow writes a persisted history event with structured inventory/payment side-effect summaries in hidden metadata.
- [ ] The workflow returns a structured result including business summaries, idempotent/no-op status, and the created or reused history event.
- [ ] Service tests and view integration tests cover normal clearance, idempotent retry behavior, and history/side-effect outcomes.
- [ ] Normal-path browser/manual E2E verification confirms detail history, PDF history, exact-once inventory posting, and payment preparation after clearance only.

## Blocked by

- Issue 1: Persist Receiving workflow history for existing audit timeline

---

## 3. Route COO-required approval path through Receiving workflow service

Labels: `needs-triage`

## What to build

Move send-to-COO and COO approval into the Receiving workflow service while preserving current status behavior. COO approval should clear for payment, post inventory once, prepare payment once, and write persisted workflow history with side-effect summaries.

## Acceptance criteria

- [ ] Pure Receiving business facts such as COO-required and pending-COO decision are shared by views and service without duplicating view-only logic.
- [ ] Sending to COO delegates to the workflow service, records sent-to-COO audit fields/history, and preserves current status semantics.
- [ ] COO approval delegates to the workflow service and clears for payment using the same stock/payment timing as the current codebase.
- [ ] COO approval writes persisted workflow history with grouped inventory/payment side-effect summaries under the approval/clearance event.
- [ ] Retries of COO approval do not duplicate history, stock postings, or pending payments.
- [ ] Service tests cover send-to-COO, COO approval, eligibility rules, and idempotent retries.
- [ ] View integration tests cover COO-required flow delegation and existing route/form behavior.
- [ ] COO-required browser/manual E2E verification confirms detail history, PDF history, exact-once inventory posting, and payment preparation after clearance only.

## Blocked by

- Issue 1: Persist Receiving workflow history for existing audit timeline
- Issue 2: Route normal accounting clearance through Receiving workflow service

---

## 4. Add Receiving denial and invalid-state workflow handling

Labels: `needs-triage`

## What to build

Move accounting denial and COO denial into named Receiving workflow service actions, and define how invalid business states are handled. Denials should be client-facing workflow history events; validation failures and unauthorized attempts should remain outside workflow history.

## Acceptance criteria

- [ ] Accounting denial delegates to the Receiving workflow service and writes a client-facing denial history event.
- [ ] COO denial delegates to the Receiving workflow service and writes a client-facing denial history event.
- [ ] Denial behavior preserves existing status values and user-facing route/form behavior.
- [ ] Validation failures, malformed submissions, unauthorized attempts, and blocked invalid actions are not persisted as client-facing workflow history.
- [ ] The service raises domain exceptions for invalid business states such as COO decision before eligibility or attempts to clear denied Receivings.
- [ ] Views/forms continue to handle expected input problems and convert service errors to appropriate messages/errors.
- [ ] Service tests cover accounting denial, COO denial, invalid states, and absence of history for validation failures.
- [ ] View integration tests cover denial flows and invalid-state handling.

## Blocked by

- Issue 1: Persist Receiving workflow history for existing audit timeline
- Issue 2: Route normal accounting clearance through Receiving workflow service
- Issue 3: Route COO-required approval path through Receiving workflow service

---

## 5. Harden Receiving workflow history rendering and PDF coverage

Labels: `needs-triage`

## What to build

Polish the final Receiving workflow history presentation across detail page and PDF. This slice should ensure normalized client-facing labels, grouped clearance side-effect summaries, hidden metadata exclusion, actor display snapshots, fallback behavior, ordering, and PDF smoke coverage where feasible.

## Acceptance criteria

- [ ] Client-facing workflow history labels are normalized slightly while preserving current meaning and style.
- [ ] Clearance events render concise inventory/payment side-effect summaries as grouped details rather than noisy separate client-facing rows.
- [ ] Hidden metadata such as stock transaction IDs and payment IDs is not exposed in UI or PDF output.
- [ ] Actor display snapshot is used for stable client-facing history display while actor FK remains available internally.
- [ ] History renders in chronological order by occurred-at time with deterministic tie-breaking.
- [ ] Persisted history and derived fallback both produce coherent detail-page history.
- [ ] Receiving PDF includes workflow history and grouped clearance side-effect summaries.
- [ ] Automated PDF content smoke coverage is added if reliable extraction is feasible; otherwise the implementation documents why manual PDF verification is used for this slice.
- [ ] Tests cover history reader ordering, fallback, grouping, metadata hiding, and PDF behavior where feasible.

## Blocked by

- Issue 1: Persist Receiving workflow history for existing audit timeline
- Issue 2: Route normal accounting clearance through Receiving workflow service
- Issue 3: Route COO-required approval path through Receiving workflow service
- Issue 4: Add Receiving denial and invalid-state workflow handling

---

## 6. Run final Receiving workflow regression and E2E acceptance pass

Labels: `needs-triage`

## What to build

Perform the final acceptance pass for the Receiving workflow architecture slice. This issue verifies automated tests and browser/manual E2E flows for normal and COO-required clearance, with no video or screen recording unless explicitly requested.

## Acceptance criteria

- [ ] Full automated test suite runs and the exact result is reported.
- [ ] Normal Receiving clearance browser/manual E2E flow passes from product/requisition/PO through receiving, inventory, payment, detail history, and PDF history.
- [ ] COO-required Receiving clearance browser/manual E2E flow passes from product/requisition/PO through receiving, COO approval, inventory, payment, detail history, and PDF history.
- [ ] Both E2E paths confirm inventory posts exactly once per Receiving.
- [ ] Both E2E paths confirm payment is prepared only after Receiving is cleared for payment.
- [ ] Both E2E paths confirm existing routes/forms/navigation remain usable.
- [ ] Any failure is captured with enough evidence to explain and fix it, then the E2E path is repeated.
- [ ] No video or screen recording is required unless explicitly requested.

## Blocked by

- Issue 1: Persist Receiving workflow history for existing audit timeline
- Issue 2: Route normal accounting clearance through Receiving workflow service
- Issue 3: Route COO-required approval path through Receiving workflow service
- Issue 4: Add Receiving denial and invalid-state workflow handling
- Issue 5: Harden Receiving workflow history rendering and PDF coverage
