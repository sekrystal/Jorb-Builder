#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess
from common import builder_root, load_data, write_data, product_repo_path

ROOT = builder_root()
ACTIVE = ROOT / "active_task.yml"
STATUS = ROOT / "status.yml"
RESULT_NAME = "verifier.json"


def run_command(command: str, cwd: Path) -> dict:
    process = subprocess.run(command, shell=True, cwd=str(cwd), capture_output=True, text=True)
    return {
        "command": command,
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "passed": process.returncode == 0,
    }


def main() -> int:
    active = load_data(ACTIVE)
    status = load_data(STATUS)
    if not active.get("task_id") or not active.get("run_log_dir"):
        print("NO_ACTIVE_TASK_TO_VERIFY")
        return 1

    product_repo = product_repo_path()
    if not product_repo.exists():
        print(f"MISSING_PRODUCT_REPO {product_repo}")
        return 2

    status["state"] = "verifying"
    status["active_task_id"] = active["task_id"]
    status["last_run_at"] = datetime.now(timezone.utc).isoformat()
    write_data(STATUS, status)

    run_dir = Path(active["run_log_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    results = []
    all_passed = True
    for command in active.get("verification_commands", []):
        result = run_command(command, product_repo)
        results.append(result)
        if not result["passed"]:
            all_passed = False

    payload = {
        "task_id": active["task_id"],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "passed": all_passed,
        "results": results,
    }
    (run_dir / RESULT_NAME).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("PASS" if all_passed else "FAIL")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
