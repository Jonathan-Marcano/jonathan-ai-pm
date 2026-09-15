# Roadmap

## Phase 0 — Foundation

Status: complete when repository and Drive publication are verified.

- Define vision, product boundaries, and success indicators.
- Establish GitHub and Google Drive responsibilities.
- Define the initial domain model and lifecycle rules.
- Document the daily operating workflow.
- Add safe configuration and synthetic seed data.
- Prepare an actionable Phase 1 backlog.

## Phase 1 — Manual-first MVP

Status: complete.

- Implement persistence and domain validation.
- Provide manual CRUD for the core hierarchy.
- Implement inbox capture and action-item triage.
- Generate Morning Brief from internal records.
- Support task progress, work logs, and Evening Close.
- Provide project and effort summaries.
- Add automated tests, migrations, and basic observability.

No external messaging or calendar write actions are required for Phase 1.

## Phase 2 — Calendar and shared-document context

Status: in progress; P2-01 through P2-05 complete.

- Read-only calendar synchronization with deduplication.
- Google Drive artifact linking and metadata refresh.
- Meeting preparation and post-meeting review flows.
- Permission, retention, and audit controls.

## Phase 3 — Assisted capture and AI

- Optional LLM classification, summarization, and translation.
- User-confirmed extraction of action items from selected content.
- Confidence indicators, source citations, and correction feedback.
- Explicit cost, retention, and customer-data policies.

## Phase 4 — Messaging channels and proactive operation

- Approved WhatsApp capture path using a supported business integration.
- Notifications for briefs, overdue items, and close reminders.
- Controlled outbound actions with previews and confirmation.
- Reliability monitoring, retry policies, and integration audit trail.

## Decision gates

Each integration advances only after scope, permissions, data handling, failure behavior, and user confirmation rules are documented and tested.
