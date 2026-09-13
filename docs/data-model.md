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
| Meeting | Scheduled or completed discussion | `id`, `project_id`, `title`, `starts_at`, `status` |
| Action Item | Commitment or follow-up captured from a meeting | `id`, `meeting_id`, `title`, `status`, `owner` |
| Work Log | Measured effort and progress evidence | `id`, `task_id`, `started_at`, `minutes`, `summary` |
| Capture | Frictionless raw input awaiting triage | `id`, `text`, `status`, `captured_at` |

## Key references

- `task.deliverable_id` is optional: administrative tasks may advance a project without producing a deliverable.
- `task.source_action_item_id` is optional and unique when a task was created from an action item.
- `action_item.task_id` is optional during capture, then required for an accepted work commitment.
- `action_item.deliverable_id` is optional and provides direct impact traceability.
- `deliverable.drive_url` is optional and links the shared artifact without duplicating its contents.
- `capture.task_id` or `capture.action_item_id` records the object created during triage.
- `capture.disposition`, `triaged_at`, and `disposition_note` preserve the triage decision.
- All externally synchronized entities may carry `source_system`, `external_id`, and `last_synced_at`.

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
3. A task can be marked `done` only when its completion note or work log explains the result.
4. A deliverable moves to `in_review` only when its acceptance criteria are addressed and an artifact or evidence link exists.
5. A capture is triaged once; its original text, timestamp, disposition, output link, and note remain recorded.
6. Evening Close reviews all items captured that day and records the disposition of unfinished work.
7. Project health is explicitly confirmed by the user even when the system suggests a value.

## Identifiers and time

- IDs use stable strings with readable prefixes, for example `prj_demo_network_refresh`.
- Dates and timestamps follow ISO 8601.
- Stored timestamps use UTC; display uses the workspace timezone.
- Records include `created_at` and `updated_at` when persisted.

The machine-readable Phase 0 contract is [schemas/domain-model.schema.json](../schemas/domain-model.schema.json). It validates the synthetic aggregate in [data/seed/demo-workspace.json](../data/seed/demo-workspace.json).
