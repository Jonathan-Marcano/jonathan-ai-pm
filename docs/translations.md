# Manual translations

P1-14 stores optional multilingual display text without changing the canonical source record.
No LLM or external translation provider is called.

## Supported sources

| Entity | Original field |
|---|---|
| Project | `name` |
| Deliverable | `title` |
| Task | `title` |
| Meeting | `title` |
| Action item | `title` |
| Capture | `text` |

A source field can have multiple translations, but only one per language. Language values use
BCP 47-style codes such as `en`, `es`, or `pt-BR`.

## API

- `POST /api/v1/translations` adds a manual translation.
- `GET /api/v1/translations` filters by entity, field, or language.
- `GET /api/v1/translations/{id}` returns one translation.
- `PATCH /api/v1/translations/{id}` changes translated text only.
- `DELETE /api/v1/translations/{id}` removes it.

The source entity must exist and the requested field must match its canonical display field.
Deleting a source that still has translations is rejected. Translation changes are audited and
snapshot version `1.1` includes them. Import remains compatible with version `1.0`, which
contains no translations.
