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
SATISFIED_BACKLOG_STATUSES = {"accepted", "done"}


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


def _acceptance_text(criteria: list[Any]) -> str:
    return " ".join(str(item).strip().lower() for item in criteria if str(item).strip())


def _acceptance_criteria_for_proposal(proposal: dict[str, Any]) -> list[str]:
    action = str(proposal.get("proposed_action_type") or "")
    issue = str(proposal.get("evidence_summary") or proposal.get("title") or "the observed issue").strip().rstrip(".")
    family = str(proposal.get("affected_ticket_family") or "JORB-INFRA").strip() or "JORB-INFRA"
    recurrence = proposal.get("recurrence_count")
    proposal_id = str(proposal.get("proposal_id") or "").strip() or "unknown_proposal"
    evidence_links = [str(item).strip() for item in proposal.get("evidence_links", []) if str(item).strip()]
    recurrence_clause = (
        f"Canonical run ledger recorded {recurrence} blocked runtime outcome(s) for {family}."
        if recurrence not in (None, "")
        else f"Canonical evidence remains recorded for {family}."
    )
    evidence_clause = (
        "Provenance points back to "
        + proposal_id
        + " via evidence links: "
        + ", ".join(evidence_links)
        + "."
        if evidence_links
        else f"Provenance points back to {proposal_id}."
    )
    base = [
        f"Automated validation proves the recurring issue is handled explicitly: {issue}. {recurrence_clause}",
        "Operator-visible status or artifacts show the new routing or decision boundary without relying on narrative summary.",
        f"Evidence artifacts include judge_decision.md and evidence_bundle.json with provenance back to the triggering proposal. {evidence_clause}",
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


def _synthesized_ticket_ids(synthesized_payload: dict[str, Any]) -> set[str]:
    return {
        str(entry.get("ticket_id_placeholder"))
        for entry in synthesized_payload.get("entries", [])
        if str(entry.get("ticket_id_placeholder") or "").strip()
    }


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
        acceptance_text = _acceptance_text(entry["acceptance_criteria"])
        if "operator-visible status or artifacts show the new routing or decision boundary" not in acceptance_text:
            issues.append("acceptance_criteria:missing_operator_truth_gate")
        if "judge_decision.md" not in acceptance_text or "evidence_bundle.json" not in acceptance_text:
            issues.append("acceptance_criteria:missing_evidence_artifact_gate")
        if "provenance" not in acceptance_text or "triggering proposal" not in acceptance_text:
            issues.append("acceptance_criteria:missing_provenance_gate")
        provenance = entry.get("provenance") or {}
        recurrence = provenance.get("recurrence_count")
        family = str(entry.get("affected_ticket_family") or "").strip()
        if recurrence not in (None, ""):
            recurrence_phrase = f"{recurrence} blocked runtime outcome(s)"
            if recurrence_phrase not in acceptance_text:
                issues.append("acceptance_criteria:missing_recurrence_count")
        if family and family.lower() not in acceptance_text:
            issues.append("acceptance_criteria:missing_ticket_family")
    if not entry.get("evidence_links"):
        issues.append("evidence_links:missing")
    if not entry.get("operator_approval", {}).get("approved"):
        issues.append("operator_approval:missing")
    valid_dependency_ids = _existing_backlog_ids(backlog) | _synthesized_ticket_ids(synthesized_payload)
    valid_dependency_ids.discard(str(entry.get("ticket_id_placeholder") or ""))
    invalid_dependencies = [dependency for dependency in entry.get("dependencies", []) if dependency not in valid_dependency_ids]
    if invalid_dependencies:
        issues.extend(f"invalid_dependency:{dependency}" for dependency in invalid_dependencies)
    duplicates = _duplicate_matches(entry, backlog, synthesized_payload)
    return {
        "issues": issues,
        "invalid_dependencies": invalid_dependencies,
        "duplicate_matches": duplicates,
        "passed": not issues and not duplicates,
    }


def _priority_rank(value: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(str(value or "").strip().lower(), 3)


def _execution_sort_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _priority_rank(str(entry.get("priority_recommendation") or "")),
        str(entry.get("title") or "").strip().lower(),
        str(entry.get("ticket_id_placeholder") or "").strip(),
        str(entry.get("synthesis_id") or "").strip(),
    )


def build_synthesis_plan(
    entries: list[dict[str, Any]],
    *,
    backlog: dict[str, Any],
) -> dict[str, Any]:
    backlog_by_id = {
        str(task.get("id")): task
        for task in backlog.get("tasks", [])
        if str(task.get("id") or "").strip()
    }
    entry_by_ticket = {
        str(entry.get("ticket_id_placeholder")): entry
        for entry in entries
        if str(entry.get("ticket_id_placeholder") or "").strip()
    }
    entry_by_synthesis = {
        str(entry.get("synthesis_id")): entry
        for entry in entries
        if str(entry.get("synthesis_id") or "").strip()
    }

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    internal_dependents: dict[str, set[str]] = {synthesis_id: set() for synthesis_id in entry_by_synthesis}
    indegree: dict[str, int] = {synthesis_id: 0 for synthesis_id in entry_by_synthesis}

    for entry in entries:
        synthesis_id = str(entry.get("synthesis_id") or "")
        ticket_id = str(entry.get("ticket_id_placeholder") or "")
        dependencies = [str(dep) for dep in entry.get("dependencies", []) if str(dep).strip()]
        internal_dependencies: list[str] = []
        external_dependencies: list[dict[str, Any]] = []
        missing_dependencies: list[str] = []

        for dependency in dependencies:
            if dependency in entry_by_ticket:
                dep_entry = entry_by_ticket[dependency]
                dep_synthesis_id = str(dep_entry.get("synthesis_id") or "")
                internal_dependencies.append(dep_synthesis_id)
                if dep_synthesis_id in indegree:
                    indegree[synthesis_id] += 1
                    internal_dependents.setdefault(dep_synthesis_id, set()).add(synthesis_id)
                edges.append(
                    {
                        "from_ticket_id": dependency,
                        "from_synthesis_id": dep_synthesis_id,
                        "to_ticket_id": ticket_id,
                        "to_synthesis_id": synthesis_id,
                        "kind": "synthesized_dependency",
                    }
                )
                continue
            backlog_task = backlog_by_id.get(dependency)
            if backlog_task is None:
                missing_dependencies.append(dependency)
                edges.append(
                    {
                        "from_ticket_id": dependency,
                        "from_synthesis_id": None,
                        "to_ticket_id": ticket_id,
                        "to_synthesis_id": synthesis_id,
                        "kind": "missing_dependency",
                    }
                )
                continue
            external_dependencies.append(
                {
                    "ticket_id": dependency,
                    "status": str(backlog_task.get("status") or "unknown"),
                    "satisfied": str(backlog_task.get("status") or "") in SATISFIED_BACKLOG_STATUSES,
                }
            )
            edges.append(
                {
                    "from_ticket_id": dependency,
                    "from_synthesis_id": None,
                    "to_ticket_id": ticket_id,
                    "to_synthesis_id": synthesis_id,
                    "kind": "backlog_dependency",
                }
            )

        unmet_external_dependencies = [
            dependency["ticket_id"] for dependency in external_dependencies if not dependency["satisfied"]
        ]
        validation = entry.get("validation") or {}
        plan_blockers: list[str] = []
        if not entry.get("operator_approval", {}).get("approved"):
            plan_blockers.append("operator_approval")
        if entry.get("synthesis_eval_blocked"):
            plan_blockers.append("synthesis_eval")
        if validation.get("issues") or validation.get("duplicate_matches"):
            plan_blockers.append("validation")
        if missing_dependencies:
            plan_blockers.extend(f"missing_dependency:{dependency}" for dependency in missing_dependencies)
        if unmet_external_dependencies:
            plan_blockers.extend(f"external_dependency:{dependency}" for dependency in unmet_external_dependencies)

        if entry.get("status") == "applied":
            plan_state = "applied"
        elif plan_blockers:
            plan_state = "blocked"
        else:
            plan_state = "ready"

        nodes.append(
            {
                "synthesis_id": synthesis_id,
                "ticket_id": ticket_id,
                "title": entry.get("title"),
                "status": entry.get("status"),
                "plan_state": plan_state,
                "priority_recommendation": entry.get("priority_recommendation"),
                "dependencies": dependencies,
                "internal_dependencies": internal_dependencies,
                "external_dependencies": external_dependencies,
                "missing_dependencies": missing_dependencies,
                "validation_passed": bool(validation.get("passed")),
                "synthesis_eval_passed": not entry.get("synthesis_eval_blocked", False),
                "operator_approved": bool(entry.get("operator_approval", {}).get("approved")),
                "plan_blockers": plan_blockers,
            }
        )

    ready_queue = sorted(
        [entry for entry in entries if str(entry.get("synthesis_id") or "") in indegree and indegree[str(entry.get("synthesis_id") or "")] == 0],
        key=_execution_sort_key,
    )
    ordered_synthesis_ids: list[str] = []
    while ready_queue:
        current = ready_queue.pop(0)
        current_id = str(current.get("synthesis_id") or "")
        ordered_synthesis_ids.append(current_id)
        for dependent_id in sorted(internal_dependents.get(current_id, set())):
            indegree[dependent_id] -= 1
            if indegree[dependent_id] == 0:
                ready_queue.append(entry_by_synthesis[dependent_id])
        ready_queue.sort(key=_execution_sort_key)

    cycle_ids = [
        synthesis_id
        for synthesis_id in sorted(indegree)
        if indegree[synthesis_id] > 0 and synthesis_id not in ordered_synthesis_ids
    ]
    for synthesis_id in cycle_ids:
        ordered_synthesis_ids.append(synthesis_id)

    node_by_synthesis = {node["synthesis_id"]: node for node in nodes}
    execution_order: list[dict[str, Any]] = []
    for position, synthesis_id in enumerate(ordered_synthesis_ids, start=1):
        node = dict(node_by_synthesis[synthesis_id])
        if synthesis_id in cycle_ids and "dependency_cycle" not in node["plan_blockers"]:
            node["plan_blockers"] = list(node["plan_blockers"]) + ["dependency_cycle"]
            if node["plan_state"] != "applied":
                node["plan_state"] = "blocked"
        execution_order.append(
            {
                "position": position,
                "synthesis_id": synthesis_id,
                "ticket_id": node["ticket_id"],
                "title": node.get("title"),
                "plan_state": node.get("plan_state"),
                "priority_recommendation": node.get("priority_recommendation"),
                "plan_blockers": node.get("plan_blockers", []),
            }
        )

    return {
        "nodes": sorted(nodes, key=lambda item: (item["ticket_id"], item["synthesis_id"])),
        "edges": sorted(edges, key=lambda item: (item["to_ticket_id"], item["from_ticket_id"], item["kind"])),
        "execution_order": execution_order,
        "cycles": cycle_ids,
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
    new_entries: list[dict[str, Any]] = []

    for proposal in proposals_payload.get("proposals", []):
        if not _proposal_is_supported(proposal):
            continue
        proposal_id = str(proposal["proposal_id"])
        if proposal_id in prior_by_proposal:
            continue
        entry = synthesize_entry_from_proposal(proposal, root=repo_root)
        new_entries.append(entry)

    batch_entries = entries + new_entries
    for entry in new_entries:
        validation = validate_synthesized_entry(entry, backlog=backlog, synthesized_payload={"entries": batch_entries})
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

    synthesis_plan = build_synthesis_plan(entries, backlog=backlog)
    payload = {
        "generated_at": now_iso(),
        "entries": entries,
        "dependency_graph": {
            "nodes": synthesis_plan["nodes"],
            "edges": synthesis_plan["edges"],
            "cycles": synthesis_plan["cycles"],
        },
        "execution_order": synthesis_plan["execution_order"],
    }
    if not dry_run:
        _write_json(repo_root / "synthesized_backlog_entries.json", payload)
    return payload


def _canonical_status_for_entry(entry: dict[str, Any], *, backlog: dict[str, Any], payload: dict[str, Any]) -> str:
    synthesis_plan = build_synthesis_plan(payload.get("entries", []), backlog=backlog)
    node = next(
        (item for item in synthesis_plan.get("nodes", []) if item.get("synthesis_id") == entry.get("synthesis_id")),
        None,
    )
    if node and node.get("plan_state") == "ready":
        return "ready"
    return str(entry.get("status_default", "pending"))


def _backlog_task_from_entry(entry: dict[str, Any], *, canonical_status: str | None = None) -> dict[str, Any]:
    return {
        "id": entry["ticket_id_placeholder"],
        "title": entry["title"],
        "type": entry.get("type", "infrastructure"),
        "area": entry.get("area", "builder"),
        "repo_path": entry.get("repo_path", "~/projects/jorb-builder"),
        "priority": 2 if entry.get("priority_recommendation") == "high" else 3,
        "status": canonical_status or entry.get("status_default", "pending"),
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

    canonical_status = _canonical_status_for_entry(entry, backlog=backlog, payload=payload)
    backlog.setdefault("tasks", []).append(_backlog_task_from_entry(entry, canonical_status=canonical_status))
    write_data(backlog_path, backlog)
    backlog_after_text = backlog_path.read_text(encoding="utf-8")

    entry["status"] = "applied"
    entry["applied_at"] = now_iso()
    payload["generated_at"] = now_iso()
    synthesis_plan = build_synthesis_plan(payload.get("entries", []), backlog=backlog)
    payload["dependency_graph"] = {
        "nodes": synthesis_plan["nodes"],
        "edges": synthesis_plan["edges"],
        "cycles": synthesis_plan["cycles"],
    }
    payload["execution_order"] = synthesis_plan["execution_order"]
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
    backlog = load_data(repo_root / "backlog.yml")
    synthesis_plan = build_synthesis_plan(entries, backlog=backlog)
    draft = [entry for entry in entries if entry.get("status") == "draft"]
    applied = [entry for entry in entries if entry.get("status") == "applied"]
    blocked = [entry for entry in entries if entry.get("synthesis_eval_blocked")]
    top_draft = draft[0] if draft else None
    applied_ticket_ids = {str(entry.get("ticket_id_placeholder")) for entry in applied}
    backlog_ready = {
        str(task.get("id")): task
        for task in backlog.get("tasks", [])
        if str(task.get("status")) in {"ready", "retry_ready"}
    }
    next_ready = next(
        (
            item for item in synthesis_plan["execution_order"]
            if item.get("ticket_id") in applied_ticket_ids and item.get("ticket_id") in backlog_ready
        ),
        None,
    )
    return {
        "entry_count": len(entries),
        "draft_count": len(draft),
        "applied_count": len(applied),
        "blocked_count": len(blocked),
        "dependency_edge_count": len(synthesis_plan["edges"]),
        "dependency_cycle_count": len(synthesis_plan["cycles"]),
        "top_draft": top_draft,
        "top_draft_eval_score": None if top_draft is None else (top_draft.get("synthesis_eval") or {}).get("overall_score"),
        "top_draft_eval_passed": None if top_draft is None else not top_draft.get("synthesis_eval_blocked"),
        "next_execution_target": None
        if next_ready is None
        else (next_ready.get("ticket_id") or next_ready.get("synthesis_id")),
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
