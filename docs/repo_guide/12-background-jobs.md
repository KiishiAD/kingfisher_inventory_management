# 12 — Background Jobs

## Findings
No Celery/RQ/cron worker framework is configured in this repository.

## What exists instead
- Synchronous notification sends (email/SMS) from request flow.
- `transaction.on_commit` used in requisition approval to delay notification until DB commit.

## Recommendation
If traffic grows, move notification calls to async workers to avoid user-facing request latency.
