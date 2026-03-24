# Jorb Builder v1

This is the external builder control plane for Jorb.

It is intentionally separate from the product repo.

## Workspace assumptions
- Product repo: `~/projects/jorb`
- Builder workspace: `~/projects/jorb-builder`

All builder scripts expand `~` at runtime, so the control files stay portable across your local user environment.

## What this does
- selects one bounded task from `backlog.yml`
- writes the active task to `active_task.yml`
- renders a Codex task packet into `run_logs/<timestamp>/codex_prompt.md`
- runs deterministic verification commands against the product repo
- records pass/fail into backlog, history, memory, and blockers
- resumes cleanly from files after interruption

## What this does not do
- it does not edit the product repo automatically
- it does not use a database
- it does not run in the background
- it does not use OpenAI Agents SDK
- it does not create a web dashboard

## Prerequisites
Both of these should exist:
- `~/projects/jorb`
- `~/projects/jorb-builder`

Run this first:

```bash
cd ~/projects/jorb-builder
python3 scripts/bootstrap_check.py
```

## Operator loop
1. In the builder window:
```bash
cd ~/projects/jorb-builder
python3 scripts/show_status.py
./scripts/run_once.sh
```

2. If `run_once.sh` prints a packet, open the packet file and give it to Codex in the Jorb window.

3. Once you have handed the packet to Codex:
```bash
python3 scripts/mark_in_progress.py
```

4. After Codex applies changes and returns its structured result, save that response into the run log directory as `codex_result.md` if you want it preserved.

5. Run verification:
```bash
python3 scripts/verify_task.py
```

6. Record the outcome:
```bash
python3 scripts/record_result.py --codex-result-file ~/projects/jorb-builder/run_logs/<timestamp>/codex_result.md
python3 scripts/show_status.py
```

## Safe recovery
If the builder is stuck on a stale task you want to clear safely:

```bash
python3 scripts/abandon_task.py --reason "why the task is being cleared"
```

That clears the active task and returns it to `ready` or `retry_ready` depending on its prior backlog state.
