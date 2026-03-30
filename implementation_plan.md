# Implementation Plan

Current ticket: `JORB-INFRA-023`

## First production slice

1. add explicit private eval fixtures for a small set of strong builder ticket families
2. score runs by rubric dimensions instead of artifact existence alone
3. replay historical run artifacts through the same scoring path
4. compare current runs against the latest comparable prior run
5. surface eval truth in the canonical operator ledger
6. let judge gating block acceptance when fixture thresholds fail

## Follow-on work

1. larger offline datasets by ticket family
2. richer rubric dimensions for API and UI contract quality
3. better replay support for incomplete historical artifacts
4. operator diff views for two compared runs
5. trend reporting across many runs and families

Current ticket: `JORB-INFRA-024 / JORB-INFRA-025`

## First production slice

1. replace flat memory extraction with typed, provenance-backed entries
2. add memory overrides for invalidation, supersession, and pinning
3. implement explainable ranking with decay and status-aware filtering
4. add role-specific retrieval bundles for planner, architect, and judge
5. surface memory truth in operator tools and per-run artifacts

## Follow-on work

1. smarter usefulness feedback loop from judge and eval outcomes
2. richer playbook ingestion from docs and accepted infra tasks
3. memory merge policies beyond signature dedupe
4. retrieval analytics across many runs

Current ticket: `JORB-INFRA-031 / JORB-INFRA-032`

## First production slice

1. normalize operator feedback and recurring run evidence into structured signals
2. generate conservative draft backlog proposals into a proposal queue
3. suppress duplicate proposals and downweight weak evidence
4. expose proposal truth in `show_status.py`
5. allow operator review status transitions without touching canonical backlog files

## Follow-on work

1. stronger subsystem targeting for proposals
2. proposal-to-backlog assisted drafting workflows
3. richer memory feedback loops from accepted/rejected proposals
4. roadmap-level proposal support behind stronger guardrails
# Implementation Plan

## Current slice

- extend the private eval suite with backlog synthesis quality scoring
- synthesize approved proposals into structured backlog-entry drafts
- validate synthesized entries before any canonical apply
- require explicit apply with append-only audit
- expose synthesis truth in the operator status surface
