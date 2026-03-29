#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from common import (
    ACTIVE_TASK_STATES,
    builder_root,
    compute_backlog_diagnostics,
    load_data,
    load_validated_backlog,
    write_data,
)

ROOT = builder_root()
STATUS = ROOT / "status.yml"
ACTIVE = ROOT / "active_task.yml"


def main() -> int:
    backlog = load_validated_backlog()
    status = load_data(STATUS)
    active = load_data(ACTIVE)

    if backlog.get("errors"):
        print("BACKLOG_INVALID")
        for error in backlog["errors"]:
            print(f"- {error.get('code')}: {error.get('detail')}")
        return 1

    if active.get("task_id") and active.get("state") in ACTIVE_TASK_STATES:
        print(f"ACTIVE_TASK_ALREADY_SET {active['task_id']}")
        return 0

    diagnostics = compute_backlog_diagnostics(backlog)
    task_id = diagnostics.get("next_selected_task_id")
    task = next((entry for entry in backlog.get("tasks", []) if entry.get("id") == task_id), None)
    if not task:
        if diagnostics.get("selector_filtered_everything"):
            print("SELECTOR_FILTERED_EVERYTHING")
        else:
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
        "vm_verification_commands": task.get("vm_verification", []),
        "vm_bootstrap_commands": task.get("vm_bootstrap", []),
        "vm_cleanup_commands": task.get("vm_cleanup", []),
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
