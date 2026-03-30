# Recovery Taxonomy

Failure classes:
- prompt_planning_failure
- implementation_failure
- local_test_failure
- runtime_vm_failure
- repo_state_failure
- auth_connectivity_failure
- artifact_completeness_failure
- flaky_nondeterministic_failure
- spec_ambiguity_failure
- configuration_defect

Recovery actions:
- retry_with_modified_strategy
- replan_required
- block_pending_operator_decision
- quarantine_flaky_task

Loop protection:
- repeated refined failures of the same failure class are blocked for replan instead of looping indefinitely
