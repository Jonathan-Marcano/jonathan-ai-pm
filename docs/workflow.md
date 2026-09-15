# Daily operating workflow

## 1. Morning Brief

Inputs include internal records, manual meetings, and meetings reconciled through the read-only
calendar boundary. Live account authorization remains a separate deployment decision.

The brief should show:

- today's meetings and preparation tasks;
- overdue and due-soon commitments;
- the three most important executable tasks;
- deliverables that can be advanced today;
- blockers and projects at risk;
- available capacity compared with planned effort.

The user confirms the proposed focus before the plan becomes authoritative.

Phase 1 ranks the focus list deterministically: open tasks must be `ready` or `in_progress`, then
priority, due date, and stable ID determine the top three. The full selection rules are documented
in [Morning Brief](morning-brief.md).

## 2. Capture during the day

New work enters a single inbox with minimal fields: text, source, capture time, and optional project hint. The user can add it manually from the main interface. Future channels such as WhatsApp may feed the same capture boundary only after explicit authorization.

Triage converts each capture into one of:

- a task;
- a meeting action item linked to a task;
- a deliverable update;
- a reference note;
- a dismissed item with reason.

## 3. Incremental deliverable work

Large documents are decomposed into small tasks such as gathering inputs, drafting a section, validating commands, reviewing diagrams, or sending for approval. Each work session can create a work log and a short evidence note.

Progress is measured by acceptance criteria completed, task flow, and focused time—not by document percentage alone.

The implemented manual flow starts or resumes a task, appends one work log per focused session,
and completes the task only after evidence exists. Starting work activates a planned project and
moves a linked planned deliverable to `in_progress`; review and acceptance remain explicit. See
[Incremental work](incremental-work.md) for endpoints and lifecycle rules.

## 4. Evening Close

The implemented close reviews:

1. tasks completed and evidence produced;
2. time logged versus planned;
3. captures and action items still unclassified;
4. unfinished work to reschedule, delegate, block, or cancel;
5. deliverable and project status changes;
6. tomorrow's likely first action.

The result is a dated summary with completed outcomes, open loops, blockers, and project updates.
It also proposes tomorrow's first action using the same deterministic ranking as Morning Brief.
The user updates the underlying records with the existing API and reruns the close until each open
loop has an explicit disposition. See [Evening Close](evening-close.md) for the selection rules and
current limitations.

Before or during Evening Close, the post-meeting review queue surfaces every past meeting that has
not received an explicit outcome. The user records a short result and either captures one or more
actions or confirms that no follow-up is required. The meeting, decision, actor, timestamp, and
new actions are committed together. See [Post-meeting review](post-meeting-review.md).

## 5. Weekly review

Once enough daily records exist, a weekly review aggregates effort, completed deliverables, overdue commitments, blocked time, and risks by workspace/job, client, and project.

## Measurement definitions

| Metric | Definition |
|---|---|
| Planned minutes | Estimated minutes of tasks selected for the day |
| Logged minutes | Sum of completed work-log minutes |
| Completion rate | Planned tasks completed / planned tasks |
| Capture closure | Captured items triaged / captured items |
| Deliverable throughput | Deliverables accepted during the period |
| Blocked age | Time since a task entered `blocked` |
| Commitment reliability | Accepted action items completed by their due dates |

Metrics are decision aids, not employee-surveillance measures.
