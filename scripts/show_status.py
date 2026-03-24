#!/usr/bin/env python3
from __future__ import annotations

from common import builder_root, load_data

ROOT = builder_root()
BACKLOG = ROOT / "backlog.yml"
STATUS = ROOT / "status.yml"
ACTIVE = ROOT / "active_task.yml"
BLOCKERS = ROOT / "blockers"
TASK_HISTORY = ROOT / "task_history"


def main() -> int:
    backlog = load_data(BACKLOG)
    status = load_data(STATUS)
    active = load_data(ACTIVE)

    print("=== Jorb Builder Status ===")
    print(f"State: {status.get('state')}")
    print(f"State meaning: {(status.get('state_legend') or {}).get(status.get('state'), 'unknown')}")
    focus = status.get("roadmap_focus", {})
    print(f"Roadmap focus: {focus.get('milestone')} / {focus.get('theme')}")
    print(f"Active task: {active.get('task_id') or 'none'}")
    if active.get("task_id"):
        print(f"  Title: {active.get('title')}")
        print(f"  State: {active.get('state')}")
        print(f"  Attempt: {active.get('attempt')}")
        print(f"  Started at: {active.get('started_at')}")
        print(f"  Handed to Codex at: {active.get('handed_to_codex_at')}")
        print(f"  Prompt file: {active.get('prompt_file')}")

    print("\nNext ready tasks:")
    ready = [task for task in backlog.get("tasks", []) if task.get("status") in {"ready", "retry_ready"}]
    ready.sort(key=lambda item: (item.get("priority", 999), item.get("id", "")))
    if not ready:
        print("- none")
    for task in ready[:5]:
        print(f"- {task['id']} [{task['status']}] p{task.get('priority', '?')}: {task['title']}")

    print("\nOpen blockers:")
    blocker_files = sorted(BLOCKERS.glob("*.yml")) if BLOCKERS.exists() else []
    open_count = 0
    for file in blocker_files:
        data = load_data(file)
        if data.get("status") == "open":
            open_count += 1
            print(f"- {data.get('id')}: {data.get('title')}")
    if open_count == 0:
        print("- none")

    print("\nRecent completions:")
    history_files = sorted(TASK_HISTORY.glob("*.yml"), reverse=True)[:5]
    if not history_files:
        print("- none")
    for file in history_files:
        data = load_data(file)
        print(f"- {data.get('task_id')}: {data.get('status')} at {data.get('completed_at')}")

    print("\nStats:")
    for key, value in (status.get("stats") or {}).items():
        print(f"- {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
