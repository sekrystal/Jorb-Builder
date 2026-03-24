#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from common import builder_root, load_data, write_data

ROOT = builder_root()
BACKLOG = ROOT / "backlog.yml"
STATUS = ROOT / "status.yml"
ACTIVE = ROOT / "active_task.yml"
BLOCKERS_DIR = ROOT / "blockers"
READY_STATES = {"ready", "retry_ready"}
DONE_STATES = {"done", "accepted"}
ACTIVE_STATES = {"selected", "packet_rendered", "implementing", "verifying"}


def completed_ids(tasks: list[dict]) -> set[str]:
    return {task["id"] for task in tasks if task.get("status") in DONE_STATES}


def open_blocked_task_ids() -> set[str]:
    blocked: set[str] = set()
    if not BLOCKERS_DIR.exists():
        return blocked
    for file in sorted(BLOCKERS_DIR.glob("*.yml")):
        data = load_data(file)
        if data.get("status") != "open":
            continue
        for task_id in data.get("related_tasks", []):
            blocked.add(task_id)
    return blocked


def is_unblocked(task: dict, done: set[str], blocked_ids: set[str]) -> bool:
    if task.get("id") in blocked_ids:
        return False
    return all(dep in done for dep in task.get("depends_on", []))


def choose_task(tasks: list[dict]) -> dict | None:
    done = completed_ids(tasks)
    blocked_ids = open_blocked_task_ids()
    candidates = [
        task for task in tasks
        if task.get("status") in READY_STATES and is_unblocked(task, done, blocked_ids)
    ]
    candidates.sort(key=lambda task: (task.get("priority", 999), task.get("id", "")))
    return candidates[0] if candidates else None


def main() -> int:
    backlog = load_data(BACKLOG)
    status = load_data(STATUS)
    active = load_data(ACTIVE)

    if active.get("task_id") and active.get("state") in ACTIVE_STATES:
        print(f"ACTIVE_TASK_ALREADY_SET {active['task_id']}")
        return 0

    task = choose_task(backlog.get("tasks", []))
    if not task:
        print("NO_READY_TASK")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    active_payload = {
        "task_id": task["id"],
        "title": task["title"],
        "state": "selected",
        "attempt": int(task.get("retries_used", 0)) + 1,
        "started_at": now,
        "handed_to_codex_at": None,
        "prompt_file": None,
        "run_log_dir": None,
        "verification_commands": task.get("verification", []),
        "allowlist": task.get("allowlist", []),
        "failure_summary": None,
        "notes": [],
    }
    write_data(ACTIVE, active_payload)

    status["state"] = "task_selected"
    status["active_task_id"] = task["id"]
    status["last_run_at"] = now
    write_data(STATUS, status)

    print(f"SELECTED {task['id']}: {task['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
