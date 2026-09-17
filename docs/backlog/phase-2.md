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
| P2-04 | Must | Reconcile calendar events idempotently | **Done** — repeated syncs update one meeting, avoid duplicates, mark cancellations, and never delete operational records |
| P2-05 | Must | Associate imported meetings with projects | **Done** — unmatched imported meetings enter a review queue while confirmed source-key mappings reuse that project on later syncs without reading confidential event content |
| P2-06 | Must | Link Google Drive artifacts | **Done** — deliverables retain read-only Drive file identity and link metadata through the provider-neutral document contract without copying document bodies |
| P2-07 | Must | Refresh Drive metadata | **Done** — name, URL, MIME type, version marker, and modification time refresh idempotently through `reconcile_drive_files` and preserve the external file |
| P2-08 | Should | Support Google Calendar read-only | **Done** — personal calendar events use the same contracts, boundaries, and deduplication rules through a `calendar.readonly` adapter with no write capability |
| P2-09 | Should | Prepare meetings | **Done** — a dated preparation view combines the meeting, its linked project and client, open actions, task and deliverable deadlines, and relevant artifact links without exposing confidential provider content |
| P2-10 | Should | Review completed meetings | **Done** — completed meetings enter a post-meeting review queue; acknowledgment clears the queue while retaining source references (see [Meeting review](../meeting-review.md)) |
| P2-11 | Must | Enforce integration permissions and retention | **Done** — startup and sync checks reject write scopes and capabilities, provider errors are redacted, deliverable deletion requires unlinking Drive files first, and retention/disconnection behavior is documented (see [Integration permissions and retention](../integration-retention.md)) |
| P2-12 | Should | Expose synchronization status | **Done** — manual sync and status endpoints report bounded, auditable outcomes and safe retry information (see [Synchronization status](../integration-status.md)) |

## Delivery slices

### Slice A — Safe synchronization foundation

P2-01 through P2-05: contracts, persistence, Microsoft 365 read-only import, deduplication, and
project association.

Current increment: Slice A (P2-01 through P2-05) is complete. P2-06 is next.

### Slice B — Shared document context

P2-06 and P2-07: Google Drive links and metadata refresh without document-body replication.

Current increment: Slice B (P2-06 and P2-07) is complete. P2-08 is next.

### Slice C — Daily-loop context

P2-08 through P2-12: optional Google Calendar, meeting preparation/review, permission controls,
and synchronization visibility.

Current increment: **Phase 2 is complete** — Google Calendar read-only (P2-08), meeting
preparation (P2-09), meeting review (P2-10), integration permission/retention controls (P2-11), and
synchronization status (P2-12) are Done. Phase 3 (LLM classification, summarization, translation,
confidence/evidence, and cost/data policy) is next.

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
