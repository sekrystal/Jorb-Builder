# Builder Hardening Spec

Phase 4B extends builder from a staged executor into a trustworthy supervisor.

Target capabilities:
- scored capability evals beyond artifact presence
- structured external memory with provenance and retrieval
- failure taxonomy tied to recovery routing
- canonical operator-visible run truth
- stricter preflight and lock ownership

Current production slice:
- memory retrieval from `task_history/` and `blockers/` into planning
- run-level eval scoring written to `eval_result.json`
- failure taxonomy with recovery action mapping
- retry-loop detection that blocks repeated same-class refined failures
- canonical run ledger at `run_ledger.json`

Non-goals for this slice:
- full offline eval dataset runner
- long-term memory aging automation
- multi-process distributed lock coordination
