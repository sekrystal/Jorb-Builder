# Proposal Guardrails

The proposal engine is intentionally conservative.

## Guardrails

- no silent mutation of `backlog.yml`
- no silent mutation of `roadmap.yml`
- weak evidence does not create strong proposals
- one-off noise is downweighted
- duplicate proposals are suppressed by `dedupe_key`
- recurring patterns are required unless severity is high
- accepted and rejected proposal outcomes are written back into memory carefully

## Priority preference

The engine prefers:

1. refining acceptance criteria
2. adding eval coverage
3. follow-up hardening tickets

It avoids spawning duplicate tickets for the same recurring issue.

For product tickets, proposals should prefer explicit completeness contracts over shallow local fixes:

- state the full product contract, not only the visible UI symptom
- identify the systemic layers that must agree before the task is done
- call out misleading partial implementations that must not be accepted as success
- add `not_done_until` clauses for refresh, restore, loading, empty, blocked, or persistence semantics when the user request implies them
