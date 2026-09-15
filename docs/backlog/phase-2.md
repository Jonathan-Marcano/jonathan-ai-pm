# Phase 2 backlog — Calendar and shared-document context

## Goal

Add trusted scheduling and document context to the Phase 1 daily loop while external systems remain
authoritative. Integrations begin read-only, retain stable source identity, minimize copied content,
and never create external changes.

## Prioritized backlog

| ID | Priority | Story | Acceptance summary |
|---|---:|---|---|
| P2-01 | Must | Establish integration contracts and sync policy | **Done** — provider-neutral, read-only calendar and document contracts enforce stable source keys, timezone-aware UTC values, minimal metadata, and explicit no-write capabilities |
| P2-02 | Must | Persist external identities and synchronization runs | **Done** — meetings and deliverables retain stable provider identities while sync runs store bounded windows, outcome counts, lifecycle state, and redacted errors without credentials |
| P2-03 | Must | Synchronize Microsoft 365 calendars read-only | **Done** — the Microsoft Graph `calendarView` adapter retrieves bounded UTC windows with delegated `Calendars.ReadBasic`, safe pagination, multiple calendar scopes, and no write operation |
| P2-04 | Must | Reconcile calendar events idempotently | **Done** — repeated windows update one meeting, duplicate provider items are skipped, explicit cancellations are applied, and missing events are flagged without deleting operational records |
| P2-05 | Must | Associate imported meetings with projects | **Done** — unmatched events enter an idempotent review queue; explicit user decisions create scoped, reusable mappings without content-based guessing |
| P2-06 | Could | Link Google Drive artifacts | **Deferred** — deliverables already support optional manual `drive_url` references; advanced Drive identity is not required for the PM workflow |
| P2-07 | Could | Refresh Drive metadata | **Deferred with P2-06** — automatic file metadata refresh is unnecessary while documents remain managed separately |
| P2-08 | Should | Support Google Calendar read-only | Personal calendar events use the same contracts, boundaries, and deduplication rules |
| P2-09 | Should | Prepare meetings | **Done** — a deterministic dated view combines every scheduled meeting with its client, project health, open actions, project tasks, deadlines, blockers, and optional manual artifact links |
| P2-10 | Should | Review completed meetings | **Done** — a catch-up queue lists past unreviewed meetings; one explicit, audited transaction closes the meeting as either `actions_captured` or `no_follow_up` and optionally creates validated action items while preserving its source reference |
| P2-11 | Must | Enforce integration permissions and retention | **Done** — startup, adapter, and reconciliation checks reject unapproved or write-enabled permissions; configurable retention removes only expired completed history and resolved reviews; explicit disconnection removes provider links while preserving operational records and anonymizing retained run scopes |
| P2-12 | Should | Expose synchronization status | Manual sync and status endpoints report bounded, auditable outcomes and safe retry information |

## Delivery slices

### Slice A — Safe synchronization foundation

P2-01 through P2-05: contracts, persistence, Microsoft 365 read-only import, deduplication, and
project association.

P2-01 through P2-05 are complete. Slice A is closed.

### Slice B — Shared document context

P2-06 and P2-07 are deferred. Documents continue to be created and managed outside Jonathan AI PM;
the existing optional `drive_url` field is sufficient for manual references.

### Slice C — Daily-loop context

P2-08 through P2-12: optional Google Calendar, meeting preparation/review, permission controls,
and synchronization visibility.

P2-09 through P2-11 are complete. P2-12 synchronization status and manual operation is next;
optional P2-08 remains non-blocking.

## Definition of done

- Provider scopes are documented and technically constrained to read-only behavior.
- Sync windows are bounded and all supplied timestamps include a timezone.
- External identity, provider, and last synchronization state are traceable.
- Repeating a sync does not create duplicate operational records.
- Provider failures preserve existing operational data and produce redacted audit information.
- External deletions do not automatically delete Drive documents or accepted project records.
- Tests use fictional adapters and fixtures; CI never calls customer systems.
- Documentation changes with every integration behavior change.

## Explicitly deferred

- Calendar writes, invitations, responses, or event deletion.
- Copying Google Drive document bodies into the operational datastore.
- Automatic project association based on confidential event content.
- WhatsApp connectivity, notifications, and outbound actions.
- LLM classification, summarization, translation, or autonomous changes.
- Multi-user enterprise permissions.
