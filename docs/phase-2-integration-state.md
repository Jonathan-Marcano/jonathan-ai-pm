# Phase 2 integration state

P2-02 adds durable provider identity and synchronization history without connecting to a live
provider. The integration layer remains read-only and contains no OAuth or API credentials.

## External identities

`external_identities` maps one provider resource to an existing meeting or deliverable. Calendar
identity uses `source_system + external_scope + external_id`, where `external_scope` is the calendar
ID. Document identity uses an empty scope and the provider file ID.

Calling `upsert_identity` with the same source key refreshes version, link, modification, and sync
metadata on the same row and clears `missing_since`. A source key cannot silently move to a
different operational entity.

## Calendar association state

P2-05 adds `calendar_import_reviews` for unmatched event snapshots and
`calendar_project_mappings` for explicit, attributable project decisions. Both use the same scoped
calendar source key as external identities. Reconciliation may reuse a confirmed mapping, but it
never derives one from event content. See
[Calendar project associations](calendar-project-associations.md).

## Synchronization runs

Each execution starts as a `running` row in `sync_runs`. It records the provider, resource kind,
optional source scope, bounded UTC window, start/completion timestamps, and these outcome counts:

- seen;
- created;
- updated;
- unchanged;
- skipped;
- errors.

Completed runs are `succeeded`, `partial`, or `failed`. Classified outcome counts must add up to the
seen count, negative counts are rejected, and a completed run cannot be modified through the state
service.

## Error safety

`sync_run_errors` keeps a safe error code, redacted message, timestamp, and optional identity link.
Authorization headers, bearer values, passwords, tokens, secrets, cookies, and API keys are removed
before commit. Provider credentials and raw response payloads have no columns in these tables.

## Current boundary

P2-11 provides local retention and disconnection operations for this state. It still does not
store OAuth credentials, copy Drive document bodies, expose synchronization endpoints, or delete
operational meetings and tasks. See
[Integration security, retention, and disconnection](integration-security-retention.md).
