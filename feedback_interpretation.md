# Feedback Interpretation

The feedback interpretation engine converts raw operator feedback and recurring run evidence into structured signals.

## Summary
- generated_at: 2026-03-31T15:29:30.690152+00:00
- signal_count: 7
- proposal_count: 9

## Structured Signals
### sig-508834552f75
- signal_type: preflight_failure
- feedback_dimension: capability_gap
- interpreted_issue: repeated_preflight_failure
- system_gap: Required automation capability or task contract is missing, so the backlog cannot converge through bounded execution.
- corrective_work: Add or refine a targeted builder task that supplies the missing capability and the proof path for it.
- proposed_action_type: refine_existing_ticket
- confidence: 0.9
- recurrence_count: 3
- affected_ticket_family: JORB-V1
- affected_subsystem: jorb-v1
- raw_observation: Missing automation configuration: executor.codex_cli; Authentication preflight indicates repeated or interactive prompts are likely.; Authentication preflight indicates repeated or interactive prompts are likely.
- evidence_links: /Users/samuelkrystal/projects/jorb-builder/task_history/2026-03-25T013237Z-JORB-V1-003.yml, /Users/samuelkrystal/projects/jorb-builder/task_history/2026-03-25T050715Z-JORB-V1-007.yml, /Users/samuelkrystal/projects/jorb-builder/task_history/2026-03-25T050925Z-JORB-V1-007.yml

### sig-6b2d51e1aaf6
- signal_type: preflight_failure
- feedback_dimension: capability_gap
- interpreted_issue: repeated_preflight_failure
- system_gap: Required automation capability or task contract is missing, so the backlog cannot converge through bounded execution.
- corrective_work: Add or refine a targeted builder task that supplies the missing capability and the proof path for it.
- proposed_action_type: refine_existing_ticket
- confidence: 0.8
- recurrence_count: 2
- affected_ticket_family: JORB-V3
- affected_subsystem: jorb-v3
- raw_observation: Missing automation configuration: executor.codex_cli; Missing automation configuration: vm.runtime_validation_commands or task.vm_verification
- evidence_links: /Users/samuelkrystal/projects/jorb-builder/task_history/2026-03-29T190200Z-JORB-V3-001.yml, /Users/samuelkrystal/projects/jorb-builder/task_history/2026-03-29T222718Z-JORB-V3-002.yml

### sig-9fcb38c88c74
- signal_type: eval_regression
- feedback_dimension: evaluation
- interpreted_issue: eval_regression
- system_gap: Validation coverage is not proving the behavior that regressed.
- corrective_work: Add or tighten evaluation coverage before accepting similar work again.
- proposed_action_type: add_missing_eval_coverage
- confidence: 0.8
- recurrence_count: 2
- affected_ticket_family: JORB-INFRA
- affected_subsystem: jorb-infra
- raw_observation: Builder repo is dirty before automated execution; refusing to continue.; executor_transport_failure: DNS/network resolution failed while Codex tried to reach chatgpt.com
- evidence_links: /Users/samuelkrystal/projects/jorb-builder/task_history/2026-03-30T192337Z-JORB-INFRA-010.yml, /Users/samuelkrystal/projects/jorb-builder/task_history/2026-03-30T200609Z-JORB-INFRA-010.yml

### sig-baaab0a47ec1
- signal_type: runtime_outcome
- feedback_dimension: artifact_enforcement
- interpreted_issue: phase4_artifact_enforcement_failed
- system_gap: Required builder artifacts are incomplete or missing evidence needed for acceptance.
- corrective_work: Strengthen artifact generation or acceptance gates so the missing evidence becomes mandatory.
- proposed_action_type: add_missing_acceptance_criteria
- confidence: 0.8
- recurrence_count: 2
- affected_ticket_family: JORB-INFRA
- affected_subsystem: jorb-infra
- raw_observation: Phase 4 artifact enforcement failed: compiled_feature_spec.md, proposal.md, tradeoff_matrix.md, research_brief.md, research_brief.md; Phase 4 artifact enforcement failed: compiled_feature_spec.md:missing_machine_payload
- evidence_links: /Users/samuelkrystal/projects/jorb-builder/run_ledger.json

### sig-3188672a3ac9
- signal_type: runtime_outcome
- feedback_dimension: jorb-infra
- interpreted_issue: builder_repo_is_dirty_before_automated_execution_refusing_to_continue
- system_gap: Operator feedback indicates a builder-system gap that is not yet categorized more precisely.
- corrective_work: Review the evidence and convert the gap into a bounded corrective backlog item.
- proposed_action_type: create_follow_up_hardening_ticket
- confidence: 0.8
- recurrence_count: 2
- affected_ticket_family: JORB-INFRA
- affected_subsystem: jorb-infra
- raw_observation: Builder repo is dirty before automated execution; refusing to continue.
- evidence_links: /Users/samuelkrystal/projects/jorb-builder/run_ledger.json

### sig-39686ff0f8a3
- signal_type: failure_class
- feedback_dimension: draft-jorb
- interpreted_issue: repeated_repo_state_failure
- system_gap: Operator feedback indicates a builder-system gap that is not yet categorized more precisely.
- corrective_work: Review the evidence and convert the gap into a bounded corrective backlog item.
- proposed_action_type: create_follow_up_hardening_ticket
- confidence: 0.75
- recurrence_count: 3
- affected_ticket_family: DRAFT-JORB
- affected_subsystem: draft-jorb
- raw_observation: Builder repo is dirty before automated execution; refusing to continue.; Executor changed files outside the task allowlist.; Builder repo is dirty before automated execution; refusing to continue.
- evidence_links: /Users/samuelkrystal/projects/jorb-builder/task_history/2026-03-30T204723Z-DRAFT-JORB-INFRA-STATUS-TRUTH.yml, /Users/samuelkrystal/projects/jorb-builder/task_history/2026-03-30T205825Z-DRAFT-JORB-INFRA-STATUS-TRUTH.yml, /Users/samuelkrystal/projects/jorb-builder/task_history/2026-03-31T014204Z-DRAFT-JORB-INFRA-PHASE4_ARTIFACT_ENFORCEMENT_FAILED.yml

### sig-85b731d5275e
- signal_type: failure_class
- feedback_dimension: jorb-infra
- interpreted_issue: repeated_repo_state_failure
- system_gap: Operator feedback indicates a builder-system gap that is not yet categorized more precisely.
- corrective_work: Review the evidence and convert the gap into a bounded corrective backlog item.
- proposed_action_type: create_follow_up_hardening_ticket
- confidence: 0.65
- recurrence_count: 2
- affected_ticket_family: JORB-INFRA
- affected_subsystem: jorb-infra
- raw_observation: Builder repo is dirty before automated execution; refusing to continue.; Builder repo is dirty before automated execution; refusing to continue.
- evidence_links: /Users/samuelkrystal/projects/jorb-builder/task_history/2026-03-30T192337Z-JORB-INFRA-010.yml, /Users/samuelkrystal/projects/jorb-builder/task_history/2026-03-31T152930Z-JORB-INFRA-035.yml
