# Phase 3 backlog — Capture classification and confirmation

## Goal

Turn the manual daily-loop captures into the "project-manager assistant": free text entered at any
moment (during a meeting, on the phone, on the computer) becomes a structured, dated, and confirmed
proposal instead of a manual form. The human always decides; the classification never binds a record
to a project on its own.

The Phase 1 capture queue already stores text, keeps dispositions immutable, and can create
`task`/`deliverable`/`action_item` records through triage. Phase 3 adds a provider-neutral classifier
that fills in the structured suggestion (kind, project/client candidates, priority, due date) with
reasons quoted from the captured text, plus a confirmation step that applies only the explicitly
confirmed proposal.

## Prioritized backlog

| ID | Priority | Story | Acceptance summary |
|---|---|---|---|
| P3-01 | Must | Enrich captures with a pending proposal | Captures retain a read-only suggestion (kind, candidate project/client, priority, due date) with confidence and quoted supporting text; manual triage keeps working unchanged |
| P3-02 | Must | Classify captures through a provider-neutral contract | A `suggest_capture_disposition(text, candidates)` service returns a bounded, validated proposal with confidence and quoted reasons; no credentials live in the repository and unconfigured providers answer HTTP 503 |
| P3-03 | Must | Apply a capture only on explicit confirmation | `POST /api/v1/captures/{id}/apply` creates the operational record exactly from the confirmed proposal, is idempotent, and never binds an unconfirmed capture to a project |
| P3-04 | Should | Preserve the decision trail | Confirmations reference the exact immutable proposal and original text; audit links the capture, the applied record, and the source wording |
| P3-05 | Must | Bound LLM cost and data exposure | Prompt bodies are redacted, per-text caching and token limits prevent repeated charges, and no test ever calls a live model |

## Explicitly deferred

- Translation of operational content into other languages.
- Provider accounts for live models (services answer HTTP 503 until authorized).
- Anything that assigns a record to a project without a human decision.
- Confidential event or document bodies passed to a model.