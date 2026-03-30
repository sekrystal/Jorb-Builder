# Ranking and Decay

Memory ranking combines:

- exact task match
- ticket family match
- area match
- role-specific memory-type fit
- role-specific origin fit
- tag overlap with the current task
- tag biases defined by the role profile
- confidence
- freshness decay
- pinned or stale status adjustments

## Decay

Each memory gets freshness metadata:

- `observed_at`
- `age_days`
- `decay_factor`
- `stale_after_days`
- `freshness_state`

Older memories are downranked via `decay_factor`.
Stale memories are still retrievable but receive an explicit penalty.

## Invalidation and supersession

Invalidated memories are excluded from retrieval.
Superseded memories are excluded from retrieval.
Pinned memories receive an explicit boost and remain visible to the operator.

## Explainability

Every selected memory includes:

- `selection_score`
- `selection_reasons`

This makes ranking inspectable after the run.
