# Integration permissions and retention

Phase 2 integrations are strictly read-only with respect to the provider. Two layers enforce that
contract so a provider can never receive outbound mutations from the application, and operational
records are deliberately retained independent of external changes.

## Read-only enforcement

- **Startup check** — on application startup `assert_registered_providers_read_only()` audits every
  registered adapter class (`microsoft-365`, `google-calendar`, `google-drive`). An adapter that
  declares `create`, `update`, or `delete` capability, or a write-like delegated scope, prevents the
  process from booting instead of failing later.
- **Sync-time check** — before listing or refreshing, `check_read_only_adapter()` validates the
  concrete adapter instance used by a run. A write-capable adapter is recorded as a failed run with
  `code="unsafe_adapter"` and a redacted message; provider methods are never called.
- **Scope markers** — delegated scopes are matched against read/write markers (`write`, `readwrite`,
  `calendar.readwrite`, `drive.file`, `mail.send`, ...) and rejected when present.

Provider errors are redacted before persistence through the shared
[local-data-protection](local-data-protection.md) rules, so authorization headers, tokens, passwords,
and API keys never reach the datastore or logs.

## Retention

- **External deletions never propagate** — a document or calendar entry removed at the provider is
  not deleted from the operational datastore. Re-synchronizing a calendar window marks missing
  events' cancelled status only for unsettled meetings; settled records and Drive links are preserved.
- **Source identity is stable** — external identities and confirmed project mappings are retained
  as audit-grade state. Removing a mapping never touches the meeting or its project.
- **Deliverables with Drive links are protected** — deleting a deliverable that still references an
  external file returns HTTP 422 ("Unlink Drive files before deleting the deliverable"). Unlink the
  file first (`DELETE /api/v1/deliverables/{id}/drive-link`), then delete the deliverable. Unlinking
  never touches the external file.
- **Synchronization history is kept** — sync runs and their redacted errors are the audit trail for
  provider behavior. See [Synchronization status](integration-status.md).

## Disconnection behavior

- Removing provider configuration (no authorization supplied) makes `build_*_adapter()` raise `*NotConfigured`,
  surfaced as HTTP 503. Sync/refresh endpoints report the disabled state without partial writes.
- Disabling or removing a provider does **not** delete imported meetings, linked deliverables,
  identities, mappings, or sync history. Those are independently owned operational records.
- Re-enabling a provider resumes from the bounded windows the operator synchronizes; the application
  never backfills automatically and never rewrites settled records from re-synchronization.