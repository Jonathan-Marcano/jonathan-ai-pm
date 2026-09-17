# Synchronization status

Every calendar sync and Drive refresh records a synchronization run with bounded outcome counts and
redacted errors. The status endpoints expose that history read-only for monitoring and safe retries.

## Runs

- `GET /api/v1/integrations/sync-runs` — list runs, newest first, with the usual `limit`/`offset`
  pagination and optional filters `source_system`, `resource_kind` (`calendar`|`document`), and
  `status` (`running`|`succeeded`|`partial`|`failed`).
- `GET /api/v1/integrations/sync-runs/{id}` — one run with its source key, bounded window
  (`window_starts_at`, `window_ends_at`), lifecycle timestamps, and outcome counts. Unknown runs
  return HTTP 404.
- `GET /api/v1/integrations/sync-runs/{id}/errors` — that run's recorded errors chronologically,
  with `code`, redacted `message`, and optional linked `external_identity_id`. Unknown runs return
  HTTP 404.

Run messages are redacted at write time using the shared
[local-data-protection](local-data-protection.md) rules; credentials never appear in responses.

## Safe retry

- `POST /api/v1/integrations/sync-runs/{id}/retry` — re-runs the same bounded window captured on the
  original run, so a retry cannot expand the reconciliation scope. For a `document` run it re-refreshes
  the previously synced identities. Returns HTTP 404 for unknown runs, HTTP 422 when a calendar run
  has no saved window, and HTTP 503 until the provider authorization is configured.

Retrying reuses the same idempotent reconciliation rules: re-syncing never duplicates meetings or
links and never reopens settled records. See [Integration state](phase-2-integration-state.md) and
[Integration permissions and retention](integration-retention.md).