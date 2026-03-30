# Canonical Mutation Policy

Canonical backlog mutation is allowed only through `scripts/backlog_synthesis.py --apply <synthesis_id>`.

Requirements:
- synthesized entry exists
- synthesized entry came from an approved supported proposal
- operator approval is present
- synthesis validation passes
- synthesis eval passes threshold
- an append-only audit record is written

Audit fields:
- timestamp
- synthesis id
- source proposal id
- backlog before hash
- backlog after hash
- inserted ticket id
- operator review metadata

No other synthesis path may write to `backlog.yml`.
