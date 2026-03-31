#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
from typing import Any

from common import builder_root, load_data, task_family, write_data


ROOT = builder_root()
TASK_HISTORY = ROOT / "task_history"
RUN_LEDGER = ROOT / "run_ledger.json"
BACKLOG = ROOT / "backlog.yml"
STATUS = ROOT / "status.yml"
FEEDBACK_INPUT = ROOT / "operator_feedback.json"
SIGNALS_FILE = ROOT / "feedback_signals.json"
PROPOSALS_FILE = ROOT / "backlog_proposals.json"
INTERPRETATION_FILE = ROOT / "feedback_interpretation.md"
MEMORY_OVERRIDES = ROOT / "memory_overrides.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _safe_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return load_data(path)


def _signal_id(kind: str, key: str) -> str:
    return "sig-" + hashlib.sha1(f"{kind}:{key}".encode("utf-8")).hexdigest()[:12]


def _proposal_id(key: str) -> str:
    return "prop-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _confidence_from_recurrence(recurrence: int, *, severe: bool = False) -> float:
    base = 0.45 + min(recurrence, 5) * 0.1
    if severe:
        base += 0.15
    return round(min(base, 0.95), 2)


def classify_feedback_interpretation(
    *,
    observation: str,
    interpreted_issue: str,
    proposed_action: str,
    signal_type: str,
    subsystem: str,
) -> dict[str, str]:
    lower_observation = observation.lower()
    normalized_issue = interpreted_issue.strip().lower()
    normalized_action = proposed_action.strip().lower()
    normalized_signal_type = signal_type.strip().lower()
    normalized_subsystem = subsystem.strip().lower() or "builder"

    if "ux" in normalized_issue or "ux" in lower_observation or normalized_subsystem in {"ui", "ux", "figma"}:
        dimension = "ux"
        gap = "The produced interface or presentation does not match the operator's intent."
        corrective_work = "Create or refine a focused UX correction ticket with explicit acceptance evidence."
    elif "memory" in normalized_issue or "memory" in lower_observation:
        dimension = "memory"
        gap = "Retrieved memory context is adding noise instead of helping the active task."
        corrective_work = "Tighten memory retrieval filters or add overrides that suppress irrelevant memory entries."
    elif "eval" in normalized_issue or normalized_action == "add_missing_eval_coverage" or normalized_signal_type == "eval_regression":
        dimension = "evaluation"
        gap = "Validation coverage is not proving the behavior that regressed."
        corrective_work = "Add or tighten evaluation coverage before accepting similar work again."
    elif "artifact" in normalized_issue or normalized_signal_type == "artifact_gap":
        dimension = "artifact_enforcement"
        gap = "Required builder artifacts are incomplete or missing evidence needed for acceptance."
        corrective_work = "Strengthen artifact generation or acceptance gates so the missing evidence becomes mandatory."
    elif "preflight" in normalized_issue or normalized_signal_type == "preflight_failure":
        dimension = "preflight"
        gap = "The task packet or environment setup is missing prerequisites for bounded execution."
        corrective_work = "Refine task preflight checks or task metadata before retrying execution."
    elif "retry_loop" in normalized_issue or normalized_signal_type == "retry_loop":
        dimension = "planning"
        gap = "The current task shape or plan is causing repeated retries without converging."
        corrective_work = "Split the work or refine the implementation plan to stop the retry loop."
    elif "flaky" in normalized_issue or "nondeterministic" in lower_observation:
        dimension = "determinism"
        gap = "The workflow is producing unstable or nondeterministic outcomes."
        corrective_work = "Harden the execution or validation path so repeated runs behave deterministically."
    else:
        dimension = normalized_subsystem.replace(" ", "_") or "builder"
        gap = "Operator feedback indicates a builder-system gap that is not yet categorized more precisely."
        corrective_work = "Review the evidence and convert the gap into a bounded corrective backlog item."

    return {
        "feedback_dimension": dimension,
        "system_gap": gap,
        "corrective_work": corrective_work,
    }


def load_operator_feedback(root: Path | None = None) -> list[dict[str, Any]]:
    repo_root = Path(root or ROOT)
    payload = _safe_load(repo_root / "operator_feedback.json", {"entries": []})
    entries = payload.get("entries", []) if isinstance(payload, dict) else []
    return [entry for entry in entries if isinstance(entry, dict)]


def normalize_operator_feedback(entry: dict[str, Any]) -> dict[str, Any]:
    observation = str(entry.get("feedback") or entry.get("observation") or "").strip()
    subsystem = str(entry.get("subsystem") or entry.get("ticket_family") or "builder")
    inferred_issue = str(entry.get("interpreted_issue") or "").strip()
    if not inferred_issue:
        lower = observation.lower()
        if "ux" in lower or "figma" in lower:
            inferred_issue = "ux_mismatch"
        elif "flaky" in lower or "nondeterministic" in lower:
            inferred_issue = "flaky_validation"
        elif "memory" in lower and ("noise" in lower or "irrelevant" in lower):
            inferred_issue = "memory_noise"
        else:
            inferred_issue = "operator_reported_gap"
    proposed_action = str(entry.get("proposed_action_type") or "request_operator_decision")
    evidence_links = list(entry.get("evidence_links") or [])
    feedback_id = str(entry.get("feedback_id") or _signal_id("operator_feedback", observation + subsystem))
    interpretation = classify_feedback_interpretation(
        observation=observation,
        interpreted_issue=inferred_issue,
        proposed_action=proposed_action,
        signal_type="operator_feedback",
        subsystem=subsystem,
    )
    return {
        "signal_id": feedback_id,
        "signal_type": "operator_feedback",
        "raw_observation": observation,
        "interpreted_issue": inferred_issue,
        "confidence": float(entry.get("confidence") or 0.75),
        "evidence_links": evidence_links,
        "affected_ticket_family": entry.get("ticket_family"),
        "affected_subsystem": subsystem,
        "proposed_action_type": proposed_action,
        "observation": observation,
        "inference": str(entry.get("inference") or f"Operator feedback suggests {inferred_issue.replace('_', ' ')}."),
        "recommendation": str(entry.get("recommendation") or "Review and decide whether a corrective ticket or refinement is needed."),
        "recurrence_count": int(entry.get("recurrence_count") or 1),
        "severity": str(entry.get("severity") or "medium"),
        "source_artifacts": evidence_links,
        "created_at": str(entry.get("created_at") or now_iso()),
        "status": str(entry.get("status") or "active"),
        **interpretation,
    }


def _history_entries(root: Path | None = None) -> list[dict[str, Any]]:
    repo_root = Path(root or ROOT)
    entries: list[dict[str, Any]] = []
    for path in sorted((repo_root / "task_history").glob("*.yml")):
        payload = load_data(path)
        payload["_path"] = str(path)
        entries.append(payload)
    return entries


def _history_signal_groups(root: Path | None = None) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for payload in _history_entries(root):
        task_id = str(payload.get("task_id") or "")
        family = task_family(task_id)
        taxonomy = payload.get("failure_taxonomy") or {}
        eval_result = payload.get("eval_result") or {}
        summary = str((payload.get("notes") or [""])[0] if payload.get("notes") else "")

        if taxonomy.get("failure_class"):
            grouped[("failure_class", family, str(taxonomy["failure_class"]))].append(payload)
        if eval_result.get("regression_vs_prior", {}).get("trend") == "regressed":
            grouped[("eval_regression", family, "regressed")].append(payload)
        if "retry loop detected" in summary.lower():
            grouped[("retry_loop", family, "retry_loop")].append(payload)
        if "artifact enforcement failed" in summary.lower() or "ux conformance evidence is incomplete" in summary.lower():
            grouped[("artifact_gap", family, "artifact_gap")].append(payload)
        if "preflight" in summary.lower() or "missing automation configuration" in summary.lower():
            grouped[("preflight_failure", family, "preflight_failure")].append(payload)
    return grouped


def _signal_from_group(kind: str, family: str, label: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    recurrence = len(items)
    severe = kind in {"preflight_failure", "eval_regression"} and recurrence >= 1
    if recurrence < 2 and not severe:
        return None
    latest = items[-1]
    evidence_links = [str(item.get("_path")) for item in items[-5:]]
    observation = "; ".join(str((item.get("notes") or [""])[0]) for item in items[-3:] if item.get("notes"))
    interpreted_issue = {
        "failure_class": f"repeated_{label}",
        "eval_regression": "eval_regression",
        "retry_loop": "retry_loop_pattern",
        "artifact_gap": "artifact_gap_pattern",
        "preflight_failure": "repeated_preflight_failure",
    }.get(kind, kind)
    proposed_action = {
        "failure_class": "create_follow_up_hardening_ticket",
        "eval_regression": "add_missing_eval_coverage",
        "retry_loop": "split_oversized_ticket",
        "artifact_gap": "add_missing_acceptance_criteria",
        "preflight_failure": "refine_existing_ticket",
    }.get(kind, "request_operator_decision")
    interpretation = classify_feedback_interpretation(
        observation=observation or str((latest.get("notes") or [""])[0]),
        interpreted_issue=interpreted_issue,
        proposed_action=proposed_action,
        signal_type=kind,
        subsystem=family.lower(),
    )
    return {
        "signal_id": _signal_id(kind, f"{family}:{label}"),
        "signal_type": kind,
        "raw_observation": observation or str((latest.get("notes") or [""])[0]),
        "interpreted_issue": interpreted_issue,
        "confidence": _confidence_from_recurrence(recurrence, severe=severe),
        "evidence_links": evidence_links,
        "affected_ticket_family": family,
        "affected_subsystem": family.lower(),
        "proposed_action_type": proposed_action,
        "observation": observation or str((latest.get("notes") or [""])[0]),
        "inference": f"Pattern observed {recurrence} times in {family}.",
        "recommendation": f"Consider {proposed_action.replace('_', ' ')} for {family}.",
        "recurrence_count": recurrence,
        "severity": "high" if severe or recurrence >= 3 else "medium",
        "source_artifacts": evidence_links,
        "created_at": now_iso(),
        "status": "active",
        **interpretation,
    }


def render_feedback_interpretation(signals_payload: dict[str, Any], proposals_payload: dict[str, Any]) -> str:
    signals = list(signals_payload.get("signals", []))
    proposals = list(proposals_payload.get("proposals", []))
    lines = [
        "# Feedback Interpretation",
        "",
        "The feedback interpretation engine converts raw operator feedback and recurring run evidence into structured signals.",
        "",
        "## Summary",
        f"- generated_at: {signals_payload.get('generated_at')}",
        f"- signal_count: {len(signals)}",
        f"- proposal_count: {len(proposals)}",
        "",
        "## Structured Signals",
    ]
    if not signals:
        lines.extend(["No active feedback signals were generated.", ""])
        return "\n".join(lines).rstrip() + "\n"
    for signal in signals:
        lines.extend(
            [
                f"### {signal.get('signal_id')}",
                f"- signal_type: {signal.get('signal_type')}",
                f"- feedback_dimension: {signal.get('feedback_dimension')}",
                f"- interpreted_issue: {signal.get('interpreted_issue')}",
                f"- system_gap: {signal.get('system_gap')}",
                f"- corrective_work: {signal.get('corrective_work')}",
                f"- proposed_action_type: {signal.get('proposed_action_type')}",
                f"- confidence: {signal.get('confidence')}",
                f"- recurrence_count: {signal.get('recurrence_count')}",
                f"- affected_ticket_family: {signal.get('affected_ticket_family')}",
                f"- affected_subsystem: {signal.get('affected_subsystem')}",
                f"- raw_observation: {signal.get('raw_observation')}",
            ]
        )
        evidence_links = list(signal.get("evidence_links") or [])
        if evidence_links:
            lines.append(f"- evidence_links: {', '.join(str(link) for link in evidence_links)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_feedback_signals(root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root or ROOT)
    signals: list[dict[str, Any]] = []
    for entry in load_operator_feedback(repo_root):
        signals.append(normalize_operator_feedback(entry))
    for (kind, family, label), items in _history_signal_groups(repo_root).items():
        signal = _signal_from_group(kind, family, label, items)
        if signal is not None:
            signals.append(signal)
    signals.sort(key=lambda item: (float(item.get("confidence") or 0.0), int(item.get("recurrence_count") or 0)), reverse=True)
    return {"generated_at": now_iso(), "signals": signals}


def _load_proposals(root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root or ROOT)
    return _safe_load(repo_root / "backlog_proposals.json", {"generated_at": None, "proposals": []})


def _proposal_key(signal: dict[str, Any]) -> str:
    return f"{signal.get('interpreted_issue')}::{signal.get('affected_ticket_family')}::{signal.get('proposed_action_type')}"


def _proposal_exists(existing: list[dict[str, Any]], key: str) -> bool:
    for proposal in existing:
        if proposal.get("dedupe_key") == key and proposal.get("status") in {"draft", "accepted", "under_review"}:
            return True
    return False


def _proposal_from_signal(signal: dict[str, Any], backlog: dict[str, Any]) -> dict[str, Any] | None:
    recurrence = int(signal.get("recurrence_count") or 1)
    confidence = float(signal.get("confidence") or 0.0)
    severe = str(signal.get("severity") or "") == "high"
    if recurrence < 2 and not severe:
        return None
    if confidence < 0.6:
        return None
    family = str(signal.get("affected_ticket_family") or "JORB-INFRA")
    interpreted_issue = str(signal.get("interpreted_issue") or "builder_gap")
    action = str(signal.get("proposed_action_type") or "request_operator_decision")
    title = {
        "add_missing_eval_coverage": f"Add eval coverage for {family} {interpreted_issue.replace('_', ' ')}",
        "add_missing_acceptance_criteria": f"Strengthen acceptance criteria for {family} {interpreted_issue.replace('_', ' ')}",
        "create_follow_up_hardening_ticket": f"Harden {family} against {interpreted_issue.replace('_', ' ')}",
        "split_oversized_ticket": f"Split recurring {family} retry-loop work",
        "refine_existing_ticket": f"Refine preflight handling for {family}",
    }.get(action, f"Review {family} {interpreted_issue.replace('_', ' ')}")
    evidence_links = list(signal.get("evidence_links") or signal.get("source_artifacts") or [])
    dependencies = []
    if family.startswith("JORB-INFRA"):
        dependencies.append("JORB-INFRA-010")
    dedupe_key = _proposal_key(signal)
    return {
        "proposal_id": _proposal_id(dedupe_key),
        "dedupe_key": dedupe_key,
        "status": "draft",
        "source_signal_id": signal.get("signal_id"),
        "title": title,
        "rationale": signal.get("recommendation"),
        "evidence_summary": signal.get("inference"),
        "evidence_links": evidence_links,
        "affected_ticket_family": family,
        "priority_recommendation": "high" if severe else "medium",
        "confidence": confidence,
        "recurrence_count": recurrence,
        "proposed_action_type": action,
        "dependencies": dependencies,
        "operator_approval_required": True,
        "draft_ticket": {
            "id_placeholder": f"DRAFT-{family}-{interpreted_issue.upper()}",
            "title": title,
            "type": "infrastructure" if family.startswith("JORB-INFRA") else "hardening",
            "area": "builder" if family.startswith("JORB-INFRA") else "product",
            "objective": signal.get("recommendation"),
            "evidence_basis": evidence_links,
        },
        "created_at": now_iso(),
    }


def generate_backlog_proposals(root: Path | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    repo_root = Path(root or ROOT)
    signals_payload = build_feedback_signals(repo_root)
    backlog = load_data(repo_root / "backlog.yml")
    existing_payload = _load_proposals(repo_root)
    proposals = list(existing_payload.get("proposals", []))
    for signal in signals_payload.get("signals", []):
        key = _proposal_key(signal)
        if _proposal_exists(proposals, key):
            continue
        proposal = _proposal_from_signal(signal, backlog)
        if proposal is not None:
            proposals.append(proposal)
    payload = {"generated_at": now_iso(), "proposals": proposals}
    interpretation_text = render_feedback_interpretation(signals_payload, payload)
    if not dry_run:
        _write_json(repo_root / SIGNALS_FILE.name, signals_payload)
        _write_json(repo_root / PROPOSALS_FILE.name, payload)
        (repo_root / INTERPRETATION_FILE.name).write_text(interpretation_text, encoding="utf-8")
    return {"signals": signals_payload, "proposals": payload}


def update_proposal_status(proposal_id: str, status: str, *, note: str | None = None, root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root or ROOT)
    payload = _load_proposals(repo_root)
    updated: dict[str, Any] | None = None
    for proposal in payload.get("proposals", []):
        if proposal.get("proposal_id") == proposal_id:
            proposal["status"] = status
            proposal["reviewed_at"] = now_iso()
            if note:
                proposal["review_note"] = note
            updated = proposal
            break
    if updated is None:
        raise KeyError(proposal_id)
    _write_json(repo_root / "backlog_proposals.json", payload)
    persist_proposal_feedback_memory(updated, root=repo_root)
    return updated


def persist_proposal_feedback_memory(proposal: dict[str, Any], *, root: Path | None = None) -> None:
    repo_root = Path(root or ROOT)
    payload = _safe_load(repo_root / "memory_overrides.json", {"memory_status": {}, "manual_entries": [], "pins": []})
    manual_entries = [entry for entry in payload.get("manual_entries", []) if entry.get("memory_id") != f"proposal-{proposal['proposal_id']}"]
    status = str(proposal.get("status") or "draft")
    entry = {
        "memory_id": f"proposal-{proposal['proposal_id']}",
        "memory_type": "operator_feedback",
        "ticket_family": proposal.get("affected_ticket_family"),
        "observation": proposal.get("evidence_summary"),
        "inference": proposal.get("rationale"),
        "primary_basis": "inference",
        "origin": "operator",
        "role_fit": ["planner", "judge"],
        "relevance_tags": ["proposal_review", status],
        "status": "active" if status == "accepted" else "invalidated" if status == "rejected" else "stale",
        "status_reason": f"proposal_{status}",
        "source_artifact": str(repo_root / "backlog_proposals.json"),
        "confidence": float(proposal.get("confidence") or 0.7),
        "content": proposal.get("title"),
    }
    manual_entries.append(entry)
    payload["manual_entries"] = manual_entries
    _write_json(repo_root / "memory_overrides.json", payload)


def feedback_summary_for_operator(root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root or ROOT)
    signals = _safe_load(repo_root / "feedback_signals.json", {"signals": []})
    proposals = _safe_load(repo_root / "backlog_proposals.json", {"proposals": []})
    draft = [item for item in proposals.get("proposals", []) if item.get("status") == "draft"]
    return {
        "signal_count": len(signals.get("signals", [])),
        "proposal_count": len(proposals.get("proposals", [])),
        "draft_count": len(draft),
        "top_draft": draft[0] if draft else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate structured feedback signals and backlog proposals.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true", help="Print current signal/proposal summary.")
    parser.add_argument("--review", nargs=2, metavar=("PROPOSAL_ID", "STATUS"), help="Update proposal status to draft|under_review|accepted|rejected|superseded.")
    parser.add_argument("--note", default=None)
    args = parser.parse_args()

    if args.status:
        print(json.dumps(feedback_summary_for_operator(ROOT), indent=2))
        return 0
    if args.review:
        proposal_id, status = args.review
        print(json.dumps(update_proposal_status(proposal_id, status, note=args.note, root=ROOT), indent=2))
        return 0
    payload = generate_backlog_proposals(ROOT, dry_run=args.dry_run)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
