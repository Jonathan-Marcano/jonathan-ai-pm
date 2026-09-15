# Architecture

## Phase 0 logical architecture

The architecture is implementation-neutral so Phase 1 can choose a small, reversible technology stack.

```text
Interaction layer
  Morning Brief | Quick Capture | Evening Close | Reviews
        |
Application services
  Briefing | Capture/Triage | Planning | Progress | Metrics
        |
Domain model
  Workspaces/Jobs | Clients | Projects | Deliverables | Tasks
  Meetings | Action Items | Work Logs | Translations
        |
Ports/adapters
  Local DB | Google Drive | Calendars | WhatsApp | LLM provider
```

## Component responsibilities

| Component | Responsibility | Phase |
|---|---|---|
| Domain model | Entity identity, relationships, status and validation rules | 0 |
| Seed fixtures | Repeatable synthetic dataset for development and tests | 0 |
| Capture service | Normalize manual inputs and preserve their source | 1 |
| Planning service | Rank tasks and assemble a daily plan | 1 |
| Briefing service | Generate Morning Brief from internal records | 1 |
| Close service | Reconcile the day and update statuses/work logs | 1 |
| Metrics service | Aggregate effort, throughput, aging, and risk | 1 |
| Google Drive adapter | Link shared working documents and deliverables | 2 |
| Calendar adapters | Import meetings and scheduling context | 2 |
| WhatsApp adapter | Capture explicitly forwarded or authorized messages | Later |
| LLM adapter | Summarize, classify, translate, and propose actions | Later |

## Boundaries

- Domain logic must not depend directly on a vendor API.
- Integration code must use adapters behind stable application interfaces.
- External identities are stored separately and retain `source_system`, provider scope,
  `external_id`, version metadata, and `last_synced_at` for idempotent synchronization.
- Every synchronization has a durable run record with bounded windows, outcome totals, and
  separately queryable redacted errors; credentials and provider payload bodies are excluded.
- Microsoft 365 calendar retrieval uses delegated `Calendars.ReadBasic`, `calendarView`, forced UTC
  responses, bounded page counts, and validated `graph.microsoft.com` continuation links.
- A link to a Drive artifact is preferred over copying sensitive document content into the operational database.
- Automated extraction creates a proposed record; user confirmation changes it to an accepted commitment.
- All timestamps are stored in UTC and rendered using `APP_TIMEZONE`.

## Data ownership

| Information | System of record |
|---|---|
| Code, schemas, versioned technical decisions | GitHub |
| Shared project documents and management artifacts | Google Drive |
| Operational task state and work logs | Jonathan AI PM datastore (from Phase 1) |
| Meeting schedule | Connected calendar, once enabled |
| Original message | Source channel, once enabled |

See [ADR 0001](decisions/0001-systems-of-record.md) for the decision rationale.

## Security and privacy baseline

- Credentials exist only in environment variables or an approved secret store.
- Logs must redact tokens, customer identifiers, and message bodies by default.
- Integrations request the minimum scopes needed and begin read-only where possible.
- Seed and test data must remain fictional.
- Deleting a local reference must not delete the underlying Drive document unless explicitly requested.
- Future AI processing must define retention, provider, and customer-data rules before activation.

## Deployment direction

Phase 1 should begin as a single-user modular application with a relational datastore. A modular monolith keeps deployment and observability simple while the domain stabilizes. Separate services are only justified by measured scale, security isolation, or independent lifecycle needs.
