#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
from common import builder_root, load_data, write_data

ROOT = builder_root()
CONFIG = ROOT / "config.yml"
BACKLOG = ROOT / "backlog.yml"
STATUS = ROOT / "status.yml"
ACTIVE = ROOT / "active_task.yml"
MEMORY = ROOT / "builder_memory.md"
TASK_HISTORY = ROOT / "task_history"
BLOCKERS = ROOT / "blockers"


def find_task(backlog: dict, task_id: str) -> dict:
    for task in backlog.get("tasks", []):
        if task.get("id") == task_id:
            return task
    raise KeyError(task_id)


def write_history(task: dict, active: dict, verifier: dict, codex_result_text: str | None) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    path = TASK_HISTORY / f"{timestamp}-{task['id']}.yml"
    payload = {
        "task_id": task["id"],
        "title": task["title"],
        "status": "passed" if verifier["passed"] else "failed",
        "attempt": active.get("attempt", 1),
        "started_at": active.get("started_at"),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "prompt": active.get("prompt_file"),
        "files_changed": [],
        "commands_run": [result["command"] for result in verifier.get("results", [])],
        "results": ["PASS" if verifier["passed"] else "FAIL"],
        "acceptance_met": task.get("acceptance", []) if verifier["passed"] else [],
        "acceptance_unmet": [] if verifier["passed"] else task.get("acceptance", []),
        "blocker_opened": None,
        "notes": [codex_result_text] if codex_result_text else [],
        "unproven_runtime_gaps": [],
    }
    write_data(path, payload)
    return path


def append_memory(line: str) -> None:
    with MEMORY.open("a", encoding="utf-8") as handle:
        handle.write(f"\n- {line}\n")


def open_blocker(task: dict, verifier: dict) -> Path:
    path = BLOCKERS / f"BLK-{task['id']}.yml"
    payload = {
        "id": f"BLK-{task['id']}",
        "title": f"Task {task['id']} blocked after retries",
        "severity": "high",
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "related_tasks": [task["id"]],
        "status": "open",
        "symptoms": [result["command"] for result in verifier.get("results", []) if not result["passed"]],
        "diagnosis": "Verification continued to fail after retry budget was exhausted.",
        "evidence": [result["stderr"] or result["stdout"] for result in verifier.get("results", []) if not result["passed"]],
        "next_actions": ["Inspect verifier output and narrow a manual debug task."],
        "human_needed": True,
    }
    write_data(path, payload)
    return path


def reset_active() -> dict:
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
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-result-file", default=None)
    args = parser.parse_args()

    config = load_data(CONFIG)
    backlog = load_data(BACKLOG)
    status = load_data(STATUS)
    active = load_data(ACTIVE)
    if not active.get("task_id") or not active.get("run_log_dir"):
        print("NO_ACTIVE_TASK_TO_RECORD")
        return 1

    verifier_path = Path(active["run_log_dir"]) / "verifier.json"
    if not verifier_path.exists():
        print("MISSING_VERIFIER_RESULT")
        return 1

    verifier = json.loads(verifier_path.read_text(encoding="utf-8"))
    task = find_task(backlog, active["task_id"])
    codex_result_text = None
    if args.codex_result_file and Path(args.codex_result_file).expanduser().exists():
        codex_result_text = Path(args.codex_result_file).expanduser().read_text(encoding="utf-8")

    max_retries = int(config["execution"]["max_retries_per_task"])
    if verifier["passed"]:
        task["status"] = "done"
        history_path = write_history(task, active, verifier, codex_result_text)
        status.setdefault("stats", {})
        status["state"] = "idle"
        status["last_task_id"] = task["id"]
        status["active_task_id"] = None
        status["last_result"] = "passed"
        status["last_run_at"] = datetime.now(timezone.utc).isoformat()
        status["stats"]["completed_tasks"] = int(status["stats"].get("completed_tasks", 0)) + 1
        append_memory(f"{task['id']} passed with deterministic verification. History: {history_path.name}")
        write_data(ACTIVE, reset_active())
        write_data(BACKLOG, backlog)
        write_data(STATUS, status)
        print(f"RECORDED_PASS {task['id']}")
        return 0

    task["retries_used"] = int(task.get("retries_used", 0)) + 1
    if task["retries_used"] <= max_retries:
        task["status"] = "retry_ready"
        active["state"] = "failed"
        active["failure_summary"] = "; ".join(
            result["command"] for result in verifier.get("results", []) if not result["passed"]
        )
        status.setdefault("stats", {})
        status["state"] = "retry_ready"
        status["last_task_id"] = task["id"]
        status["active_task_id"] = task["id"]
        status["last_result"] = "failed"
        status["last_run_at"] = datetime.now(timezone.utc).isoformat()
        status["stats"]["retry_ready_tasks"] = int(status["stats"].get("retry_ready_tasks", 0)) + 1
        append_memory(f"{task['id']} failed verification and moved to retry_ready (attempt {task['retries_used']}).")
        write_data(ACTIVE, active)
        write_data(BACKLOG, backlog)
        write_data(STATUS, status)
        print(f"RECORDED_RETRY {task['id']}")
        return 1

    task["status"] = "blocked"
    blocker_path = open_blocker(task, verifier)
    history_path = write_history(task, active, verifier, codex_result_text)
    status.setdefault("stats", {})
    status["state"] = "blocked"
    status["last_task_id"] = task["id"]
    status["active_task_id"] = None
    status["last_result"] = "blocked"
    status["last_run_at"] = datetime.now(timezone.utc).isoformat()
    status["stats"]["blocked_tasks"] = int(status["stats"].get("blocked_tasks", 0)) + 1
    append_memory(f"{task['id']} opened blocker {blocker_path.name} after exhausted retries. History: {history_path.name}")
    write_data(ACTIVE, reset_active())
    write_data(BACKLOG, backlog)
    write_data(STATUS, status)
    print(f"RECORDED_BLOCKER {task['id']} -> {blocker_path.name}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
