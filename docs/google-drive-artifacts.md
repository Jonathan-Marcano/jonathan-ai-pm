# Google Drive artifacts

P2-06 and P2-07 connect one Google Drive file to a deliverable and refresh its metadata without
ever copying the document body into the operational datastore.

## Read-only boundary

The Drive adapter (`integrations/google_drive.py`) uses the delegated scope
`https://www.googleapis.com/auth/drive.metadata.readonly` and declares the same read-only
capabilities as every Phase 2 provider. It fetches only `id, name, webViewLink, mimeType,
modifiedTime, version` for one file. It performs no writes and downloads no content.

Tenant authorization is not configured yet. `POST /api/v1/integrations/drive/refresh` returns
HTTP 503 with `Drive integration is not configured` until credentials are supplied.

## Linking a file

`POST /api/v1/deliverables/{deliverable_id}/drive-link` with:

```json
{
  "source_system": "google-drive",
  "external_id": "1abC2dEf3GhI",
  "name": "Project plan.pdf",
  "web_url": "https://drive.google.com/drive/folders/...",
  "mime_type": "application/pdf"
}
```

The deliverable's `drive_url` is kept in sync with the link's `web_url`. A source key already
linked to another deliverable is rejected (HTTP 422). `DELETE
/api/v1/deliverables/{deliverable_id}/drive-link` removes the link; the external file is
unaffected.

## Refreshing metadata

`reconcile_drive_files(session, adapter=..., external_ids=[...])` refreshes name, URL, MIME type,
version marker (`version` mapped to the identity version), and modification time for already-linked
deliverables:

- unchanged metadata reports `unchanged` on the document sync run;
- changed metadata updates the same identity row and the deliverable `drive_url`;
- repeated refreshes are idempotent and never duplicate rows;
- unknown or mismatched file ids are skipped with a redacted `sync_run_errors` entry;
- a failed provider read keeps existing deliverable data.

`GET /api/v1/integrations/drive-links` lists the links with deliverable context, and `POST
/api/v1/integrations/drive/refresh` triggers a run once authorization is available.

## Safety notes

- Content is never copied; only link metadata is persisted.
- The external file is never modified, renamed, or deleted by this integration.
- Errors are redacted before persistence, and no credentials are stored.
- Unlinking a deliverable never changes the Drive file.