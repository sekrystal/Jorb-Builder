#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import textwrap
from common import (
    builder_root,
    is_product_facing_ux_task,
    load_config,
    load_data,
    write_data,
    product_repo_path,
)

ROOT = builder_root()
BACKLOG = ROOT / "backlog.yml"
ACTIVE = ROOT / "active_task.yml"
STATUS = ROOT / "status.yml"
PROMPTS = ROOT / "prompts"
RUN_LOGS = ROOT / "run_logs"


def find_task(backlog: dict, task_id: str) -> dict:
    for task in backlog.get("tasks", []):
        if task.get("id") == task_id:
            return task
    raise KeyError(task_id)


def fmt_list(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- none"


def ux_requirements_block(task: dict) -> str:
    if not is_product_facing_ux_task(task):
        return "- none"
    deviations = task.get("intentional_design_deviations", [])
    deviation_lines = [f"  - {item}" for item in deviations] if deviations else ["  - none"]
    lines = [
        "Design section mapping:",
        *[f"  - {item}" for item in task.get("design_section_mapping", [])],
        "Intentional design deviations:",
        *deviation_lines,
        "Product-first acceptance checklist:",
        *[f"  - {item}" for item in task.get("product_first_acceptance_checks", [])],
        "Primary UX prohibited surfaces:",
        *[f"  - {item}" for item in task.get("primary_ux_prohibited_surfaces", [])],
        "For product-facing UX tasks, section 1 of the final response must include labeled lines for:",
        "  - UX Design Section Mapping:",
        "  - UX Intentional Design Deviations:",
        "  - UX Product-First Checklist:",
        "Set the checklist line to include hierarchy=yes, prohibited_surfaces=yes, and backend_wiring_only=no when justified by the work.",
    ]
    return "\n".join(lines)


def target_kind_for_task(task: dict, builder_label: str) -> str:
    allowlist = list(task.get("allowlist", []))
    if task.get("repo_path") == builder_label or task.get("area") == "builder":
        return "builder"
    if any(str(entry).startswith("../jorb-builder") for entry in allowlist):
        return "builder"
    return "product"


def main() -> int:
    config = load_config()
    backlog = load_data(BACKLOG)
    active = load_data(ACTIVE)
    task_id = active.get("task_id")
    if not task_id:
        print("NO_ACTIVE_TASK")
        return 1

    product_repo = product_repo_path()
    product_label = config["paths"]["product_repo"]
    builder_label = config["paths"]["builder_root"]
    if not product_repo.exists():
        print(f"MISSING_PRODUCT_REPO {product_label}")
        return 2

    task = find_task(backlog, task_id)
    target_kind_label = target_kind_for_task(task, builder_label)
    target_repo_label = builder_label if target_kind_label == "builder" else product_label
    prompt_name = task.get("prompt") or config["execution"]["default_prompt"]
    prompt_template = (PROMPTS / f"{prompt_name}.md").read_text(encoding="utf-8")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    run_dir = RUN_LOGS / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = run_dir / "codex_prompt.md"

    repo_context = textwrap.dedent(
        f"""\
        Repo context:
        - Product repo: {product_label}
        - Builder workspace: {builder_label}
        - Current focus: truthful discovery status, discovery observability, bounded runtime behavior
        - Known hot path to preserve: /leads is fast again and should not be regressed casually

        """
    )

    rendered = prompt_template.format(
        product_repo=product_label,
        target_repo=target_repo_label,
        target_kind=target_kind_label,
        task_id=task["id"],
        title=task["title"],
        objective=task.get("objective", task["title"]),
        why_it_matters=task.get("why_it_matters", ""),
        allowlist=fmt_list(task.get("allowlist", [])),
        forbidlist=fmt_list(task.get("forbid", [])),
        acceptance=fmt_list(task.get("acceptance", [])),
        verification_commands=fmt_list(task.get("verification", [])),
        failure_summary=active.get("failure_summary") or "No failure summary recorded.",
        builder_edit_constraint="- Do not edit product files." if target_kind_label == "builder" else "- Do not edit builder files.",
        ux_conformance_requirements=ux_requirements_block(task),
    )

    header = textwrap.dedent(
        f"""\
---
task_id: {task['id']}
title: {task['title']}
type: {task.get('type', 'task')}
area: {task.get('area', 'unknown')}
repo_path: {target_repo_label}
attempt: {active.get('attempt', 1)}
allowlist:
{fmt_list(task.get('allowlist', []))}
denylist:
{fmt_list(task.get('forbid', []))}
verification:
{fmt_list(task.get('verification', []))}
---

"""
    )

    prompt_file.write_text(header + repo_context + rendered + "\n", encoding="utf-8")

    active["state"] = "packet_rendered"
    active["prompt_file"] = str(prompt_file)
    active["run_log_dir"] = str(run_dir)
    write_data(ACTIVE, active)

    status = load_data(STATUS)
    status["state"] = "packet_rendered"
    status["active_task_id"] = task["id"]
    status["last_run_at"] = datetime.now(timezone.utc).isoformat()
    write_data(STATUS, status)

    print(str(prompt_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
