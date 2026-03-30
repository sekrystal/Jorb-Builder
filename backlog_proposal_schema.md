# Backlog Proposal Schema

Draft backlog proposals are stored in `backlog_proposals.json`.

Each proposal includes:

- `proposal_id`
- `dedupe_key`
- `status`
- `source_signal_id`
- `title`
- `rationale`
- `evidence_summary`
- `evidence_links`
- `affected_ticket_family`
- `priority_recommendation`
- `confidence`
- `recurrence_count`
- `proposed_action_type`
- `dependencies`
- `operator_approval_required`
- `draft_ticket`

## Status values

- `draft`
- `under_review`
- `accepted`
- `rejected`
- `superseded`

## Safety rule

These proposals are review artifacts, not canonical backlog mutations.
