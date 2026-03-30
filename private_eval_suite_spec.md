# Private Eval Suite Spec
# Private Eval Suite Spec

The private eval suite now supports:

- offline fixture families for infra hardening, runtime VM work, product UX work, repo recovery, and proposal-to-backlog synthesis
- replay over historical `task_history/*.yml`
- compare mode for two attempts
- machine-readable output via stdout and `--output`
- judge-facing threshold gating through `eval_result.json`

Synthesis-specific evals score draft backlog entries on:

- backlog synthesis quality
- evidence quality
- operator handoff quality
- planning quality
This builder-private eval suite scores runs against explicit fixture families instead of relying only on artifact presence.

## Goals

- define what good looks like for core builder ticket families
- replay historical runs without re-executing builder
- compare one attempt against another
- persist machine-readable eval truth into the normal judge and operator flow

## Scope of the first slice

- fixture-backed evals for:
  - infra hardening
  - product-facing UX
  - runtime and VM work
  - repo-state and recovery failures
- replay from `task_history/*.yml` plus referenced run artifacts
- regression comparison against the latest comparable historical run
- judge blocking when fixture thresholds are not met
- operator visibility through `run_ledger.json` and `scripts/show_status.py`

## Non-goals for this slice

- broad public benchmark coverage
- cross-repo generic evaluation framework
- model-based grading
- automated repair generation from eval feedback

## Integration points

- `scripts/private_eval_suite.py` owns fixture loading, scoring, replay, and comparison
- `scripts/automate_task_loop.py` calls the suite inside the existing eval gate
- `scripts/show_status.py` exposes eval family, pass/fail, and regression delta

## Evidence model

Each scored run emits or reuses:

- `eval_result.json`
- `judge_decision.md`
- `evidence_bundle.json`
- `runtime_proof.log`
- `automation_result.json`

Historical replay reads `task_history/*.yml` and the run log directory referenced there.
