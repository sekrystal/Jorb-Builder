#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import argparse
from common import builder_root, load_data, write_data

ROOT = builder_root()
BACKLOG = ROOT / "backlog.yml"
STATUS = ROOT / "status.yml"
ACTIVE = ROOT / "active_task.yml"
MEMORY = ROOT / "builder_memory.md"


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
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    backlog = load_data(BACKLOG)
    status = load_data(STATUS)
    active = load_data(ACTIVE)

    task_id = active.get("task_id")
    if not task_id:
        print("NO_ACTIVE_TASK")
        return 1

    target = None
    for task in backlog.get("tasks", []):
        if task.get("id") == task_id:
            target = task
            break
    if target is None:
        print(f"MISSING_BACKLOG_TASK {task_id}")
        return 1

    if target.get("status") not in {"done", "blocked"}:
        if int(target.get("retries_used", 0)) > 0:
            target["status"] = "retry_ready"
        else:
            target["status"] = "ready"

    now = datetime.now(timezone.utc).isoformat()
    status["state"] = "idle"
    status["active_task_id"] = None
    status["last_task_id"] = task_id
    status["last_result"] = "abandoned"
    status["last_run_at"] = now

    with MEMORY.open("a", encoding="utf-8") as handle:
        handle.write(f"\n- {task_id} was abandoned manually at {now}. Reason: {args.reason}\n")

    write_data(BACKLOG, backlog)
    write_data(STATUS, status)
    write_data(ACTIVE, reset_active())
    print(f"ABANDONED {task_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
