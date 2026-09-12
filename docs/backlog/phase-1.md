# Phase 1 backlog — Manual-first MVP

## Goal

Deliver a usable single-user workflow from manual capture to Morning Brief and Evening Close, backed by a persistent domain model and measurable work logs.

## Prioritized backlog

| ID | Priority | Story | Acceptance summary |
|---|---:|---|---|
| P1-01 | Must | Select the Phase 1 stack and record the decision | ADR covers runtime, database, UI/API, testing, migration, and local setup |
| P1-02 | Must | Persist the core hierarchy | CRUD and constraints exist for workspace/job, client, project, deliverable, and task |
| P1-03 | Must | Manage meetings and action items | Actions retain meeting source and can create or link one task |
| P1-04 | Must | Capture work into one inbox | Manual capture requires only text; project and type can be assigned during triage |
| P1-05 | Must | Triage every capture | Item can become task/action/reference/dismissed; disposition is auditable |
| P1-06 | Must | Generate a Morning Brief | Shows meetings, overdue/due-soon work, priorities, blockers, and deliverable opportunities |
| P1-07 | Must | Record incremental work | User can start/update/complete tasks and add minutes plus evidence summary |
| P1-08 | Must | Run Evening Close | User reconciles today's captures, work, deferrals, blockers, and project changes |
| P1-09 | Must | Validate domain rules | Service and schema tests cover relationships, status transitions, and invalid records |
| P1-10 | Should | Summarize workload and progress | Views aggregate tasks and logged time by workspace, client, project, and deliverable |
| P1-11 | Should | Import/export a portable snapshot | JSON export and validated import support backup and development fixtures |
| P1-12 | Should | Add basic audit history | Creation, status, assignment, and due-date changes retain actor and timestamp |
| P1-13 | Should | Protect local data | Secrets excluded, sensitive logs redacted, backup and deletion behavior documented |
| P1-14 | Could | Support multilingual display fields | Original text is retained and optional translated text can be stored manually |

## Suggested delivery slices

### Slice A — Reliable records

P1-01, P1-02, P1-03, P1-09, and migrations.

### Slice B — Daily loop

P1-04 through P1-08 with a minimal interface.

### Slice C — Measurement and resilience

P1-10 through P1-13, automated tests, backups, and operational documentation.

## Definition of done

- Acceptance criteria have automated or documented verification.
- Schema changes include a migration and rollback note.
- No production credentials or real customer data exist in repository fixtures.
- User-facing status changes are traceable.
- Documentation is updated in the same pull request.
- The daily loop works end to end with only manual inputs.

## Explicitly deferred

- WhatsApp connectivity or message ingestion.
- Google or Microsoft calendar synchronization.
- Live Google Drive API synchronization.
- LLM provider calls and autonomous action-taking.
- Multi-user permissions and enterprise tenancy.
