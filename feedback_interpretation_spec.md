# Feedback Interpretation Spec

The feedback interpretation engine converts raw operator feedback and recurring run evidence into structured signals.

## Signal sources

- explicit operator feedback from `operator_feedback.json`
- repeated failure classes in `task_history/*.yml`
- eval regressions recorded in `eval_result.regression_vs_prior`
- retry loop patterns
- repeated artifact-gap failures
- repeated preflight/configuration failures

## Signal model

Each signal includes:

- raw observation
- interpreted issue
- confidence
- evidence links
- affected ticket family or subsystem
- proposed action type
- recurrence count
- observation / inference / recommendation separation

## Design intent

Signals are advisory and evidence-backed.
They do not mutate canonical backlog or roadmap files directly.
