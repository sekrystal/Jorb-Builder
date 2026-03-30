# Eval Fixture Schema
# Eval Fixture Schema

Supported rubric dimensions include:

- planning_quality
- implementation_quality
- test_adequacy
- runtime_proof_quality
- evidence_quality
- recovery_quality
- operator_handoff_quality
- ui_validation_quality
- data_contract_compliance
- backlog_synthesis_quality
Each fixture file lives under `eval_fixtures/*.json`.

## Required fields

- `fixture_id`
- `fixture_family`
- `description`
- `selector`
- `mandatory_artifacts`
- `rubric_dimensions`
- `pass_threshold`

## Selector

Selectors are explicit and machine-checkable. Supported keys in this slice:

- `task_family`
- `area`
- `product_facing_ux`
- `requires_vm_runtime_proof`
- `title_contains`
- `failure_classes`

## Rubric dimensions

Supported rubric dimensions in this slice:

- `planning_quality`
- `implementation_quality`
- `test_adequacy`
- `runtime_proof_quality`
- `evidence_quality`
- `recovery_quality`
- `operator_handoff_quality`
- `ui_validation_quality`
- `data_contract_compliance`

Each rubric dimension entry must include:

- `name`
- `weight`
- `threshold`
- `description`

## Pass rule

A run passes a fixture only when:

1. all mandatory artifacts are present
2. weighted overall score is at or above `pass_threshold`
3. no rubric dimension falls below its own threshold

This prevents high scores in one area from masking hard misses in another.
