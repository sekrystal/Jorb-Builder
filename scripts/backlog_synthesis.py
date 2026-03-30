#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
from typing import Any

from common import builder_root, load_data, write_data
from private_eval_suite import compare_eval_results, score_synthesized_entry


ROOT = builder_root()
BACKLOG = ROOT / "backlog.yml"
PROPOSALS = ROOT / "backlog_proposals.json"
SYNTHESIZED = ROOT / "synthesized_backlog_entries.json"
APPLY_AUDIT = ROOT / "backlog_apply_audit.json"
SUPPORTED_SYNTHESIS_FAMILIES = {"JORB-INFRA"}

REQUIRED_ENTRY_FIELDS = (
    "ticket_id_placeholder",
    "title",
    "status_default",
    "priority_recommendation",
    "rationale",
    "evidence_summary",
    "dependencies",
    "affected_ticket_family",
    "acceptance_criteria",
    "required_artifacts",
    "validation_expectations",
    "requires_vm_runtime_proof",
    "provenance",
    "operator_approval",
)
GENERIC_ACCEPTANCE_PHRASES = {
    "works correctly",
    "works as expected",
    "is complete",
    "no regressions",
    "done",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return load_data(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _synthesis_id(proposal_id: str) -> str:
    return "syn-" + hashlib.sha1(proposal_id.encode("utf-8")).hexdigest()[:12]


def _load_proposals(root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root or ROOT)
    return _safe_load(repo_root / "backlog_proposals.json", {"generated_at": None, "proposals": []})


def _load_synthesized(root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root or ROOT)
    return _safe_load(repo_root / "synthesized_backlog_entries.json", {"generated_at": None, "entries": []})


def _family_defaults(family: str, proposal: dict[str, Any]) -> dict[str, Any]:
    required_artifacts = [
        "compiled_feature_spec.md",
        "proposal.md",
        "tradeoff_matrix.md",
        "judge_decision.md",
        "evidence_bundle.json",
    ]
    validation_expectations = [
        "python3 -m py_compile scripts/*.py",
        "pytest tests/test_automate_task_loop.py",
    ]
    return {
        "area": "builder",
        "type": "infrastructure",
        "repo_path": "~/projects/jorb-builder",
        "allowlist": ["../jorb-builder/**"],
        "forbid": ["../jorb/**"],
        "requires_vm_runtime_proof": False,
        "required_artifacts": required_artifacts,
        "validation_expectations": validation_expectations,
    }


def _acceptance_criteria_for_proposal(proposal: dict[str, Any]) -> list[str]:
    action = str(proposal.get("proposed_action_type") or "")
    issue = str(proposal.get("evidence_summary") or proposal.get("title") or "the observed issue").strip().rstrip(".")
    base = [
        f"Automated validation proves the recurring issue is handled explicitly: {issue}.",
        "Operator-visible status or artifacts show the new routing or decision boundary without relying on narrative summary.",
        "Evidence artifacts include judge_decision.md and evidence_bundle.json with provenance back to the triggering proposal.",
        "The implementation remains scoped to one builder mechanism and does not silently mutate backlog or roadmap state.",
    ]
    if action == "add_missing_eval_coverage":
        base.append("Replay or comparison output demonstrates the targeted eval gap before and after the change.")
    elif action == "split_oversized_ticket":
        base.append("The change reduces retry-loop risk by decomposing the work into smaller, independently testable steps.")
    elif action == "refine_existing_ticket":
        base.append("Preflight or validation behavior prevents the same recurring failure from surfacing again without clearer routing.")
    else:
        base.append("The change preserves provenance back to the source proposal and evidence links.")
    return base


def _proposal_is_supported(proposal: dict[str, Any]) -> bool:
    return (
        proposal.get("status") == "accepted"
        and str(proposal.get("affected_ticket_family") or "") in SUPPORTED_SYNTHESIS_FAMILIES
        and bool(proposal.get("evidence_links"))
    )


def _existing_backlog_ids(backlog: dict[str, Any]) -> set[str]:
    return {str(task.get("id")) for task in backlog.get("tasks", [])}


def _duplicate_matches(entry: dict[str, Any], backlog: dict[str, Any], synthesized_payload: dict[str, Any]) -> list[str]:
    matches: list[str] = []
    existing_ids = _existing_backlog_ids(backlog)
    if entry["ticket_id_placeholder"] in existing_ids:
        matches.append(f"id:{entry['ticket_id_placeholder']}")
    title = entry["title"].strip().lower()
    for task in backlog.get("tasks", []):
        if str(task.get("title") or "").strip().lower() == title:
            matches.append(f"title:{task.get('id')}")
    for other in synthesized_payload.get("entries", []):
        if other.get("synthesis_id") == entry.get("synthesis_id"):
            continue
        if other.get("ticket_id_placeholder") == entry["ticket_id_placeholder"]:
            matches.append(f"synthesized_id:{other.get('synthesis_id')}")
        if str(other.get("title") or "").strip().lower() == title:
            matches.append(f"synthesized_title:{other.get('synthesis_id')}")
    return matches


def validate_synthesized_entry(
    entry: dict[str, Any],
    *,
    backlog: dict[str, Any],
    synthesized_payload: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    for field in REQUIRED_ENTRY_FIELDS:
        if field not in entry:
            issues.append(f"missing:{field}")
    if not entry.get("acceptance_criteria") or not isinstance(entry.get("acceptance_criteria"), list):
        issues.append("acceptance_criteria:missing_or_invalid")
    else:
        generic = [
            criterion
            for criterion in entry["acceptance_criteria"]
            if str(criterion).strip().lower() in GENERIC_ACCEPTANCE_PHRASES
        ]
        if generic:
            issues.append("acceptance_criteria:generic")
    if not entry.get("evidence_links"):
        issues.append("evidence_links:missing")
    if not entry.get("operator_approval", {}).get("approved"):
        issues.append("operator_approval:missing")
    backlog_ids = _existing_backlog_ids(backlog)
    invalid_dependencies = [dependency for dependency in entry.get("dependencies", []) if dependency not in backlog_ids]
    if invalid_dependencies:
        issues.extend(f"invalid_dependency:{dependency}" for dependency in invalid_dependencies)
    duplicates = _duplicate_matches(entry, backlog, synthesized_payload)
    return {
        "issues": issues,
        "invalid_dependencies": invalid_dependencies,
        "duplicate_matches": duplicates,
        "passed": not issues and not duplicates,
    }


def synthesize_entry_from_proposal(proposal: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root or ROOT)
    family = str(proposal.get("affected_ticket_family") or "JORB-INFRA")
    defaults = _family_defaults(family, proposal)
    ticket_id_placeholder = str((proposal.get("draft_ticket") or {}).get("id_placeholder") or f"DRAFT-{family}-FOLLOWUP")
    entry = {
        "synthesis_id": _synthesis_id(str(proposal["proposal_id"])),
        "ticket_id_placeholder": ticket_id_placeholder,
        "title": proposal["title"],
        "status_default": "pending",
        "priority_recommendation": proposal.get("priority_recommendation") or "medium",
        "rationale": proposal.get("rationale"),
        "evidence_summary": proposal.get("evidence_summary"),
        "evidence_links": list(proposal.get("evidence_links") or []),
        "dependencies": list(proposal.get("dependencies") or []),
        "affected_ticket_family": family,
        "subsystem": proposal.get("affected_ticket_family"),
        "acceptance_criteria": _acceptance_criteria_for_proposal(proposal),
        "required_artifacts": defaults["required_artifacts"],
        "validation_expectations": defaults["validation_expectations"],
        "requires_vm_runtime_proof": defaults["requires_vm_runtime_proof"],
        "type": defaults["type"],
        "area": defaults["area"],
        "repo_path": defaults["repo_path"],
        "allowlist": list(defaults["allowlist"]),
        "forbid": list(defaults["forbid"]),
        "provenance": {
            "source_proposal_id": proposal["proposal_id"],
            "evidence_links": list(proposal.get("evidence_links") or []),
            "confidence": proposal.get("confidence"),
            "recurrence_count": proposal.get("recurrence_count"),
            "generated_at": now_iso(),
        },
        "operator_approval": {
            "required": True,
            "approved": proposal.get("status") == "accepted",
            "review_status": proposal.get("status"),
            "reviewed_at": proposal.get("reviewed_at"),
            "review_note": proposal.get("review_note"),
        },
        "source_signal_id": proposal.get("source_signal_id"),
        "artifact_dir": str(repo_root / "run_logs"),
        "status": "draft",
        "created_at": now_iso(),
    }
    return entry


def generate_synthesized_entries(root: Path | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    repo_root = Path(root or ROOT)
    backlog = load_data(repo_root / "backlog.yml")
    proposals_payload = _load_proposals(repo_root)
    existing_payload = _load_synthesized(repo_root)
    entries = list(existing_payload.get("entries", []))
    prior_by_proposal = {entry.get("provenance", {}).get("source_proposal_id"): entry for entry in entries}

    for proposal in proposals_payload.get("proposals", []):
        if not _proposal_is_supported(proposal):
            continue
        proposal_id = str(proposal["proposal_id"])
        if proposal_id in prior_by_proposal:
            continue
        entry = synthesize_entry_from_proposal(proposal, root=repo_root)
        validation = validate_synthesized_entry(entry, backlog=backlog, synthesized_payload={"entries": entries})
        entry["validation"] = validation
        eval_result = score_synthesized_entry(entry, root=repo_root)
        prior_eval = None
        existing_for_title = next(
            (
                item.get("synthesis_eval")
                for item in entries
                if str(item.get("title") or "").strip().lower() == str(entry.get("title") or "").strip().lower()
                and item.get("synthesis_eval")
            ),
            None,
        )
        if existing_for_title:
            prior_eval = compare_eval_results(existing_for_title, eval_result)
        entry["synthesis_eval"] = eval_result
        entry["eval_comparison"] = prior_eval
        entry["synthesis_eval_blocked"] = not eval_result.get("passed", True)
        entries.append(entry)

    payload = {"generated_at": now_iso(), "entries": entries}
    if not dry_run:
        _write_json(repo_root / "synthesized_backlog_entries.json", payload)
    return payload


def _backlog_task_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry["ticket_id_placeholder"],
        "title": entry["title"],
        "type": entry.get("type", "infrastructure"),
        "area": entry.get("area", "builder"),
        "repo_path": entry.get("repo_path", "~/projects/jorb-builder"),
        "priority": 2 if entry.get("priority_recommendation") == "high" else 3,
        "status": entry.get("status_default", "pending"),
        "retries_used": 0,
        "depends_on": entry.get("dependencies", []),
        "prompt": "implement_feature",
        "objective": entry.get("rationale"),
        "why_it_matters": entry.get("evidence_summary"),
        "acceptance_criteria": entry.get("acceptance_criteria", []),
        "verification": entry.get("validation_expectations", []),
        "allowlist": entry.get("allowlist", ["../jorb-builder/**"]),
        "forbid": entry.get("forbid", ["../jorb/**"]),
        "required_artifacts": entry.get("required_artifacts", []),
        "requires_vm_runtime_proof": entry.get("requires_vm_runtime_proof", False),
        "provenance": entry.get("provenance"),
        "operator_approval": entry.get("operator_approval"),
        "notes": [f"Synthesized from proposal {entry.get('provenance', {}).get('source_proposal_id')}"],
    }


def apply_synthesized_entry(synthesis_id: str, *, root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root or ROOT)
    backlog_path = repo_root / "backlog.yml"
    backlog_before_text = backlog_path.read_text(encoding="utf-8")
    backlog = load_data(backlog_path)
    payload = _load_synthesized(repo_root)
    entry = next((item for item in payload.get("entries", []) if item.get("synthesis_id") == synthesis_id), None)
    if entry is None:
        raise KeyError(synthesis_id)
    validation = validate_synthesized_entry(entry, backlog=backlog, synthesized_payload=payload)
    if not entry.get("operator_approval", {}).get("approved"):
        raise ValueError("operator approval required before apply")
    if not validation.get("passed"):
        raise ValueError(f"entry validation failed: {validation}")
    if entry.get("synthesis_eval_blocked"):
        raise ValueError("synthesis eval threshold not met")

    backlog.setdefault("tasks", []).append(_backlog_task_from_entry(entry))
    write_data(backlog_path, backlog)
    backlog_after_text = backlog_path.read_text(encoding="utf-8")

    entry["status"] = "applied"
    entry["applied_at"] = now_iso()
    payload["generated_at"] = now_iso()
    _write_json(repo_root / "synthesized_backlog_entries.json", payload)

    audit_payload = _safe_load(repo_root / "backlog_apply_audit.json", {"events": []})
    audit_payload["events"].append(
        {
            "applied_at": now_iso(),
            "synthesis_id": synthesis_id,
            "source_proposal_id": entry.get("provenance", {}).get("source_proposal_id"),
            "synthesized_entry_sha1": _sha1_text(json.dumps(entry, sort_keys=True)),
            "backlog_before_sha1": _sha1_text(backlog_before_text),
            "backlog_after_sha1": _sha1_text(backlog_after_text),
            "ticket_id": entry["ticket_id_placeholder"],
            "operator_review": entry.get("operator_approval"),
        }
    )
    _write_json(repo_root / "backlog_apply_audit.json", audit_payload)
    return entry


def synthesis_summary_for_operator(root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root or ROOT)
    payload = _load_synthesized(repo_root)
    entries = payload.get("entries", [])
    draft = [entry for entry in entries if entry.get("status") == "draft"]
    applied = [entry for entry in entries if entry.get("status") == "applied"]
    blocked = [entry for entry in entries if entry.get("synthesis_eval_blocked")]
    top_draft = draft[0] if draft else None
    return {
        "entry_count": len(entries),
        "draft_count": len(draft),
        "applied_count": len(applied),
        "blocked_count": len(blocked),
        "top_draft": top_draft,
        "top_draft_eval_score": None if top_draft is None else (top_draft.get("synthesis_eval") or {}).get("overall_score"),
        "top_draft_eval_passed": None if top_draft is None else not top_draft.get("synthesis_eval_blocked"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthesize approved backlog proposals into validated backlog-entry drafts.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--apply", metavar="SYNTHESIS_ID")
    args = parser.parse_args()

    if args.status:
        print(json.dumps(synthesis_summary_for_operator(ROOT), indent=2))
        return 0
    if args.apply:
        print(json.dumps(apply_synthesized_entry(args.apply, root=ROOT), indent=2))
        return 0
    print(json.dumps(generate_synthesized_entries(ROOT, dry_run=args.dry_run), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
