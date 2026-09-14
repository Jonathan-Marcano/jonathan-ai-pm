# Phase 2 backlog — Calendar and shared-document context

## Goal

Add trusted scheduling and document context to the Phase 1 daily loop while external systems remain
authoritative. Integrations begin read-only, retain stable source identity, minimize copied content,
and never create external changes.

## Prioritized backlog

| ID | Priority | Story | Acceptance summary |
|---|---:|---|---|
| P2-01 | Must | Establish integration contracts and sync policy | **Done** — provider-neutral, read-only calendar and document contracts enforce stable source keys, timezone-aware UTC values, minimal metadata, and explicit no-write capabilities |
| P2-02 | Must | Persist external identities and synchronization runs | Meetings and artifacts retain provider IDs, sync timestamps, outcome counts, and auditable errors without storing credentials |
| P2-03 | Must | Synchronize Microsoft 365 calendars read-only | Configured work calendars import bounded event windows with least-privilege Microsoft Graph permissions |
| P2-04 | Must | Reconcile calendar events idempotently | Repeated syncs update one meeting, avoid duplicates, and treat external cancellations or removals according to documented rules |
| P2-05 | Must | Associate imported meetings with projects | Unmatched events enter a review queue; user-confirmed mappings can be reused without guessing from confidential text |
| P2-06 | Must | Link Google Drive artifacts | Deliverables retain Drive file identity and link metadata without copying document bodies |
| P2-07 | Must | Refresh Drive metadata | Name, URL, MIME type, version marker, and modification time refresh idempotently and preserve the external file |
| P2-08 | Should | Support Google Calendar read-only | Personal calendar events use the same contracts, boundaries, and deduplication rules |
| P2-09 | Should | Prepare meetings | A dated preparation view combines the meeting, linked project, open actions, deadlines, and relevant artifact links |
| P2-10 | Should | Review completed meetings | A post-meeting queue supports manual decisions and action capture while retaining source references |
| P2-11 | Must | Enforce integration permissions and retention | Startup and sync checks reject write scopes, redact provider errors, and document retention/disconnection behavior |
| P2-12 | Should | Expose synchronization status | Manual sync and status endpoints report bounded, auditable outcomes and safe retry information |

## Delivery slices

### Slice A — Safe synchronization foundation

P2-01 through P2-05: contracts, persistence, Microsoft 365 read-only import, deduplication, and
project association.

Current increment: P2-01 is complete. P2-02 is next.

### Slice B — Shared document context

P2-06 and P2-07: Google Drive links and metadata refresh without document-body replication.

### Slice C — Daily-loop context

P2-08 through P2-12: optional Google Calendar, meeting preparation/review, permission controls,
and synchronization visibility.

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
