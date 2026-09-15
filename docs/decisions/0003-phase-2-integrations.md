# ADR 0003: Phase 2 read-only integration boundary

- Status: Accepted
- Date: 2026-09-14

## Context

Phase 2 needs scheduling and shared-document context from vendor systems. Directly coupling domain
services to Microsoft Graph or Google Drive would weaken testing, portability, privacy controls,
and future provider choice.

## Decision

- Vendor clients implement provider-neutral calendar or document adapter protocols.
- Every adapter declares capabilities; Phase 2 accepts read access only and exposes no external
  create, update, or delete operation.
- Microsoft 365 Calendar is the first scheduling provider because the primary work calendars are
  Microsoft 365. Google Calendar remains a later adapter using the same contract.
- Microsoft 365 uses delegated `Calendars.ReadBasic`, the minimum permission that supplies event
  metadata while excluding bodies, attachments, and extensions. `Calendars.ReadWrite` is rejected.
- Google Drive is the shared-document provider and contributes links plus minimal metadata; file
  bodies are not copied.
- Calendar identity is `source_system + calendar_id + external_id`; document identity is
  `source_system + external_id`. Titles and names never participate in deduplication.
- Provider timestamps must include timezone information and are normalized to UTC.
- Credentials remain environment-only and must never enter domain records, logs, snapshots, or
  fixtures.
- Configured permissions are validated against an explicit read-only allowlist at startup and
  checked again at adapter and reconciliation boundaries.
- Disconnecting a provider removes its local identities, association queue, and mappings while
  preserving operational work. Retained synchronization rows lose their source scope.

## Consequences

- Domain synchronization can be developed and tested with fictional adapters before credentials
  are configured.
- Renamed meetings or files update existing records instead of producing duplicates.
- Persisted source metadata and sync-run history are required before a live adapter is enabled.
- Each Microsoft 365 work account authorizes its own delegated session. A non-sensitive local alias
  namespaces each calendar identity without storing account email addresses in fixtures or logs.
- Calendar and Drive writes remain unavailable until a later explicit decision gate.
