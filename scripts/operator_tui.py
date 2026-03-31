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


def _status_badge(label: str) -> str:
    return {
        "Running": "[RUNNING]",
        "Waiting on Codex": "[CODEX]",
        "Waiting on Validation": "[VALIDATION]",
        "Blocked": "[BLOCKED]",
        "Waiting on Approval": "[APPROVAL]",
        "Waiting on Dependencies": "[DEPENDENCIES]",
        "Exhausted": "[EXHAUSTED]",
        "Completed": "[COMPLETED]",
    }.get(label, "[STATE]")


def selector_options(snapshot: dict[str, Any], kind: str) -> tuple[list[dict[str, Any]], str]:
    items = list((snapshot.get("selector_items") or {}).get(kind, []))
    if kind == "proposals":
        empty = "No draft proposals are awaiting approval."
    elif kind == "approved_proposals":
        empty = "No approved proposals are awaiting synthesis."
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


def _checkpoint_commit(repo_root: Path, runner: Callable[..., subprocess.CompletedProcess[str]], *, message: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["JORB_BUILDER_ROOT"] = str(repo_root)
    add_result = runner(["git", "add", "-A"], cwd=str(repo_root), text=True, capture_output=True, env=env)
    if add_result.returncode != 0:
        return {
            "ok": False,
            "message": (add_result.stderr or add_result.stdout or "").strip() or "git add failed",
            "command": ["git", "add", "-A"],
            "returncode": add_result.returncode,
        }
    commit_result = runner(["git", "commit", "-m", message], cwd=str(repo_root), text=True, capture_output=True, env=env)
    return {
        "ok": commit_result.returncode == 0,
        "message": (commit_result.stdout or commit_result.stderr or "").strip() or "git commit finished",
        "command": ["git", "commit", "-m", message],
        "returncode": commit_result.returncode,
    }


def _checkpoint_if_needed(repo_root: Path, runner: Callable[..., subprocess.CompletedProcess[str]], *, message: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["JORB_BUILDER_ROOT"] = str(repo_root)
    status_result = runner(["git", "status", "--short"], cwd=str(repo_root), text=True, capture_output=True, env=env)
    if status_result.returncode != 0:
        return {
            "ok": False,
            "message": (status_result.stderr or status_result.stdout or "").strip() or "git status failed",
            "command": ["git", "status", "--short"],
            "returncode": status_result.returncode,
        }
    if not [line for line in status_result.stdout.splitlines() if line.strip()]:
        return {"ok": True, "message": "Repo is already clean; no checkpoint commit was needed."}
    checkpoint = _checkpoint_commit(repo_root, runner, message=message)
    if checkpoint.get("ok"):
        return checkpoint
    if "nothing to commit" in str(checkpoint.get("message") or "").lower():
        return {"ok": True, "message": "Repo was already effectively clean; no checkpoint commit was needed."}
    return checkpoint


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


def render_operator_view(
    snapshot: dict[str, Any],
    *,
    width: int = 120,
    height: int = 40,
    loop_mode: str = LOOP_MODE_SINGLE,
    status_message: str | None = None,
) -> str:
    backlog_diag = snapshot["backlog_diagnostics"]
    artifact = snapshot["artifact_panel"]
    eval_result = snapshot["eval_result"]
    review_result = snapshot.get("review_result") or {}
    proposals = snapshot["proposals"]
    synthesis = snapshot["synthesis"]
    latest_blocker = snapshot["latest_blocker"] or {}
    plain_state = snapshot.get("plain_state") or {}
    compact_progress = snapshot.get("compact_progress") or {}
    blocker_guidance = snapshot.get("blocker_guidance") or {}
    queue_explanation = snapshot.get("queue_explanation") or {}
    lines: list[str] = []
    lines.append("JORB Builder Operator TUI")
    lines.append("=" * min(width, 80))
    lines.append(f"STATE >>> {_status_badge(str(plain_state.get('label') or ''))} {plain_state.get('label') or snapshot['status'].get('state')}")
    lines.append(f"WHY >>> {plain_state.get('reason') or 'No plain-language explanation available.'}")
    lines.append(f"MODE >>> {LOOP_MODE_LABELS.get(loop_mode, loop_mode)}   ACTIVE >>> {snapshot['active'].get('task_id') or 'none'}")
    lines.append("STOP POLICY >>> " + ", ".join(STOP_CONDITIONS))
    lines.append("NEXT ACTION >>> " + (snapshot.get("next_recommended_action") or "none"))
    if status_message:
        lines.append("ACTION STATUS >>> " + status_message)
    lines.append(f"Blocker: {snapshot['ledger'].get('current_blocker') or latest_blocker.get('diagnosis') or 'none'}")
    lines.append(f"Latest run dir: {snapshot.get('latest_run_dir') or 'none'}")
    lines.append("")
    lines.append("Current task and progress")
    lines.append("-" * min(width, 80))
    current_task = snapshot['active'].get('task_id') or backlog_diag.get('next_selected_task_id') or snapshot['status'].get('last_task_id') or 'none'
    task_source = str(snapshot.get("current_task_source") or "none").replace("_", " ")
    lines.append(f"Current task : {current_task}")
    lines.append(f"Task source  : {task_source}")
    lines.append(f"Current phase: {compact_progress.get('current_phase') or 'none'}")
    lines.append(f"Elapsed      : {compact_progress.get('elapsed') or 'n/a'}")
    lines.append(f"Health       : {compact_progress.get('health') or 'unknown'}")
    lines.append(f"Waiting for  : {compact_progress.get('waiting_for') or 'none'}")
    for item in snapshot["stage_progress"]:
        lines.append(f"{_icon(item['status'])} {item['label']}")
    truth_warnings = snapshot.get("truth_warnings") or []
    if truth_warnings:
        lines.append("Truth warning: " + truth_warnings[0])
    if snapshot.get("current_run_dir"):
        lines.append(f"Current run  : {snapshot.get('current_run_dir')}")
    lines.append("")
    lines.append("Blocker diagnosis and recovery")
    lines.append("-" * min(width, 80))
    lines.append(f"Plain reason : {blocker_guidance.get('plain_reason') or 'none'}")
    lines.append(f"Why it stops : {blocker_guidance.get('why_it_stops') or 'none'}")
    lines.append(f"Safe auto-fix: {blocker_guidance.get('auto_fix_safe')}")
    options = blocker_guidance.get("options") or []
    if options:
        lines.append("Recovery opts: " + " | ".join(f"{item['key']} {item['label']}" for item in options))
    else:
        lines.append("Recovery opts: none")
    changed_files = blocker_guidance.get("changed_files") or []
    if changed_files:
        lines.append("Changed files: " + ", ".join(changed_files[:4]) + (" ..." if len(changed_files) > 4 else ""))
    lines.append("")
    lines.append("Queue explanation")
    lines.append("-" * min(width, 80))
    lines.append(f"Summary      : {queue_explanation.get('summary') or 'none'}")
    lines.append(f"Why now      : {queue_explanation.get('why_now') or 'none'}")
    lines.append(f"Waiting on   : {queue_explanation.get('waiting_on') or 'none'}")
    lines.append("")
    lines.append("Artifacts and eval")
    lines.append("-" * min(width, 80))
    lines.append(f"Expected: {', '.join(artifact.get('expected', [])) or 'none'}")
    lines.append(f"Present : {', '.join(artifact.get('present', [])) or 'none'}")
    lines.append(f"Missing : {', '.join(artifact.get('missing', [])) or 'none'}")
    lines.append(f"Eval    : score={eval_result.get('overall_score', 'n/a')} threshold={eval_result.get('threshold', 'n/a')} passed={eval_result.get('passed', 'n/a')}")
    lines.append(f"Trajectory: {(eval_result.get('scores') or {}).get('trajectory_quality', 'n/a')}")
    lines.append(f"Judge   : {snapshot.get('judge_result') or 'none'}")
    lines.append(f"Review  : verdict={review_result.get('verdict', 'n/a')} passed={review_result.get('passed', 'n/a')}")
    if review_result.get("summary"):
        lines.append(f"Review note: {review_result.get('summary')}")
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
    lines.append("System reality")
    lines.append("-" * min(width, 80))
    for item in snapshot.get("system_reality", [])[:5]:
        lines.append(f"{item.get('name')}: {item.get('status')} | {item.get('detail')}")
        lines.append(f"  Limit: {item.get('limit')}")
    lines.append("")
    lines.append("Recent meaningful events")
    lines.append("-" * min(width, 80))
    if not snapshot["event_feed"]:
        lines.append("No canonical events recorded yet.")
    else:
        for item in snapshot["event_feed"][: min(10, max(3, height - 28))]:
            recommendation = f" -> {item['recommendation']}" if item.get("recommendation") else ""
            detail = f" :: {item['detail']}" if item.get("detail") else ""
            lines.append(f"{item.get('at') or 'unknown'} | {_event_prefix(item)} | {item.get('summary')}{detail}{recommendation}")
    lines.append("")
    lines.append("Actions: x run | m mode | r refresh | p proposals | s synthesize | a syntheses | b blockers | u auto-recover | g changed files | c checkpoint | t repair | d details | o latest run dir | i artifacts | q quit")
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
    if action == "inspect_dirty_files":
        changed_files = []
        try:
            completed = runner(["git", "status", "--short"], cwd=str(repo_root), text=True, capture_output=True, env={**os.environ, "JORB_BUILDER_ROOT": str(repo_root)})
            if completed.returncode == 0:
                changed_files = [line.rstrip() for line in completed.stdout.splitlines() if line.strip()]
        except Exception:
            changed_files = []
        return {
            "ok": True,
            "message": "Changed files: " + (", ".join(changed_files) if changed_files else "none"),
            "changed_files": changed_files,
        }
    if action == "checkpoint_commit":
        return _checkpoint_commit(repo_root, runner, message="Checkpoint operator TUI recovery state")
    if action == "recover_common_blocker":
        checkpoint = _checkpoint_if_needed(repo_root, runner, message="Checkpoint operator-guided blocker recovery")
        if not checkpoint.get("ok"):
            return checkpoint
        repair = _run_repo_command([sys.executable, str(AUTOMATE_TASK_LOOP), "--repair-state"], repo_root=repo_root, runner=runner)
        prefix = checkpoint.get("message") or "Checkpoint step finished."
        repair["message"] = f"{prefix} {repair.get('message') or ''}".strip()
        return repair
    if action == "synthesize_approved":
        return _run_repo_command([sys.executable, str(BACKLOG_SYNTHESIS)], repo_root=repo_root, runner=runner)
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
    prompt_row = max(0, height - 2)
    input_row = max(0, height - 1)
    _safe_addstr(stdscr, prompt_row, 0, " " * max(1, width - 1), width=width)
    _safe_addstr(stdscr, prompt_row, 0, label, width=width)
    stdscr.refresh()
    curses.echo()
    try:
        value = stdscr.getstr(input_row, 0).decode("utf-8").strip()
    finally:
        curses.noecho()
    return value


def _safe_addstr(stdscr: Any, y: int, x: int, text: str, *, width: int | None = None) -> None:
    try:
        max_y, max_x = stdscr.getmaxyx()
    except Exception:
        return
    if max_y <= 0 or max_x <= 0:
        return
    if y < 0 or y >= max_y or x < 0 or x >= max_x:
        return
    usable_width = max_x if width is None else min(max_x, max(1, width))
    clipped = str(text or "")[: max(0, usable_width - x - 1)]
    if not clipped:
        return
    try:
        stdscr.addstr(y, x, clipped)
    except curses.error:
        return


def _choose_selector(stdscr: Any, snapshot: dict[str, Any], kind: str, title: str) -> dict[str, Any] | None:
    options, empty_message = selector_options(snapshot, kind)
    if not options:
        height, width = stdscr.getmaxyx()
        _safe_addstr(stdscr, max(0, height - 1), 0, empty_message, width=width)
        stdscr.refresh()
        return None
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    _safe_addstr(stdscr, 0, 0, title, width=width)
    _safe_addstr(stdscr, 1, 0, "-" * min(width - 1, 80), width=width)
    for idx, item in enumerate(options, start=1):
        line = f"{idx}. {item.get('label')} [{item.get('id')}]"
        if item.get("detail"):
            line += f" :: {item['detail']}"
        _safe_addstr(stdscr, min(idx + 1, max(0, height - 3)), 0, line, width=width)
    choice = _prompt(stdscr, "Select number (blank to cancel):")
    return resolve_selector_choice(options, choice)


def _paint_screen(stdscr: Any, snapshot: dict[str, Any], *, loop_mode: str, message: str) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    body = render_operator_view(snapshot, width=width, height=height, loop_mode=loop_mode, status_message=message)
    for idx, line in enumerate(body.splitlines()[: max(1, height - 2)]):
        _safe_addstr(stdscr, idx, 0, line, width=width)
    _safe_addstr(stdscr, max(0, height - 1), 0, message, width=width)
    stdscr.refresh()


def _tui(stdscr: Any) -> int:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.nodelay(False)
    message = "Loaded canonical operator view. Common flow: p approve -> s synthesize -> a apply -> x run."
    snapshot = build_operator_snapshot(ROOT)
    loop_mode = LOOP_MODE_SINGLE
    show_details = False
    while True:
        visible_snapshot = dict(snapshot)
        if not show_details:
            visible_snapshot["event_feed"] = list(snapshot.get("event_feed", []))[:6]
        _paint_screen(stdscr, visible_snapshot, loop_mode=loop_mode, message=message)
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
        elif key == ord("d"):
            show_details = not show_details
            message = "Technical detail expanded." if show_details else "Technical detail collapsed."
        elif key == ord("x"):
            action = "run_until_failure" if loop_mode == LOOP_MODE_UNTIL_FAILURE else "run_single_cycle"
            message = f"Running {LOOP_MODE_LABELS[loop_mode]} now. Waiting for canonical automation result..."
            _paint_screen(stdscr, snapshot, loop_mode=loop_mode, message=message)
            result = run_operator_action(action, root=ROOT)
            snapshot = build_operator_snapshot(ROOT)
            message = f"Run mode {LOOP_MODE_LABELS[loop_mode]} completed with {result.get('stop_reason', 'result')}: {result['message']}"
        elif key == ord("b"):
            blocker = _choose_selector(stdscr, snapshot, "blockers", "Open blockers")
            if blocker:
                label = blocker.get("label") or blocker.get("id") or "blocker"
                detail = blocker.get("detail") or "No diagnosis recorded."
                message = f"Selected blocker {label}. Detail: {detail}"
            else:
                message = "No blocker selected."
        elif key == ord("s"):
            approved = _choose_selector(stdscr, snapshot, "approved_proposals", "Approved proposals awaiting synthesis")
            if approved:
                message = f"Selected approved proposal {approved.get('id')}. Running synthesis now..."
                _paint_screen(stdscr, snapshot, loop_mode=loop_mode, message=message)
                result = run_operator_action("synthesize_approved", root=ROOT, identifier=str(approved.get("id")))
                snapshot = build_operator_snapshot(ROOT)
                message = f"Selected approved proposal {approved.get('id')}. {result['message'] or 'Synthesis run completed.'} Next: press a to apply a new synthesis draft if one was created."
            else:
                message = "No approved proposal selected."
        elif key == ord("o"):
            result = run_operator_action("latest_run_dir", root=ROOT)
            message = result["message"]
        elif key == ord("u"):
            message = "Running guided blocker recovery now..."
            _paint_screen(stdscr, snapshot, loop_mode=loop_mode, message=message)
            result = run_operator_action("recover_common_blocker", root=ROOT)
            snapshot = build_operator_snapshot(ROOT)
            message = result["message"] or ("Common blocker recovery passed." if result["ok"] else "Common blocker recovery failed.")
        elif key == ord("g"):
            result = run_operator_action("inspect_dirty_files", root=ROOT)
            message = result["message"]
        elif key == ord("c"):
            message = "Checkpointing current repo state now..."
            _paint_screen(stdscr, snapshot, loop_mode=loop_mode, message=message)
            result = run_operator_action("checkpoint_commit", root=ROOT)
            snapshot = build_operator_snapshot(ROOT)
            message = result["message"]
        elif key == ord("i"):
            result = run_operator_action("inspect_artifacts", root=ROOT)
            panel = result.get("artifact_panel") or {}
            message = f"Artifacts present: {', '.join(panel.get('present', [])) or 'none'}"
        elif key == ord("t"):
            message = "Running blocked-task repair now..."
            _paint_screen(stdscr, snapshot, loop_mode=loop_mode, message=message)
            result = run_operator_action("retry_blocked_task", root=ROOT)
            snapshot = build_operator_snapshot(ROOT)
            message = result["message"] or ("Retry repair passed." if result["ok"] else "Retry repair failed.")
        elif key == ord("p"):
            proposal = _choose_selector(stdscr, snapshot, "proposals", "Draft proposals awaiting approval")
            if proposal:
                message = f"Selected proposal {proposal.get('id')}. Approving now..."
                _paint_screen(stdscr, snapshot, loop_mode=loop_mode, message=message)
                result = run_operator_action("approve_proposal", root=ROOT, identifier=str(proposal.get("id")))
                snapshot = build_operator_snapshot(ROOT)
                message = f"Selected proposal {proposal.get('id')}. {result['message'] or 'Proposal approved.'} Next: press s to synthesize the approved proposal."
            else:
                message = "No proposal selected."
        elif key == ord("a"):
            synthesis = _choose_selector(stdscr, snapshot, "syntheses", "Synthesized draft entries")
            if synthesis:
                message = f"Selected synthesis {synthesis.get('id')}. Applying now..."
                _paint_screen(stdscr, snapshot, loop_mode=loop_mode, message=message)
                result = run_operator_action("apply_synthesized_entry", root=ROOT, identifier=str(synthesis.get("id")))
                snapshot = build_operator_snapshot(ROOT)
                message = f"Selected synthesis {synthesis.get('id')}. {result['message'] or 'Synthesis applied.'} Next: press x to run if the task is now ready."
            else:
                message = "No synthesized entry selected."
        else:
            message = "Actions: x run | m mode | r refresh | p proposals | s synthesize | a syntheses | b blockers | u auto-recover | g changed files | c checkpoint | t repair | d details | o latest run dir | i artifacts | q quit"


def main() -> int:
    parser = argparse.ArgumentParser(description="Terminal operator interface for canonical builder supervision truth.")
    parser.add_argument("--once", action="store_true", help="Render a single snapshot and exit.")
    parser.add_argument("--action", choices=["refresh", "inspect_blocker", "approve_proposal", "synthesize_approved", "apply_synthesized_entry", "retry_blocked_task", "inspect_dirty_files", "checkpoint_commit", "recover_common_blocker", "latest_run_dir", "inspect_artifacts", "run_single_cycle", "run_until_failure"])
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
