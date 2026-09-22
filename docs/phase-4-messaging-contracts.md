# Phase 4 messaging contracts and outbound policy

P4-01 introduces stable boundaries for messaging providers and the confirmation gate that every
outbound send must pass. There are no live network calls, OAuth flows, or credentials in this
increment — WhatsApp and other providers mount on this seam later.

## Decision gate

Each Phase 4 integration advances only after the following are documented and tested:

1. **Scope** — exactly which conversations and message types the adapter may read, and which
   destinations it may send to (P4-02 for inbound, P4-03 for outbound notices).
2. **Permissions** — the delegated read/write-scope the provider requires, with no wider scope.
3. **Data handling** — message bodies are bounded and never logged in full; identities are stable
   and timezone-aware (UTC); content is only ever used to feed the existing inbox or a notice.
4. **Failure behavior** — bounded retry policy and redacted errors (P4-05).
5. **User confirmation** — nothing is applied to a project and nothing is sent without an explicit
   preview-and-confirm step (`OutboundPolicy` below).

## Messaging contract

A provider-neutral messaging adapter has two channels:

### Inbound — capture candidates

An `ExternalInboundMessage` holds only what the inbox needs: provider identity, `conversation_id`,
`external_id`, a bounded `text` body, the UTC `received_at`, and an optional `sender_display`. The
deduplication key is:

```text
source_system + conversation_id + external_id
```

The same deduplication discipline as calendar events applies: a repeated poll returns the same key
and updates nothing instead of duplicating the capture. Message text is capped at
`MAX_MESSAGE_CHARS` (4000), and listings cap the batch at `MAX_MESSAGES_PER_LISTING` (200).

### Outbound — confirmed notices

An `OutboundNotice` is the neutral payload the workspace intends to send: provider, destination,
bounded body, and optional `reply_to_conversation_id`. Like inbound messages, bodies are bounded,
the destination and provider identity are required, and everything is normalized (provider key
lowercased).

## Outbound confirmation policy

Sending is a controlled act. `OutboundPolicy` refuses any send whose `confirmation` token does not
exactly match the content-addressed preview digest of the notice:

```text
preview_digest = sha256(src + SEP + destination + SEP + body + SEP + reply_to_conversation_id)
```

A service that wants to notify the user must first render the preview, show it, and only then call
`assert_can_send` with the digest the user confirmed. Any send without that explicit token raises
`OutboundConfirmationError`, so no brief, reminder, or close recall ever leaves without a human
decision. The policy also re-checks the body bound at send time, and `require_confirmation=False`
is opt-in only for explicitly documented internal paths.

## Safety boundary

| Channel | Capability | Guard |
|---|---:|---|
| Inbound read | Enabled | bounded listings, stable keys, UTC, no write |
| Outbound send | Enabled | `OutboundPolicy.assert_can_send(...)` required |
| Create/update/delete on FaroFlow records | Disabled | messaging feeds the inbox and notices only |

P4-02 implements the approved WhatsApp capture path behind the inbound contract, P4-03 notifies
briefs/overdue/close reminders through the confirmed outbound path, and P4-05 adds the audited,
bounded retry runs that mirror the Phase 2 sync-run outcomes.