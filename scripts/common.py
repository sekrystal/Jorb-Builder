#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import os
import json
import re
from typing import Any

VALID_TASK_STATUSES = {
    "pending",
    "ready",
    "retry_ready",
    "selected",
    "packet_rendered",
    "implementing",
    "verifying",
    "blocked",
    "accepted",
    "done",
}
READY_TASK_STATUSES = {"ready", "retry_ready"}
DONE_TASK_STATUSES = {"done", "accepted"}
ACTIVE_TASK_STATES = {"selected", "packet_rendered", "implementing", "verifying", "paused", "failed"}
REQUIRED_TASK_FIELDS = (
    "id",
    "title",
    "priority",
    "status",
    "type",
    "area",
    "repo_path",
    "description",
    "acceptance_criteria",
    "verification",
)
DEFAULT_PRIMARY_UX_PROHIBITED_SURFACES = [
    "source matrix",
    "discovery internals",
    "learning",
    "autonomy ops",
    "agent activity",
    "investigations",
    "diagnostics",
    "operator controls",
]
DEFAULT_PRODUCT_FIRST_UX_CHECKLIST = [
    "confirm the primary hierarchy keeps jobs or core user value ahead of secondary controls",
    "confirm prohibited surfaces stay out of the primary user-facing shell",
    "confirm backend wiring or real data alone is not treated as sufficient UX acceptance evidence",
]
CANONICAL_FIGMA_SOURCE = "/Users/samuelkrystal/projects/jorb/design/figma"
PHASE4_BUILDER_TASK_PATTERN = re.compile(r"^JORB-INFRA-(0(1[0-9]|2[0-9])|03[0-3])$")
MEMORY_STORE_FILE = "memory_store.json"
MEMORY_OVERRIDES_FILE = "memory_overrides.json"
DEFAULT_MEMORY_PROFILE_BUDGET = 4
MEMORY_STATUS_PRIORITY = {
    "pinned": 5,
    "invalidated": 4,
    "superseded": 3,
    "active": 2,
    "stale": 1,
}
MEMORY_ROLE_PROFILES = {
    "planner": {
        "limit": 4,
        "preferred_types": {"prior_similar_ticket", "successful_fix", "playbook", "failure_mode"},
        "preferred_origins": {"planner", "operator", "judge"},
        "tag_biases": {"accepted_pattern": 0.8, "failure_avoidance": 1.0, "playbook": 0.9},
    },
    "architect": {
        "limit": 4,
        "preferred_types": {"successful_fix", "repo_heuristic", "environment_assumption", "playbook", "failure_mode"},
        "preferred_origins": {"architect", "runtime_proof", "judge", "operator"},
        "tag_biases": {"implementation_pattern": 1.0, "environment": 0.9, "constraint": 0.8},
    },
    "judge": {
        "limit": 5,
        "preferred_types": {"failure_mode", "flaky_validation", "operator_feedback", "playbook", "prior_similar_ticket"},
        "preferred_origins": {"judge", "validator", "runtime_proof", "operator"},
        "tag_biases": {"acceptance_boundary": 1.1, "proof_pattern": 1.0, "regression": 0.8},
    },
}
MEMORY_ARTIFACT_ROLE_PROFILES = {
    "planner": {
        "limit": 4,
        "preferred_names": {
            "compiled_feature_spec.md",
            "research_brief.md",
            "performance_profile.md",
            "automation_summary.md",
        },
        "preferred_labels": {
            "phase4:compiled_feature_spec.md",
            "phase4:research_brief.md",
            "performance_profile",
            "automation_summary",
        },
    },
    "architect": {
        "limit": 4,
        "preferred_names": {
            "proposal.md",
            "tradeoff_matrix.md",
            "research_brief.md",
            "compiled_feature_spec.md",
            "performance_profile.md",
        },
        "preferred_labels": {
            "phase4:proposal.md",
            "phase4:tradeoff_matrix.md",
            "phase4:research_brief.md",
            "phase4:compiled_feature_spec.md",
            "performance_profile",
        },
    },
    "judge": {
        "limit": 5,
        "preferred_names": {
            "judge_decision.md",
            "evidence_bundle.json",
            "runtime_proof.log",
            "eval_result.json",
            "compiled_feature_spec.md",
            "proposal.md",
            "tradeoff_matrix.md",
            "research_brief.md",
            "performance_profile.md",
        },
        "preferred_labels": {
            "judge_decision",
            "phase4:judge_decision.md",
            "phase4:evidence_bundle.json",
            "phase4:runtime_proof.log",
            "eval_result",
            "phase4:compiled_feature_spec.md",
            "phase4:proposal.md",
            "phase4:tradeoff_matrix.md",
            "phase4:research_brief.md",
            "performance_profile",
        },
    },
}
PHASE4_OPERATOR_ARTIFACTS = (
    "compiled_feature_spec.md",
    "proposal.md",
    "tradeoff_matrix.md",
    "research_brief.md",
    "judge_decision.md",
    "evidence_bundle.json",
    "runtime_proof.log",
)
AUTOMATION_RUN_ARTIFACT_LABELS = {
    "automation_result.json": "automation_result",
    "automation_summary.md": "automation_summary",
    "progress.jsonl": "progress_log",
    "codex_last_message.md": "executor_output",
    "local_validation.json": "local_validation",
    "vm_validation.json": "vm_validation",
    "git.json": "git",
    "executor.json": "executor",
    "eval_result.json": "eval_result",
    "judge_memory_context.json": "judge_memory_context",
}
PHASE4_ARTIFACT_FAILURE_PREFIX = "Phase 4 artifact enforcement failed:"


def expand_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def builder_root() -> Path:
    override = os.environ.get("JORB_BUILDER_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def config_path() -> Path:
    return builder_root() / "config.yml"


def load_data(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_data(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_config() -> dict:
    return load_data(config_path())


def product_repo_path() -> Path:
    return expand_path(load_config()["paths"]["product_repo"])


def builder_path_from_config(key: str) -> Path:
    return expand_path(load_config()["paths"][key])


def infer_task_repo_path(task: dict, config: dict) -> str:
    if task.get("repo_path"):
        return str(task["repo_path"])
    allowlist = list(task.get("allowlist", []))
    if task.get("area") == "builder" or any(str(entry).startswith("../jorb-builder") for entry in allowlist):
        return str(config["paths"]["builder_root"])
    return str(config["paths"]["product_repo"])


def is_product_facing_ux_task(task: dict) -> bool:
    if bool(task.get("product_facing_ux")):
        return True
    area = str(task.get("area", "")).strip().lower()
    return area in {"ux", "frontend"}


def is_phase4_builder_task(task: dict) -> bool:
    task_id = str(task.get("id", "")).strip()
    if not PHASE4_BUILDER_TASK_PATTERN.match(task_id):
        return False
    area = str(task.get("area", "")).strip().lower()
    return area == "builder"


def load_repo_local_standards(root: Path | None = None) -> dict:
    repo_root = Path(root or builder_root()).expanduser().resolve()
    agents_path = repo_root / "AGENTS.md"
    skills_dir = repo_root / "skills"
    skill_files = sorted(str(path.relative_to(repo_root)) for path in skills_dir.rglob("*.md")) if skills_dir.exists() else []
    agents_text = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    agents_lines = [line.rstrip() for line in agents_text.splitlines()]
    core_expectations: list[str] = []
    execution_roles: dict[str, str] = {}
    current_section: str | None = None
    for raw_line in agents_lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith(":"):
            normalized = line[:-1].strip().lower()
            if normalized in {"core expectations", "execution roles"}:
                current_section = normalized
                continue
        if not line.startswith("- "):
            continue
        item = line[2:].strip()
        if current_section == "core expectations":
            core_expectations.append(item)
            continue
        if current_section == "execution roles" and ":" in item:
            role, detail = item.split(":", 1)
            execution_roles[role.strip()] = detail.strip()
    skill_entries: list[dict[str, str]] = []
    for relative_path in skill_files:
        skill_path = repo_root / relative_path
        skill_text = skill_path.read_text(encoding="utf-8")
        for raw_line in skill_text.splitlines():
            line = raw_line.strip()
            if not line.startswith("- "):
                continue
            item = line[2:].strip()
            match = re.match(r"`([^`]+)`:\s*(.+)", item)
            if match:
                skill_entries.append(
                    {
                        "file": relative_path,
                        "name": match.group(1).strip(),
                        "summary": match.group(2).strip(),
                    }
                )
    return {
        "repo_root": str(repo_root),
        "agents_path": str(agents_path),
        "agents_exists": agents_path.exists(),
        "agents_text": agents_text,
        "agents_core_expectations": core_expectations,
        "agents_execution_roles": execution_roles,
        "skills_dir": str(skills_dir),
        "skills_exists": skills_dir.exists(),
        "skill_files": skill_files,
        "skill_entries": skill_entries,
    }


def task_family(task_id: str) -> str:
    parts = [part for part in str(task_id).split("-") if part]
    return "-".join(parts[:2]) if len(parts) >= 2 else str(task_id)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def parse_iso_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_phase4_artifact_failure_detail(detail: Any) -> list[str]:
    text = str(detail or "").strip()
    if PHASE4_ARTIFACT_FAILURE_PREFIX not in text:
        return []
    suffix = text.split(PHASE4_ARTIFACT_FAILURE_PREFIX, 1)[1].strip()
    artifacts: list[str] = []
    for raw_item in suffix.split(","):
        candidate = raw_item.strip()
        if not candidate:
            continue
        name = candidate.split(":", 1)[0].strip()
        if name.endswith((".md", ".json", ".log")):
            artifacts.append(name)
    return artifacts


def derive_phase4_operator_truth(ledger: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(ledger or {})
    task_id = payload.get("current_task")
    if not task_id or payload.get("run_state") not in {"blocked", "dry_run"}:
        return payload
    events = list(payload.get("events") or [])
    artifact_events: list[dict[str, Any]] = []
    for event in reversed(events):
        if event.get("task_id") != task_id:
            continue
        run_state = str(event.get("run_state") or "")
        if run_state in {"accepted", "completed"}:
            if artifact_events:
                break
            return payload
        missing = parse_phase4_artifact_failure_detail(event.get("detail"))
        if run_state == "blocked" and missing:
            artifact_events.append({"detail": event.get("detail"), "missing": missing})
    if not artifact_events:
        return payload

    artifact_state = payload.get("artifact_completeness") or {}
    present = [str(name) for name in artifact_state.get("present", [])]
    missing = [str(name) for name in artifact_state.get("missing", [])]
    missing_set = set(missing)
    present_set = set(present)
    event_missing_set: set[str] = set()
    for event in artifact_events:
        for name in event["missing"]:
            event_missing_set.add(name)
            missing_set.add(name)
            present_set.discard(name)

    ordered_missing = [name for name in PHASE4_OPERATOR_ARTIFACTS if name in missing_set]
    ordered_missing.extend(sorted(name for name in missing_set if name not in PHASE4_OPERATOR_ARTIFACTS))
    ordered_present = [name for name in PHASE4_OPERATOR_ARTIFACTS if name in present_set]
    ordered_present.extend(sorted(name for name in present_set if name not in PHASE4_OPERATOR_ARTIFACTS))
    ordered_event_missing = [name for name in PHASE4_OPERATOR_ARTIFACTS if name in event_missing_set]
    ordered_event_missing.extend(sorted(name for name in event_missing_set if name not in PHASE4_OPERATOR_ARTIFACTS))

    payload["run_state"] = "blocked"
    payload["current_stage"] = "judge"
    payload["current_blocker"] = (
        f"{PHASE4_ARTIFACT_FAILURE_PREFIX} {', '.join(ordered_event_missing)}"
        if ordered_event_missing
        else artifact_events[0]["detail"]
    )
    payload["artifact_completeness"] = {
        "present": ordered_present,
        "missing": ordered_missing,
    }
    payload["failure_taxonomy"] = payload.get("failure_taxonomy") or {
        "failure_class": "artifact_completeness_failure",
        "recovery_action": "replan_required",
        "retryable": True,
    }
    return payload


def task_area(task_id: str) -> str:
    family = task_family(task_id)
    if family == "JORB-INFRA":
        return "builder"
    if family == "JORB-V3":
        return "frontend"
    if family == "JORB-V2":
        return "product"
    return "unknown"


def _content_signature(*parts: object) -> str:
    normalized = "||".join(str(part or "").strip().lower() for part in parts)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _memory_id(kind: str, task_id: str, signature: str) -> str:
    seed = f"{kind}:{task_id}:{signature}"
    return "mem-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _derive_memory_type_from_history(payload: dict) -> str:
    diagnostics = payload.get("operator_diagnostics") or {}
    taxonomy = payload.get("failure_taxonomy") or {}
    status = str(payload.get("status") or "").lower()
    if diagnostics.get("accepted") or status == "accepted":
        return "successful_fix"
    if taxonomy.get("failure_class") == "flaky_nondeterministic_failure":
        return "flaky_validation"
    if taxonomy.get("failure_class") in {"repo_state_failure", "configuration_defect"}:
        return "environment_assumption"
    if status in {"blocked", "refined", "interrupted"}:
        return "failure_mode"
    return "prior_similar_ticket"


def _derive_origin_from_history(payload: dict) -> str:
    diagnostics = payload.get("operator_diagnostics") or {}
    taxonomy = payload.get("failure_taxonomy") or {}
    if diagnostics.get("ux_conformance", {}).get("required"):
        return "judge"
    if taxonomy.get("failure_class"):
        return "validator"
    if diagnostics.get("accepted") is True:
        return "judge"
    return "operator"


def _derive_tags_from_history(payload: dict) -> list[str]:
    tags: set[str] = set()
    diagnostics = payload.get("operator_diagnostics") or {}
    taxonomy = payload.get("failure_taxonomy") or {}
    status = str(payload.get("status") or "").lower()
    tags.add(task_family(str(payload.get("task_id") or "")))
    tags.add(str(payload.get("title") or "").lower().replace(" ", "_"))
    if diagnostics.get("accepted") or status == "accepted":
        tags.add("accepted_pattern")
        tags.add("implementation_pattern")
    if status in {"blocked", "refined", "interrupted"}:
        tags.add("failure_avoidance")
        tags.add("acceptance_boundary")
    if taxonomy.get("failure_class"):
        tags.add(str(taxonomy["failure_class"]))
    if diagnostics.get("ux_conformance", {}).get("required"):
        tags.add("ux")
    if payload.get("unproven_runtime_gaps") == [] and diagnostics.get("accepted"):
        tags.add("proof_pattern")
    if "vm_validation" in " ".join(step.get("name", "") for step in diagnostics.get("step_outcomes", [])):
        tags.add("environment")
    return sorted(tag for tag in tags if tag and tag != "none")


def _derive_tags_from_blocker(payload: dict, task_id: str) -> list[str]:
    tags: set[str] = {task_family(task_id), "failure_avoidance", "acceptance_boundary"}
    diagnosis = str(payload.get("diagnosis") or "").lower()
    if "vm" in diagnosis or "runtime" in diagnosis:
        tags.add("proof_pattern")
        tags.add("environment")
    if "dirty" in diagnosis:
        tags.add("constraint")
    return sorted(tags)


def _freshness_metadata(timestamp: str | None, *, stale_after_days: int = 21) -> dict[str, Any]:
    observed_at = parse_iso_datetime(timestamp)
    if observed_at is None:
        return {
            "observed_at": timestamp,
            "age_days": None,
            "decay_factor": 0.6,
            "stale_after_days": stale_after_days,
            "freshness_state": "unknown",
        }
    age_days = max(0, int((now_utc() - observed_at).total_seconds() // 86400))
    decay = max(0.15, round(1.0 - min(age_days, stale_after_days * 3) / float(stale_after_days * 3), 3))
    freshness_state = "fresh" if age_days <= stale_after_days else "stale"
    return {
        "observed_at": observed_at.isoformat(),
        "age_days": age_days,
        "decay_factor": decay,
        "stale_after_days": stale_after_days,
        "freshness_state": freshness_state,
    }


def _default_memory_status(freshness: dict[str, Any]) -> str:
    if freshness.get("freshness_state") == "stale":
        return "stale"
    return "active"


def _build_history_memory_entry(path: Path, payload: dict) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "")
    diagnostics = payload.get("operator_diagnostics") or {}
    summary = payload.get("notes", [""])[0] if payload.get("notes") else diagnostics.get("decision_summary") or ""
    observation = diagnostics.get("decision_summary") or summary
    inference = "Past successful execution pattern" if diagnostics.get("accepted") else "Past failure or refinement pattern"
    signature = _content_signature(task_id, observation, inference, payload.get("status"))
    freshness = _freshness_metadata(payload.get("completed_at") or payload.get("started_at"))
    memory_type = _derive_memory_type_from_history(payload)
    return {
        "memory_id": _memory_id("task_history", task_id, signature),
        "memory_type": memory_type,
        "ticket_family": task_family(task_id),
        "task_id": task_id,
        "area": task_area(task_id),
        "summary": summary,
        "source_artifact": str(path),
        "timestamp": freshness.get("observed_at"),
        "confidence": 0.88 if diagnostics.get("accepted") else 0.72,
        "freshness": freshness,
        "observation": observation,
        "inference": inference,
        "primary_basis": "observation",
        "relevance_tags": _derive_tags_from_history(payload),
        "origin": _derive_origin_from_history(payload),
        "status": _default_memory_status(freshness),
        "status_reason": "derived_from_history",
        "provenance": [{"path": str(path), "kind": "task_history"}],
        "signature": signature,
        "support_count": 1,
        "superseded_by": None,
        "supersedes": [],
        "manual": False,
        "role_fit": ["planner", "architect", "judge"],
        "content": summary,
    }


def _build_blocker_memory_entry(path: Path, payload: dict, task_id: str) -> dict[str, Any]:
    diagnosis = payload.get("diagnosis") or (payload.get("symptoms") or [""])[0]
    observation = str(diagnosis or "")
    inference = "Known blocker pattern"
    signature = _content_signature(task_id, observation, inference, payload.get("status"))
    freshness = _freshness_metadata(payload.get("opened_at"))
    return {
        "memory_id": _memory_id("blocker", task_id, signature),
        "memory_type": "failure_mode" if payload.get("status") == "open" else "environment_assumption",
        "ticket_family": task_family(task_id),
        "task_id": task_id,
        "area": task_area(task_id),
        "summary": observation,
        "source_artifact": str(path),
        "timestamp": freshness.get("observed_at"),
        "confidence": 0.82 if payload.get("status") == "open" else 0.65,
        "freshness": freshness,
        "observation": observation,
        "inference": inference,
        "primary_basis": "observation",
        "relevance_tags": _derive_tags_from_blocker(payload, task_id),
        "origin": "operator",
        "status": _default_memory_status(freshness) if payload.get("status") != "resolved" else "superseded",
        "status_reason": f"blocker:{payload.get('status')}",
        "provenance": [{"path": str(path), "kind": "blocker"}],
        "signature": signature,
        "support_count": 1,
        "superseded_by": None,
        "supersedes": [],
        "manual": False,
        "role_fit": ["planner", "architect", "judge"],
        "content": observation,
    }


def _load_memory_overrides(repo_root: Path) -> dict[str, Any]:
    path = repo_root / MEMORY_OVERRIDES_FILE
    if not path.exists():
        return {"memory_status": {}, "manual_entries": [], "pins": []}
    payload = load_data(path)
    if not isinstance(payload, dict):
        return {"memory_status": {}, "manual_entries": [], "pins": []}
    payload.setdefault("memory_status", {})
    payload.setdefault("manual_entries", [])
    payload.setdefault("pins", [])
    return payload


def _apply_memory_overrides(entry: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    override = (overrides.get("memory_status") or {}).get(entry["memory_id"], {})
    if not isinstance(override, dict):
        override = {}
    for field in ("status", "status_reason", "superseded_by"):
        if override.get(field) is not None:
            entry[field] = override[field]
    if override.get("pinned"):
        entry["status"] = "pinned"
        entry["status_reason"] = "operator_pinned"
    if isinstance(override.get("relevance_tags"), list):
        entry["relevance_tags"] = sorted({*entry.get("relevance_tags", []), *[str(item) for item in override["relevance_tags"]]})
    return entry


def _merge_duplicate_memory_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for entry in entries:
        existing = merged.get(entry["signature"])
        if existing is None:
            merged[entry["signature"]] = entry
            continue
        existing["support_count"] = int(existing.get("support_count", 1)) + 1
        existing["provenance"].extend(entry.get("provenance", []))
        existing["provenance"] = existing["provenance"][-10:]
        existing["confidence"] = round(max(float(existing.get("confidence") or 0.0), float(entry.get("confidence") or 0.0)), 3)
        existing["freshness"] = existing.get("freshness") if (existing.get("freshness") or {}).get("decay_factor", 0) >= (entry.get("freshness") or {}).get("decay_factor", 0) else entry.get("freshness")
        if MEMORY_STATUS_PRIORITY.get(str(entry.get("status")), 0) > MEMORY_STATUS_PRIORITY.get(str(existing.get("status")), 0):
            existing["status"] = entry.get("status")
            existing["status_reason"] = entry.get("status_reason")
        existing["relevance_tags"] = sorted({*existing.get("relevance_tags", []), *entry.get("relevance_tags", [])})
    return sorted(merged.values(), key=lambda item: (MEMORY_STATUS_PRIORITY.get(str(item.get("status")), 0), str(item.get("timestamp") or "")), reverse=True)


def _normalize_manual_memory_entry(entry: dict[str, Any]) -> dict[str, Any]:
    timestamp = entry.get("timestamp") or now_iso()
    freshness = _freshness_metadata(timestamp, stale_after_days=int(entry.get("freshness", {}).get("stale_after_days", 45)) if isinstance(entry.get("freshness"), dict) else 45)
    memory_id = str(entry.get("memory_id") or _memory_id("manual", str(entry.get("task_id") or entry.get("ticket_family") or "manual"), _content_signature(entry.get("content") or entry.get("observation") or "", entry.get("memory_type") or "manual")))
    return {
        "memory_id": memory_id,
        "memory_type": str(entry.get("memory_type") or "playbook"),
        "ticket_family": str(entry.get("ticket_family") or "GENERAL"),
        "task_id": entry.get("task_id"),
        "area": str(entry.get("area") or "builder"),
        "summary": str(entry.get("summary") or entry.get("content") or entry.get("observation") or ""),
        "source_artifact": str(entry.get("source_artifact") or MEMORY_OVERRIDES_FILE),
        "timestamp": freshness.get("observed_at"),
        "confidence": float(entry.get("confidence") or 0.85),
        "freshness": freshness,
        "observation": str(entry.get("observation") or entry.get("content") or ""),
        "inference": str(entry.get("inference") or ""),
        "primary_basis": str(entry.get("primary_basis") or "inference"),
        "relevance_tags": sorted({str(tag) for tag in entry.get("relevance_tags", [])}),
        "origin": str(entry.get("origin") or "operator"),
        "status": str(entry.get("status") or "active"),
        "status_reason": str(entry.get("status_reason") or "manual_entry"),
        "provenance": [{"path": str(entry.get("source_artifact") or MEMORY_OVERRIDES_FILE), "kind": "manual"}],
        "signature": str(entry.get("signature") or _content_signature(entry.get("memory_type"), entry.get("observation") or entry.get("content"), entry.get("inference"))),
        "support_count": int(entry.get("support_count") or 1),
        "superseded_by": entry.get("superseded_by"),
        "supersedes": list(entry.get("supersedes") or []),
        "manual": True,
        "role_fit": list(entry.get("role_fit") or ["planner", "architect", "judge"]),
        "content": str(entry.get("content") or entry.get("observation") or ""),
    }


def _memory_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        key = str(entry.get("status") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _serializable_memory_profiles() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for role, profile in MEMORY_ROLE_PROFILES.items():
        payload[role] = {
            "limit": profile.get("limit", DEFAULT_MEMORY_PROFILE_BUDGET),
            "preferred_types": sorted(profile.get("preferred_types", set())),
            "preferred_origins": sorted(profile.get("preferred_origins", set())),
            "tag_biases": profile.get("tag_biases", {}),
        }
    return payload


def _artifact_relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _artifact_search_tokens(*parts: Any) -> list[str]:
    tokens: set[str] = set()
    for part in parts:
        if part is None:
            continue
        for token in re.split(r"[^a-zA-Z0-9_.-]+", str(part).lower()):
            if token:
                tokens.add(token)
    return sorted(tokens)


def _artifact_candidate_paths(payload: dict[str, Any], history_path: Path) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    prompt = payload.get("prompt")
    if prompt:
        candidates.append(("prompt", Path(str(prompt)).expanduser()))
    run_log_dir = payload.get("run_log_dir")
    if run_log_dir:
        run_dir = Path(str(run_log_dir)).expanduser()
        candidates.append(("run_log_dir", run_dir))
        for name, label in AUTOMATION_RUN_ARTIFACT_LABELS.items():
            candidates.append((label, run_dir / name))
        for name in PHASE4_OPERATOR_ARTIFACTS:
            candidates.append((f"phase4:{name}", run_dir / name))
    for item in payload.get("evidence_artifacts", []):
        if not isinstance(item, dict):
            continue
        artifact_path = item.get("path")
        if not artifact_path:
            continue
        candidates.append((str(item.get("label") or "artifact"), Path(str(artifact_path)).expanduser()))
    return candidates


def build_artifact_metadata_index(root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root or builder_root()).expanduser().resolve()
    task_history_dir = repo_root / "task_history"
    records: dict[tuple[str, str], dict[str, Any]] = {}
    for history_path in sorted(task_history_dir.glob("*.yml")) if task_history_dir.exists() else []:
        payload = load_data(history_path)
        task_id = str(payload.get("task_id") or "")
        ticket_family = task_family(task_id)
        run_log_dir = payload.get("run_log_dir")
        run_dir = Path(str(run_log_dir)).expanduser().resolve() if run_log_dir else None
        timestamp = payload.get("completed_at") or payload.get("started_at")
        for label, candidate in _artifact_candidate_paths(payload, history_path):
            resolved = candidate.resolve()
            if not resolved.exists():
                continue
            key = (task_id, str(resolved))
            record = records.get(key)
            if record is None:
                is_dir = resolved.is_dir()
                suffix = resolved.suffix.lower()
                record = {
                    "artifact_id": _memory_id("artifact", task_id or "unknown", f"{history_path}:{resolved}"),
                    "task_id": task_id or None,
                    "ticket_family": ticket_family,
                    "history_path": str(history_path),
                    "run_log_dir": str(run_dir) if run_dir is not None else None,
                    "path": str(resolved),
                    "relative_path": _artifact_relative_path(resolved, repo_root),
                    "artifact_name": resolved.name,
                    "artifact_stem": resolved.stem,
                    "extension": suffix,
                    "kind": "directory" if is_dir else "file",
                    "size_bytes": None if is_dir else resolved.stat().st_size,
                    "timestamp": timestamp,
                    "history_status": str(payload.get("status") or "unknown"),
                    "labels": [],
                    "phase4_artifact": resolved.name in PHASE4_OPERATOR_ARTIFACTS,
                    "search_tokens": [],
                }
                records[key] = record
            record["labels"] = sorted({*record.get("labels", []), label})
            record["search_tokens"] = _artifact_search_tokens(
                task_id,
                ticket_family,
                resolved.name,
                resolved.stem,
                resolved.suffix,
                label,
                history_path.name,
                payload.get("status"),
            )

    entries = sorted(
        records.values(),
        key=lambda item: (str(item.get("timestamp") or ""), str(item.get("task_id") or ""), item["path"]),
        reverse=True,
    )
    by_task_id: dict[str, list[str]] = {}
    by_label: dict[str, list[str]] = {}
    by_name: dict[str, list[str]] = {}
    counts_by_label: dict[str, int] = {}
    counts_by_kind: dict[str, int] = {}
    for entry in entries:
        artifact_id = str(entry["artifact_id"])
        task_id = str(entry.get("task_id") or "")
        if task_id:
            by_task_id.setdefault(task_id, []).append(artifact_id)
        by_name.setdefault(str(entry["artifact_name"]), []).append(artifact_id)
        kind = str(entry["kind"])
        counts_by_kind[kind] = counts_by_kind.get(kind, 0) + 1
        for label in entry.get("labels", []):
            by_label.setdefault(str(label), []).append(artifact_id)
            counts_by_label[str(label)] = counts_by_label.get(str(label), 0) + 1
    return {
        "generated_at": now_iso(),
        "entries": entries,
        "counts_by_label": counts_by_label,
        "counts_by_kind": counts_by_kind,
        "by_task_id": by_task_id,
        "by_label": by_label,
        "by_name": by_name,
    }


def build_memory_store(root: Path | None = None) -> dict:
    repo_root = Path(root or builder_root()).expanduser().resolve()
    task_history_dir = repo_root / "task_history"
    blockers_dir = repo_root / "blockers"
    entries: list[dict] = []
    overrides = _load_memory_overrides(repo_root)

    for path in sorted(task_history_dir.glob("*.yml")) if task_history_dir.exists() else []:
        payload = load_data(path)
        entries.append(_apply_memory_overrides(_build_history_memory_entry(path, payload), overrides))

    for path in sorted(blockers_dir.glob("*.yml")) if blockers_dir.exists() else []:
        payload = load_data(path)
        related = [str(item) for item in payload.get("related_tasks", [])]
        for task_id in related:
            entries.append(_apply_memory_overrides(_build_blocker_memory_entry(path, payload, task_id), overrides))

    for manual in overrides.get("manual_entries", []):
        entries.append(_normalize_manual_memory_entry(manual))

    entries = _merge_duplicate_memory_entries(entries)

    store = {
        "generated_at": now_iso(),
        "entries": entries,
        "artifact_index": build_artifact_metadata_index(repo_root),
        "profiles": _serializable_memory_profiles(),
        "counts_by_status": _memory_counts(entries),
        "source_counts": {
            "task_history": len([entry for entry in entries if any(item.get("kind") == "task_history" for item in entry.get("provenance", []))]),
            "blockers": len([entry for entry in entries if any(item.get("kind") == "blocker" for item in entry.get("provenance", []))]),
            "manual": len([entry for entry in entries if entry.get("manual")]),
        },
    }
    return store


def _role_profile(role: str) -> dict[str, Any]:
    return MEMORY_ROLE_PROFILES.get(role, {"limit": DEFAULT_MEMORY_PROFILE_BUDGET, "preferred_types": set(), "preferred_origins": set(), "tag_biases": {}})


def _artifact_role_profile(role: str) -> dict[str, Any]:
    return MEMORY_ARTIFACT_ROLE_PROFILES.get(role, {"limit": DEFAULT_MEMORY_PROFILE_BUDGET, "preferred_names": set(), "preferred_labels": set()})


def _task_relevance_tags(task: dict) -> set[str]:
    tags = {task_family(str(task.get("id") or "")), str(task.get("area") or "").lower()}
    if is_product_facing_ux_task(task):
        tags.add("ux")
    if bool(task.get("requires_vm_runtime_proof")):
        tags.add("proof_pattern")
        tags.add("environment")
    return {tag for tag in tags if tag and tag != "unknown"}


def retrieve_memory_for_role(
    task: dict,
    store: dict,
    *,
    role: str,
    limit: int | None = None,
) -> dict[str, Any]:
    task_id = str(task.get("id") or "")
    area = str(task.get("area") or "").lower()
    family = task_family(task_id)
    profile = _role_profile(role)
    budget = int(limit or profile.get("limit") or DEFAULT_MEMORY_PROFILE_BUDGET)
    task_tags = _task_relevance_tags(task)
    scored: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for entry in store.get("entries", []):
        status = str(entry.get("status") or "active")
        reasons: list[str] = []
        score = 0.0
        if status in {"invalidated", "superseded"}:
            excluded.append({"memory_id": entry.get("memory_id"), "status": status, "excluded_reason": status})
            continue
        if entry.get("task_id") == task_id:
            score += 5.0
            reasons.append("exact_task_match")
        if entry.get("ticket_family") == family:
            score += 3.0
            reasons.append("same_ticket_family")
        if area and area in str(entry.get("summary") or entry.get("content") or entry.get("observation") or "").lower():
            score += 1.0
            reasons.append("area_match")
        if str(entry.get("memory_type")) in set(profile.get("preferred_types", set())):
            score += 1.25
            reasons.append("role_type_fit")
        if str(entry.get("origin")) in set(profile.get("preferred_origins", set())):
            score += 0.8
            reasons.append("role_origin_fit")
        overlap = task_tags & set(entry.get("relevance_tags") or [])
        if overlap:
            tag_bonus = 0.4 * len(overlap)
            score += tag_bonus
            reasons.append(f"tag_overlap:{','.join(sorted(overlap))}")
        for tag, bonus in (profile.get("tag_biases") or {}).items():
            if tag in set(entry.get("relevance_tags") or []):
                score += float(bonus)
                reasons.append(f"role_tag_bias:{tag}")
        decay = float((entry.get("freshness") or {}).get("decay_factor") or 0.6)
        score += decay
        reasons.append(f"decay:{decay}")
        confidence = float(entry.get("confidence") or 0.0)
        score += confidence
        reasons.append(f"confidence:{confidence}")
        if status == "pinned":
            score += 2.5
            reasons.append("pinned")
        elif status == "active":
            score += 0.5
            reasons.append("active")
        elif status == "stale":
            score -= 0.6
            reasons.append("stale_downrank")
        scored.append(
            {
                "memory_id": entry.get("memory_id"),
                "entry": entry,
                "score": round(score, 3),
                "reasons": reasons,
            }
        )
    scored.sort(key=lambda item: (item["score"], float(item["entry"].get("confidence") or 0.0)), reverse=True)
    selected = scored[:budget]
    for item in scored[budget: min(len(scored), budget + 10)]:
        excluded.append(
            {
                "memory_id": item["memory_id"],
                "status": item["entry"].get("status"),
                "excluded_reason": "budget",
                "score": item["score"],
            }
        )
    return {
        "role": role,
        "profile": {
            "limit": budget,
            "preferred_types": sorted(profile.get("preferred_types", set())),
            "preferred_origins": sorted(profile.get("preferred_origins", set())),
            "tag_biases": profile.get("tag_biases", {}),
        },
        "selected": [
            {
                **item["entry"],
                "selection_score": item["score"],
                "selection_reasons": item["reasons"],
            }
            for item in selected
        ],
        "excluded": excluded,
    }


def retrieve_memory_for_task(task: dict, store: dict, *, limit: int = 5) -> list[dict]:
    return retrieve_memory_for_role(task, store, role="planner", limit=limit)["selected"]


def retrieve_artifacts_for_role(
    task: dict,
    store: dict,
    *,
    role: str,
    limit: int | None = None,
) -> dict[str, Any]:
    task_id = str(task.get("id") or "")
    family = task_family(task_id)
    task_tags = _task_relevance_tags(task)
    profile = _artifact_role_profile(role)
    budget = int(limit or profile.get("limit") or DEFAULT_MEMORY_PROFILE_BUDGET)
    memory_bundle = retrieve_memory_for_role(task, store, role=role, limit=budget)
    supporting_history_paths = {
        str(item.get("path"))
        for entry in memory_bundle.get("selected", [])
        for item in entry.get("provenance", [])
        if item.get("kind") == "task_history"
    }
    supporting_task_ids = {str(entry.get("task_id")) for entry in memory_bundle.get("selected", []) if entry.get("task_id")}
    scored: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    artifact_index = store.get("artifact_index") or {}
    for entry in artifact_index.get("entries", []):
        if str(entry.get("kind")) != "file":
            continue
        reasons: list[str] = []
        score = 0.0
        entry_task_id = str(entry.get("task_id") or "")
        if entry_task_id == task_id:
            score += 5.0
            reasons.append("exact_task_match")
        elif str(entry.get("ticket_family") or "") == family:
            score += 3.0
            reasons.append("same_ticket_family")
        if entry_task_id and entry_task_id in supporting_task_ids:
            score += 1.2
            reasons.append("memory_task_link")
        if str(entry.get("history_path") or "") in supporting_history_paths:
            score += 1.2
            reasons.append("memory_history_link")
        labels = set(str(label) for label in entry.get("labels", []))
        if str(entry.get("artifact_name")) in set(profile.get("preferred_names", set())):
            score += 1.4
            reasons.append("role_name_fit")
        label_overlap = labels & set(profile.get("preferred_labels", set()))
        if label_overlap:
            score += 1.1 + (0.1 * len(label_overlap))
            reasons.append(f"role_label_fit:{','.join(sorted(label_overlap))}")
        token_overlap = task_tags & set(str(token) for token in entry.get("search_tokens", []))
        if token_overlap:
            score += 0.35 * len(token_overlap)
            reasons.append(f"tag_overlap:{','.join(sorted(token_overlap))}")
        freshness = _freshness_metadata(entry.get("timestamp"))
        decay = float(freshness.get("decay_factor") or 0.6)
        score += decay
        reasons.append(f"decay:{decay}")
        if entry.get("phase4_artifact"):
            score += 0.25
            reasons.append("phase4_artifact")
        if str(entry.get("history_status") or "") == "accepted":
            score += 0.4
            reasons.append("accepted_history")
        scored.append(
            {
                "artifact_id": entry.get("artifact_id"),
                "entry": entry,
                "score": round(score, 3),
                "reasons": reasons,
            }
        )
    scored.sort(key=lambda item: (item["score"], str(item["entry"].get("timestamp") or ""), str(item["entry"].get("path") or "")), reverse=True)
    selected = scored[:budget]
    for item in scored[budget : min(len(scored), budget + 10)]:
        excluded.append(
            {
                "artifact_id": item["artifact_id"],
                "excluded_reason": "budget",
                "score": item["score"],
            }
        )
    return {
        "role": role,
        "profile": {
            "limit": budget,
            "preferred_names": sorted(profile.get("preferred_names", set())),
            "preferred_labels": sorted(profile.get("preferred_labels", set())),
        },
        "selected": [
            {
                **item["entry"],
                "selection_score": item["score"],
                "selection_reasons": item["reasons"],
            }
            for item in selected
        ],
        "excluded": excluded,
    }


def format_memory_bundle_text(bundle: dict[str, Any], *, max_items: int | None = None) -> str:
    role = str(bundle.get("role") or "planner")
    selected = list(bundle.get("selected", []))
    if max_items is not None:
        selected = selected[:max_items]
    lines = [f"{role.title()} memory bundle:"]
    if not selected:
        lines.append("- none")
        return "\n".join(lines)
    for entry in selected:
        lines.append(
            "- "
            + f"[{entry.get('memory_type')}] {entry.get('ticket_family')} :: {entry.get('observation') or entry.get('content')} "
            + f"(status={entry.get('status')}, confidence={entry.get('confidence')}, score={entry.get('selection_score')}, provenance={entry.get('source_artifact')})"
        )
    return "\n".join(lines)


def format_artifact_bundle_text(bundle: dict[str, Any], *, max_items: int | None = None) -> str:
    role = str(bundle.get("role") or "planner")
    selected = list(bundle.get("selected", []))
    if max_items is not None:
        selected = selected[:max_items]
    lines = [f"{role.title()} artifact retrieval:"]
    if not selected:
        lines.append("- none")
        return "\n".join(lines)
    for entry in selected:
        lines.append(
            "- "
            + f"{entry.get('artifact_name')} ({entry.get('relative_path')}, labels={','.join(entry.get('labels', [])) or 'none'}, "
            + f"status={entry.get('history_status')}, score={entry.get('selection_score')})"
        )
    return "\n".join(lines)


def validate_memory_store_schema(store: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not isinstance(store.get("entries"), list):
        return ["entries:not_list"]
    artifact_index = store.get("artifact_index")
    if not isinstance(artifact_index, dict):
        issues.append("artifact_index:not_object")
        artifact_entries: list[dict[str, Any]] = []
    else:
        artifact_entries = artifact_index.get("entries", [])
        if not isinstance(artifact_entries, list):
            issues.append("artifact_index.entries:not_list")
            artifact_entries = []
    required_fields = {
        "memory_id",
        "memory_type",
        "ticket_family",
        "source_artifact",
        "timestamp",
        "confidence",
        "freshness",
        "observation",
        "inference",
        "primary_basis",
        "relevance_tags",
        "origin",
        "status",
        "provenance",
    }
    for index, entry in enumerate(store.get("entries", [])):
        missing = sorted(required_fields - set(entry.keys()))
        for field in missing:
            issues.append(f"entries[{index}]:missing:{field}")
    artifact_required_fields = {
        "artifact_id",
        "task_id",
        "ticket_family",
        "history_path",
        "run_log_dir",
        "path",
        "relative_path",
        "artifact_name",
        "artifact_stem",
        "extension",
        "kind",
        "size_bytes",
        "timestamp",
        "history_status",
        "labels",
        "phase4_artifact",
        "search_tokens",
    }
    for index, entry in enumerate(artifact_entries):
        missing = sorted(artifact_required_fields - set(entry.keys()))
        for field in missing:
            issues.append(f"artifact_index.entries[{index}]:missing:{field}")
    return issues


def references_canonical_figma_source(value: object) -> bool:
    return CANONICAL_FIGMA_SOURCE in str(value or "")


def ux_conformance_planning_issues(task: dict) -> list[str]:
    if not is_product_facing_ux_task(task):
        return []
    issues: list[str] = []
    section_mapping = task.get("design_section_mapping", [])
    if not isinstance(section_mapping, list) or not [item for item in section_mapping if str(item).strip()]:
        issues.append("design_section_mapping")
    elif not any(references_canonical_figma_source(item) for item in section_mapping):
        issues.append("design_section_mapping.figma_source")
    deviations = task.get("intentional_design_deviations", [])
    if not isinstance(deviations, list):
        issues.append("intentional_design_deviations")
    checklist = task.get("product_first_acceptance_checks", [])
    if not isinstance(checklist, list) or not checklist:
        issues.append("product_first_acceptance_checks")
    else:
        checklist_text = " ".join(str(item).lower() for item in checklist)
        if "hierarchy" not in checklist_text:
            issues.append("product_first_acceptance_checks.hierarchy")
        if "prohibited" not in checklist_text:
            issues.append("product_first_acceptance_checks.prohibited_surfaces")
        if "backend wiring" not in checklist_text and "real data alone" not in checklist_text:
            issues.append("product_first_acceptance_checks.backend_wiring_only")
    prohibited = task.get("primary_ux_prohibited_surfaces", [])
    if not isinstance(prohibited, list) or not [item for item in prohibited if str(item).strip()]:
        issues.append("primary_ux_prohibited_surfaces")
    return issues


def vm_runtime_contract_issues(task: dict, config: dict) -> list[str]:
    if not bool(task.get("requires_vm_runtime_proof")):
        return []
    issues: list[str] = []
    vm_config = config.get("vm", {})
    task_vm_verification = task.get("vm_verification", [])
    task_vm_bootstrap = task.get("vm_bootstrap", [])
    config_vm_bootstrap = vm_config.get("bootstrap_commands", [])
    if not isinstance(task_vm_verification, list) or not [item for item in task_vm_verification if str(item).strip()]:
        issues.append("vm_verification")
    if (
        not isinstance(task_vm_bootstrap, list)
        or not [item for item in task_vm_bootstrap if str(item).strip()]
    ) and (
        not isinstance(config_vm_bootstrap, list)
        or not [item for item in config_vm_bootstrap if str(item).strip()]
    ):
        issues.append("vm_bootstrap_or_config_vm.bootstrap_commands")
    bootstrap_commands = task_vm_bootstrap if isinstance(task_vm_bootstrap, list) and [item for item in task_vm_bootstrap if str(item).strip()] else config_vm_bootstrap
    bootstrap_port = None
    for command in bootstrap_commands:
        match = re.search(r"--server\.port\s+(\d+)", str(command))
        if match:
            bootstrap_port = match.group(1)
            break
    if bootstrap_port and isinstance(task_vm_verification, list):
        expected_ui_url = f"http://127.0.0.1:{bootstrap_port}"
        for command in task_vm_verification:
            text = str(command)
            if "runtime_self_check.sh" in text:
                match = re.search(r"UI_URL=([^\s]+)", text)
                runtime_self_check_ui = match.group(1) if match else "http://127.0.0.1:8500"
                if runtime_self_check_ui != expected_ui_url:
                    issues.append(f"vm_ui_port_mismatch:{expected_ui_url}!={runtime_self_check_ui}")
            if "curl" in text and "127.0.0.1:85" in text:
                match = re.search(r"http://127\.0\.0\.1:(\d+)", text)
                if match and match.group(1) != bootstrap_port:
                    issues.append(f"vm_ui_port_mismatch:{expected_ui_url}!=http://127.0.0.1:{match.group(1)}")
    return issues


def canonicalize_task(task: dict, config: dict) -> dict:
    normalized = dict(task)
    normalized["repo_path"] = infer_task_repo_path(task, config)
    if not normalized.get("description"):
        objective = str(task.get("objective", "")).strip()
        why = str(task.get("why_it_matters", "")).strip()
        description_parts = [part for part in (objective, why) if part]
        normalized["description"] = "\n\n".join(description_parts)
    if "acceptance_criteria" not in normalized:
        normalized["acceptance_criteria"] = list(task.get("acceptance", []))
    normalized.setdefault("allow_noop_completion", bool(task.get("allow_noop_completion", False)))
    if is_product_facing_ux_task(normalized):
        normalized.setdefault("product_facing_ux", True)
        normalized.setdefault("design_section_mapping", list(task.get("design_section_mapping", [])))
        section_mapping = normalized.get("design_section_mapping", [])
        if isinstance(section_mapping, list) and section_mapping and not any(references_canonical_figma_source(item) for item in section_mapping):
            normalized["design_section_mapping"] = list(section_mapping) + [f"Canonical Figma source: {CANONICAL_FIGMA_SOURCE}"]
        normalized.setdefault("intentional_design_deviations", list(task.get("intentional_design_deviations", [])))
        normalized.setdefault("product_first_acceptance_checks", list(task.get("product_first_acceptance_checks", DEFAULT_PRODUCT_FIRST_UX_CHECKLIST)))
        normalized.setdefault("primary_ux_prohibited_surfaces", list(task.get("primary_ux_prohibited_surfaces", DEFAULT_PRIMARY_UX_PROHIBITED_SURFACES)))
    return normalized


def validate_backlog_payload(payload: dict, config: dict) -> dict:
    errors: list[dict] = []
    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, list):
        return {"tasks": [], "errors": [{"code": "backlog_not_task_list", "detail": "backlog.tasks must be a list"}]}

    seen_ids: dict[str, int] = {}
    tasks: list[dict] = []
    for index, raw in enumerate(raw_tasks):
        if not isinstance(raw, dict):
            errors.append({"code": "task_not_mapping", "task_index": index, "detail": "task entry must be an object"})
            continue
        task = canonicalize_task(raw, config)
        task_id = task.get("id")
        if task_id in seen_ids:
            errors.append({"code": "duplicate_task_id", "task_id": task_id, "detail": f"duplicate task id at indexes {seen_ids[task_id]} and {index}"})
        else:
            seen_ids[str(task_id)] = index

        missing = [field for field in REQUIRED_TASK_FIELDS if field not in task or task.get(field) in (None, "")]
        if missing:
            errors.append({"code": "missing_required_fields", "task_id": task_id, "detail": f"missing required fields: {', '.join(missing)}"})
        if not isinstance(task.get("priority"), int):
            errors.append({"code": "invalid_priority", "task_id": task_id, "detail": f"priority must be an integer, got {task.get('priority')!r}"})
        if task.get("status") not in VALID_TASK_STATUSES:
            errors.append({"code": "invalid_status", "task_id": task_id, "detail": f"status must be one of {sorted(VALID_TASK_STATUSES)}, got {task.get('status')!r}"})
        if not isinstance(task.get("verification", []), list):
            errors.append({"code": "invalid_verification", "task_id": task_id, "detail": "verification must be a list"})
        if "vm_verification" in task and not isinstance(task.get("vm_verification", []), list):
            errors.append({"code": "invalid_vm_verification", "task_id": task_id, "detail": "vm_verification must be a list"})
        if "vm_bootstrap" in task and not isinstance(task.get("vm_bootstrap", []), list):
            errors.append({"code": "invalid_vm_bootstrap", "task_id": task_id, "detail": "vm_bootstrap must be a list"})
        if "vm_cleanup" in task and not isinstance(task.get("vm_cleanup", []), list):
            errors.append({"code": "invalid_vm_cleanup", "task_id": task_id, "detail": "vm_cleanup must be a list"})
        if not isinstance(task.get("acceptance_criteria", []), list):
            errors.append({"code": "invalid_acceptance_criteria", "task_id": task_id, "detail": "acceptance_criteria must be a list"})
        if "allow_noop_completion" in task and not isinstance(task.get("allow_noop_completion"), bool):
            errors.append({"code": "invalid_allow_noop_completion", "task_id": task_id, "detail": "allow_noop_completion must be a boolean"})
        vm_runtime_issues = vm_runtime_contract_issues(task, config)
        if vm_runtime_issues:
            errors.append(
                {
                    "code": "invalid_vm_runtime_contract",
                    "task_id": task_id,
                    "detail": "missing VM runtime proof fields: " + ", ".join(vm_runtime_issues),
                }
            )
        ux_issues = ux_conformance_planning_issues(task)
        if ux_issues:
            errors.append(
                {
                    "code": "invalid_product_facing_ux_task",
                    "task_id": task_id,
                    "detail": "missing UX conformance planning fields: " + ", ".join(ux_issues),
                }
            )
        tasks.append(task)
    return {"tasks": tasks, "errors": errors}


def load_validated_backlog() -> dict:
    config = load_config()
    payload = load_data(builder_root() / "backlog.yml")
    validated = validate_backlog_payload(payload, config)
    validated["version"] = payload.get("version")
    return validated


def load_open_blocked_task_ids() -> set[str]:
    blocked_dir = builder_root() / "blockers"
    blocked: set[str] = set()
    if not blocked_dir.exists():
        return blocked
    for file in sorted(blocked_dir.glob("*.yml")):
        data = load_data(file)
        if data.get("status") != "open":
            continue
        for task_id in data.get("related_tasks", []):
            blocked.add(str(task_id))
    return blocked


def compute_backlog_diagnostics(validated_backlog: dict) -> dict:
    tasks = list(validated_backlog.get("tasks", []))
    blocked_ids = load_open_blocked_task_ids()
    config = load_config()
    completed = {task["id"] for task in tasks if task.get("status") in DONE_TASK_STATUSES}
    counts_by_status: dict[str, int] = {}
    ready_status_ids: list[str] = []
    pending_ids: list[str] = []
    retry_ready_ids: list[str] = []
    blocked_status_ids: list[str] = []
    skipped_reasons: dict[str, list[str]] = {}
    candidates: list[dict] = []
    product_facing_ux_task_ids: list[str] = []
    product_facing_ux_missing_requirements: dict[str, list[str]] = {}

    for task in tasks:
        status = str(task.get("status"))
        counts_by_status[status] = counts_by_status.get(status, 0) + 1
        task_id = str(task.get("id"))
        ux_issues = ux_conformance_planning_issues(task)
        if is_product_facing_ux_task(task):
            product_facing_ux_task_ids.append(task_id)
        if ux_issues:
            product_facing_ux_missing_requirements[task_id] = ux_issues
        if status in READY_TASK_STATUSES:
            ready_status_ids.append(task_id)
        elif status == "pending":
            pending_ids.append(task_id)
        elif status == "retry_ready":
            retry_ready_ids.append(task_id)
        elif status == "blocked":
            blocked_status_ids.append(task_id)

        reasons: list[str] = []
        vm_runtime_issues = vm_runtime_contract_issues(task, config)
        if status not in READY_TASK_STATUSES:
            reasons.append(f"status:{status}")
        else:
            if task_id in blocked_ids:
                reasons.append("open_blocker")
            unmet = [dep for dep in task.get("depends_on", []) if dep not in completed]
            if unmet:
                reasons.append("unmet_dependencies:" + ",".join(sorted(unmet)))
            if vm_runtime_issues:
                reasons.append("missing_vm_runtime_contract:" + ",".join(vm_runtime_issues))
            if not reasons:
                candidates.append(task)
        if reasons:
            skipped_reasons[task_id] = reasons

    candidates.sort(key=lambda task: (task.get("priority", 999), task.get("id", "")))
    return {
        "total_tasks": len(tasks),
        "counts_by_status": counts_by_status,
        "ready_task_ids": ready_status_ids,
        "pending_task_ids": pending_ids,
        "retry_ready_task_ids": retry_ready_ids,
        "blocked_task_ids": blocked_status_ids,
        "open_blocked_task_ids": sorted(blocked_ids),
        "ordered_ready_queue": [task["id"] for task in candidates],
        "next_selected_task_id": candidates[0]["id"] if candidates else None,
        "selector_filtered_everything": bool(ready_status_ids) and not bool(candidates),
        "roadmap_affected": False,
        "skipped_reasons": skipped_reasons,
        "product_facing_ux_task_ids": product_facing_ux_task_ids,
        "product_facing_ux_missing_requirements": product_facing_ux_missing_requirements,
    }
