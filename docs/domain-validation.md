# Domain validation

P1-09 closes the Phase 1 domain-rule baseline. Rules live in `DomainStore`, not only in HTTP
handlers, so the manual API and any future authorized ingestion channel share the same safeguards.

## Validation matrix

| Area | Enforced rule | Verification |
|---|---|---|
| Hierarchy | Foreign keys reject orphan records and referenced records cannot be deleted | Persistence and HTTP conflict tests |
| Project scope | Tasks, deliverables, meetings, and action items cannot cross project boundaries | Create/update rollback tests |
| Task completion | `done` requires a non-blank completion note or an existing work log | Service and endpoint tests |
| Incremental work | Start is guarded; work logs require an in-progress task, positive minutes, evidence, and timezone-aware start | Lifecycle and input tests |
| Deliverable review | `in_review` requires non-blank acceptance criteria and evidence URL | Service and endpoint tests |
| Action disposition | Only a captured action creates one task; accepted requires a task; dismissed cannot retain one | Relationship and terminal-state tests |
| Capture triage | Input text is non-blank, dismissal has a reason, and a capture is triaged once | Service and endpoint tests |
| Immutability | Capture history cannot be generically rewritten and work logs are append-only | Service tests |
| Daily views | Morning Brief and Evening Close use stable ranking and workspace-local calendar dates | Timezone boundary tests |
| Transactions | Failed cross-project mutations roll back without leaving partial state | Rollback tests |
| API errors | Missing records map to 404, relationship conflicts to 409, and domain rejection to 422 | API tests |
| Migrations | A clean database supports `upgrade → downgrade → upgrade` | CI migration job |

## Continuous validation

GitHub Actions runs on every push and pull request using Python 3.12. The required checks are:

```bash
ruff check .
pytest
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

All fixtures remain synthetic. The suite does not connect to WhatsApp, calendars, Google Drive,
an LLM provider, or customer systems.

## Change policy

A domain-rule change is complete only when its service enforcement, API behavior when applicable,
automated test, and documentation change together. Schema changes additionally require a reversible
migration.
