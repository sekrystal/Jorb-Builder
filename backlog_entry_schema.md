# Backlog Entry Schema

Synthesized backlog entries include:

- `synthesis_id`
- `ticket_id_placeholder`
- `title`
- `status_default`
- `priority_recommendation`
- `rationale`
- `evidence_summary`
- `evidence_links`
- `dependencies`
- `affected_ticket_family`
- `acceptance_criteria`
- `required_artifacts`
- `validation_expectations`
- `requires_vm_runtime_proof`
- `provenance`
- `operator_approval`
- `validation`
- `synthesis_eval`

Synthesized backlog payload also includes:

- `dependency_graph.nodes`
- `dependency_graph.edges`
- `dependency_graph.cycles`
- `execution_order`

Validation rejects:
- missing required fields
- missing evidence links
- missing operator approval
- invalid dependencies
- duplicate ids or near-match duplicate titles
- empty or generic acceptance criteria
