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

LOOP_MODE_SINGLE = "single-run"
LOOP_MODE_UNTIL_FAILURE = "until-failure"
LOOP_MODE_LABELS = {
    LOOP_MODE_SINGLE: "single-run",
    LOOP_MODE_UNTIL_FAILURE: "until-failure",
}
STOP_CONDITIONS = [
    "task blocks",
    "operator approval required",
    "synthesis eval fails",
    "clean-worktree or auth precondition fails",
    "no runnable tasks remain",
    "operator interrupts",
]


def _icon(status: str) -> str:
    return {
        "complete": "[x]",
        "current": "[>]",
        "failed": "[!]",
        "pending": "[ ]",
        "skipped": "[-]",
    }.get(status, "[ ]")


def toggle_loop_mode(current: str) -> str:
    return LOOP_MODE_UNTIL_FAILURE if current == LOOP_MODE_SINGLE else LOOP_MODE_SINGLE


def _event_prefix(item: dict[str, Any]) -> str:
    emphasis = str(item.get("emphasis") or "normal")
    if emphasis == "critical":
        return "[BLOCKED]"
    if emphasis == "success":
        return "[ACCEPTED]"
    if emphasis == "attention":
        return "[ACTION]"
    return "[EVENT]"


def selector_options(snapshot: dict[str, Any], kind: str) -> tuple[list[dict[str, Any]], str]:
    items = list((snapshot.get("selector_items") or {}).get(kind, []))
    if kind == "proposals":
        empty = "No draft proposals are awaiting approval."
    elif kind == "syntheses":
        empty = "No synthesized draft entries are ready to apply."
    elif kind == "blockers":
        empty = "No open blockers are available to inspect."
    else:
        empty = "No items available."
    return items, empty


def resolve_selector_choice(options: list[dict[str, Any]], raw_choice: str) -> dict[str, Any] | None:
    choice = str(raw_choice or "").strip()
    if not choice:
        return None
    if choice.isdigit():
        index = int(choice) - 1
        if 0 <= index < len(options):
            return options[index]
    for item in options:
        if choice == str(item.get("id")):
            return item
    return None


def _task_by_id(snapshot: dict[str, Any], task_id: str | None) -> dict[str, Any] | None:
    if not task_id:
        return None
    for task in snapshot.get("backlog", {}).get("tasks", []):
        if str(task.get("id")) == str(task_id):
            return task
    return None


def _ready_task_requires_product_auth(snapshot: dict[str, Any]) -> bool:
    next_task_id = (snapshot.get("backlog_diagnostics") or {}).get("next_selected_task_id")
    task = _task_by_id(snapshot, next_task_id)
    if not task:
        return False
    repo_path = str(task.get("repo_path") or "")
    return repo_path.endswith("/jorb") or "/jorb" in repo_path


def _run_repo_command(
    cmd: list[str],
    *,
    repo_root: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> dict[str, Any]:
    env = os.environ.copy()
    env["JORB_BUILDER_ROOT"] = str(repo_root)
    completed = runner(cmd, cwd=str(repo_root), text=True, capture_output=True, env=env)
    return {
        "ok": completed.returncode == 0,
        "message": (completed.stdout or completed.stderr or "").strip(),
        "command": cmd,
        "returncode": completed.returncode,
    }


def run_loop_mode(
    mode: str,
    *,
    root: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    snapshot_builder: Callable[[Path | None], dict[str, Any]] = build_operator_snapshot,
    max_iterations: int | None = None,
) -> dict[str, Any]:
    repo_root = Path(root or ROOT).expanduser().resolve()
    iterations = 0
    history: list[dict[str, Any]] = []
    while True:
        snapshot = snapshot_builder(repo_root)
        backlog_diag = snapshot.get("backlog_diagnostics") or {}
        proposals = snapshot.get("proposals") or {}
        synthesis = snapshot.get("synthesis") or {}
        if snapshot.get("latest_blocker"):
            return {
                "ok": False,
                "message": snapshot.get("next_recommended_action") or "Blocked task requires operator intervention.",
                "stop_reason": "blocked",
                "iterations": iterations,
                "history": history,
            }
        if synthesis.get("eval_blocked_entries", 0):
            return {
                "ok": False,
                "message": "Synthesis eval is blocking at least one drafted entry; inspect synthesized backlog state.",
                "stop_reason": "synthesis_eval_failed",
                "iterations": iterations,
                "history": history,
            }
        if not backlog_diag.get("next_selected_task_id"):
            if proposals.get("draft_count", 0):
                return {
                    "ok": True,
                    "message": "No runnable tasks remain; operator approval is required for draft proposals.",
                    "stop_reason": "operator_approval_required",
                    "iterations": iterations,
                    "history": history,
                }
            return {
                "ok": True,
                "message": "No runnable tasks remain under current canonical backlog truth.",
                "stop_reason": "no_runnable_tasks_remain",
                "iterations": iterations,
                "history": history,
            }
        if _ready_task_requires_product_auth(snapshot):
            auth_result = _run_repo_command([sys.executable, str(AUTOMATE_TASK_LOOP), "--check-auth"], repo_root=repo_root, runner=runner)
            history.append({"phase": "check-auth", **auth_result})
            auth_text = auth_result.get("message", "")
            if auth_result.get("returncode") not in {0, None} or "interactive_auth_required" in auth_text or "run_interactive: true" in auth_text:
                return {
                    "ok": False,
                    "message": auth_text or "Authentication or SSH precondition failed.",
                    "stop_reason": "auth_precondition_failed",
                    "iterations": iterations,
                    "history": history,
                }
        run_result = _run_repo_command([sys.executable, str(AUTOMATE_TASK_LOOP)], repo_root=repo_root, runner=runner)
        history.append({"phase": "run", **run_result})
        iterations += 1
        if mode == LOOP_MODE_SINGLE:
            stop_reason = "single_run_complete" if run_result.get("ok") else "single_run_failed"
            return {
                "ok": bool(run_result.get("ok")),
                "message": run_result.get("message") or "Single-run execution finished.",
                "stop_reason": stop_reason,
                "iterations": iterations,
                "history": history,
            }
        if max_iterations is not None and iterations >= max_iterations:
            return {
                "ok": True,
                "message": f"Stopped after {iterations} run(s) because max_iterations was reached.",
                "stop_reason": "max_iterations_reached",
                "iterations": iterations,
                "history": history,
            }


def render_operator_view(snapshot: dict[str, Any], *, width: int = 120, height: int = 40, loop_mode: str = LOOP_MODE_SINGLE) -> str:
    backlog_diag = snapshot["backlog_diagnostics"]
    artifact = snapshot["artifact_panel"]
    eval_result = snapshot["eval_result"]
    proposals = snapshot["proposals"]
    synthesis = snapshot["synthesis"]
    latest_blocker = snapshot["latest_blocker"] or {}
    lines: list[str] = []
    lines.append("JORB Builder Operator TUI")
    lines.append("=" * min(width, 80))
    lines.append(f"MODE >>> {LOOP_MODE_LABELS.get(loop_mode, loop_mode)}   STATUS >>> {snapshot['status'].get('state')}   ACTIVE >>> {snapshot['active'].get('task_id') or 'none'}")
    lines.append("STOP POLICY >>> " + ", ".join(STOP_CONDITIONS))
    lines.append("NEXT ACTION >>> " + (snapshot.get("next_recommended_action") or "none"))
    lines.append(f"Blocker: {snapshot['ledger'].get('current_blocker') or latest_blocker.get('diagnosis') or 'none'}")
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
            lines.append(f"{item.get('at') or 'unknown'} | {_event_prefix(item)} | {item.get('summary')}{detail}{recommendation}")
    lines.append("")
    lines.append("Actions: x run | m mode | r refresh | b blockers | p proposals | a syntheses | t retry blocked | o latest run dir | i artifacts | q quit")
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
    if action == "run_single_cycle":
        return run_loop_mode(LOOP_MODE_SINGLE, root=repo_root, runner=runner)
    if action == "run_until_failure":
        return run_loop_mode(LOOP_MODE_UNTIL_FAILURE, root=repo_root, runner=runner)
    if action == "retry_blocked_task":
        return _run_repo_command([sys.executable, str(AUTOMATE_TASK_LOOP), "--repair-state"], repo_root=repo_root, runner=runner)
    elif action == "approve_proposal":
        if not identifier:
            return {"ok": False, "message": "approve_proposal requires a proposal id."}
        return _run_repo_command([sys.executable, str(FEEDBACK_ENGINE), "--review", identifier, "accepted", "--note", note or "approved from operator_tui"], repo_root=repo_root, runner=runner)
    elif action == "apply_synthesized_entry":
        if not identifier:
            return {"ok": False, "message": "apply_synthesized_entry requires a synthesis id."}
        return _run_repo_command([sys.executable, str(BACKLOG_SYNTHESIS), "--apply", identifier], repo_root=repo_root, runner=runner)
    else:
        return {"ok": False, "message": f"Unknown action: {action}"}


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


def _choose_selector(stdscr: Any, snapshot: dict[str, Any], kind: str, title: str) -> dict[str, Any] | None:
    options, empty_message = selector_options(snapshot, kind)
    if not options:
        height, width = stdscr.getmaxyx()
        stdscr.addstr(height - 1, 0, empty_message[: max(1, width - 1)])
        stdscr.refresh()
        return None
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    stdscr.addstr(0, 0, title[: max(1, width - 1)])
    stdscr.addstr(1, 0, "-" * min(width - 1, 80))
    for idx, item in enumerate(options, start=1):
        line = f"{idx}. {item.get('label')} [{item.get('id')}]"
        if item.get("detail"):
            line += f" :: {item['detail']}"
        stdscr.addstr(min(idx + 1, height - 3), 0, line[: max(1, width - 1)])
    choice = _prompt(stdscr, "Select number (blank to cancel):")
    return resolve_selector_choice(options, choice)


def _tui(stdscr: Any) -> int:
    curses.curs_set(0)
    stdscr.nodelay(False)
    message = "Operator view loaded."
    snapshot = build_operator_snapshot(ROOT)
    loop_mode = LOOP_MODE_SINGLE
    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        body = render_operator_view(snapshot, width=width, height=height, loop_mode=loop_mode)
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
        elif key == ord("m"):
            loop_mode = toggle_loop_mode(loop_mode)
            message = f"Loop mode set to {LOOP_MODE_LABELS[loop_mode]}."
        elif key == ord("x"):
            action = "run_until_failure" if loop_mode == LOOP_MODE_UNTIL_FAILURE else "run_single_cycle"
            result = run_operator_action(action, root=ROOT)
            snapshot = build_operator_snapshot(ROOT)
            message = f"{LOOP_MODE_LABELS[loop_mode]}: {result['message']}"
        elif key == ord("b"):
            blocker = _choose_selector(stdscr, snapshot, "blockers", "Open blockers")
            if blocker:
                message = blocker.get("detail") or blocker.get("label") or blocker.get("id") or "Blocker selected."
            else:
                message = "No blocker selected."
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
            proposal = _choose_selector(stdscr, snapshot, "proposals", "Draft proposals awaiting approval")
            if proposal:
                result = run_operator_action("approve_proposal", root=ROOT, identifier=str(proposal.get("id")))
                snapshot = build_operator_snapshot(ROOT)
                message = result["message"]
            else:
                message = "No proposal selected."
        elif key == ord("a"):
            synthesis = _choose_selector(stdscr, snapshot, "syntheses", "Synthesized draft entries")
            if synthesis:
                result = run_operator_action("apply_synthesized_entry", root=ROOT, identifier=str(synthesis.get("id")))
                snapshot = build_operator_snapshot(ROOT)
                message = result["message"]
            else:
                message = "No synthesized entry selected."
        else:
            message = "Actions: x run | m mode | r refresh | b blockers | p proposals | a syntheses | t retry blocked | o latest run dir | i artifacts | q quit"


def main() -> int:
    parser = argparse.ArgumentParser(description="Terminal operator interface for canonical builder supervision truth.")
    parser.add_argument("--once", action="store_true", help="Render a single snapshot and exit.")
    parser.add_argument("--action", choices=["refresh", "inspect_blocker", "approve_proposal", "apply_synthesized_entry", "retry_blocked_task", "latest_run_dir", "inspect_artifacts", "run_single_cycle", "run_until_failure"])
    parser.add_argument("--loop-mode", choices=[LOOP_MODE_SINGLE, LOOP_MODE_UNTIL_FAILURE], default=LOOP_MODE_SINGLE)
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
        print(render_operator_view(snapshot, loop_mode=args.loop_mode))
        return 0
    return curses.wrapper(_tui)


if __name__ == "__main__":
    raise SystemExit(main())
