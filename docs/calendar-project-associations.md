# Calendar project associations

P2-05 adds a human-controlled boundary between external calendar metadata and operational projects.
An event without a known project is not imported as a meeting and is never classified from its
title, attendees, description, client name, or other confidential content.

## Workflow

1. Reconciliation receives a normalized event with no external identity or confirmed mapping.
2. One `calendar_import_review` row is created for its scoped source key. Repeated results refresh
   the same row instead of creating duplicates.
3. The user confirms a real project or dismisses the review item. Both decisions retain the actor
   and time; a confirmed decision also creates one `calendar_project_mapping`.
4. The next reconciliation reuses the mapping and creates the meeting plus external identity under
   the selected project.
5. Later runs update that same meeting idempotently. A changed mapping cannot silently reassign an
   already imported meeting.

The mapping key is:

```text
source_system + external_scope + external_id
```

The calendar scope is part of the key so identical provider event IDs from different work accounts
cannot share a project decision.

## Review states

| State | Meaning |
|---|---|
| `pending` | Waiting for an explicit user decision |
| `resolved` | A project was confirmed and a reusable mapping exists |
| `dismissed` | The user chose not to import the event |

A dismissed item keeps its state when the event reappears, while its safe review metadata and
`last_seen_at` are refreshed. It therefore stays out of the pending queue without being deleted.

## Stored data and safety

The review snapshot contains only the normalized fields already allowed by the read-only calendar
contract: source key, title, start/end, provider status, web link, modification time, and observation
timestamps. Bodies, attendees, attachments, credentials, and raw provider payloads are excluded.

Confirmation requires an existing project plus a non-empty actor. The mapping records
`confirmed_by` and `confirmed_at`. P2-05 is an application service and persistence layer only; it
does not enable live tenant credentials, calendar writes, invitations, responses, or deletions.
