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
- Google Drive is the shared-document provider and contributes links plus minimal metadata; file
  bodies are not copied.
- Calendar identity is `source_system + calendar_id + external_id`; document identity is
  `source_system + external_id`. Titles and names never participate in deduplication.
- Provider timestamps must include timezone information and are normalized to UTC.
- Credentials remain environment-only and must never enter domain records, logs, snapshots, or
  fixtures.

## Consequences

- Domain synchronization can be developed and tested with fictional adapters before credentials
  are configured.
- Renamed meetings or files update existing records instead of producing duplicates.
- Persisted source metadata and sync-run history are required before a live adapter is enabled.
- Calendar and Drive writes remain unavailable until a later explicit decision gate.
