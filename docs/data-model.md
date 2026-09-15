# Initial domain model

## Relationship model

```text
Workspace / Job 1 ── * Client 1 ── * Project
Project 1 ── * Deliverable 1 ── * Task
Project 1 ── * Meeting 1 ── * Action Item
Action Item 0..1 ── 1 Task
Action Item 0..1 ── 1 Deliverable
Task 1 ── * Work Log
Capture 1 ── 0..1 Task / Action Item / Project reference
Project / Deliverable / Task / Meeting / Action Item / Capture 1 ── * Translation
Meeting / Deliverable 1 ── * External Identity
Sync Run 1 ── * Sync Run Error
External Identity 0..1 ── * Sync Run Error
```

An action item may create a new task or link to an existing task. It may also point to the deliverable it advances. It must not remain open without one of these dispositions after triage.

## Entities

| Entity | Purpose | Required core fields |
|---|---|---|
| Workspace / Job | Top-level employment or operating context | `id`, `name`, `status`, `timezone` |
| Client | Customer or internal stakeholder group within a workspace | `id`, `workspace_id`, `name`, `status` |
| Project | Time-bounded outcome for a client | `id`, `client_id`, `name`, `status`, `health` |
| Deliverable | Concrete output with acceptance criteria | `id`, `project_id`, `title`, `status`, `due_at` |
| Task | Executable unit of work | `id`, `project_id`, `title`, `status`, `priority` |
| Meeting | Scheduled or completed discussion with an optional explicit review outcome | `id`, `project_id`, `title`, `starts_at`, `status` |
| Action Item | Commitment or follow-up captured from a meeting | `id`, `meeting_id`, `title`, `status`, `owner` |
| Work Log | Measured effort and progress evidence | `id`, `task_id`, `started_at`, `minutes`, `summary` |
| Capture | Frictionless raw input awaiting triage | `id`, `text`, `status`, `captured_at` |
| Translation | Optional manual display translation that preserves its source | `id`, `entity_kind`, `entity_id`, `field_name`, `language`, `translated_text` |
| Audit Event | Immutable record of a committed domain change | `id`, `entity_kind`, `entity_id`, `action`, `actor`, `occurred_at`, `changes` |
| External Identity | Stable mapping from one provider resource to a meeting or deliverable | `id`, `entity_kind`, `entity_id`, `source_system`, `external_scope`, `external_id`, `last_synced_at` |
| Sync Run | Auditable lifecycle and outcome totals for one bounded provider synchronization | `id`, `source_system`, `resource_kind`, `status`, `started_at`, outcome counts |
| Sync Run Error | Redacted failure evidence associated with a synchronization | `id`, `sync_run_id`, `code`, `message`, `occurred_at` |

## Key references

- `task.deliverable_id` is optional: administrative tasks may advance a project without producing a deliverable.
- `task.source_action_item_id` is optional and unique when a task was created from an action item.
- `action_item.task_id` is optional during capture, then required for an accepted work commitment.
- `action_item.deliverable_id` is optional and provides direct impact traceability.
- `deliverable.drive_url` is optional and links the shared artifact without duplicating its contents.
- `capture.task_id` or `capture.action_item_id` records the object created during triage.
- `capture.disposition`, `triaged_at`, and `disposition_note` preserve the triage decision.
- External identity is separate from operational records and is unique by `source_system`,
  `external_scope`, and `external_id`. The scope is a calendar ID for events and empty for Drive
  files.
- `external_identity.missing_since` records the first successful window in which a linked calendar
  event was not returned. It clears when the event reappears and never deletes the meeting.
- `calendar_import_review` stores the minimum event snapshot required for a human decision and is
  unique by provider, calendar scope, and external event ID. Its lifecycle is `pending`, `resolved`,
  or `dismissed`.
- `calendar_project_mapping` stores an explicit, attributable project decision for the same scoped
  source key. It is reusable by later reconciliations and cannot silently move an imported meeting.
- A reviewed meeting stores `review_decision`, `review_summary`, `reviewed_by`, and `reviewed_at`
  as one complete state. Partial review state is rejected.
- Sync runs retain time windows and aggregate seen, created, updated, unchanged, skipped, and error
  counts. Individual error messages are redacted before persistence.
- A translation targets only the canonical display field: project `name`; deliverable, task,
  meeting, or action-item `title`; or capture `text`.
- The original display value is never replaced. A target field can have one translation per
  language, using a BCP 47-style language code such as `en` or `pt-BR`.

## Status vocabularies

| Entity | Allowed status |
|---|---|
| Workspace, Client | `active`, `paused`, `archived` |
| Project | `planned`, `active`, `paused`, `completed`, `cancelled` |
| Deliverable | `planned`, `in_progress`, `in_review`, `accepted`, `blocked`, `cancelled` |
| Task | `inbox`, `ready`, `in_progress`, `blocked`, `done`, `cancelled` |
| Meeting | `scheduled`, `completed`, `cancelled` |
| Action Item | `captured`, `accepted`, `done`, `dismissed` |
| Capture | `inbox`, `triaged` with disposition `task`, `action`, `reference`, or `dismissed` |

Project `health` is one of `unknown`, `on_track`, `at_risk`, or `off_track`; it is separate from lifecycle status.

## Lifecycle rules

1. Raw input begins as a capture requiring only text and stays in the inbox until triaged.
2. An accepted action item links to exactly one task; informational notes are dismissed with a reason.
3. A task starts from `ready` or resumes from `blocked`; work logs can be added only while it is
   `in_progress`.
4. Starting work activates a planned project and moves a linked planned deliverable to
   `in_progress`.
5. A task can be marked `done` only when its completion note or work log explains the result.
6. A deliverable moves to `in_review` only when its acceptance criteria are addressed and an artifact or evidence link exists.
7. A capture is triaged once; its original text, timestamp, disposition, output link, and note remain recorded.
8. Evening Close reviews daily outcomes and every older capture still in the inbox; corrections
   update the source records rather than creating a second copy of operational state.
9. Project health is explicitly confirmed by the user even when the system suggests a value.
10. Captures are immutable after creation except through triage, and work logs are append-only.
11. Accepted action items require a linked task; dismissed action items cannot retain one.
12. Operational timestamps supplied for meetings and work logs must include a timezone.
13. A past, non-cancelled meeting is reviewed once as `actions_captured` or `no_follow_up`; any
    new actions and the meeting closure commit atomically.

## Identifiers and time

- IDs use stable strings with readable prefixes, for example `prj_demo_network_refresh`.
- Dates and timestamps follow ISO 8601.
- Stored timestamps use UTC; display uses the workspace timezone.
- Records include `created_at` and `updated_at` when persisted.

The machine-readable Phase 0 contract is [schemas/domain-model.schema.json](../schemas/domain-model.schema.json). It validates the synthetic aggregate in [data/seed/demo-workspace.json](../data/seed/demo-workspace.json).
