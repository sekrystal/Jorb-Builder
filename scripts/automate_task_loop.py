#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import shlex
import subprocess
from typing import Any

from common import builder_root, builder_path_from_config, expand_path, load_config, load_data, product_repo_path, write_data


ROOT = builder_root()
ACTIVE = ROOT / "active_task.yml"
BACKLOG = ROOT / "backlog.yml"
STATUS = ROOT / "status.yml"
MEMORY = ROOT / "builder_memory.md"
TASK_HISTORY = ROOT / "task_history"
BLOCKERS = ROOT / "blockers"
RESULT_FILE = "automation_result.json"
SUMMARY_FILE = "automation_summary.md"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_task(backlog: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in backlog.get("tasks", []):
        if task.get("id") == task_id:
            return task
    raise KeyError(task_id)


def reset_active() -> dict[str, Any]:
    return {
        "task_id": None,
        "title": None,
        "state": "idle",
        "attempt": 0,
        "started_at": None,
        "handed_to_codex_at": None,
        "prompt_file": None,
        "run_log_dir": None,
        "verification_commands": [],
        "allowlist": [],
        "failure_summary": None,
        "notes": [],
        "target_repo": None,
        "target_kind": None,
    }


def append_memory(line: str) -> None:
    with MEMORY.open("a", encoding="utf-8") as handle:
        handle.write(f"\n- {line}\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_step(run_dir: Path, name: str, payload: dict[str, Any]) -> None:
    write_json(run_dir / f"{name}.json", payload)


def write_summary(run_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        f"# Automation Result: {payload['classification']}",
        "",
        f"- task_id: {payload['task_id']}",
        f"- classification: {payload['classification']}",
        f"- finished_at: {payload['finished_at']}",
        f"- summary: {payload['summary']}",
        "",
        "## Step Results",
    ]
    for step in payload.get("steps", []):
        lines.append(f"- {step['name']}: {step['outcome']}")
        if step.get("detail"):
            lines.append(f"  detail: {step['detail']}")
    lines.append("")
    lines.append("## Changed Files")
    changed_files = payload.get("changed_files", [])
    if changed_files:
        for path in changed_files:
            lines.append(f"- {path}")
    else:
        lines.append("- none")
    (run_dir / SUMMARY_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_result(label: str, summary: str, next_action: str | None = None, extra: str | None = None) -> None:
    print(f"{label} {summary}")
    if extra:
        print(extra)
    if next_action:
        print(f"Next action: {next_action}")


def render_template(template: str | None, context: dict[str, str]) -> str | None:
    if template is None:
        return None
    return template.format(**context)


def task_targets_builder_repo(task: dict[str, Any], active: dict[str, Any]) -> bool:
    allowlist = list(task.get("allowlist", []) or active.get("allowlist", []))
    if task.get("area") == "builder":
        return True
    if any(str(entry).startswith("../jorb-builder") for entry in allowlist):
        return True
    return False


def persist_paused_state(active: dict[str, Any], status: dict[str, Any], note: str) -> None:
    active["state"] = "paused"
    if not active.get("handed_to_codex_at"):
        active["handed_to_codex_at"] = now_iso()
    notes = list(active.get("notes", []))
    if note not in notes:
        notes.append(note)
    active["notes"] = notes
    status["state"] = "implementing"
    status["active_task_id"] = active["task_id"]
    status["last_run_at"] = now_iso()
    write_data(ACTIVE, active)
    write_data(STATUS, status)


def persist_failure_state(
    active: dict[str, Any],
    status: dict[str, Any],
    *,
    blocked: bool,
    summary: str,
) -> None:
    active["state"] = "failed"
    active["failure_summary"] = summary
    status["state"] = "blocked" if blocked else "retry_ready"
    status["active_task_id"] = active.get("task_id")
    status["last_task_id"] = active.get("task_id")
    status["last_result"] = "blocked" if blocked else "refined"
    status["last_run_at"] = now_iso()
    write_data(ACTIVE, active)
    write_data(STATUS, status)


def run_shell(command: str, cwd: Path, shell_executable: str, timeout: int | None = None) -> dict[str, Any]:
    started_at = now_iso()
    try:
        process = subprocess.run(
            command,
            shell=True,
            executable=shell_executable,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "command": command,
            "cwd": str(cwd),
            "started_at": started_at,
            "finished_at": now_iso(),
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "passed": process.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "cwd": str(cwd),
            "started_at": started_at,
            "finished_at": now_iso(),
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"Timed out after {timeout} seconds.",
            "passed": False,
        }


def run_argv(argv: list[str], cwd: Path, timeout: int | None = None) -> dict[str, Any]:
    started_at = now_iso()
    try:
        process = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "command": " ".join(shlex.quote(part) for part in argv),
            "cwd": str(cwd),
            "started_at": started_at,
            "finished_at": now_iso(),
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "passed": process.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(shlex.quote(part) for part in argv),
            "cwd": str(cwd),
            "started_at": started_at,
            "finished_at": now_iso(),
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"Timed out after {timeout} seconds.",
            "passed": False,
        }


def ignored_git_paths_for_target(target_kind: str) -> tuple[str, ...]:
    if target_kind != "builder":
        return ()
    return (
        "active_task.yml",
        "backlog.yml",
        "status.yml",
        "builder_memory.md",
        "task_history/",
        "blockers/",
        "run_logs/",
    )


def git_status_porcelain(repo: Path, *, ignored_prefixes: tuple[str, ...] = ()) -> dict[str, Any]:
    result = run_argv(["git", "status", "--porcelain"], repo)
    files: list[str] = []
    for line in result.get("stdout", "").splitlines():
        if not line.strip():
            continue
        path = line[3:] if len(line) > 3 else line
        if any(path == prefix or path.startswith(prefix) for prefix in ignored_prefixes):
            continue
        files.append(path)
    result["files"] = files
    return result


def changed_files_are_allowlisted(changed_files: list[str], allowlist: list[str]) -> tuple[bool, list[str]]:
    if not changed_files:
        return True, []
    disallowed: list[str] = []
    for changed in changed_files:
        normalized = changed.strip()
        allowed = any(
            normalized == entry
            or entry == "../jorb-builder/**"
            or (
                entry.startswith("../jorb-builder/")
                and (
                    entry.removeprefix("../jorb-builder/") == "**"
                    or normalized.startswith(entry.removeprefix("../jorb-builder/").removesuffix("/**"))
                )
            )
            or (
                entry.endswith("/**")
                and normalized.startswith(entry.removesuffix("/**"))
            )
            or (entry.endswith("/") and normalized.startswith(entry))
            for entry in allowlist
        )
        if not allowed:
            disallowed.append(normalized)
    return len(disallowed) == 0, disallowed


def resolve_product_validation_venv(product_repo: Path) -> Path | None:
    for dirname in (".venv_validation", ".venv", ".venv_j1"):
        candidate = product_repo / dirname
        if candidate.exists():
            return candidate
    return None


def validation_commands_for_target(
    commands: list[str],
    *,
    target_kind: str,
    target_repo: Path,
) -> tuple[list[str], Path | None]:
    if target_kind != "product":
        return commands, None
    venv_path = resolve_product_validation_venv(target_repo)
    if venv_path is None:
        return commands, None
    wrapped = [f"source {shlex.quote(str(venv_path / 'bin' / 'activate'))} && {command}" for command in commands]
    return wrapped, venv_path


def ssh_command(target: str, options: list[str], remote_command: str, cwd: Path) -> dict[str, Any]:
    return run_argv(["ssh", *options, target, remote_command], cwd)


def record_history(task: dict[str, Any], active: dict[str, Any], automation_result: dict[str, Any]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    path = TASK_HISTORY / f"{timestamp}-{task['id']}.yml"
    payload = {
        "task_id": task["id"],
        "title": task["title"],
        "status": automation_result["classification"],
        "attempt": active.get("attempt", 1),
        "started_at": active.get("started_at"),
        "completed_at": automation_result["finished_at"],
        "prompt": active.get("prompt_file"),
        "files_changed": automation_result.get("changed_files", []),
        "commands_run": [step.get("command") for step in automation_result.get("steps", []) if step.get("command")],
        "results": [step["outcome"] for step in automation_result.get("steps", [])],
        "acceptance_met": task.get("acceptance", []) if automation_result["classification"] == "accepted" else [],
        "acceptance_unmet": [] if automation_result["classification"] == "accepted" else task.get("acceptance", []),
        "blocker_opened": None,
        "notes": [automation_result["summary"]],
        "unproven_runtime_gaps": automation_result.get("unproven_runtime_gaps", []),
    }
    write_data(path, payload)
    return path


def open_blocker(task: dict[str, Any], summary: str, evidence: list[str]) -> Path:
    path = BLOCKERS / f"BLK-{task['id']}.yml"
    payload = {
        "id": f"BLK-{task['id']}",
        "title": f"Task {task['id']} blocked during automated execution",
        "severity": "high",
        "opened_at": now_iso(),
        "related_tasks": [task["id"]],
        "status": "open",
        "symptoms": [summary],
        "diagnosis": summary,
        "evidence": evidence,
        "next_actions": ["Inspect automation_result.json and narrow the next bounded refinement."],
        "human_needed": True,
    }
    write_data(path, payload)
    return path


def validate_active_task_context(
    active: dict[str, Any],
    status: dict[str, Any],
    task: dict[str, Any] | None,
    *,
    resume: bool,
) -> tuple[str, str, str | None] | None:
    if not active.get("task_id"):
        return ("NO_ACTIVE_TASK", "No active task is currently loaded.", "Restore or select a task packet before rerunning automation.")
    if task is None:
        return ("INVALID_ACTIVE_TASK_STATE", f"Active task {active.get('task_id')} is missing from backlog.", "Repair backlog/active_task alignment before rerunning automation.")
    if not active.get("run_log_dir"):
        return ("INVALID_ACTIVE_TASK_STATE", "Active task is missing run_log_dir.", "Restore the active task from its existing run log before rerunning automation.")
    if not active.get("prompt_file"):
        return ("MISSING_PACKET", "Active task is missing prompt_file.", "Restore or rerender the packet before rerunning automation.")
    prompt_file = Path(active["prompt_file"]).expanduser().resolve()
    if not prompt_file.exists():
        return ("MISSING_PACKET", f"Prompt file does not exist: {prompt_file}", "Restore or rerender the packet before rerunning automation.")
    if resume and active.get("state") not in {"paused", "implementing"}:
        return ("INVALID_ACTIVE_TASK_STATE", f"Cannot resume from active state '{active.get('state')}'.", "Run python3 scripts/automate_task_loop.py directly, or restore the paused task state first.")
    if resume and active.get("state") == "implementing" and not active.get("handed_to_codex_at"):
        return ("STALE_IMPLEMENTING_STATE", "Active task is implementing but has no recorded handoff time.", "Re-run python3 scripts/automate_task_loop.py to record a fresh pause/handoff before using --resume.")
    if status.get("state") == "blocked" and status.get("active_task_id") is None:
        return ("INVALID_ACTIVE_TASK_STATE", "Global status is blocked but no active task is attached.", "Restore the intended active task before rerunning automation.")
    return None


def is_retry_continuation(active: dict[str, Any], status: dict[str, Any], *, resume: bool) -> bool:
    return (
        not resume
        and active.get("state") == "failed"
        and status.get("state") == "retry_ready"
        and status.get("active_task_id") == active.get("task_id")
    )


def load_prior_automation_result(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / RESULT_FILE
    if not path.exists():
        return None
    return load_data(path)


def prior_result_supports_vm_retry(run_dir: Path) -> dict[str, Any] | None:
    prior = load_prior_automation_result(run_dir)
    if prior:
        steps = {step.get("name"): step for step in prior.get("steps", [])}
        if (
            steps.get("local_validation", {}).get("outcome") == "passed"
            and steps.get("git", {}).get("outcome") == "passed"
            and steps.get("vm_validation", {}).get("outcome") == "refined"
            and prior.get("changed_files")
        ):
            return prior

    local_validation_path = run_dir / "local_validation.json"
    git_path = run_dir / "git.json"
    vm_validation_path = run_dir / "vm_validation.json"
    if not (local_validation_path.exists() and git_path.exists() and vm_validation_path.exists()):
        return None

    local_validation = load_data(local_validation_path)
    git_result = load_data(git_path)
    vm_validation = load_data(vm_validation_path)
    if not local_validation.get("passed"):
        return None
    if not (
        git_result.get("add", {}).get("passed")
        and git_result.get("commit", {}).get("passed")
        and git_result.get("push", {}).get("passed")
    ):
        return None
    if vm_validation.get("passed") is not False:
        return None

    changed_files: list[str] = []
    for result in local_validation.get("results", []):
        stdout = str(result.get("stdout", ""))
        if "== git status --short ==" not in stdout:
            continue
        capture = False
        for line in stdout.splitlines():
            if line.strip() == "== git status --short ==":
                capture = True
                continue
            if capture and line.startswith("== "):
                break
            if not capture:
                continue
            if not line.strip():
                continue
            changed_files.append(line[3:] if len(line) > 3 else line.strip())
        if changed_files:
            break
    if not changed_files:
        previous = load_prior_automation_result(run_dir)
        if previous and previous.get("changed_files"):
            changed_files = list(previous.get("changed_files", []))
    if not changed_files:
        return None

    return {
        "task_id": None,
        "classification": "refined",
        "summary": "VM validation failed after local validation and git push succeeded.",
        "steps": [
            {"name": "local_validation", "outcome": "passed"},
            {"name": "git", "outcome": "passed"},
            {"name": "vm_validation", "outcome": "refined"},
        ],
        "changed_files": changed_files,
    }
    return None


def classify_and_update_state(
    classification: str,
    summary: str,
    task: dict[str, Any],
    backlog: dict[str, Any],
    active: dict[str, Any],
    status: dict[str, Any],
    automation_result: dict[str, Any],
) -> None:
    status.setdefault("stats", {})
    history_path = record_history(task, active, automation_result)

    if classification == "accepted":
        task["status"] = "accepted"
        task.setdefault("notes", []).append(summary)
        status["state"] = "idle"
        status["last_task_id"] = task["id"]
        status["active_task_id"] = None
        status["last_result"] = "accepted"
        status["last_run_at"] = now_iso()
        status["stats"]["completed_tasks"] = int(status["stats"].get("completed_tasks", 0)) + 1
        append_memory(f"{task['id']} accepted by automated loop. History: {history_path.name}")
        write_data(ACTIVE, reset_active())
        return

    if classification == "refined":
        task["retries_used"] = int(task.get("retries_used", 0)) + 1
        task["status"] = "retry_ready"
        task.setdefault("notes", []).append(summary)
        status["stats"]["retry_ready_tasks"] = int(status["stats"].get("retry_ready_tasks", 0)) + 1
        append_memory(f"{task['id']} refined by automated loop. History: {history_path.name}")
        persist_failure_state(active, status, blocked=False, summary=summary)
        return

    task["status"] = "blocked"
    task.setdefault("notes", []).append(summary)
    blocker_path = open_blocker(task, summary, automation_result.get("blocker_evidence", []))
    status["stats"]["blocked_tasks"] = int(status["stats"].get("blocked_tasks", 0)) + 1
    append_memory(f"{task['id']} blocked by automated loop via {blocker_path.name}. History: {history_path.name}")
    persist_failure_state(active, status, blocked=True, summary=summary)


def build_context(
    active: dict[str, Any],
    task: dict[str, Any],
    product_repo: Path,
    builder_root_path: Path,
    target_repo: Path,
    target_kind: str,
) -> dict[str, str]:
    return {
        "task_id": task["id"],
        "title": task["title"],
        "prompt_file": active.get("prompt_file") or "",
        "run_log_dir": active.get("run_log_dir") or "",
        "product_repo": str(product_repo),
        "builder_root": str(builder_root_path),
        "target_repo": str(target_repo),
        "target_kind": target_kind,
    }


def attach_target_to_active(active: dict[str, Any], *, target_repo: Path, target_kind: str) -> None:
    active["target_repo"] = str(target_repo)
    active["target_kind"] = target_kind


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    config = load_config()
    backlog = load_data(BACKLOG)
    active = load_data(ACTIVE)
    status = load_data(STATUS)

    product_repo = product_repo_path()
    builder_repo = builder_path_from_config("builder_root")
    task = None
    if active.get("task_id"):
        try:
            task = find_task(backlog, active["task_id"])
        except KeyError:
            task = None
    validation_error = validate_active_task_context(active, status, task, resume=args.resume)
    if validation_error:
        label, summary, next_action = validation_error
        print_result(label, summary, next_action)
        return 1

    run_dir = Path(active["run_log_dir"]).expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    target_kind = "builder" if task_targets_builder_repo(task, active) else "product"
    target_repo = builder_repo if target_kind == "builder" else product_repo
    attach_target_to_active(active, target_repo=target_repo, target_kind=target_kind)
    write_data(ACTIVE, active)
    context = build_context(active, task, product_repo, ROOT, target_repo, target_kind)

    executor_config = config.get("executor", {})
    git_config = config.get("git", {})
    vm_config = config.get("vm", {})
    executor_mode = executor_config.get("mode") or "command"
    shell_executable = executor_config.get("shell") or "/bin/zsh"
    vm_repo = expand_path(vm_config.get("product_repo", "~/projects/jorb"))
    context["vm_product_repo"] = str(vm_repo)

    vm_commands = list(vm_config.get("validation_commands", [])) + list(vm_config.get("runtime_validation_commands", []))
    local_validation_commands = list(active.get("verification_commands", []))
    prepared_validation_commands, validation_venv = validation_commands_for_target(
        local_validation_commands,
        target_kind=target_kind,
        target_repo=target_repo,
    )
    use_vm_flow = target_kind == "product"
    ignored_git_paths = ignored_git_paths_for_target(target_kind)
    retry_continuation = is_retry_continuation(active, status, resume=args.resume)
    plan = {
        "task_id": task["id"],
        "prompt_file": active["prompt_file"],
        "run_log_dir": active["run_log_dir"],
        "target_kind": target_kind,
        "target_repo": str(target_repo),
        "executor_mode": executor_mode,
        "executor_command": render_template(executor_config.get("command"), context),
        "local_validation_commands": local_validation_commands,
        "prepared_local_validation_commands": prepared_validation_commands,
        "git_push_command": render_template(git_config.get("push_command"), context),
        "vm_pull_command": render_template(vm_config.get("pull_command"), context) if use_vm_flow else None,
        "vm_commands": [render_template(command, context) for command in vm_commands] if use_vm_flow else [],
        "ssh_target": vm_config.get("ssh_target") if use_vm_flow else None,
        "missing_configuration": [],
        "retry_continuation": retry_continuation,
    }
    if executor_mode != "human_gated" and not executor_config.get("command"):
        plan["missing_configuration"].append("executor.command")
    if use_vm_flow and not vm_config.get("ssh_target"):
        plan["missing_configuration"].append("vm.ssh_target")
    if use_vm_flow and not vm_commands:
        plan["missing_configuration"].append("vm.validation_commands or vm.runtime_validation_commands")

    if args.dry_run:
        payload = {
            "task_id": task["id"],
            "classification": "dry_run",
            "finished_at": now_iso(),
            "summary": "Dry run only. No executor, git, or VM commands were executed.",
            "steps": [
                {"name": "plan", "outcome": "planned", "detail": json.dumps(plan, indent=2)},
            ],
            "changed_files": [],
            "unproven_runtime_gaps": ["Automation loop not executed; this was a dry run."],
        }
        write_json(run_dir / RESULT_FILE, payload)
        write_summary(run_dir, payload)
        print_result("DRY_RUN", f"Plan written to {run_dir / RESULT_FILE}")
        return 0

    status["state"] = "implementing"
    status["active_task_id"] = task["id"]
    status["last_run_at"] = now_iso()
    write_data(STATUS, status)

    steps: list[dict[str, Any]] = []
    blocker_evidence: list[str] = []
    continue_from_prior_vm_retry = False

    if plan["missing_configuration"]:
        summary = "Missing automation configuration: " + ", ".join(plan["missing_configuration"])
        automation_result = {
            "task_id": task["id"],
            "classification": "blocked",
            "finished_at": now_iso(),
            "summary": summary,
            "steps": [{"name": "configuration", "outcome": "blocked", "detail": summary}],
            "changed_files": [],
            "blocker_evidence": plan["missing_configuration"],
            "unproven_runtime_gaps": [summary],
        }
        write_json(run_dir / RESULT_FILE, automation_result)
        write_summary(run_dir, automation_result)
        classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result)
        write_data(BACKLOG, backlog)
        write_data(STATUS, status)
        print_result("BLOCKED", summary, "Set the missing config values in config.yml and rerun python3 scripts/automate_task_loop.py.")
        return 2

    baseline = git_status_porcelain(target_repo, ignored_prefixes=ignored_git_paths)
    write_step(run_dir, "git_status_before", baseline)
    if not args.resume and not retry_continuation and git_config.get("require_clean_worktree", True) and baseline.get("files"):
        summary = f"{target_kind.title()} repo is dirty before automated execution; refusing to continue."
        blocker_evidence.extend(baseline.get("files", []))
        automation_result = {
            "task_id": task["id"],
            "classification": "blocked",
            "finished_at": now_iso(),
            "summary": summary,
            "steps": [{"name": "git_status_before", "outcome": "blocked", "detail": "\n".join(baseline.get("files", []))}],
            "changed_files": baseline.get("files", []),
            "blocker_evidence": blocker_evidence,
            "unproven_runtime_gaps": [summary],
        }
        write_json(run_dir / RESULT_FILE, automation_result)
        write_summary(run_dir, automation_result)
        classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result)
        write_data(BACKLOG, backlog)
        write_data(STATUS, status)
        print_result("BLOCKED", summary, f"Clean {target_repo} or relax git.require_clean_worktree before rerunning python3 scripts/automate_task_loop.py.")
        return 2

    if not args.resume and not retry_continuation and executor_mode == "human_gated":
        handoff_note = "Manual JORB Codex execution is required before resume."
        handoff_payload = {
            "mode": "human_gated",
            "task_id": task["id"],
            "prompt_file": active["prompt_file"],
            "run_log_dir": active["run_log_dir"],
            "resume_command": "python3 scripts/automate_task_loop.py --resume",
            "target_kind": target_kind,
            "target_repo": str(target_repo),
            "message": f"Open the packet, run the task in the {'builder' if target_kind == 'builder' else 'JORB'} Codex workspace, then resume after {target_kind} repo changes are present.",
            "started_at": now_iso(),
        }
        write_step(run_dir, "executor_handoff", handoff_payload)
        automation_result = {
            "task_id": task["id"],
            "classification": "paused",
            "finished_at": now_iso(),
            "summary": f"Manual executor handoff recorded. Resume after {target_kind} repo changes are applied.",
            "steps": [
                {
                    "name": "executor_handoff",
                    "outcome": "paused",
                    "detail": f"packet: {active['prompt_file']}; target_repo: {target_repo}; resume: python3 scripts/automate_task_loop.py --resume",
                }
            ],
            "changed_files": [],
            "unproven_runtime_gaps": [f"{target_kind.title()} repo changes have not been applied yet; resume is required after manual Codex execution."],
        }
        write_json(run_dir / RESULT_FILE, automation_result)
        write_summary(run_dir, automation_result)
        persist_paused_state(active, status, handoff_note)
        print_result(
            "PAUSED",
            f"Manual executor handoff recorded for {active['prompt_file']}.",
            "After Codex applies changes in the target repo, run python3 scripts/automate_task_loop.py --resume.",
            extra=f"Target repo: {target_repo}",
        )
        return 0

    if args.resume:
        after_executor = baseline
        write_step(run_dir, "resume_check", after_executor)
        steps.append({
            "name": "resume_check",
            "outcome": "passed" if after_executor.get("files") else "paused",
            "detail": f"Detected {target_kind} repo changes after manual execution." if after_executor.get("files") else f"No {target_kind} repo changes detected yet.",
        })
        if not after_executor.get("files"):
            automation_result = {
                "task_id": task["id"],
                "classification": "paused",
                "finished_at": now_iso(),
                "summary": f"Resume requested, but no {target_kind} repo changes were detected yet.",
                "steps": steps,
                "changed_files": [],
                "unproven_runtime_gaps": [f"Manual Codex execution has not produced detectable {target_kind} repo changes yet."],
            }
            write_json(run_dir / RESULT_FILE, automation_result)
            write_summary(run_dir, automation_result)
            persist_paused_state(active, status, f"Resume attempted before {target_kind} repo changes were present.")
            print_result(
                "PAUSED",
                f"No {target_kind} repo changes were detected yet.",
                f"Apply the packet in {target_repo} first, then rerun python3 scripts/automate_task_loop.py --resume.",
                extra=f"Prompt file: {active['prompt_file']}",
            )
            return 0
    elif retry_continuation:
        after_executor = baseline
        write_step(run_dir, "retry_check", after_executor)
        steps.append({
            "name": "retry_check",
            "outcome": "passed" if after_executor.get("files") else "refined",
            "detail": f"Continuing from existing {target_kind} repo task changes." if after_executor.get("files") else f"No {target_kind} repo changes were found for retry continuation.",
        })
        if not after_executor.get("files"):
            prior_vm_retry = prior_result_supports_vm_retry(run_dir)
            if prior_vm_retry:
                steps[-1]["outcome"] = "passed"
                steps[-1]["detail"] = "No current dirty repo changes; continuing from prior post-push VM retry context."
            else:
                summary = f"Retry-ready task has no {target_kind} repo changes to continue from."
                automation_result = {
                    "task_id": task["id"],
                    "classification": "refined",
                    "finished_at": now_iso(),
                    "summary": summary,
                    "steps": steps,
                    "changed_files": [],
                    "blocker_evidence": [],
                    "unproven_runtime_gaps": [summary],
                }
                write_json(run_dir / RESULT_FILE, automation_result)
                write_summary(run_dir, automation_result)
                classify_and_update_state("refined", summary, task, backlog, active, status, automation_result)
                write_data(BACKLOG, backlog)
                write_data(STATUS, status)
                print_result("REFINED", summary, f"Reapply or restore the task changes in {target_repo}, then rerun python3 scripts/automate_task_loop.py.")
                return 1
    else:
        executor_result = run_shell(
            plan["executor_command"],
            ROOT,
            shell_executable=shell_executable,
            timeout=int(executor_config.get("timeout_seconds", 1800)),
        )
        write_step(run_dir, "executor", executor_result)
        steps.append({
            "name": "executor",
            "outcome": "passed" if executor_result["passed"] else "blocked",
            "detail": executor_result["stderr"] or executor_result["stdout"],
            "command": executor_result["command"],
        })
        if not executor_result["passed"]:
            summary = "Executor command failed before local validation."
            blocker_evidence.append(executor_result["stderr"] or executor_result["stdout"])
            automation_result = {
                "task_id": task["id"],
                "classification": "blocked",
                "finished_at": now_iso(),
                "summary": summary,
                "steps": steps,
                "changed_files": [],
                "blocker_evidence": blocker_evidence,
                "unproven_runtime_gaps": [summary],
            }
            write_json(run_dir / RESULT_FILE, automation_result)
            write_summary(run_dir, automation_result)
            classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result)
            write_data(BACKLOG, backlog)
            write_data(STATUS, status)
            print_result("BLOCKED", summary, "Fix the executor integration or switch back to human_gated mode before rerunning python3 scripts/automate_task_loop.py.")
            return 2
        after_executor = git_status_porcelain(target_repo, ignored_prefixes=ignored_git_paths)
        write_step(run_dir, "git_status_after_executor", after_executor)

    changed_files = after_executor.get("files", [])
    if retry_continuation and not changed_files:
        prior_vm_retry = prior_result_supports_vm_retry(run_dir)
        if prior_vm_retry:
            changed_files = list(prior_vm_retry.get("changed_files", []))
            continue_from_prior_vm_retry = True
            steps[-1]["detail"] = "No current dirty repo changes; continuing from prior post-push VM retry context."

    allowlisted, disallowed = changed_files_are_allowlisted(changed_files, active.get("allowlist", []))
    if not allowlisted:
        summary = "Executor changed files outside the task allowlist."
        automation_result = {
            "task_id": task["id"],
            "classification": "blocked",
            "finished_at": now_iso(),
            "summary": summary,
            "steps": steps + [{"name": "allowlist_check", "outcome": "blocked", "detail": "\n".join(disallowed)}],
            "changed_files": changed_files,
            "blocker_evidence": disallowed,
            "unproven_runtime_gaps": [summary],
        }
        write_json(run_dir / RESULT_FILE, automation_result)
        write_summary(run_dir, automation_result)
        classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result)
        write_data(BACKLOG, backlog)
        write_data(STATUS, status)
        print_result("BLOCKED", summary, f"Keep changes within the allowlist or adjust the task packet before rerunning. Current target repo: {target_repo}.")
        return 2

    if not changed_files:
        summary = f"Executor completed but no {target_kind} repo changes were detected."
        automation_result = {
            "task_id": task["id"],
            "classification": "refined",
            "finished_at": now_iso(),
            "summary": summary,
            "steps": steps + [{"name": "change_detection", "outcome": "refined", "detail": summary}],
            "changed_files": [],
            "blocker_evidence": [],
            "unproven_runtime_gaps": [summary],
        }
        write_json(run_dir / RESULT_FILE, automation_result)
        write_summary(run_dir, automation_result)
        classify_and_update_state("refined", summary, task, backlog, active, status, automation_result)
        write_data(BACKLOG, backlog)
        write_data(STATUS, status)
        if retry_continuation:
            next_action = f"Fix the task changes already present in {target_repo}, then rerun python3 scripts/automate_task_loop.py."
        else:
            next_action = f"Apply the packet in {target_repo} and rerun python3 scripts/automate_task_loop.py --resume if using human-gated execution."
        print_result("REFINED", summary, next_action)
        return 1

    if target_kind == "product" and local_validation_commands and validation_venv is None and not continue_from_prior_vm_retry:
        summary = "No product validation virtualenv found. Expected one of: .venv_validation, .venv, .venv_j1."
        automation_result = {
            "task_id": task["id"],
            "classification": "blocked",
            "finished_at": now_iso(),
            "summary": summary,
            "steps": steps + [{"name": "local_validation_environment", "outcome": "blocked", "detail": summary}],
            "changed_files": changed_files,
            "blocker_evidence": [summary],
            "unproven_runtime_gaps": [summary],
        }
        write_json(run_dir / RESULT_FILE, automation_result)
        write_summary(run_dir, automation_result)
        classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result)
        write_data(BACKLOG, backlog)
        write_data(STATUS, status)
        print_result("BLOCKED", summary, f"Create one of {target_repo}/.venv_validation, {target_repo}/.venv, or {target_repo}/.venv_j1, then rerun python3 scripts/automate_task_loop.py.")
        return 2

    if not continue_from_prior_vm_retry:
        local_results: list[dict[str, Any]] = []
        local_passed = True
        for command in prepared_validation_commands:
            result = run_shell(command, target_repo, shell_executable=shell_executable)
            local_results.append(result)
            if not result["passed"]:
                local_passed = False
        write_step(
            run_dir,
            "local_validation",
            {
                "results": local_results,
                "passed": local_passed,
                "venv_path": str(validation_venv) if validation_venv else None,
            },
        )
        steps.append({
            "name": "local_validation",
            "outcome": "passed" if local_passed else "refined",
            "detail": "All local verification commands passed." if local_passed else "At least one local verification command failed.",
        })
        if not local_passed:
            summary = "Local validation failed after executor changes."
            automation_result = {
                "task_id": task["id"],
                "classification": "refined",
                "finished_at": now_iso(),
                "summary": summary,
                "steps": steps,
                "changed_files": changed_files,
                "blocker_evidence": [],
                "unproven_runtime_gaps": [summary],
            }
            write_json(run_dir / RESULT_FILE, automation_result)
            write_summary(run_dir, automation_result)
            classify_and_update_state("refined", summary, task, backlog, active, status, automation_result)
            write_data(BACKLOG, backlog)
            write_data(STATUS, status)
            if retry_continuation:
                next_action = f"Inspect local validation output in {run_dir / RESULT_FILE}, fix the current task changes in {target_repo}, then rerun python3 scripts/automate_task_loop.py."
            else:
                next_action = f"Inspect local validation output in {run_dir / RESULT_FILE}, fix the issue, then rerun python3 scripts/automate_task_loop.py."
            print_result("REFINED", summary, next_action)
            return 1

        git_add = run_argv(["git", "add", "-A"], target_repo)
        commit_message = render_template(git_config.get("commit_message_template"), context) or f"{task['id']}: {task['title']}"
        git_commit = run_argv(["git", "commit", "-m", commit_message], target_repo)
        git_push = run_shell(
            render_template(git_config.get("push_command"), context) or "git push",
            target_repo,
            shell_executable=shell_executable,
        )
        write_step(run_dir, "git", {"add": git_add, "commit": git_commit, "push": git_push})
        steps.append({
            "name": "git",
            "outcome": "passed" if git_add["passed"] and git_commit["passed"] and git_push["passed"] else "blocked",
            "detail": git_push["stderr"] or git_commit["stderr"] or git_add["stderr"],
        })
        if not (git_add["passed"] and git_commit["passed"] and git_push["passed"]):
            summary = "Git add/commit/push failed after local validation passed."
            blocker_evidence.extend([
                git_add["stderr"] or git_add["stdout"],
                git_commit["stderr"] or git_commit["stdout"],
                git_push["stderr"] or git_push["stdout"],
            ])
            automation_result = {
                "task_id": task["id"],
                "classification": "blocked",
                "finished_at": now_iso(),
                "summary": summary,
                "steps": steps,
                "changed_files": changed_files,
                "blocker_evidence": [item for item in blocker_evidence if item],
                "unproven_runtime_gaps": [summary],
            }
            write_json(run_dir / RESULT_FILE, automation_result)
            write_summary(run_dir, automation_result)
            classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result)
            write_data(BACKLOG, backlog)
            write_data(STATUS, status)
            print_result("BLOCKED", summary, f"Inspect git output in {run_dir / RESULT_FILE} and repair repo/push state before rerunning python3 scripts/automate_task_loop.py.")
            return 2

    vm_passed = True
    if use_vm_flow:
        ssh_target = vm_config["ssh_target"]
        ssh_options = list(vm_config.get("ssh_options", []))
        vm_pull_command = f"cd {shlex.quote(str(vm_repo))} && {plan['vm_pull_command']}"
        vm_pull = ssh_command(ssh_target, ssh_options, vm_pull_command, ROOT)
        vm_results = [vm_pull]
        vm_passed = vm_pull["passed"]
        if vm_passed:
            for command in plan["vm_commands"]:
                remote = f"cd {shlex.quote(str(vm_repo))} && {command}"
                result = ssh_command(ssh_target, ssh_options, remote, ROOT)
                vm_results.append(result)
                if not result["passed"]:
                    vm_passed = False
                    break
        write_step(run_dir, "vm_validation", {"results": vm_results, "passed": vm_passed})
        steps.append({
            "name": "vm_validation",
            "outcome": "accepted" if vm_passed else "refined",
            "detail": "All VM validation commands passed." if vm_passed else "At least one VM validation command failed.",
        })
        classification = "accepted" if vm_passed else "refined"
        summary = (
            "Automated loop completed with VM validation success."
            if vm_passed
            else "VM validation failed after local validation and git push succeeded."
        )
    else:
        classification = "accepted"
        summary = "Automated loop completed with builder-side local validation success."
    automation_result = {
        "task_id": task["id"],
        "classification": classification,
        "finished_at": now_iso(),
        "summary": summary,
        "steps": steps,
        "changed_files": changed_files,
        "blocker_evidence": [],
        "unproven_runtime_gaps": [] if vm_passed else [summary],
    }
    write_json(run_dir / RESULT_FILE, automation_result)
    write_summary(run_dir, automation_result)
    classify_and_update_state(classification, summary, task, backlog, active, status, automation_result)
    write_data(BACKLOG, backlog)
    write_data(STATUS, status)
    if classification == "accepted":
        print_result("ACCEPTED", summary, "Review automation_summary.md for evidence and proceed to the next task.")
    else:
        print_result("REFINED", summary, f"Inspect {run_dir / RESULT_FILE} for VM validation details, then rerun once the issue is fixed.")
    return 0 if vm_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
