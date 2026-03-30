# Memory Model

Builder memory is structured external state, not raw prompt stuffing.

## Storage

- derived index: `memory_store.json`
- operator overrides: `memory_overrides.json`
- per-run retrieval artifacts:
  - `memory_context.json`
  - `judge_memory_context.json`

## Entry shape

Each memory entry includes:

- `memory_id`
- `memory_type`
- `ticket_family`
- `task_id`
- `area`
- `source_artifact`
- `timestamp`
- `confidence`
- `freshness`
- `observation`
- `inference`
- `primary_basis`
- `relevance_tags`
- `origin`
- `status`
- `status_reason`
- `provenance`
- `signature`
- `support_count`
- `superseded_by`
- `supersedes`

## Supported memory types in this slice

- `prior_similar_ticket`
- `failure_mode`
- `successful_fix`
- `flaky_validation`
- `repo_heuristic`
- `playbook`
- `operator_feedback`
- `environment_assumption`

## Observation versus inference

The model stores both explicitly.

- `observation`: direct evidence from artifacts
- `inference`: derived conclusion or guidance
- `primary_basis`: whether the entry is primarily acting as an observation or inference memory

## Status lifecycle

- `active`
- `stale`
- `invalidated`
- `superseded`
- `pinned`

Operator controls can move memories between these states without editing raw history.
