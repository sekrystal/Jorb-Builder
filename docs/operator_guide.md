# Operator Guide

This guide is for someone operating `jorb-builder`, not developing it.

## The Four Questions To Ask First

When you open the repo, answer these in order:

1. Is something actively running?
2. Is the system blocked?
3. Is there ready work?
4. Is the system waiting on approval, synthesis, or repair?

The fastest ways to answer:

```bash
cd ~/projects/jorb-builder
python3 scripts/show_status.py
python3 scripts/automate_task_loop.py --inspect-backlog
```

Or use the TUI:

```bash
python3 scripts/operator_tui.py
```

## Recommended Day-To-Day Workflow

### TUI first

```bash
python3 scripts/operator_tui.py
```

Use:
- `x` run
- `m` toggle loop mode
- `p` approve draft proposals
- `s` synthesize approved proposals
- `a` apply synthesized entries
- `b` inspect blockers
- `u` auto-recover a common blocker
- `t` run repair-state
- `q` quit

### Single-run mode

Use when you want one bounded run:

```bash
python3 scripts/automate_task_loop.py
```

### Until-failure mode

Use when you want the builder to continue until a real stop condition:
- blocked task
- approval needed
- synthesis eval fail
- auth/clean-worktree precondition fail
- no runnable tasks remain
- operator interrupt

In the TUI:
- press `m` until the mode is `until-failure`
- press `x`

## Recovery Flows

### Dirty repo blocker

What it means:
- the repo has local changes and automation refuses to mix them silently into a run

In the TUI:
- `g` inspect changed files
- `c` checkpoint current changes
- `u` do the common recovery flow
- `t` repair/reopen state if needed

Shell equivalent:

```bash
git status --short
git add -A
git commit -m "Checkpoint builder state"
python3 scripts/automate_task_loop.py --repair-state
```

### Stale active/blocker state

Use:

```bash
python3 scripts/automate_task_loop.py --repair-state
```

This is the canonical repair tool. The TUI uses the same underlying behavior.

### Auth / VM precondition issues

Inspect:

```bash
python3 scripts/automate_task_loop.py --check-auth
```

The automation loop is designed to fail fast rather than waiting on interactive auth.

## Proposal And Synthesis Flow

The builder can create follow-on improvement work.

The flow is:
1. proposal is generated
2. operator approves proposal
3. approved proposal is synthesized
4. synthesis eval passes
5. synthesized entry is applied into canonical backlog
6. applied task becomes runnable through normal backlog selection

Operator commands:

```bash
python3 scripts/feedback_engine.py --status
python3 scripts/backlog_synthesis.py --status
```

## Canonical Files Operators Should Know

- [backlog.yml](/Users/samuelkrystal/projects/jorb-builder/backlog.yml)
  - backlog truth
- [active_task.yml](/Users/samuelkrystal/projects/jorb-builder/active_task.yml)
  - active task slot
- [status.yml](/Users/samuelkrystal/projects/jorb-builder/status.yml)
  - top-level state
- [run_ledger.json](/Users/samuelkrystal/projects/jorb-builder/run_ledger.json)
  - event/operator truth
- [blockers/](/Users/samuelkrystal/projects/jorb-builder/blockers)
  - blocker truth

## Generated Evidence You Will Inspect Often

- [run_logs/](/Users/samuelkrystal/projects/jorb-builder/run_logs)
  - prompts, progress, eval, summaries, evidence
- [task_history/](/Users/samuelkrystal/projects/jorb-builder/task_history)
  - finalized task records

## If You Need A One-Minute Mental Model

- `backlog.yml` decides what can run
- `active_task.yml` and `status.yml` say what is happening now
- `run_ledger.json` and `blockers/` explain what happened
- `run_logs/` and `task_history/` prove it
- the TUI is the preferred way to operate the system, but it should always reflect those files, not replace them
