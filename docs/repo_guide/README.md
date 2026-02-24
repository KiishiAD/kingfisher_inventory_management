# Repository Guide (Kingfisher Inventory Management)

Welcome! This guide explains the whole Django codebase from “what is this app?” to “how does a payment get processed?”.

## Start here
1. **[00-quickstart.md](00-quickstart.md)** — run the project locally in minutes.
2. **[01-architecture-overview.md](01-architecture-overview.md)** — big picture architecture + request flow.
3. **[02-repo-tour.md](02-repo-tour.md)** — where files live.
4. **[03-domain-model.md](03-domain-model.md)** + **[04-data-model-erd.md](04-data-model-erd.md)** — business entities and relationships.

## Security, roles, and workflow docs
- [05-auth-and-permissions.md](05-auth-and-permissions.md)
- [06-core-workflows.md](06-core-workflows.md)

## App-by-app deep dives
- [07-django-apps/accounts.md](07-django-apps/accounts.md)
- [07-django-apps/supplychain.md](07-django-apps/supplychain.md)

## UI, operations, infra
- [08-templates-and-frontend.md](08-templates-and-frontend.md)
- [09-admin-and-operations.md](09-admin-and-operations.md)
- [10-settings-and-environments.md](10-settings-and-environments.md)
- [11-deployment-and-infra.md](11-deployment-and-infra.md)
- [12-background-jobs.md](12-background-jobs.md)
- [13-testing-and-quality.md](13-testing-and-quality.md)
- [14-troubleshooting.md](14-troubleshooting.md)
- [15-glossary.md](15-glossary.md)

## Reading mode (important)
- Most key chapters now include plain-English, step-by-step explanations first.
- Visuals are included as text diagrams, with Mermaid only as optional extra where useful.
- If your previewer cannot render Mermaid, you will still get complete explanations.

## Coverage checklist
- ✅ All Django apps documented.
- ✅ All models and relationships mapped (including constraints).
- ✅ URL → view → form/model/template flows explained.
- ✅ Auth, templates, admin, settings, deploy, tests covered.

> Tip: If you are new to Django, read this set in numeric order. It is intentionally layered from beginner to advanced.
