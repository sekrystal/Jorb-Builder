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
- can optionally automate the bounded JORB execution loop when executor/git/vm config is set explicitly

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

## Optional Automated Loop

Once you have explicit executor, git, and VM settings in `config.yml`, the builder can run the narrow packet-to-VM loop in one bounded script:

```bash
cd ~/projects/jorb-builder
python3 scripts/automate_task_loop.py --dry-run
python3 scripts/automate_task_loop.py
```

What it does in v1:
- loads the current active task and packet
- invokes the configured executor command directly, or pauses in explicit human-gated handoff mode if you switch back to that mode
- captures executor output in the active run log
- detects whether the product repo changed
- runs the task's local verification commands
- if local verification passes, commits and pushes the product repo
- SSHes to the configured VM, pulls latest product code, and runs configured VM validation commands
- writes `automation_result.json` and `automation_summary.md` into the active run log
- classifies the outcome as `accepted`, `refined`, or `blocked`

Important constraints:
- keep the builder external to `~/projects/jorb`
- keep the product repo worktree clean before automated execution unless you intentionally relax that rule
- prefer explicit config in `config.yml` over environment-specific magic
- use `--dry-run` first to confirm the planned executor/git/vm steps
- the default executor mode is `codex_exec`, which runs `codex exec` non-interactively in the target repo with the packet on stdin and writes the final Codex message into the active run log
- if you need the older bounded fallback, set `executor.mode` back to `human_gated`, run `python3 scripts/automate_task_loop.py`, complete the packet manually in the JORB Codex workspace, then continue with `python3 scripts/automate_task_loop.py --resume`

## Non-Interactive Auth Setup

The automated loop is designed to fail fast instead of waiting on password prompts. Set up both the product repo and the VM for SSH key auth before relying on unattended runs.

Required local setup:
- ensure the product repo origin uses SSH, not HTTPS:
```bash
cd ~/projects/jorb
git remote set-url origin git@github.com:<org>/<repo>.git
```
- load your key into the local SSH agent:
```bash
ssh-add ~/.ssh/id_ed25519
```

Required VM setup:
- make sure `config.yml` points at the correct VM user and host in `vm.ssh_target`
- install the same GitHub-capable SSH key on the VM user that owns `vm.product_repo`
- make sure the VM repo origin also uses SSH:
```bash
ssh <vm-user>@<vm-host> 'cd ~/projects/jorb && git remote set-url origin git@github.com:<org>/<repo>.git'
```
- preload the VM host key locally if needed:
```bash
ssh-keyscan -H <vm-host> >> ~/.ssh/known_hosts
```

Preflight check:
```bash
cd ~/projects/jorb-builder
python3 scripts/automate_task_loop.py --check-auth
```

If auth is still wrong, the loop now exits with a failure instead of waiting for interactive Git or SSH input.

## Safe recovery
If the builder is stuck on a stale task you want to clear safely:

```bash
python3 scripts/abandon_task.py --reason "why the task is being cleared"
```

That clears the active task and returns it to `ready` or `retry_ready` depending on its prior backlog state.
