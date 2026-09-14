# Phase 1 backlog — Manual-first MVP

## Goal

Deliver a usable single-user workflow from manual capture to Morning Brief and Evening Close, backed by a persistent domain model and measurable work logs.

## Prioritized backlog

| ID | Priority | Story | Acceptance summary |
|---|---:|---|---|
| P1-01 | Must | Select the Phase 1 stack and record the decision | **Done** — ADR 0002 covers runtime, database, API, testing, migration, and local setup |
| P1-02 | Must | Persist the core hierarchy | **Done** — CRUD, HTTP endpoints, filters, and relational constraints exist |
| P1-03 | Must | Manage meetings and action items | **Done** — actions retain meeting source and create or link one task transactionally |
| P1-04 | Must | Capture work into one inbox | **Done** — manual capture requires only text; context is optional until triage |
| P1-05 | Must | Triage every capture | **Done** — task/action/reference/dismissed dispositions retain timestamp, note, and output links |
| P1-06 | Must | Generate a Morning Brief | **Done** — dated local view covers meetings, deadlines, top-three focus, blockers, opportunities, and project risk |
| P1-07 | Must | Record incremental work | **Done** — guarded start/resume, append-only minutes and evidence history, and evidence-backed completion are available through the API |
| P1-08 | Must | Run Evening Close | **Done** — a dated, timezone-aware reconciliation covers completed work, minutes, captures, actions, unfinished tasks, blockers, touched deliverables/projects, and tomorrow's first action |
| P1-09 | Must | Validate domain rules | **Done** — the rule matrix covers relationships, lifecycle guards, evidence, immutability, timezones, transactions, and HTTP errors; CI runs on every push and pull request |
| P1-10 | Should | Summarize workload and progress | **Done** — one timezone-aware report aggregates task states, overdue work, completion, deliverable states, and filtered work-log minutes at every hierarchy level |
| P1-11 | Should | Import/export a portable snapshot | **Done** — versioned JSON export and graph-validated, atomic empty-store import preserve every entity and audit event |
| P1-12 | Should | Add basic audit history | **Done** — immutable events retain actor, timestamp, action, entity, and field-level before/after values in the originating transaction |
| P1-13 | Should | Protect local data | **Done** — local database and backup files receive private permissions, sensitive log values are redacted, backup overwrite is explicit, and deletion behavior is documented |
| P1-14 | Could | Support multilingual display fields | **Done** — versioned manual translations support multiple languages per display field without replacing source text and are included in snapshots and audit history |

## Suggested delivery slices

### Slice A — Reliable records

P1-01, P1-02, P1-03, P1-09, and migrations.

Current increment: stack decision, migrations, core CRUD, meeting/action-item persistence, guarded
domain rules, rollback coverage, and continuous validation are complete.

### Slice B — Daily loop

P1-04 through P1-08 with a minimal interface.

Current increment: P1-04 through P1-08 are complete through the HTTP API. The manual daily loop is
now complete; workload and progress summaries continue in P1-10.

### Slice C — Measurement and resilience

P1-10 through P1-13, automated tests, backups, and operational documentation.

Current increment: P1-10 through P1-14 are complete with dashboard-ready rollups, portable
snapshots, transactional audit history, local-data safeguards, and manual translations. Phase 1
is complete.

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
