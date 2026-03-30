# Retrieval Profiles

Builder retrieval is role-aware.

## Planner

Planner prefers:

- prior similar tickets
- successful fixes
- playbooks
- high-confidence failure avoidances

Planner budget: 4 memories

## Architect

Architect prefers:

- successful fixes
- repo heuristics
- environment assumptions
- playbooks
- constraint-heavy failure modes

Architect budget: 4 memories

## Judge

Judge prefers:

- failure modes
- flaky validations
- operator feedback
- playbooks
- prior acceptance-boundary examples

Judge budget: 5 memories

Each role receives:

- selected memories
- per-memory score
- selection reasons
- excluded entries with exclusion reason where budget trimming occurred
