#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
import textwrap
from common import (
    build_memory_store,
    builder_root,
    default_not_done_until,
    default_product_contract,
    default_systemic_layers,
    format_artifact_bundle_text,
    format_memory_bundle_text,
    is_product_facing_ux_task,
    is_phase4_builder_task,
    load_config,
    load_data,
    load_repo_local_standards,
    retrieve_artifacts_for_role,
    retrieve_memory_for_role,
    task_target_kind,
    validate_memory_store_schema,
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
        "The UX Design Section Mapping line must explicitly cite the exact canonical Figma source path shown above; do not refer to it generically as only 'figma'.",
        "Set the checklist line to include hierarchy=yes, prohibited_surfaces=yes, and backend_wiring_only=no when justified by the work.",
    ]
    return "\n".join(lines)


def repo_local_standards_block() -> str:
    standards = load_repo_local_standards(ROOT)
    lines = [
        "Repo-local standards:",
        f"- AGENTS.md: {'present' if standards.get('agents_exists') else 'missing'}",
        f"- skills/: {'present' if standards.get('skills_exists') else 'missing'}",
        f"- skill files: {', '.join(standards.get('skill_files', [])) or 'none'}",
    ]
    for expectation in standards.get("agents_core_expectations", []):
        lines.append(f"- AGENTS core expectation: {expectation}")
    for role, detail in standards.get("agents_execution_roles", {}).items():
        lines.append(f"- AGENTS execution role: {role} => {detail}")
    for entry in standards.get("skill_entries", []):
        lines.append(f"- repo skill: {entry.get('name')} => {entry.get('summary')}")
    return "\n".join(lines)


def phase4_enforcement_block(task: dict) -> str:
    if not is_phase4_builder_task(task):
        return "- none"
    return "\n".join(
        [
            "Phase 4 builder enforcement artifacts:",
            "- compiled_feature_spec.md",
            "- research_brief.md",
            "- proposal.md",
            "- tradeoff_matrix.md",
            "- runtime_proof.log",
            "- evidence_bundle.json",
            "- judge_decision.md",
            "Decision checkpoint behavior:",
            "- pause if materially different implementation options exist without a selected approach.",
        ]
    )


def product_contract_requirements_block(task: dict) -> str:
    if task_target_kind(task) != "product":
        return "- none"
    contract = str(task.get("product_contract") or default_product_contract(task)).strip()
    layers = list(task.get("systemic_layers", default_systemic_layers(task)))
    misleading = list(task.get("misleading_partial_implementations", []))
    not_done_until = list(task.get("not_done_until", default_not_done_until(task)))
    lines = [f"Product contract: {contract or 'none'}", "Systemic layers that must be audited before calling the task done:"]
    lines.extend([f"  - {item}" for item in layers] if layers else ["  - none"])
    lines.extend(
        [
            "Misleading partial implementations that do NOT count as done:",
            *([f"  - {item}" for item in misleading] if misleading else ["  - none"]),
            "Not done until:",
            *([f"  - {item}" for item in not_done_until] if not_done_until else ["  - none"]),
            "For product tasks, section 1 of the final response must include labeled lines for:",
            "  - Product Contract:",
            "  - Layers Audited:",
            "  - Misleading Partials Avoided:",
            "  - Not Done Until:",
            "  - Remaining Gaps:",
            "Do not stop at the easiest visible layer if the task contract implies backend, persistence, loading, empty-state, or restore semantics.",
        ]
    )
    return "\n".join(lines)


def memory_context_block(task: dict) -> tuple[str, dict]:
    store = build_memory_store(ROOT)
    (ROOT / "memory_store.json").write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")
    planner_bundle = retrieve_memory_for_role(task, store, role="planner")
    architect_bundle = retrieve_memory_for_role(task, store, role="architect")
    planner_artifacts = retrieve_artifacts_for_role(task, store, role="planner")
    architect_artifacts = retrieve_artifacts_for_role(task, store, role="architect")
    schema_issues = validate_memory_store_schema(store)
    lines = [
        "Retrieved memory context:",
        format_memory_bundle_text(planner_bundle),
        "",
        format_artifact_bundle_text(planner_artifacts),
        "",
        format_memory_bundle_text(architect_bundle),
        "",
        format_artifact_bundle_text(architect_artifacts),
    ]
    if schema_issues:
        lines.extend(["", "Memory schema issues:", *[f"- {issue}" for issue in schema_issues]])
    return "\n".join(lines), {
        "store": store,
        "planner_bundle": planner_bundle,
        "planner_artifacts": planner_artifacts,
        "architect_bundle": architect_bundle,
        "architect_artifacts": architect_artifacts,
        "schema_issues": schema_issues,
    }


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
    target_kind_label = task_target_kind(task)
    target_repo_label = builder_label if target_kind_label == "builder" else product_label
    prompt_name = task.get("prompt") or config["execution"]["default_prompt"]
    prompt_template = (PROMPTS / f"{prompt_name}.md").read_text(encoding="utf-8")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    run_dir = RUN_LOGS / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = run_dir / "codex_prompt.md"
    memory_block, memory_payload = memory_context_block(task)
    (run_dir / "memory_context.json").write_text(json.dumps(memory_payload, indent=2) + "\n", encoding="utf-8")

    repo_context = textwrap.dedent(
        f"""\
        Repo context:
        - Product repo: {product_label}
        - Builder workspace: {builder_label}
        - Current focus: truthful discovery status, discovery observability, bounded runtime behavior
        - Known hot path to preserve: /leads is fast again and should not be regressed casually

        """
    )

    verification_block = fmt_list(task.get("verification", []))
    vm_verification = task.get("vm_verification", [])
    vm_bootstrap = task.get("vm_bootstrap", [])
    vm_cleanup = task.get("vm_cleanup", [])
    if vm_bootstrap:
        verification_block += "\nVM bootstrap commands:\n" + fmt_list(vm_bootstrap)
    if vm_verification:
        verification_block += "\nVM-only verification commands:\n" + fmt_list(vm_verification)
    if vm_cleanup:
        verification_block += "\nVM cleanup commands:\n" + fmt_list(vm_cleanup)

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
        verification_commands=verification_block,
        failure_summary=active.get("failure_summary") or "No failure summary recorded.",
        builder_edit_constraint="- Do not edit product files." if target_kind_label == "builder" else "- Do not edit builder files.",
        ux_conformance_requirements=ux_requirements_block(task),
        product_contract_requirements=product_contract_requirements_block(task),
        repo_local_standards=repo_local_standards_block(),
        phase4_enforcement_requirements=phase4_enforcement_block(task),
        memory_context=memory_block,
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
vm_verification:
{fmt_list(task.get('vm_verification', []))}
vm_bootstrap:
{fmt_list(task.get('vm_bootstrap', []))}
vm_cleanup:
{fmt_list(task.get('vm_cleanup', []))}
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
