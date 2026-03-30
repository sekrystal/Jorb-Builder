# Regression Runner Design
# Regression Runner Design

Replay and compare can now emit machine-readable artifacts via `--output`, for example:

- `replay_summary.json`
- `eval_comparison.json`

Replay works over stored `task_history/*.yml` and the run artifacts those histories reference.
## Replay source

The first replay path uses existing builder evidence:

- `task_history/*.yml`
- referenced `run_log_dir`
- `automation_result.json`
- validation payloads
- judge and evidence artifacts when present

## Replay flow

1. load historical task history entry
2. recover the matching task metadata from current `backlog.yml` when available
3. load the referenced `automation_result.json` if it still exists
4. select the best matching eval fixture
5. rescore the run without re-executing builder

## Comparison flow

1. replay two runs into normalized eval results
2. compute per-category deltas
3. compute overall delta
4. classify the trend as `improved`, `regressed`, or `unchanged`

## Aggregate flow

Replay results can be summarized by fixture family with:

- run count
- pass count
- pass rate
- average overall score
- average category scores

## Limits of the first slice

- replay assumes the referenced run log directories still exist
- historical runs without `automation_result.json` fall back to the task history summary
- regression comparison is currently against the latest comparable historical run, not the statistically best baseline
