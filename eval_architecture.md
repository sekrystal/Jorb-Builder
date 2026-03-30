# Eval Architecture

Eval families:
- planning_quality
- implementation_quality
- test_adequacy
- runtime_proof_quality
- evidence_quality
- operator_handoff_quality

Mechanism:
- each run writes `eval_result.json`
- scores are numeric and machine-readable
- overall score uses explicit thresholding
- accepted Phase 4/4B runs are blocked if eval threshold is not met

This slice evaluates both process and outcome:
- process: planning artifacts, evidence bundle, judge artifact
- outcome: validation success, runtime proof presence
