# PRD: Receiving Workflow Architecture Deepening

## Problem Statement

Kingfisher’s Receiving workflow is a central operational and financial checkpoint: goods are received against purchase orders, accounting reviews quantities and variances, COO approval may be required, inventory is posted, payment is prepared, and users need a trustworthy client-facing audit trail of what happened.

Today, this workflow works, but too much business behavior is spread across views, utility functions, model fields, and side-effect helpers. State transitions, audit field updates, stock posting, payment preparation, and timeline presentation are not owned by one coherent Receiving workflow module. This makes the system harder to reason about, harder to test, and vulnerable to architectural drift as more Receiving behavior is added.

The highest-risk invariants are:

1. Stock must not be posted twice for the same Receiving.
2. The audit trail must remain trustworthy and client-facing.
3. Payment must not be prepared before Receiving is cleared for payment.
4. Workflow state changes should not bypass the intended business rules.

The current client-facing audit trail is derived from existing audit fields. It is useful, but it is not first-class, append-only workflow history. The refactor should evolve the existing audit trail into a persisted Receiving workflow history while preserving the simple client-facing presentation users already understand.

## Solution

Build a full vertical Receiving architecture slice that keeps current business timing and user-facing workflow semantics, but moves Receiving state changes and side effects behind a clear Receiving workflow service.

The solution will introduce:

- Named Receiving workflow actions instead of generic transition logic.
- A Receiving-specific workflow history model for append-only, client-facing business events.
- Runtime workflow history creation centralized inside the Receiving workflow service.
- A hybrid backfill and fallback strategy so existing records continue to show a timeline.
- Thin inventory and payment seams called by the Receiving workflow service.
- Idempotency for workflow history, inventory posting, and payment preparation.
- Clear service result objects and side-effect summary objects for tests, views, history metadata, and PDF rendering.
- Detail page and PDF rendering based on persisted workflow history, with derived fallback where history is missing.
- Automated tests across service, views, migration/backfill, and PDF smoke coverage where feasible.
- Browser/manual E2E verification for the normal path and COO-required path.

The refactor should preserve current URLs, forms, status values, route structure, and core user-facing workflow wording unless a change is directly necessary for the new workflow history presentation.

## User Stories

1. As a receiving user, I want to record goods received against a purchase order, so that the system captures what physically arrived.
2. As a receiving user, I want the Receiving workflow to keep existing forms and navigation, so that I do not need to learn a new process.
3. As an accounting user, I want to review Receiving items and quantities, so that I can clear accurate receipts and flag exceptions.
4. As an accounting user, I want Receiving item edits to be saved before workflow decisions are applied, so that review decisions use the latest line-item data.
5. As an accounting user, I want normal Receiving approvals to clear the Receiving for payment when COO approval is not required, so that the existing business timing remains unchanged.
6. As an accounting user, I want oversupply or variance rules to determine whether COO approval is required, so that high-risk Receivings get additional review.
7. As an accounting user, I want to send a Receiving to COO without changing the current status semantics, so that existing workflow behavior remains stable.
8. As an accounting user, I want to deny a Receiving during review, so that invalid or unacceptable Receivings can be closed with an auditable decision.
9. As a COO user, I want to approve a Receiving that was sent to me, so that it can be cleared for payment.
10. As a COO user, I want to deny a Receiving that was sent to me, so that exceptions can be rejected with an auditable decision.
11. As a user viewing a Receiving, I want to see a simple timeline of business events, so that I understand what happened without seeing technical internals.
12. As a user viewing a Receiving, I want audit history labels to be clear and human-readable, so that the timeline reads like a business narrative.
13. As a user viewing a Receiving, I want denial decisions to appear in history, so that the audit trail explains why the workflow stopped.
14. As a user viewing a Receiving, I want validation failures and unauthorized attempts excluded from the client-facing history, so that the audit trail stays focused on successful business actions.
15. As a user viewing a Receiving, I want inventory and payment side effects summarized under the clearance event, so that I can see the business outcome without a noisy timeline.
16. As a user viewing a Receiving PDF, I want the same workflow history to appear in the PDF, so that exported records match the detail page.
17. As a manager, I want the workflow history to preserve actor display names, so that historical audit entries remain readable even if user accounts change.
18. As a manager, I want old Receivings to continue showing timeline history, so that historical records do not look blank after the refactor.
19. As an admin, I want read-only access to Receiving workflow history in admin, so that I can inspect audit entries without rewriting them.
20. As a developer, I want all state-changing Receiving views to delegate to a workflow service, so that business rules are enforced in one place.
21. As a developer, I want Receiving workflow actions to have explicit names, so that each action’s inputs, side effects, and tests are clear.
22. As a developer, I want the service to own transaction boundaries, so that status updates, history writes, inventory posting, and payment preparation commit or roll back together.
23. As a developer, I want workflow actions to reload and lock Receiving records internally, so that state-changing operations use fresh database state without forcing a broad app-wide API style change.
24. As a developer, I want pure Receiving facts to live as side-effect-free model helpers, so that views and services can share business logic without duplication.
25. As a developer, I want the workflow service to raise domain errors for invalid business states, so that invariant violations are explicit and testable.
26. As a developer, I want expected form/input problems handled in views and forms, so that the service stays focused on business workflow rules.
27. As a developer, I want structured workflow results, so that views and tests can inspect outcomes without parsing messages or hidden metadata.
28. As a developer, I want typed side-effect summaries, so that inventory and payment seams return predictable business summaries.
29. As a developer, I want inventory posting to be idempotent per Receiving, so that retries cannot duplicate stock movements.
30. As a developer, I want payment preparation to be idempotent per Receiving, so that retries cannot create duplicate pending payments.
31. As a developer, I want workflow history events to use idempotency keys with database uniqueness, so that retries cannot duplicate audit rows.
32. As a developer, I want old derived timeline behavior available as fallback, so that edge cases continue to render useful history.
33. As a developer, I want the fallback source to be internally detectable, so that tests and debugging can distinguish persisted history from derived history without confusing clients.
34. As a developer, I want history ordered by business occurrence time, so that backfilled events display in the right chronological order.
35. As a developer, I want the history event to store both controlled action type and stable label/details strings, so that the event is both queryable and client-facing.
36. As a developer, I want new workflow behavior proven by direct service tests, so that the architecture is not only exercised through views.
37. As a developer, I want view integration tests to prove Receiving state-changing views use the workflow path, so that direct mutations do not quietly return.
38. As a developer, I want migration/backfill tests, so that old audit fields are safely converted into simple visible history.
39. As a developer, I want PDF verification, so that workflow history is not only correct on the web page.
40. As a developer, I want browser/manual E2E verification without mandatory video recording, so that the real workflow is proven without unnecessary recording overhead.

## Implementation Decisions

- The first implementation slice is a full vertical Receiving slice, not a broad app-wide refactor.
- Receiving workflow side effects should be owned by a Receiving workflow service.
- The service should expose named business actions rather than a generic transition engine.
- The service should be implemented as service-layer code, not as fat model methods.
- Pure, side-effect-free Receiving business facts may live on Receiving or ReceivingItem model helpers.
- Pure model helpers may query related data when needed, as long as they do not write or trigger side effects.
- State-changing workflow actions should accept existing model instances for compatibility with the codebase’s current calling style.
- State-changing workflow actions must reload and lock the Receiving row inside a transaction before enforcing invariants or applying side effects.
- Views and forms remain responsible for validation and saving form/formset data.
- After form/formset saves, the workflow service reloads the Receiving and required related data before variance checks, history writes, inventory posting, or payment preparation.
- All Receiving state-changing views must call the workflow service instead of directly mutating Receiving status/audit fields.
- Enforcement against bypasses is moderate: service-level invariants, tests, and documentation/comments. No model save guards, signals, or database triggers are required.
- Runtime Receiving workflow history creation is centralized inside the Receiving workflow service.
- Inventory and payment seams return business summaries and metadata to the Receiving workflow service; they do not write Receiving workflow history directly.
- Add a Receiving-specific workflow history model rather than a generic workflow history framework.
- Workflow history should include a Receiving relationship, controlled action type, label, details, nullable actor, actor display snapshot, occurrence timestamp, idempotency key, and hidden metadata.
- Workflow history should store both business occurrence time and normal row creation/update timestamps when consistent with existing model patterns.
- Workflow history should order by occurrence time, then deterministic row identity.
- Workflow history labels and details are stored per event as stable client-facing strings.
- Actor should be nullable to support backfill, legacy records, and system events.
- Actor display should be snapshotted for stable client-facing audit display.
- Workflow history should use idempotency keys with database uniqueness scoped to Receiving, action type, and idempotency key.
- Runtime retries should return an existing/idempotent result instead of creating duplicate history events.
- Inventory posting idempotency applies per Receiving.
- Payment preparation idempotency applies per Receiving.
- Stock posting remains timed exactly as in the current codebase: only when Receiving is cleared for payment.
- Payment preparation remains timed exactly as in the current codebase: only when Receiving is cleared for payment.
- Clearing for payment occurs through accounting approval when COO approval is not required, or through COO approval when COO approval is required.
- Sending to COO remains status-preserving and does not start using the existing pending-COO status as part of this slice.
- Current database-visible Receiving status values and constants must be preserved exactly.
- Current user-facing routes, forms, and navigation should be preserved.
- Current user-facing labels/messages should be preserved unless directly necessary for workflow history presentation.
- Workflow history labels may be slightly normalized for clarity while preserving current meaning.
- Approval/clearance is the primary workflow event; inventory and payment side effects appear as structured summaries under that event.
- Side-effect summaries for clearance should be stored in hidden event metadata and rendered as concise client-facing detail text.
- Hidden metadata may include side-effect identifiers and business summaries, but UI/PDF should show only the business summaries/details.
- Accounting denial and COO denial are successful workflow decisions and must appear in client-facing history.
- Validation failures, malformed submissions, unauthorized attempts, and blocked invalid actions should not be persisted in client-facing workflow history.
- Expected input/form problems should remain handled by forms/views.
- Invalid business actions or invalid workflow states should raise domain exceptions from the workflow service.
- Successful and idempotent workflow actions should return structured result objects.
- Workflow results should include business summaries, idempotent/no-op status, and the created or reused workflow history event reference.
- Generic side-effect summary contracts should live in a small shared service types module.
- Receiving-specific result objects and domain exceptions should live with the Receiving workflow service.
- Receiving timeline/history read logic should move out of the general utilities area into a Receiving-focused history reader/helper.
- The history reader should prefer persisted workflow history and fall back to derived audit-field timeline events when persisted history is missing.
- Derived fallback should remain in place for resilience, not only as a temporary migration bridge.
- Derived fallback should not show a client-facing “legacy” marker, but may expose internal source metadata for debugging/tests/admin use.
- Register workflow history in admin as read-only for inspection/debugging.
- Treat workflow history as append-only by application convention. No model-level update/delete guards or database triggers are required in this slice.
- Add a Django data migration that idempotently backfills simple workflow history rows from existing Receiving audit fields.
- Historical backfill should prioritize visible continuity, not rich side-effect metadata reconstruction.
- Rich side-effect metadata is required only for new workflow actions after the refactor.

## Testing Decisions

Good tests for this PRD should verify external behavior and domain invariants, not incidental implementation details. The core proof should be that Receiving workflow actions produce correct state, history, side effects, and idempotent retry behavior through the same paths production uses.

Required testing layers:

- Direct workflow service tests for each named Receiving workflow action.
- View integration tests for state-changing Receiving views.
- Migration/backfill tests for historical workflow history creation.
- History reader tests for persisted history, fallback behavior, grouping/presentation source, and ordering.
- Inventory seam tests proving stock posting is idempotent per Receiving.
- Payment seam tests proving payment preparation is idempotent per Receiving.
- Workflow history tests proving idempotency keys prevent duplicate events.
- Domain exception tests for invalid business states.
- PDF smoke/content test if reliable text extraction is feasible in the current test stack.
- Browser/manual E2E verification covering the normal clearance path and the COO-required clearance path.

Service tests should cover, at minimum:

- Recording or representing goods received in the workflow history where applicable.
- Accounting approval that clears directly when COO approval is not required.
- Accounting denial.
- Sending to COO.
- COO approval after send-to-COO.
- COO denial after send-to-COO.
- Invalid COO decision before the Receiving is eligible.
- Invalid attempts to clear denied or otherwise ineligible Receivings.
- Idempotent retries for clearance/history/inventory/payment behavior.
- Side-effect summaries included under clearance events.

View integration tests should prove:

- State-changing Receiving views produce workflow history through the service path.
- Views no longer rely on direct status/audit mutation as the source of truth.
- Existing URLs/forms/navigation remain functional.
- User-facing messages and statuses remain stable unless intentionally adjusted for workflow history.

Migration/backfill tests should prove:

- Existing audit fields produce simple visible history rows.
- Backfill is idempotent.
- Historical events use appropriate occurrence timestamps.
- Historical events preserve actor display when actor data exists.
- Historical events do not attempt to reconstruct rich inventory/payment side-effect metadata.

History/PDF tests should prove:

- Detail page history prefers persisted events.
- Detail page history falls back to derived events when persisted history is missing.
- Fallback source can be detected internally without showing a confusing client-facing marker.
- Workflow history appears in the Receiving PDF.
- If automated PDF text extraction is impractical, the implementation must document why and rely on manual PDF verification for this slice.

Browser/manual E2E verification must cover:

1. Normal Receiving clearance that does not require COO approval.
2. COO-required Receiving clearance.

Each E2E path should verify:

- Detail page workflow history renders correctly.
- PDF workflow history renders correctly.
- Inventory posts exactly once.
- Pending payment is prepared only after clearance.
- Existing routes/forms/navigation remain usable.
- No video or screen recording is required unless explicitly requested.

A lightweight static guard against direct Receiving status mutation in views may be added if useful, but it is optional and not an acceptance requirement.

Performance testing does not require query-count tests. The implementation should avoid obvious N+1 query patterns and use practical related-object loading for history rendering.

## Out of Scope

This PRD explicitly excludes:

- CSV audit-history export.
- Global Receiving status typo cleanup or status migration.
- Broad Inventory architecture rewrite.
- Broad Payment architecture rewrite.
- Requisition workflow refactor.
- Purchase Order workflow refactor.
- Notification redesign.
- Generic approval framework.
- Dashboard or reporting redesign beyond Receiving detail/PDF needs.
- Broad template redesign.
- Broad utility-module cleanup beyond moving/using Receiving timeline/history logic.
- User role/permission redesign beyond enforcing Receiving business invariants inside the service.
- PO-level payment aggregation.
- Supplier-invoice-level payment modeling.
- Inventory adjustment/correction workflows for already-posted Receivings.
- Parent/child workflow history event modeling.
- Generic content-type-based workflow history.
- Persisting validation failures or unauthorized attempts in workflow history.
- Model-level or database-level hard append-only enforcement.
- Mandatory video/screen recording for E2E verification.

## Further Notes

This PRD is intentionally a maximum-payoff architecture slice, but only inside Receiving. The goal is to create one deep, tested module boundary that proves how Kingfisher can evolve safely without refactoring every workflow at once.

The existing behavior around stock posting and payment preparation should be preserved: both happen only when Receiving is cleared for payment. The refactor changes ownership, atomicity, history, and idempotency; it should not change the business timing.

The existing derived audit trail should not be discarded. It should evolve into first-class persisted workflow history, with derived fallback retained for resilience and historical continuity.

The new Receiving workflow service should be the place future developers look first when changing Receiving business behavior. Views should coordinate HTTP/form concerns, permissions, messages, and redirects; the service should enforce Receiving workflow invariants and orchestrate side effects.

The implementation should follow DRY, KISS, and SOLID. Prefer small, explicit service seams and focused model helpers over broad abstractions or a generic workflow engine.
