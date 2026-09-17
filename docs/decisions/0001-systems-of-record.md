# ADR 0001: Systems of record

- Status: Accepted
- Date: 2026-09-12

## Context

The project needs collaborative documents, versioned code, and operational project state. Treating one tool as the owner of every type of information would create poor collaboration or weak engineering controls.

## Decision

- GitHub owns code, schemas, tests, technical decisions, and versioned engineering documentation.
- Google Drive owns shared documents and management artifacts intended for collaborators.
- A future FaroFlow datastore owns normalized operational state such as task status and work logs.
- External systems remain authoritative for their original events or messages; integrations store references and synchronization metadata.

## Consequences

- Shared Drive documents may summarize repository decisions but should link back to the versioned source.
- Operational records should link to Drive artifacts rather than duplicate sensitive file bodies.
- Synchronization requires explicit conflict and deletion rules before implementation.
- Phase 0 can publish documentation to Drive without implementing a runtime Drive integration.
