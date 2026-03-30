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
