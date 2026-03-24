#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from common import builder_root, load_data, write_data

ROOT = builder_root()
ACTIVE = ROOT / "active_task.yml"
STATUS = ROOT / "status.yml"


def main() -> int:
    active = load_data(ACTIVE)
    status = load_data(STATUS)

    if not active.get("task_id"):
        print("NO_ACTIVE_TASK")
        return 1

    if active.get("state") == "implementing":
        print(f"ALREADY_IMPLEMENTING {active['task_id']}")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    active["state"] = "implementing"
    active["handed_to_codex_at"] = now
    status["state"] = "implementing"
    status["active_task_id"] = active["task_id"]
    status["last_run_at"] = now

    write_data(ACTIVE, active)
    write_data(STATUS, status)
    print(f"MARKED_IMPLEMENTING {active['task_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
