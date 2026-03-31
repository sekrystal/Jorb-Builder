#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import subprocess
from typing import Any

from backlog_synthesis import synthesis_summary_for_operator
from common import (
    PHASE4_OPERATOR_ARTIFACTS,
    READY_TASK_STATUSES,
    build_memory_store,
    builder_root,
    compute_backlog_diagnostics,
    derive_phase4_operator_truth,
    load_data,
    now_iso,
    parse_iso_datetime,
)
from feedback_engine import feedback_summary_for_operator

ROOT = builder_root()
BACKLOG = ROOT / "backlog.yml"
STATUS = ROOT / "status.yml"
ACTIVE = ROOT / "active_task.yml"
BLOCKERS = ROOT / "blockers"
TASK_HISTORY = ROOT / "task_history"
RUN_LEDGER = ROOT / "run_ledger.json"
BACKLOG_PROPOSALS = ROOT / "backlog_proposals.json"
SYNTHESIZED = ROOT / "synthesized_backlog_entries.json"
BACKLOG_APPLY_AUDIT = ROOT / "backlog_apply_audit.json"

OPERATOR_STAGE_ORDER = [
    "queued",
    "selected",
    "prompt_rendered",
    "planning_artifacts",
    "execution_started",
    "validation",
    "judge",
    "terminal",
]

OPERATOR_STAGE_LABELS = {
    "queued": "Queued",
    "selected": "Selected",
    "prompt_rendered": "Prompt rendered",
    "planning_artifacts": "Planning artifacts emitted",
    "execution_started": "Execution started",
    "validation": "Validation",
    "judge": "Judge",
    "terminal": "Accepted / Blocked",
}

PROGRESS_STAGE_MAP = {
    1: "selected",
    2: "prompt_rendered",
    3: "execution_started",
    4: "execution_started",
    5: "validation",
    6: "validation",
    7: "validation",
    8: "validation",
    9: "terminal",
}

CANONICAL_EVENT_SCHEMA_VERSION = 1
CANONICAL_EVENT_KINDS = {
    "running",
    "blocked",
    "failed",
    "accepted",
    "completed",
    "applied",
    "draft",
    "attention",
}


def _safe_load(path: Path, default: Any) -> Any:
    try:
        return load_data(path)
    except FileNotFoundError:
        return default


def _safe_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _sort_key(value: Any) -> tuple[int, str]:
    parsed = parse_iso_datetime(value)
    if parsed is None:
        return (0, "")
    return (1, parsed.isoformat())


def _latest_history_entry(root: Path, task_id: str | None = None) -> dict[str, Any] | None:
    entries: list[dict[str, Any]] = []
    for path in sorted((root / "task_history").glob("*.yml")):
        payload = _safe_load(path, {})
        if task_id and str(payload.get("task_id")) != str(task_id):
            continue
        payload["_history_path"] = str(path)
        entries.append(payload)
    if not entries:
        return None
    entries.sort(key=lambda item: _sort_key(item.get("completed_at") or item.get("started_at") or item.get("created_at")), reverse=True)
    return entries[0]


def _task_by_id(backlog: dict[str, Any], task_id: str | None) -> dict[str, Any] | None:
    if not task_id:
        return None
    for task in backlog.get("tasks", []):
        if str(task.get("id")) == str(task_id):
            return task
    return None


def _latest_run_dir(root: Path, active: dict[str, Any], status: dict[str, Any]) -> Path | None:
    for key in ("run_log_dir", "previous_run_log_dir"):
        value = active.get(key)
        if value:
            candidate = Path(str(value)).expanduser().resolve()
            if candidate.exists():
                return candidate
    last_task_id = status.get("last_task_id")
    latest = _latest_history_entry(root, str(last_task_id) if last_task_id else None)
    if latest and latest.get("run_log_dir"):
        candidate = Path(str(latest["run_log_dir"])).expanduser().resolve()
        if candidate.exists():
            return candidate
    history_fallback = _latest_history_entry(root)
    if history_fallback and history_fallback.get("run_log_dir"):
        candidate = Path(str(history_fallback["run_log_dir"])).expanduser().resolve()
        if candidate.exists():
            return candidate
    return None


def _active_run_dir(active: dict[str, Any]) -> Path | None:
    value = active.get("run_log_dir")
    if not value or not active.get("task_id"):
        return None
    candidate = Path(str(value)).expanduser().resolve()
    return candidate if candidate.exists() else None


def _latest_open_blocker(root: Path, task_id: str | None) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for path in sorted((root / "blockers").glob("*.yml")):
        payload = _safe_load(path, {})
        if payload.get("status") != "open":
            continue
        related = [str(item) for item in payload.get("related_tasks", [])]
        if task_id and str(task_id) not in related:
            continue
        payload["_path"] = str(path)
        candidates.append(payload)
    if not candidates:
        return None
    candidates.sort(key=lambda item: _sort_key(item.get("opened_at")), reverse=True)
    return candidates[0]


def _open_blockers(root: Path) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for path in sorted((root / "blockers").glob("*.yml")):
        payload = _safe_load(path, {})
        if payload.get("status") != "open":
            continue
        payload["_path"] = str(path)
        blockers.append(payload)
    blockers.sort(key=lambda item: _sort_key(item.get("opened_at")), reverse=True)
    return blockers


def _collect_expected_artifacts(task: dict[str, Any] | None) -> list[str]:
    if task is None:
        return []
    expected = [str(item).strip() for item in task.get("required_artifacts", []) if str(item).strip()]
    if expected:
        return expected
    return []


def _artifact_panel(run_dir: Path | None, task: dict[str, Any] | None, ledger_truth: dict[str, Any], *, allow_ledger_fallback: bool) -> dict[str, Any]:
    expected = _collect_expected_artifacts(task)
    if not expected and task is not None and str(task.get("area")).lower() == "builder":
        expected = list(PHASE4_OPERATOR_ARTIFACTS)
    present: list[str] = []
    actual_files: list[str] = []
    if run_dir and run_dir.exists():
        actual_files = sorted(item.name for item in run_dir.iterdir() if item.is_file())
        present = [name for name in expected if (run_dir / name).exists()]
    elif allow_ledger_fallback and ledger_truth.get("artifact_completeness"):
        artifact_state = ledger_truth.get("artifact_completeness") or {}
        present = [str(item) for item in artifact_state.get("present", [])]
    missing = [name for name in expected if name not in set(present)]
    return {
        "expected": expected,
        "present": present,
        "missing": missing,
        "actual_files": actual_files,
    }


def _load_latest_eval(run_dir: Path | None, ledger_truth: dict[str, Any], *, allow_ledger_fallback: bool) -> dict[str, Any]:
    if run_dir:
        eval_path = run_dir / "eval_result.json"
        if eval_path.exists():
            return _safe_load(eval_path, {})
    if allow_ledger_fallback:
        return dict(ledger_truth.get("eval_result") or {})
    return {}


def _latest_judge_result(run_dir: Path | None) -> str | None:
    if not run_dir:
        return None
    judge_path = run_dir / "judge_decision.md"
    if not judge_path.exists():
        return None
    text = judge_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("decision:"):
            return line.split(":", 1)[1].strip()
    return "present"


def _git_status_lines(root: Path) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(root),
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception:
        return []
    if completed.returncode != 0:
        return []
    return [line.rstrip() for line in completed.stdout.splitlines() if line.strip()]


def _stage_progress(
    *,
    task: dict[str, Any] | None,
    task_source: str,
    active: dict[str, Any],
    status: dict[str, Any],
    run_dir: Path | None,
    automation_result: dict[str, Any],
    artifact_panel: dict[str, Any],
    eval_result: dict[str, Any],
) -> list[dict[str, Any]]:
    progress = _safe_jsonl(run_dir / "progress.jsonl") if run_dir else []
    seen_stages = {PROGRESS_STAGE_MAP.get(int(item.get("stage_index", 0))) for item in progress}
    seen_stages.discard(None)
    latest_progress = progress[-1] if progress else None
    latest_mapped = PROGRESS_STAGE_MAP.get(int(latest_progress.get("stage_index", 0))) if latest_progress else None
    terminal_state = str(automation_result.get("classification") or "").lower() if task_source == "active" else ""
    blocked = terminal_state in {"blocked", "refined", "preflight_failed"}
    completed = terminal_state in {"accepted", "done", "completed"}
    prompt_exists = bool(active.get("prompt_file")) or bool(run_dir and (run_dir / "codex_prompt.md").exists())
    planning_names = {"compiled_feature_spec.md", "proposal.md", "tradeoff_matrix.md", "research_brief.md"}
    expected_planning = [name for name in artifact_panel.get("expected", []) if name in planning_names]
    planning_expected = bool(expected_planning)
    planning_present = all(name in set(artifact_panel.get("present", [])) for name in expected_planning) if expected_planning else False
    judge_present = bool(eval_result) or bool(_latest_judge_result(run_dir)) or bool(run_dir and (run_dir / "evidence_bundle.json").exists())

    statuses: dict[str, str] = {name: "pending" for name in OPERATOR_STAGE_ORDER}
    statuses["queued"] = "complete" if task_source == "active" else ("current" if task is not None else "current")
    if task_source == "active" and ("selected" in seen_stages or active.get("task_id")):
        statuses["selected"] = "complete"
    if prompt_exists:
        statuses["prompt_rendered"] = "complete"
    if planning_expected:
        statuses["planning_artifacts"] = "complete" if planning_present else "pending"
    else:
        statuses["planning_artifacts"] = "skipped"
    if "execution_started" in seen_stages or any(step.get("name") == "executor" for step in automation_result.get("steps", [])):
        statuses["execution_started"] = "complete"
    if "validation" in seen_stages or any(step.get("name") in {"local_validation", "vm_validation", "git"} for step in automation_result.get("steps", [])):
        statuses["validation"] = "complete"
    if judge_present:
        statuses["judge"] = "complete"
    elif planning_expected:
        statuses["judge"] = "pending"
    else:
        statuses["judge"] = "skipped"
    if completed:
        statuses["terminal"] = "complete"
    elif blocked:
        statuses["terminal"] = "failed"

    current_stage = latest_mapped
    if blocked:
        current_stage = latest_mapped or "terminal"
    elif task_source == "active" and active.get("task_id"):
        current_stage = latest_mapped or "selected"
    elif completed:
        current_stage = None

    if current_stage and statuses.get(current_stage) == "pending":
        statuses[current_stage] = "current"
    if blocked and current_stage:
        statuses[current_stage] = "failed"

    return [
        {
            "key": key,
            "label": OPERATOR_STAGE_LABELS[key],
            "status": statuses[key],
        }
        for key in OPERATOR_STAGE_ORDER
    ]


def _load_proposal_truth(root: Path, synthesized_source_ids: set[str] | None = None) -> dict[str, Any]:
    payload = _safe_load(root / "backlog_proposals.json", {"proposals": []})
    proposals = list(payload.get("proposals", []))
    drafts = [item for item in proposals if item.get("status") == "draft"]
    accepted = [item for item in proposals if item.get("status") == "accepted"]
    pending_synthesis = [
        item for item in accepted
        if str(item.get("proposal_id") or "") not in (synthesized_source_ids or set())
    ]
    return {
        "all": proposals,
        "draft_count": len(drafts),
        "accepted_count": len(accepted),
        "accepted_pending_synthesis_count": len(pending_synthesis),
        "top_draft": drafts[0] if drafts else None,
        "top_accepted": accepted[0] if accepted else None,
        "top_accepted_pending_synthesis": pending_synthesis[0] if pending_synthesis else None,
    }


def _event_payload(
    at: str | None,
    source: str,
    kind: str,
    summary: str,
    *,
    detail: str | None = None,
    recommendation: str | None = None,
    provenance: str | None = None,
    task_id: str | None = None,
    stage_name: str | None = None,
    stage_key: str | None = None,
    canonical_source: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": CANONICAL_EVENT_SCHEMA_VERSION,
        "at": at,
        "source": source,
        "canonical_source": canonical_source or source,
        "kind": kind,
        "summary": summary,
        "detail": detail,
        "recommendation": recommendation,
        "task_id": task_id,
        "stage_name": stage_name,
        "stage_key": stage_key,
        "provenance": provenance,
        "provenance_sources": [provenance] if provenance else [],
    }


def _event_emphasis(kind: str) -> str:
    lowered = str(kind or "").lower()
    if lowered in {"blocked", "failed"}:
        return "critical"
    if lowered in {"accepted", "applied", "completed"}:
        return "success"
    if lowered in {"waiting", "operator_approval_required", "no_runnable_tasks_remain"}:
        return "attention"
    return "normal"


def _normalize_run_event(
    *,
    at: str | None,
    source: str,
    task_id: str | None,
    stage_name: str | None,
    state: str | None,
    detail: str | None,
    provenance: str,
) -> dict[str, Any]:
    lowered_state = str(state or "").strip().lower()
    task_label = str(task_id or "system")
    stage_label = str(stage_name or "state").strip() or "state"
    cleaned_detail = str(detail or "").strip() or None
    if lowered_state in {"blocked", "failed", "preflight_failed"}:
        summary = f"{task_label} blocked at {stage_label}"
    elif lowered_state in {"accepted", "completed", "done"}:
        summary = f"{task_label} accepted"
    elif lowered_state in {"running", ""}:
        summary = f"{task_label} {stage_label}"
    else:
        summary = f"{task_label} {lowered_state.replace('_', ' ')} at {stage_label}"
    recommendation = None
    if cleaned_detail and "dirty before automated execution" in cleaned_detail.lower():
        recommendation = "Commit or stash changes, then rerun automation."
    elif lowered_state in {"blocked", "failed", "preflight_failed"}:
        recommendation = "Inspect the blocker and repair state before retrying."
    elif lowered_state in {"accepted", "completed", "done"}:
        recommendation = "Inspect the latest run or continue with the next ready task."
    normalized_stage_key = None
    lowered_stage = stage_label.lower()
    for key, label in OPERATOR_STAGE_LABELS.items():
        if lowered_stage == label.lower() or lowered_stage == key.lower():
            normalized_stage_key = key
            break
    payload = _event_payload(
        at,
        "canonical_event",
        lowered_state or "running",
        summary,
        detail=cleaned_detail,
        recommendation=recommendation,
        provenance=provenance,
        task_id=task_id,
        stage_name=stage_label,
        stage_key=normalized_stage_key,
        canonical_source=source,
    )
    payload["emphasis"] = _event_emphasis(lowered_state)
    payload["dedupe_key"] = (
        str(task_id or ""),
        stage_label.lower(),
        lowered_state or "running",
        cleaned_detail or "",
    )
    return payload


def validate_canonical_event_schema(event: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if event.get("schema_version") != CANONICAL_EVENT_SCHEMA_VERSION:
        issues.append("schema_version")
    for field in ("at", "source", "canonical_source", "kind", "summary", "provenance_sources"):
        if field not in event:
            issues.append(field)
    if event.get("source") != "canonical_event":
        issues.append("source:not_canonical_event")
    if str(event.get("kind") or "") not in CANONICAL_EVENT_KINDS:
        issues.append("kind:unsupported")
    if not isinstance(event.get("provenance_sources"), list):
        issues.append("provenance_sources:not_list")
    return issues


def _normalize_ledger_events(root: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    ledger = _safe_load(root / "run_ledger.json", {"events": []})
    for item in ledger.get("events", [])[-limit:]:
        normalized.append(
            _normalize_run_event(
                at=item.get("at"),
                source="run_ledger",
                task_id=item.get("task_id"),
                stage_name=item.get("stage_name"),
                state=item.get("run_state"),
                detail=item.get("detail"),
                provenance=str(root / "run_ledger.json"),
            )
        )
    return normalized


def _normalize_progress_events(run_dir: Path | None, *, limit: int = 10) -> list[dict[str, Any]]:
    if not run_dir or not run_dir.exists():
        return []
    normalized: list[dict[str, Any]] = []
    for item in _safe_jsonl(run_dir / "progress.jsonl")[-limit:]:
        normalized.append(
            _normalize_run_event(
                at=item.get("timestamp"),
                source="progress",
                task_id=item.get("task_id"),
                stage_name=item.get("stage_name"),
                state=item.get("state"),
                detail=item.get("detail"),
                provenance=str(run_dir / "progress.jsonl"),
            )
        )
    return normalized


def _normalize_operator_events(root: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    proposals = _safe_load(root / "backlog_proposals.json", {"proposals": []})
    for item in proposals.get("proposals", []):
        reviewed_at = item.get("reviewed_at")
        if reviewed_at:
            events.append(
                _event_payload(
                    reviewed_at,
                    "canonical_event",
                    str(item.get("status") or "attention"),
                    f"Proposal approved: {item.get('title') or item.get('proposal_id') or 'proposal reviewed'}" if item.get("status") == "accepted" else str(item.get("title") or item.get("proposal_id") or "proposal reviewed"),
                    detail=str(item.get("review_note") or "").strip() or None,
                    recommendation="Synthesize the approved proposal." if item.get("status") == "accepted" else None,
                    provenance=str(root / "backlog_proposals.json"),
                    task_id=None,
                    stage_name="proposal_review",
                    stage_key=None,
                    canonical_source="proposal",
                )
            )
    synthesized = _safe_load(root / "synthesized_backlog_entries.json", {"entries": []})
    for item in synthesized.get("entries", []):
        created_at = item.get("created_at")
        if created_at:
            events.append(
                _event_payload(
                    created_at,
                    "canonical_event",
                    str(item.get("status") or "draft"),
                    f"Synthesis draft: {item.get('title') or item.get('ticket_id_placeholder') or 'synthesized entry'}",
                    detail=str(item.get("synthesis_id") or ""),
                    recommendation="Apply the synthesized entry after review." if item.get("status") == "draft" else None,
                    provenance=str(root / "synthesized_backlog_entries.json"),
                    task_id=str(item.get("ticket_id_placeholder") or ""),
                    stage_name="synthesis_draft",
                    stage_key=None,
                    canonical_source="synthesis",
                )
            )
        applied_at = item.get("applied_at")
        if applied_at:
            events.append(
                _event_payload(
                    applied_at,
                    "canonical_event",
                    "applied",
                    f"Synthesis applied: {item.get('ticket_id_placeholder') or item.get('title') or 'synthesized entry applied'}",
                    detail=str(item.get("synthesis_id") or ""),
                    recommendation="Run the automation loop for the applied ready task.",
                    provenance=str(root / "synthesized_backlog_entries.json"),
                    task_id=str(item.get("ticket_id_placeholder") or ""),
                    stage_name="synthesis_apply",
                    stage_key=None,
                    canonical_source="synthesis",
                )
            )
    return events


def _dedupe_events(events: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for event in sorted(events, key=lambda item: _sort_key(item.get("at")), reverse=True):
        key = tuple(event.get("dedupe_key") or ())
        if key and key in by_key:
            existing = by_key[key]
            merged_sources = list(existing.get("provenance_sources", []))
            for source in event.get("provenance_sources", []):
                if source and source not in merged_sources:
                    merged_sources.append(source)
            existing["provenance_sources"] = merged_sources
            merged_canonical_sources = list(existing.get("merged_canonical_sources", [existing.get("canonical_source")]))
            for source_name in [event.get("canonical_source")]:
                if source_name and source_name not in merged_canonical_sources:
                    merged_canonical_sources.append(source_name)
            existing["merged_canonical_sources"] = merged_canonical_sources
            if not existing.get("detail") and event.get("detail"):
                existing["detail"] = event["detail"]
            if not existing.get("recommendation") and event.get("recommendation"):
                existing["recommendation"] = event["recommendation"]
            continue
        if key:
            by_key[key] = event
        deduped.append(event)
    deduped.sort(key=lambda item: _sort_key(item.get("at")), reverse=True)
    terminal = [item for item in deduped if item.get("emphasis") in {"critical", "success"}]
    remainder = [item for item in deduped if item.get("emphasis") not in {"critical", "success"}]
    final_events = terminal[:4] + remainder
    return [item for item in final_events[:limit] if not validate_canonical_event_schema(item)]


def build_canonical_event_stream(root: Path, *, run_dir: Path | None, limit: int = 18) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    events.extend(_normalize_ledger_events(root))
    events.extend(_normalize_operator_events(root))
    events.extend(_normalize_progress_events(run_dir))
    return _dedupe_events(events, limit=limit)


def _actual_stats(backlog_diag: dict[str, Any]) -> dict[str, int]:
    counts = backlog_diag.get("counts_by_status", {})
    return {
        "completed_tasks": int(counts.get("accepted", 0)) + int(counts.get("done", 0)),
        "blocked_tasks": int(counts.get("blocked", 0)),
        "retry_ready_tasks": int(counts.get("retry_ready", 0)),
    }


def _plain_state(
    *,
    status: dict[str, Any],
    active: dict[str, Any],
    latest_blocker: dict[str, Any] | None,
    stage_progress: list[dict[str, Any]],
    backlog_diag: dict[str, Any],
    proposals: dict[str, Any],
) -> dict[str, str]:
    if latest_blocker or status.get("state") == "blocked":
        return {
            "label": "Blocked",
            "reason": "A real blocker is stopping the builder and needs intervention before work can continue.",
        }
    if backlog_diag.get("ready_task_ids"):
        return {
            "label": "Ready to run",
            "reason": "The builder is idle right now, but a runnable task is waiting in the queue.",
        }
    if active.get("task_id"):
        current = next((item for item in stage_progress if item.get("status") in {"current", "failed"}), None)
        current_key = str((current or {}).get("key") or "")
        if current_key in {"execution_started", "prompt_rendered"}:
            return {
                "label": "Waiting on Codex",
                "reason": "The builder handed work to Codex and is waiting for code or execution output.",
            }
        if current_key == "validation":
            return {
                "label": "Waiting on Validation",
                "reason": "The builder is validating changes before it can judge the run result.",
            }
        return {
            "label": "Running",
            "reason": "The builder is actively processing the current task.",
        }
    if proposals.get("draft_count", 0) or proposals.get("accepted_pending_synthesis_count", 0):
        return {
            "label": "Waiting on Approval",
            "reason": "There is proposal work waiting for an operator decision or synthesis step before execution can continue.",
        }
    pending_count = len(backlog_diag.get("pending_task_ids", []))
    if pending_count:
        return {
            "label": "Waiting on Dependencies",
            "reason": "There is queued work, but nothing is runnable yet because dependencies or readiness gates are still unmet.",
        }
    return {
        "label": "Exhausted",
        "reason": "No runnable, blocked, or pending tasks remain under current backlog truth.",
    }


def _compact_progress(
    *,
    task_source: str,
    active: dict[str, Any],
    latest_run_result: dict[str, Any],
    latest_run_dir: Path | None,
    stage_progress: list[dict[str, Any]],
    backlog_diag: dict[str, Any],
) -> dict[str, Any]:
    progress_rows = _safe_jsonl(latest_run_dir / "progress.jsonl") if latest_run_dir else []
    latest = progress_rows[-1] if progress_rows else {}
    elapsed = None
    if progress_rows:
        first_at = parse_iso_datetime(progress_rows[0].get("timestamp"))
        last_at = parse_iso_datetime(latest.get("timestamp"))
        if first_at and last_at:
            elapsed_seconds = max(0, int((last_at - first_at).total_seconds()))
            minutes, seconds = divmod(elapsed_seconds, 60)
            elapsed = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
    ready_idle = task_source == "next_ready" and not active.get("task_id")
    if ready_idle:
        return {
            "current_phase": "Ready to run",
            "elapsed": "n/a",
            "health": "idle",
            "waiting_for": "operator run trigger",
            "technical_detail": {
                "latest_progress": latest,
                "latest_run_classification": latest_run_result.get("classification"),
            },
        }
    health = "blocked" if any(item.get("status") == "failed" for item in stage_progress) else ("active" if active.get("task_id") else "idle")
    current = next((item for item in stage_progress if item.get("status") in {"current", "failed"}), None)
    waiting_for = None
    current_key = str((current or {}).get("key") or "")
    if current_key in {"execution_started", "prompt_rendered"}:
        waiting_for = "Codex output"
    elif current_key == "validation":
        waiting_for = "validation results"
    elif current_key == "judge":
        waiting_for = "judge artifacts"
    elif health == "blocked":
        waiting_for = "operator recovery"
    elif health == "idle":
        waiting_for = "next runnable task"
    return {
        "current_phase": (current or {}).get("label") or ("Ready to run" if ready_idle else "none"),
        "elapsed": elapsed or "n/a",
        "health": ("idle" if ready_idle else health),
        "waiting_for": waiting_for or "none",
        "technical_detail": {
            "latest_progress": latest,
            "latest_run_classification": latest_run_result.get("classification"),
        },
    }


def _blocker_guidance(root: Path, latest_blocker: dict[str, Any] | None) -> dict[str, Any]:
    if not latest_blocker:
        return {
            "plain_reason": "No blocker is currently stopping the builder.",
            "why_it_stops": "none",
            "auto_fix_safe": False,
            "options": [],
        }
    diagnosis = str(latest_blocker.get("diagnosis") or "").strip()
    git_status = _git_status_lines(root)
    lowered = diagnosis.lower()
    if "dirty before automated execution" in lowered:
        return {
            "plain_reason": "The builder repo has uncommitted changes.",
            "why_it_stops": "The automation loop refuses to continue because running on a dirty worktree could mix unrelated edits into the task.",
            "auto_fix_safe": True,
            "options": [
                {"key": "u", "label": "Auto-recover common blocker", "action": "recover_common_blocker"},
                {"key": "g", "label": "Inspect changed files", "action": "inspect_dirty_files"},
                {"key": "c", "label": "Checkpoint commit current changes", "action": "checkpoint_commit"},
                {"key": "t", "label": "Repair and reopen blocked task", "action": "retry_blocked_task"},
            ],
            "changed_files": git_status,
        }
    if "state" in lowered and "repair" in lowered:
        return {
            "plain_reason": "The saved builder state does not match current canonical truth.",
            "why_it_stops": "The automation loop cannot safely continue until it reconciles active-task and backlog state.",
            "auto_fix_safe": True,
            "options": [
                {"key": "t", "label": "Run safe state repair", "action": "retry_blocked_task"},
            ],
        }
    return {
        "plain_reason": diagnosis or "A blocker is stopping the current task.",
        "why_it_stops": "The current task reached a terminal blocked state and needs operator intervention.",
        "auto_fix_safe": False,
        "options": [
            {"key": "b", "label": "Inspect blocker details", "action": "inspect_blocker"},
        ],
    }


def _queue_explanation(backlog_diag: dict[str, Any], proposals: dict[str, Any], synthesis: dict[str, Any]) -> dict[str, Any]:
    blocked = backlog_diag.get("blocked_task_ids", [])
    if blocked:
        return {
            "summary": "Execution is waiting on blocker recovery.",
            "why_now": f"{blocked[0]} is blocked and no further progress should happen until it is resolved or repaired.",
            "waiting_on": "blocker repair",
        }
    next_ready = backlog_diag.get("next_selected_task_id")
    if next_ready:
        return {
            "summary": f"{next_ready} is runnable now.",
            "why_now": "It is already marked ready and no blockers or dependency filters are excluding it.",
            "waiting_on": "nothing",
        }
    if proposals.get("accepted_pending_synthesis_count", 0):
        return {
            "summary": "Execution is waiting on synthesis.",
            "why_now": "At least one approved proposal has not yet been turned into a backlog draft.",
            "waiting_on": "approval-to-synthesis handoff",
        }
    if synthesis.get("draft_count", 0):
        return {
            "summary": "Execution is waiting on synthesized draft apply.",
            "why_now": "There is a draft synthesized entry that has not yet been applied into canonical backlog.",
            "waiting_on": "synthesized entry apply",
        }
    pending = backlog_diag.get("pending_task_ids", [])
    if pending:
        return {
            "summary": "Execution is waiting on dependencies or manual readiness.",
            "why_now": f"{len(pending)} task(s) are pending, but none are ready yet.",
            "waiting_on": "dependencies or ready-state transition",
        }
    return {
        "summary": "The queue is exhausted.",
        "why_now": "There are no ready, blocked, or pending tasks remaining.",
        "waiting_on": "nothing",
    }


def _truth_warnings(
    *,
    status: dict[str, Any],
    active: dict[str, Any],
    task: dict[str, Any] | None,
    backlog_diag: dict[str, Any],
    latest_blocker: dict[str, Any] | None,
) -> list[str]:
    warnings: list[str] = []
    blocked_ids = set(str(item) for item in backlog_diag.get("blocked_task_ids", []))
    ready_ids = set(str(item) for item in backlog_diag.get("ready_task_ids", []))
    active_task_id = str(active.get("task_id") or "")
    task_status = str((task or {}).get("status") or "")
    status_state = str(status.get("state") or "")
    if latest_blocker and not blocked_ids:
        warnings.append("Open blocker evidence exists, but canonical backlog currently reports no blocked task.")
    if status_state == "blocked" and not latest_blocker and not blocked_ids:
        warnings.append("Status says blocked, but canonical backlog and blocker files do not currently show an open blocker.")
    if active_task_id and task is None:
        warnings.append("Active task state references a task that is not present in canonical backlog.")
    elif active_task_id and task_status in {"accepted", "done"}:
        warnings.append("Active task state still points at a task that canonical backlog already marks complete.")
    elif active_task_id and status_state == "idle":
        warnings.append("Active task state exists even though top-level status is idle.")
    if not active_task_id and status_state in {"implementing", "task_selected", "preflight_passed", "preflight_failed"}:
        warnings.append("Top-level status suggests an active run, but there is no active task bound in canonical state.")
    if ready_ids and status_state == "completed":
        warnings.append("Top-level status says completed even though canonical backlog still has ready work.")
    return warnings


def _system_reality(
    *,
    root: Path,
    latest_run_dir: Path | None,
    memory_store: dict[str, Any],
    eval_result: dict[str, Any],
    truth_warnings: list[str],
) -> list[dict[str, str]]:
    fixtures_dir = root / "eval_fixtures"
    fixture_count = len(list(fixtures_dir.glob("*.json"))) if fixtures_dir.exists() else 0
    has_memory_context = bool(latest_run_dir and ((latest_run_dir / "memory_context.json").exists() or (latest_run_dir / "judge_memory_context.json").exists()))
    counts = memory_store.get("counts_by_status") or {}
    return [
        {
            "name": "Evals",
            "status": "proven" if eval_result.get("fixture_family") else ("partially_proven" if fixture_count else "missing"),
            "detail": (
                "Explicit scored eval fixtures are active for the latest run."
                if eval_result.get("fixture_family")
                else "Local rubric eval framework exists, but the latest run does not show a scored fixture result."
            ),
            "limit": (
                "Trajectory grading is active for the latest run."
                if "trajectory_quality" in (eval_result.get("scores") or {})
                else "Trajectory grading only appears when the selected fixture includes trajectory_quality."
            ),
        },
        {
            "name": "Memory",
            "status": "partially_proven" if memory_store.get("entries") else "missing",
            "detail": f"Structured memory store is file-backed with {len(memory_store.get('entries', []))} entries and provenance; active={counts.get('active', 0)}.",
            "limit": "Retrieval is explainable and similarity-aware, but still local/file-backed rather than service-backed retrieval.",
        },
        {
            "name": "Retrieval",
            "status": "partially_proven" if has_memory_context else "implemented_not_proven",
            "detail": "Role-specific memory/artifact bundles are emitted for runs that render memory context." if has_memory_context else "Role-specific retrieval code exists, but the latest run does not show emitted memory context artifacts.",
            "limit": "Analog lookup now uses explainable text, tag, artifact, and outcome similarity, but it is not learned or vector-backed retrieval.",
        },
        {
            "name": "Orchestration",
            "status": "partially_proven",
            "detail": "Run continuity exists through active_task.yml, status.yml, run_ledger.json, and progress logs.",
            "limit": "Streaming remains poll/file based, not webhook or push-event based.",
        },
        {
            "name": "Control plane",
            "status": "partially_proven" if truth_warnings else "proven",
            "detail": "Operator surfaces align with current canonical backlog truth." if not truth_warnings else truth_warnings[0],
            "limit": "Trust drops whenever state repair leaves stale status or blocker evidence behind.",
        },
    ]


def _recommended_action(*, backlog_diag: dict[str, Any], latest_blocker: dict[str, Any] | None, blocker_guidance: dict[str, Any], proposals: dict[str, Any], synthesis: dict[str, Any], active: dict[str, Any], status: dict[str, Any], truth_warnings: list[str]) -> str:
    if truth_warnings:
        return "Press t to reconcile control-plane state drift before taking the next action."
    if latest_blocker:
        if blocker_guidance.get("auto_fix_safe"):
            return "Press u to auto-recover the common blocker, or g/c/t to inspect, checkpoint, and repair step by step."
        return f"Inspect blocker {latest_blocker.get('id')} and run python3 scripts/automate_task_loop.py --repair-state if the condition is already resolved."
    next_ready = backlog_diag.get("next_selected_task_id")
    if next_ready:
        return "Press x to execute the next ready task."
    if proposals.get("accepted_pending_synthesis_count", 0):
        top = proposals.get("top_accepted_pending_synthesis") or {}
        return f"Press s to synthesize approved proposal {top.get('proposal_id') or 'accepted proposal'} into a backlog draft."
    if synthesis.get("draft_count", 0):
        top_draft = synthesis.get("top_draft") or {}
        return f"Press a to apply synthesized entry {top_draft.get('synthesis_id') or top_draft.get('ticket_id_placeholder') or 'draft entry'}."
    if proposals.get("draft_count", 0):
        return "Press p to review draft proposals and approve the next builder-safe candidate."
    if status.get("state") == "completed":
        return "System is idle and backlog-exhausted; review proposals or add new work."
    if active.get("task_id"):
        return "Inspect the active run artifacts."
    return "Refresh status or inspect backlog truth."


def build_operator_snapshot(root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root or ROOT).expanduser().resolve()
    backlog = _safe_load(repo_root / "backlog.yml", {"tasks": []})
    status = _safe_load(repo_root / "status.yml", {})
    active = _safe_load(repo_root / "active_task.yml", {})
    ledger = derive_phase4_operator_truth(_safe_load(repo_root / "run_ledger.json", {}))
    memory_store = build_memory_store(repo_root)
    feedback = feedback_summary_for_operator(repo_root)
    synthesized_payload = _safe_load(repo_root / "synthesized_backlog_entries.json", {"entries": []})
    synthesized_source_ids = {
        str((entry.get("provenance") or {}).get("source_proposal_id") or "")
        for entry in synthesized_payload.get("entries", [])
        if str((entry.get("provenance") or {}).get("source_proposal_id") or "").strip()
    }
    proposals = _load_proposal_truth(repo_root, synthesized_source_ids=synthesized_source_ids)
    synthesis = synthesis_summary_for_operator(repo_root)
    backlog_diag = compute_backlog_diagnostics(backlog)
    latest_run_dir = _latest_run_dir(repo_root, active, status)
    active_run_dir = _active_run_dir(active)
    current_task_id = active.get("task_id") or backlog_diag.get("next_selected_task_id") or status.get("last_task_id")
    if active.get("task_id"):
        task_source = "active"
    elif backlog_diag.get("next_selected_task_id"):
        task_source = "next_ready"
    elif status.get("last_task_id"):
        task_source = "last_task"
    else:
        task_source = "none"
    task = _task_by_id(backlog, current_task_id)
    current_run_dir = active_run_dir if task_source == "active" else None
    automation_result = _safe_load(current_run_dir / "automation_result.json", {}) if current_run_dir else {}
    latest_blocker = _latest_open_blocker(repo_root, active.get("task_id") or status.get("last_task_id"))
    open_blockers = _open_blockers(repo_root)
    artifact_panel = _artifact_panel(current_run_dir, task, ledger, allow_ledger_fallback=(task_source == "active"))
    eval_result = _load_latest_eval(current_run_dir, ledger, allow_ledger_fallback=(task_source == "active"))
    judge_result = _latest_judge_result(current_run_dir)
    stage_progress = _stage_progress(
        task=task,
        task_source=task_source,
        active=active,
        status=status,
        run_dir=current_run_dir,
        automation_result=automation_result,
        artifact_panel=artifact_panel,
        eval_result=eval_result,
    )
    event_feed = build_canonical_event_stream(repo_root, run_dir=latest_run_dir)
    plain_state = _plain_state(
        status=status,
        active=active,
        latest_blocker=latest_blocker,
        stage_progress=stage_progress,
        backlog_diag=backlog_diag,
        proposals=proposals,
    )
    compact_progress = _compact_progress(
        task_source=task_source,
        active=active,
        latest_run_result=automation_result,
        latest_run_dir=current_run_dir,
        stage_progress=stage_progress,
        backlog_diag=backlog_diag,
    )
    blocker_guidance = _blocker_guidance(repo_root, latest_blocker)
    queue_explanation = _queue_explanation(backlog_diag, proposals, synthesis)
    truth_warnings = _truth_warnings(
        status=status,
        active=active,
        task=task,
        backlog_diag=backlog_diag,
        latest_blocker=latest_blocker,
    )
    system_reality = _system_reality(
        root=repo_root,
        latest_run_dir=latest_run_dir,
        memory_store=memory_store,
        eval_result=eval_result,
        truth_warnings=truth_warnings,
    )
    next_action = _recommended_action(
        backlog_diag=backlog_diag,
        latest_blocker=latest_blocker,
        blocker_guidance=blocker_guidance,
        proposals=proposals,
        synthesis=synthesis,
        active=active,
        status=status,
        truth_warnings=truth_warnings,
    )
    selector_items = {
        "proposals": [
            {
                "id": str(item.get("proposal_id") or ""),
                "label": str(item.get("title") or item.get("proposal_id") or "draft proposal"),
                "detail": str(item.get("affected_ticket_family") or "unknown"),
            }
            for item in proposals.get("all", [])
            if item.get("status") == "draft"
        ],
        "approved_proposals": [
            {
                "id": str(item.get("proposal_id") or ""),
                "label": str(item.get("title") or item.get("proposal_id") or "approved proposal"),
                "detail": str(item.get("affected_ticket_family") or "unknown"),
            }
            for item in proposals.get("all", [])
            if item.get("status") == "accepted"
            and str(item.get("proposal_id") or "") not in synthesized_source_ids
        ],
        "syntheses": [
            {
                "id": str(item.get("synthesis_id") or ""),
                "label": str(item.get("title") or item.get("ticket_id_placeholder") or "draft synthesis"),
                "detail": str(item.get("ticket_id_placeholder") or ""),
            }
            for item in synthesized_payload.get("entries", [])
            if item.get("status") == "draft" and not item.get("synthesis_eval_blocked")
        ],
        "blockers": [
            {
                "id": str(item.get("id") or ""),
                "label": str(item.get("title") or item.get("id") or "open blocker"),
                "detail": str(item.get("diagnosis") or "").strip(),
            }
            for item in open_blockers
        ],
    }
    return {
        "generated_at": now_iso(),
        "root": str(repo_root),
        "backlog": backlog,
        "backlog_diagnostics": backlog_diag,
        "status": status,
        "active": active,
        "ledger": ledger,
        "memory_store": memory_store,
        "feedback": feedback,
        "proposals": proposals,
        "synthesis": synthesis,
        "latest_run_dir": str(latest_run_dir) if latest_run_dir else None,
        "current_run_dir": str(current_run_dir) if current_run_dir else None,
        "current_task_source": task_source,
        "latest_run_result": automation_result,
        "latest_blocker": latest_blocker,
        "open_blockers": open_blockers,
        "task": task,
        "artifact_panel": artifact_panel,
        "eval_result": eval_result,
        "judge_result": judge_result,
        "stage_progress": stage_progress,
        "plain_state": plain_state,
        "compact_progress": compact_progress,
        "blocker_guidance": blocker_guidance,
        "queue_explanation": queue_explanation,
        "truth_warnings": truth_warnings,
        "system_reality": system_reality,
        "event_feed": event_feed,
        "canonical_event_schema_version": CANONICAL_EVENT_SCHEMA_VERSION,
        "stats": _actual_stats(backlog_diag),
        "next_recommended_action": next_action,
        "selector_items": selector_items,
    }
