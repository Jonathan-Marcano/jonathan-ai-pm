# Local data protection

P1-13 establishes safeguards for the single-user local deployment. It is not a replacement for
full-disk encryption, operating-system access controls, or an enterprise secrets manager.

## Implemented safeguards

- Local SQLite files and their parent data directory receive owner-only permissions (`0600` and
  `0700`) where the operating system supports POSIX modes.
- `.env`, local databases, private data directories, backup directories, and snapshot patterns
  are excluded from Git.
- A logging filter redacts authorization values, cookies, passwords, secrets, tokens, API keys,
  and bearer credentials from configured application and Uvicorn handlers.
- `faroflow backup` writes a versioned JSON snapshot under `backups/` by default, with
  private permissions and no implicit overwrite.
- `faroflow backup --path PATH --force` is required to replace an existing backup.

Snapshots and the audit table can still contain customer names, tasks, notes, and evidence. Keep
the device encrypted, restrict account access, and store off-device copies only in an approved
private location.

## Backup and recovery

Create a backup after meaningful data changes and before upgrades:

```bash
uv run faroflow backup
```

Recovery uses the validated snapshot import endpoint and requires an empty datastore. Test
recovery periodically; a backup that has never been restored is not yet verified.

## Deletion behavior

Resource deletion is hard deletion, subject to relational safeguards:

- required references prevent deletion and return a conflict;
- optional references follow their documented `SET NULL` behavior;
- translations must be deleted before their source record;
- the immutable audit history retains before/after values, including deletion evidence.

Deleting an operational record is therefore not complete erasure. Full local erasure requires
stopping the application and deleting the SQLite database plus every exported snapshot using
operating-system-approved secure procedures. No bulk-erasure API is provided in Phase 1.
