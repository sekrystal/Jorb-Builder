#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os
import json

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


def ux_conformance_planning_issues(task: dict) -> list[str]:
    if not is_product_facing_ux_task(task):
        return []
    issues: list[str] = []
    section_mapping = task.get("design_section_mapping", [])
    if not isinstance(section_mapping, list) or not [item for item in section_mapping if str(item).strip()]:
        issues.append("design_section_mapping")
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
        if status not in READY_TASK_STATUSES:
            reasons.append(f"status:{status}")
        else:
            if task_id in blocked_ids:
                reasons.append("open_blocker")
            unmet = [dep for dep in task.get("depends_on", []) if dep not in completed]
            if unmet:
                reasons.append("unmet_dependencies:" + ",".join(sorted(unmet)))
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
