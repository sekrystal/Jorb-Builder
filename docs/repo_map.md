# Repo Map

This repo mixes control logic, canonical runtime state, and generated evidence. This map is meant to answer two questions quickly:
- where does the behavior live?
- where does the truth live?

## Top-Level Layout

### Core source

- [scripts/](/Users/samuelkrystal/projects/jorb-builder/scripts)
  - CLI entry points and most builder behavior
- [tests/](/Users/samuelkrystal/projects/jorb-builder/tests)
  - regression tests and behavior proofs
- [prompts/](/Users/samuelkrystal/projects/jorb-builder/prompts)
  - task packet templates
- [templates/](/Users/samuelkrystal/projects/jorb-builder/templates)
  - output templates such as task-history shapes
- [verifier/](/Users/samuelkrystal/projects/jorb-builder/verifier)
  - verification support config

### Canonical planning/config

- [backlog.yml](/Users/samuelkrystal/projects/jorb-builder/backlog.yml)
  - canonical backlog and task state
- [roadmap.yml](/Users/samuelkrystal/projects/jorb-builder/roadmap.yml)
  - roadmap structure
- [config.yml](/Users/samuelkrystal/projects/jorb-builder/config.yml)
  - builder execution configuration

### Canonical runtime state

- [active_task.yml](/Users/samuelkrystal/projects/jorb-builder/active_task.yml)
  - active task slot
- [status.yml](/Users/samuelkrystal/projects/jorb-builder/status.yml)
  - top-level builder state
- [run_ledger.json](/Users/samuelkrystal/projects/jorb-builder/run_ledger.json)
  - canonical operator/event ledger
- [blockers/](/Users/samuelkrystal/projects/jorb-builder/blockers)
  - canonical blocker records
- [backlog_proposals.json](/Users/samuelkrystal/projects/jorb-builder/backlog_proposals.json)
  - proposal review state
- [synthesized_backlog_entries.json](/Users/samuelkrystal/projects/jorb-builder/synthesized_backlog_entries.json)
  - synthesized backlog drafts and applied entries
- [backlog_apply_audit.json](/Users/samuelkrystal/projects/jorb-builder/backlog_apply_audit.json)
  - audited synthesis apply history

### Generated evidence and history

- [run_logs/](/Users/samuelkrystal/projects/jorb-builder/run_logs)
  - per-run prompts, progress, result artifacts, eval files, evidence
- [task_history/](/Users/samuelkrystal/projects/jorb-builder/task_history)
  - durable task outcome records
- [memory_store.json](/Users/samuelkrystal/projects/jorb-builder/memory_store.json)
  - generated memory index
- [feedback_signals.json](/Users/samuelkrystal/projects/jorb-builder/feedback_signals.json)
  - generated feedback signals

### Design/spec notes

The root contains many short spec/design notes such as:
- [eval_architecture.md](/Users/samuelkrystal/projects/jorb-builder/eval_architecture.md)
- [memory_model.md](/Users/samuelkrystal/projects/jorb-builder/memory_model.md)
- [recovery_taxonomy.md](/Users/samuelkrystal/projects/jorb-builder/recovery_taxonomy.md)

Treat these as design references, not runtime truth.

## Most Important Entry Points

### Day-to-day operator entry points

- [show_status.py](/Users/samuelkrystal/projects/jorb-builder/scripts/show_status.py)
- [operator_tui.py](/Users/samuelkrystal/projects/jorb-builder/scripts/operator_tui.py)
- [automate_task_loop.py](/Users/samuelkrystal/projects/jorb-builder/scripts/automate_task_loop.py)

### Proposal / synthesis loop

- [feedback_engine.py](/Users/samuelkrystal/projects/jorb-builder/scripts/feedback_engine.py)
- [backlog_synthesis.py](/Users/samuelkrystal/projects/jorb-builder/scripts/backlog_synthesis.py)

### Memory / eval support

- [common.py](/Users/samuelkrystal/projects/jorb-builder/scripts/common.py)
- [private_eval_suite.py](/Users/samuelkrystal/projects/jorb-builder/scripts/private_eval_suite.py)
- [memory_controls.py](/Users/samuelkrystal/projects/jorb-builder/scripts/memory_controls.py)

## Quick “Where do I look?” Guide

If you want to know:

- what task runs next:
  - [backlog.yml](/Users/samuelkrystal/projects/jorb-builder/backlog.yml)
  - `python3 scripts/automate_task_loop.py --inspect-backlog`

- what the builder thinks is happening right now:
  - [active_task.yml](/Users/samuelkrystal/projects/jorb-builder/active_task.yml)
  - [status.yml](/Users/samuelkrystal/projects/jorb-builder/status.yml)
  - [run_ledger.json](/Users/samuelkrystal/projects/jorb-builder/run_ledger.json)

- why something is blocked:
  - [blockers/](/Users/samuelkrystal/projects/jorb-builder/blockers)
  - [show_status.py](/Users/samuelkrystal/projects/jorb-builder/scripts/show_status.py)
  - [operator_tui.py](/Users/samuelkrystal/projects/jorb-builder/scripts/operator_tui.py)

- what happened in a specific run:
  - [run_logs/](/Users/samuelkrystal/projects/jorb-builder/run_logs)
  - [task_history/](/Users/samuelkrystal/projects/jorb-builder/task_history)

- how proposals become tasks:
  - [backlog_proposals.json](/Users/samuelkrystal/projects/jorb-builder/backlog_proposals.json)
  - [synthesized_backlog_entries.json](/Users/samuelkrystal/projects/jorb-builder/synthesized_backlog_entries.json)
  - [backlog_apply_audit.json](/Users/samuelkrystal/projects/jorb-builder/backlog_apply_audit.json)
