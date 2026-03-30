# Builder Agents

This repository hardens JORB Builder itself.

Core expectations:
- Treat backlog truth, config, run logs, and generated artifacts as first-class system inputs.
- Do not modify the JORB product repo during builder-only hardening unless runtime proof explicitly requires product-environment interaction.
- Enforce machine-checkable gates before implementation, before acceptance, and after failure.
- Prefer replayable artifacts over narrative-only summaries.

Execution roles:
- Planner: compile the feature/system understanding artifact.
- Architect: emit proposal and tradeoff artifacts before implementation.
- Implementer: make the bounded code change.
- Validator: run deterministic local and VM checks.
- Judge: accept or reject only from evidence.
