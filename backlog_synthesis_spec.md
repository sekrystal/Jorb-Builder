# Backlog Synthesis Spec

`scripts/backlog_synthesis.py` turns approved builder-infra proposals into validated backlog-entry drafts.

Inputs:
- approved `JORB-INFRA` proposals from `backlog_proposals.json`
- evidence links
- recurrence and confidence metadata
- proposal review metadata
- dependency hints

Outputs:
- `synthesized_backlog_entries.json`
- `synthesized_backlog_entries.json.dependency_graph`
- `synthesized_backlog_entries.json.execution_order`
- optional canonical mutation through `--apply`
- `backlog_apply_audit.json`

Rules:
- no synthesis from unapproved proposals
- no synthesis from unsupported ticket families in this first slice
- no canonical mutation without explicit `--apply`
- synthesized entries must pass validation and synthesis eval before apply
- provenance back to the source proposal is mandatory
- dependency edges and execution order must be deterministic from backlog truth plus accepted proposals
