# Architecture Overview

This is a lightweight overview for collaborators who need to understand the system quickly.

## High-Level Model

`jorb-builder` is a file-backed orchestration layer around a bounded task execution loop.

The rough flow is:

1. canonical backlog selection
2. prompt / packet rendering
3. executor run
4. local validation
5. optional VM validation
6. eval / judge / classification
7. canonical state update
8. history, blocker, memory, and proposal updates

## Core Principle

The repo uses files as the primary system interface.

That means:
- state is inspectable without a database
- repair and replay are easier
- operator tooling can read canonical files directly

It also means:
- long-running updates are mostly file/poll based
- some truth surfaces must be careful not to mix “latest run” with “current target”

## Main Runtime Layers

### Execution layer

Primary script:
- [automate_task_loop.py](/Users/samuelkrystal/projects/jorb-builder/scripts/automate_task_loop.py)

Responsibilities:
- select or resume tasks
- enforce preflight checks
- run executor
- run validation
- classify outcomes
- persist canonical state

### Eval layer

Primary script:
- [private_eval_suite.py](/Users/samuelkrystal/projects/jorb-builder/scripts/private_eval_suite.py)

Responsibilities:
- apply task-family fixtures
- score rubric dimensions
- gate acceptance
- compare current vs prior runs

### Memory / retrieval layer

Primary shared logic:
- [common.py](/Users/samuelkrystal/projects/jorb-builder/scripts/common.py)

Responsibilities:
- build memory store
- track provenance
- rank role-specific memory and artifact context

Current limitation:
- retrieval is real, but still heuristic and file-backed

### Proposal / synthesis layer

Primary scripts:
- [feedback_engine.py](/Users/samuelkrystal/projects/jorb-builder/scripts/feedback_engine.py)
- [backlog_synthesis.py](/Users/samuelkrystal/projects/jorb-builder/scripts/backlog_synthesis.py)

Responsibilities:
- interpret signals
- create structured proposals
- synthesize approved proposals
- apply audited backlog mutations

### Control plane

Primary scripts:
- [show_status.py](/Users/samuelkrystal/projects/jorb-builder/scripts/show_status.py)
- [operator_state.py](/Users/samuelkrystal/projects/jorb-builder/scripts/operator_state.py)
- [operator_tui.py](/Users/samuelkrystal/projects/jorb-builder/scripts/operator_tui.py)

Responsibilities:
- expose operator truth
- explain queue, blockers, and next action
- provide safe wrappers for common actions

## Canonical Runtime State

The most important invariant is:

The TUI and status surfaces should read canonical state, not invent it.

Canonical runtime files:
- [active_task.yml](/Users/samuelkrystal/projects/jorb-builder/active_task.yml)
- [status.yml](/Users/samuelkrystal/projects/jorb-builder/status.yml)
- [run_ledger.json](/Users/samuelkrystal/projects/jorb-builder/run_ledger.json)
- [backlog.yml](/Users/samuelkrystal/projects/jorb-builder/backlog.yml)
- [blockers/](/Users/samuelkrystal/projects/jorb-builder/blockers)

## Current Honest Limits

- not database-backed
- not webhook/push-event based
- not using a dedicated model-tier architecture in code
- not yet using strong analog retrieval
- not yet grading trajectory/trace quality explicitly

The system is real and operational, but it is still a pragmatic file-backed orchestration system rather than a fully service-oriented agent platform.
