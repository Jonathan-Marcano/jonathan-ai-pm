# Phase 4 backlog — Messaging channels and proactive operation

## Goal

Turn FaroFlow from a place the user visits into the channel the user already lives in: captures
arrive from a supported messaging application, and the loop proactively notifies (briefs, overdue
items, close reminders) through controlled outbound messages. The human always stays in control:
captures enter the inbox as proposals, outbound messages require preview and confirmation, and no
data leaves the workspace without an explicit, auditable decision.

Phase 3 already turns free text into a structured, confirmed proposal. Phase 4 transports that same
loop over messaging: an inbound capture path feeds the inbox, and outbound notices carry briefs,
reminders, and close recalls to the user. The decision gate for each integration covers scope,
permissions, data handling, failure behavior, and user confirmation rules before any adapter runs.

## Prioritized backlog

| ID | Priority | Story | Acceptance summary |
|---|---|---|---|
| P4-01 | Must | Establish messaging contracts and outbound policy | **Done** — provider-neutral inbound/outbound message contracts bound text, normalize UTC, and reject missing identities; an `OutboundPolicy` gate refuses any send without an explicit preview-confirmation digest, and the decision gate is documented (see [Messaging contracts and outbound policy](../phase-4-messaging-contracts.md)) |
| P4-02 | Must | Capture work over a supported business messaging integration | Approved WhatsApp capture path: inbound messages land in the inbox as captures through the inbound contract, deduped idempotently, without auto-applying anything |
| P4-03 | Must | Notify briefs, overdue items, and close reminders | The existing daily views generate dated outbound notices; each one is previewed and confirmed exactly once |
| P4-04 | Should | Controlled outbound actions with previews and confirmation | A confirmed reply can create a capture or acknowledge a reminder, always through the confirmation gate and audited trail |
| P4-05 | Should | Ensure reliability, retry, and audit | Outbound runs record bounded outcomes and redacted errors, retry policy is documented and tested, and every send is auditable like sync runs (P2-12) |
| P4-06 | Could | Route messages in the conversation's language | Preserve the original language of captures and notices; translation stays out until Phase 3 translation is revisited |

## Explicitly deferred

- Sending messages or accepting commitments without user confirmation.
- Unrestricted customer conversation bodies, credentials, or transcripts stored or sent to a model.
- Replacing the capture/triage flow: messaging only feeds the existing inbox.
- Live provider accounts for messaging (inbound and outbound answer as unconfigured until authorized).