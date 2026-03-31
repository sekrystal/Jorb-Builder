#!/usr/bin/env python3
from __future__ import annotations

import argparse
import curses
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable

from operator_state import build_operator_snapshot

ROOT = Path(__file__).resolve().parents[1]
FEEDBACK_ENGINE = ROOT / "scripts" / "feedback_engine.py"
BACKLOG_SYNTHESIS = ROOT / "scripts" / "backlog_synthesis.py"
AUTOMATE_TASK_LOOP = ROOT / "scripts" / "automate_task_loop.py"


def _icon(status: str) -> str:
    return {
        "complete": "[x]",
        "current": "[>]",
        "failed": "[!]",
        "pending": "[ ]",
        "skipped": "[-]",
    }.get(status, "[ ]")


def render_operator_view(snapshot: dict[str, Any], *, width: int = 120, height: int = 40) -> str:
    backlog_diag = snapshot["backlog_diagnostics"]
    artifact = snapshot["artifact_panel"]
    eval_result = snapshot["eval_result"]
    proposals = snapshot["proposals"]
    synthesis = snapshot["synthesis"]
    latest_blocker = snapshot["latest_blocker"] or {}
    lines: list[str] = []
    lines.append("JORB Builder Operator TUI")
    lines.append("=" * min(width, 80))
    lines.append(f"Run state: {snapshot['status'].get('state')}   Active: {snapshot['active'].get('task_id') or 'none'}   Last: {snapshot['status'].get('last_task_id') or 'none'}")
    lines.append(f"Blocker: {snapshot['ledger'].get('current_blocker') or latest_blocker.get('diagnosis') or 'none'}")
    lines.append(f"Next action: {snapshot.get('next_recommended_action') or 'none'}")
    lines.append(f"Latest run dir: {snapshot.get('latest_run_dir') or 'none'}")
    lines.append("")
    lines.append("Stage progress")
    lines.append("-" * min(width, 80))
    for item in snapshot["stage_progress"]:
        lines.append(f"{_icon(item['status'])} {item['label']}")
    lines.append("")
    lines.append("Artifacts and eval")
    lines.append("-" * min(width, 80))
    lines.append(f"Expected: {', '.join(artifact.get('expected', [])) or 'none'}")
    lines.append(f"Present : {', '.join(artifact.get('present', [])) or 'none'}")
    lines.append(f"Missing : {', '.join(artifact.get('missing', [])) or 'none'}")
    lines.append(f"Eval    : score={eval_result.get('overall_score', 'n/a')} threshold={eval_result.get('threshold', 'n/a')} passed={eval_result.get('passed', 'n/a')}")
    lines.append(f"Judge   : {snapshot.get('judge_result') or 'none'}")
    lines.append("")
    lines.append("Queue and backlog evolution")
    lines.append("-" * min(width, 80))
    lines.append(f"Ready tasks      : {', '.join(backlog_diag.get('ready_task_ids', [])) or 'none'}")
    lines.append(f"Blocked tasks    : {', '.join(backlog_diag.get('blocked_task_ids', [])) or 'none'}")
    lines.append(f"Accepted proposals: {proposals.get('accepted_count', 0)}")
    lines.append(f"Draft proposals  : {proposals.get('draft_count', 0)}")
    lines.append(f"Synthesized      : {synthesis.get('entry_count', 0)} (applied={synthesis.get('applied_count', 0)})")
    lines.append(f"Next execution   : {synthesis.get('next_execution_target') or 'none'}")
    lines.append("")
    lines.append("Event feed")
    lines.append("-" * min(width, 80))
    if not snapshot["event_feed"]:
        lines.append("No canonical events recorded yet.")
    else:
        for item in snapshot["event_feed"][: min(10, max(3, height - 28))]:
            recommendation = f" -> {item['recommendation']}" if item.get("recommendation") else ""
            detail = f" :: {item['detail']}" if item.get("detail") else ""
            lines.append(f"{item.get('at') or 'unknown'} | {item.get('source')} | {item.get('summary')}{detail}{recommendation}")
    lines.append("")
    lines.append("Actions: r refresh | b blocker | p approve proposal | a apply synthesis | t retry blocked | o latest run dir | i artifacts | q quit")
    return "\n".join(line[: max(20, width - 1)] for line in lines)


def run_operator_action(
    action: str,
    *,
    root: Path | None = None,
    identifier: str | None = None,
    note: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    repo_root = Path(root or ROOT).expanduser().resolve()
    snapshot = build_operator_snapshot(repo_root)
    if action == "refresh":
        return {"ok": True, "message": "Refreshed operator snapshot.", "snapshot": snapshot}
    if action == "inspect_blocker":
        blocker = snapshot.get("latest_blocker") or {}
        return {"ok": True, "message": blocker.get("diagnosis") or "No open blocker.", "blocker": blocker}
    if action == "latest_run_dir":
        return {"ok": True, "message": snapshot.get("latest_run_dir") or "No run directory available.", "path": snapshot.get("latest_run_dir")}
    if action == "inspect_artifacts":
        artifact = snapshot.get("artifact_panel") or {}
        return {
            "ok": True,
            "message": "Artifact panel loaded.",
            "artifact_panel": artifact,
            "path": snapshot.get("latest_run_dir"),
        }
    if action == "retry_blocked_task":
        cmd = [sys.executable, str(AUTOMATE_TASK_LOOP), "--repair-state"]
    elif action == "approve_proposal":
        if not identifier:
            return {"ok": False, "message": "approve_proposal requires a proposal id."}
        cmd = [sys.executable, str(FEEDBACK_ENGINE), "--review", identifier, "accepted", "--note", note or "approved from operator_tui"]
    elif action == "apply_synthesized_entry":
        if not identifier:
            return {"ok": False, "message": "apply_synthesized_entry requires a synthesis id."}
        cmd = [sys.executable, str(BACKLOG_SYNTHESIS), "--apply", identifier]
    else:
        return {"ok": False, "message": f"Unknown action: {action}"}
    env = os.environ.copy()
    env["JORB_BUILDER_ROOT"] = str(repo_root)
    completed = runner(cmd, cwd=str(repo_root), text=True, capture_output=True, env=env)
    return {
        "ok": completed.returncode == 0,
        "message": (completed.stdout or completed.stderr or "").strip(),
        "command": cmd,
        "returncode": completed.returncode,
    }


def _prompt(stdscr: Any, label: str) -> str:
    height, width = stdscr.getmaxyx()
    stdscr.addstr(height - 2, 0, " " * max(1, width - 1))
    stdscr.addstr(height - 2, 0, label[: max(1, width - 1)])
    stdscr.refresh()
    curses.echo()
    try:
        value = stdscr.getstr(height - 1, 0).decode("utf-8").strip()
    finally:
        curses.noecho()
    return value


def _tui(stdscr: Any) -> int:
    curses.curs_set(0)
    stdscr.nodelay(False)
    message = "Operator view loaded."
    snapshot = build_operator_snapshot(ROOT)
    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        body = render_operator_view(snapshot, width=width, height=height)
        for idx, line in enumerate(body.splitlines()[: max(1, height - 2)]):
            stdscr.addstr(idx, 0, line)
        stdscr.addstr(height - 1, 0, message[: max(1, width - 1)])
        stdscr.refresh()
        key = stdscr.getch()
        if key in {ord("q"), 27}:
            return 0
        if key == ord("r"):
            result = run_operator_action("refresh", root=ROOT)
            snapshot = result["snapshot"]
            message = result["message"]
        elif key == ord("b"):
            result = run_operator_action("inspect_blocker", root=ROOT)
            message = result["message"]
        elif key == ord("o"):
            result = run_operator_action("latest_run_dir", root=ROOT)
            message = result["message"]
        elif key == ord("i"):
            result = run_operator_action("inspect_artifacts", root=ROOT)
            panel = result.get("artifact_panel") or {}
            message = f"Artifacts present: {', '.join(panel.get('present', [])) or 'none'}"
        elif key == ord("t"):
            result = run_operator_action("retry_blocked_task", root=ROOT)
            snapshot = build_operator_snapshot(ROOT)
            message = result["message"] or ("Retry repair passed." if result["ok"] else "Retry repair failed.")
        elif key == ord("p"):
            proposal_id = _prompt(stdscr, "Proposal id to approve:")
            result = run_operator_action("approve_proposal", root=ROOT, identifier=proposal_id)
            snapshot = build_operator_snapshot(ROOT)
            message = result["message"]
        elif key == ord("a"):
            synthesis_id = _prompt(stdscr, "Synthesis id to apply:")
            result = run_operator_action("apply_synthesized_entry", root=ROOT, identifier=synthesis_id)
            snapshot = build_operator_snapshot(ROOT)
            message = result["message"]
        else:
            message = "Actions: r refresh | b blocker | p approve proposal | a apply synthesis | t retry blocked | o latest run dir | i artifacts | q quit"


def main() -> int:
    parser = argparse.ArgumentParser(description="Terminal operator interface for canonical builder supervision truth.")
    parser.add_argument("--once", action="store_true", help="Render a single snapshot and exit.")
    parser.add_argument("--action", choices=["refresh", "inspect_blocker", "approve_proposal", "apply_synthesized_entry", "retry_blocked_task", "latest_run_dir", "inspect_artifacts"])
    parser.add_argument("--id", default=None)
    parser.add_argument("--note", default=None)
    args = parser.parse_args()

    if args.action:
        result = run_operator_action(args.action, root=ROOT, identifier=args.id, note=args.note)
        if "snapshot" in result:
            result = dict(result)
            result["snapshot"] = {
                "next_recommended_action": result["snapshot"].get("next_recommended_action"),
                "ready_task_ids": result["snapshot"]["backlog_diagnostics"].get("ready_task_ids", []),
            }
        print(result["message"])
        return 0 if result.get("ok") else 1
    snapshot = build_operator_snapshot(ROOT)
    if args.once or not sys.stdout.isatty():
        print(render_operator_view(snapshot))
        return 0
    return curses.wrapper(_tui)


if __name__ == "__main__":
    raise SystemExit(main())
