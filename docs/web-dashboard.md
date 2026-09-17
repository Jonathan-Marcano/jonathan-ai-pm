# Web dashboard and PWA

`GET /` serves a branded dashboard built from the same FastAPI application.

## Assets

`static/` holds the design kit copied from the delivered brand system:

- `tokens.css` — reusable design tokens (brand palette and Inter font stack).
- `fonts/Inter.ttf` — the Inter typeface under the SIL Open Font License (`fonts/OFL.txt`).
- `favicon.ico` and `brand/` — favicon, app icons (192/512/1024 and claro/oscuro variants),
  and horizontal/vertical/isotipo/typography logos.
- `manifest.webmanifest` — PWA manifest for installability, served at `/manifest.webmanifest`.
- `web/index.html` + `web/app.css` + `web/app.js` — the dashboard itself.

## Dashboard views

The page reads the public API only:

- Morning Brief summary counts and focus tasks
  (`GET /api/v1/briefs/morning`).
- Upcoming meetings (`GET /api/v1/meetings`).
- The P2-05 review queue with project confirmation
  (`GET /api/v1/integrations/meetings/unmatched` +
  `POST /api/v1/integrations/meetings/{id}/project`).
- Project and open task lists (`GET /api/v1/projects`,
  `GET /api/v1/tasks`).

The dashboard is presentational: it performs no writes other than confirming a meeting's
project from the review queue, and all mutations remain available and documented through the
API in [Phase 1 HTTP API](api.md).