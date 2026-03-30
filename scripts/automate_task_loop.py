#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable

from common import (
    build_memory_store,
    builder_root,
    builder_path_from_config,
    references_canonical_figma_source,
    compute_backlog_diagnostics,
    derive_phase4_operator_truth,
    expand_path,
    format_memory_bundle_text,
    is_product_facing_ux_task,
    is_phase4_builder_task,
    load_config,
    load_data,
    load_repo_local_standards,
    load_validated_backlog,
    product_repo_path,
    retrieve_memory_for_role,
    ux_conformance_planning_issues,
    validate_memory_store_schema,
    write_data,
)
from private_eval_suite import (
    compare_eval_results as compare_private_eval_results,
    latest_comparable_history_eval,
    score_private_eval,
)
from feedback_engine import generate_backlog_proposals


ROOT = builder_root()
SCRIPTS_DIR = Path(__file__).resolve().parent
ACTIVE = ROOT / "active_task.yml"
BACKLOG = ROOT / "backlog.yml"
STATUS = ROOT / "status.yml"
MEMORY = ROOT / "builder_memory.md"
TASK_HISTORY = ROOT / "task_history"
BLOCKERS = ROOT / "blockers"
RUN_LEDGER = ROOT / "run_ledger.json"
RUN_LOCK = ROOT / "run_lock.json"
SELECT_TASK = SCRIPTS_DIR / "select_task.py"
RENDER_PACKET = SCRIPTS_DIR / "render_packet.py"
RESULT_FILE = "automation_result.json"
SUMMARY_FILE = "automation_summary.md"
PROGRESS_FILE = "progress.jsonl"
FEATURE_SPEC_ALLOW_EMPTY_KEYS = {"verification_commands"}
PHASE4_REQUIRED_ARTIFACTS = (
    "compiled_feature_spec.md",
    "proposal.md",
    "tradeoff_matrix.md",
    "research_brief.md",
    "judge_decision.md",
    "evidence_bundle.json",
    "runtime_proof.log",
)
PHASE4_FEATURE_SPEC_REQUIRED_KEYS = (
    "task_id",
    "task_title",
    "task_area",
    "task_type",
    "task_nontrivial",
    "objective",
    "why_it_matters",
    "user_story",
    "initiating_trigger",
    "data_inputs",
    "state_transitions",
    "failure_modes",
    "observability_requirements",
    "acceptance_tests",
    "verification_commands",
    "repo_bounds",
    "repo_local_standards",
)
PHASE4_OPTION_SET = (
    {
        "name": "Minimal coherent change",
        "summary": "Use the smallest machine-checkable builder change that enforces the task contract without expanding scope.",
        "complexity": "low",
        "risks": "May leave extensibility work for later if the contract grows.",
        "maintainability": "High if the enforcement boundary stays narrow and explicit.",
        "runtime": "Keeps execution overhead modest and predictable.",
        "product": "Improves trust without inventing extra process.",
        "decision": "Prefer when one bounded mechanism can enforce the requirement directly.",
    },
    {
        "name": "Generalized framework extension",
        "summary": "Introduce a more extensible subsystem that can support similar builder behaviors across future products and tasks.",
        "complexity": "medium",
        "risks": "Higher chance of overbuilding or introducing regressions in unrelated flows.",
        "maintainability": "Good if the abstractions remain narrow and well-tested.",
        "runtime": "May add more orchestration and artifact overhead.",
        "product": "Creates stronger reuse but costs more now.",
        "decision": "Prefer when the task explicitly requires reuse beyond one product or stage.",
    },
)
CANONICAL_RUN_STATES = {
    "idle",
    "task_selected",
    "preflight_passed",
    "preflight_failed",
    "implementing",
    "verifying",
    "completed",
    "blocked",
}
TERMINAL_RUN_STATES = {"preflight_failed", "completed", "blocked"}
TASK_STAGE_NAMES = [
    "Task selected",
    "Codex prompt generated",
    "Codex execution running",
    "Applying changes",
    "Local validation (pytest)",
    "Preflight check",
    "Git commit and push",
    "VM validation",
    "Classification",
]
CANONICAL_STATE_LEGEND = {
    "idle": "No active task is currently in flight.",
    "task_selected": "A task has been selected and the current run has been initialized.",
    "preflight_passed": "Auth and initial run gating passed; execution may continue.",
    "preflight_failed": "Execution stopped before implementation because preflight gating failed.",
    "implementing": "Implementation is in progress or awaiting executor-produced repo changes.",
    "verifying": "Deterministic local and/or VM verification is in progress.",
    "completed": "The active run completed successfully and reached a terminal accepted state.",
    "blocked": "The active run reached a terminal blocked/refined state and requires intervention or retry.",
}
NONINTERACTIVE_GIT_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
}
UX_MAPPING_LABEL = "UX Design Section Mapping:"
UX_DEVIATIONS_LABEL = "UX Intentional Design Deviations:"
UX_CHECKLIST_LABEL = "UX Product-First Checklist:"
TRANSIENT_EXECUTOR_FAILURE_PATTERNS = (
    "stream disconnected before completion",
    "error sending request for url",
    "attempt to write a readonly database",
    "channel closed",
    "thread/read failed",
    "not materialized yet",
)
FAILURE_RECOVERY_MAP = {
    "prompt_planning_failure": {"action": "replan_required", "retryable": True},
    "implementation_failure": {"action": "retry_with_modified_strategy", "retryable": True},
    "local_test_failure": {"action": "retry_with_modified_strategy", "retryable": True},
    "runtime_vm_failure": {"action": "retry_with_modified_strategy", "retryable": True},
    "repo_state_failure": {"action": "block_pending_operator_decision", "retryable": False},
    "auth_connectivity_failure": {"action": "block_pending_operator_decision", "retryable": False},
    "artifact_completeness_failure": {"action": "replan_required", "retryable": True},
    "flaky_nondeterministic_failure": {"action": "quarantine_flaky_task", "retryable": False},
    "spec_ambiguity_failure": {"action": "block_pending_operator_decision", "retryable": False},
    "configuration_defect": {"action": "block_pending_operator_decision", "retryable": False},
}


def is_auto_ready_synthesized_builder_followup(task: dict[str, Any], completed: set[str]) -> bool:
    if str(task.get("status")) != "pending":
        return False
    if not str(task.get("id") or "").startswith("DRAFT-JORB-INFRA-"):
        return False
    if str(task.get("area") or "").lower() != "builder":
        return False
    operator = task.get("operator_approval") or {}
    if not operator.get("approved"):
        return False
    dependencies = [str(dep) for dep in task.get("depends_on", [])]
    if any(dep not in completed for dep in dependencies):
        return False
    return True


def promote_auto_ready_pending_tasks(backlog: dict[str, Any]) -> list[str]:
    tasks = list(backlog.get("tasks", []))
    completed = {str(task.get("id")) for task in tasks if str(task.get("status")) in {"accepted", "done"}}
    promoted: list[str] = []
    for task in tasks:
        if not is_auto_ready_synthesized_builder_followup(task, completed):
            continue
        task["status"] = "ready"
        notes = list(task.get("notes", []))
        note = "Auto-promoted to ready after dependency-satisfied synthesized JORB-INFRA follow-up became runnable."
        if note not in notes:
            notes.append(note)
        task["notes"] = notes
        promoted.append(str(task.get("id")))
    return promoted


def extract_streamlit_port(commands: list[str]) -> str | None:
    for command in commands:
        match = re.search(r"--server\.port\s+(\d+)", str(command))
        if match:
            return match.group(1)
    return None


def extract_runtime_self_check_ui_url(commands: list[str]) -> str | None:
    for command in commands:
        text = str(command)
        if "runtime_self_check.sh" not in text:
            continue
        match = re.search(r"UI_URL=([^\s]+)", text)
        if match:
            return match.group(1)
        return "http://127.0.0.1:8500"
    return None


def phase4_artifact_path(run_dir: Path, name: str) -> Path:
    return run_dir / name


def phase4_required_artifact_paths(run_dir: Path) -> dict[str, Path]:
    return {name: phase4_artifact_path(run_dir, name) for name in PHASE4_REQUIRED_ARTIFACTS}


def phase4_runtime_proof_path(run_dir: Path) -> Path:
    return run_dir / "runtime_proof.log"


def phase4_research_brief_path(run_dir: Path) -> Path:
    return run_dir / "research_brief.md"


def phase4_postmortem_path(run_dir: Path) -> Path:
    return run_dir / "postmortem.md"


def phase4_requires_artifact_enforcement(task: dict[str, Any]) -> bool:
    return is_phase4_builder_task(task)


def phase4_stage_order(task: dict[str, Any], *, use_vm_flow: bool) -> list[str]:
    stages = ["planner", "architect", "implementer", "validator"]
    if use_vm_flow:
        stages.append("runtime_critic")
    if is_product_facing_ux_task(task):
        stages.append("ux_checker")
    stages.append("judge")
    return stages


def phase4_failure_category(summary: str) -> str:
    normalized = summary.lower()
    if "missing automation configuration" in normalized:
        return "configuration_defect"
    if "dirty before automated execution" in normalized:
        return "environment_defect"
    if "allowlist" in normalized:
        return "code_defect"
    if "vm bootstrap failed" in normalized or "vm preflight" in normalized or "vm smoke" in normalized:
        return "environment_defect"
    if "ux conformance" in normalized:
        return "unresolved_ux_mismatch"
    if "selector_filtered_everything" in normalized or "dependency" in normalized:
        return "dependency_ordering_defect"
    if "no product repo changes" in normalized:
        return "recovery_logic_gap"
    return "code_defect"


def repo_local_standards_issues(standards: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not standards.get("agents_exists"):
        issues.append("AGENTS.md")
    if not standards.get("skills_exists"):
        issues.append("skills/")
    return issues


def phase4_decision_checkpoint_issue(task: dict[str, Any]) -> str | None:
    if not phase4_requires_artifact_enforcement(task):
        return None
    options = task.get("implementation_options", [])
    if isinstance(options, list) and len(options) > 1 and not str(task.get("selected_approach") or "").strip():
        return "Decision checkpoint required: multiple implementation options are declared but no selected_approach is recorded."
    return None


def task_is_nontrivial(task: dict[str, Any]) -> bool:
    list_signals = (
        task.get("acceptance"),
        task.get("acceptance_criteria"),
        task.get("verification"),
        task.get("vm_verification"),
        task.get("vm_bootstrap"),
        task.get("implementation_options"),
        task.get("depends_on"),
        task.get("allowlist"),
        task.get("forbid"),
        task.get("denylist"),
    )
    if any(isinstance(items, list) and any(str(item).strip() for item in items) for items in list_signals):
        return True
    scalar_signals = (
        task.get("objective"),
        task.get("why_it_matters"),
        task.get("selected_approach"),
    )
    return any(str(value or "").strip() for value in scalar_signals)


def compile_feature_spec_trigger(task: dict[str, Any]) -> str:
    status = str(task.get("status") or "").strip()
    if status:
        return f"Backlog task {task['id']} entered automation with status {status}."
    return f"Backlog task {task['id']} entered automation."


def compile_feature_spec_inputs(task: dict[str, Any]) -> list[str]:
    inputs = [
        f"Task identity: id={task['id']}, title={task['title']}, area={task.get('area')}, type={task.get('type')}",
    ]
    if str(task.get("objective") or "").strip():
        inputs.append(f"Objective: {str(task.get('objective')).strip()}")
    if str(task.get("why_it_matters") or "").strip():
        inputs.append(f"Why it matters: {str(task.get('why_it_matters')).strip()}")
    for label, key in (
        ("acceptance", "acceptance"),
        ("acceptance_criteria", "acceptance_criteria"),
        ("verification", "verification"),
        ("vm_verification", "vm_verification"),
        ("vm_bootstrap", "vm_bootstrap"),
        ("allowlist", "allowlist"),
        ("denylist", "denylist"),
        ("forbid", "forbid"),
        ("depends_on", "depends_on"),
    ):
        values = task.get(key)
        if isinstance(values, list):
            normalized = [str(item).strip() for item in values if str(item).strip()]
            if normalized:
                inputs.append(f"{label}: {', '.join(normalized)}")
    inputs.append("Builder config, backlog truth, active task state, and repo-local standards")
    return inputs


def compile_feature_spec_state_transitions(task: dict[str, Any]) -> list[str]:
    transitions = [
        "selected -> packet_rendered -> implementing -> verifying -> completed/blocked/refined/interrupted",
    ]
    if task_is_nontrivial(task):
        transitions.insert(0, "selected -> compiled_feature_spec_ready -> packet_rendered")
    if phase4_requires_artifact_enforcement(task):
        transitions.append("acceptance is allowed only after judge/evidence enforcement succeeds")
    return transitions


def compile_feature_spec_failure_modes(task: dict[str, Any]) -> list[str]:
    modes = [
        "task intent compiled incorrectly or incompletely",
        "implementation changes exceed repo bounds or allowlist",
        "verification coverage does not match the task packet",
    ]
    if phase4_requires_artifact_enforcement(task):
        modes.extend(
            [
                "missing required artifacts",
                "unresolved decision checkpoint",
                "missing runtime proof when required",
                "misleading success without judge evidence",
            ]
        )
    return modes


def compile_feature_spec_observability(task: dict[str, Any]) -> list[str]:
    observability = [
        "compiled_feature_spec.md written before implementation begins",
        "task inputs and repo bounds reflected in machine payload",
        "run_logs preserve prompt, progress, and result artifacts",
    ]
    if phase4_requires_artifact_enforcement(task):
        observability.extend(
            [
                "explicit stage plan",
                "evidence bundle and judge decision",
            ]
        )
    return observability


def phase4_feature_spec_payload(task: dict[str, Any], standards: dict[str, Any]) -> dict[str, Any]:
    acceptance = task.get("acceptance", []) or task.get("acceptance_criteria", [])
    verification = [str(item).strip() for item in task.get("verification", []) if str(item).strip()]
    repo_bounds = {
        "allowlist": [str(item).strip() for item in task.get("allowlist", []) if str(item).strip()],
        "denylist": [str(item).strip() for item in (task.get("denylist", []) or task.get("forbid", [])) if str(item).strip()],
        "target_repo_scope": "builder-only" if str(task.get("area") or "").strip().lower() == "builder" else "task-defined",
    }
    return {
        "task_id": task["id"],
        "task_title": task["title"],
        "task_area": task.get("area"),
        "task_type": task.get("type"),
        "task_nontrivial": task_is_nontrivial(task),
        "objective": str(task.get("objective") or "").strip(),
        "why_it_matters": str(task.get("why_it_matters") or "").strip(),
        "user_story": str(task.get("objective") or "").strip() or f"Complete {task['title']} within the stated repo bounds and verification plan.",
        "initiating_trigger": compile_feature_spec_trigger(task),
        "data_inputs": compile_feature_spec_inputs(task),
        "state_transitions": compile_feature_spec_state_transitions(task),
        "failure_modes": compile_feature_spec_failure_modes(task),
        "observability_requirements": compile_feature_spec_observability(task),
        "acceptance_tests": acceptance or ["Acceptance criteria are taken directly from backlog task metadata."],
        "verification_commands": verification,
        "repo_bounds": repo_bounds,
        "repo_local_standards": {
            "agents_loaded": bool(standards.get("agents_exists")),
            "skill_files": list(standards.get("skill_files", [])),
        },
    }


def phase4_feature_spec_text(task: dict[str, Any], standards: dict[str, Any]) -> str:
    payload = phase4_feature_spec_payload(task, standards)
    return "\n".join(
        [
            f"# Compiled Feature Spec: {task['id']}",
            "",
            "## Machine-Checkable Payload",
            "```json",
            json.dumps(payload, indent=2),
            "```",
            "",
            "## User Story",
            payload["user_story"],
            "",
            "## Initiating Trigger",
            payload["initiating_trigger"],
            "",
            "## Data Inputs",
            *[f"- {item}" for item in payload["data_inputs"]],
            "",
            "## State Transitions",
            *[f"- {item}" for item in payload["state_transitions"]],
            "",
            "## Backend Changes",
            "- Builder orchestration and enforcement code only",
            "",
            "## Frontend or UX Surfaces",
            "- Builder operator artifacts and run logs",
            "",
            "## Failure Modes",
            *[f"- {item}" for item in payload["failure_modes"]],
            "",
            "## Observability Requirements",
            *[f"- {item}" for item in payload["observability_requirements"]],
            "",
            "## Out of Scope",
            "- JORB product feature implementation",
            "- product repo edits except runtime-proof interaction when explicitly required",
            "",
            "## Acceptance Test In Product Terms",
            *[f"- {item}" for item in payload["acceptance_tests"]],
            "",
            "## Repo-Local Standards",
            f"- AGENTS.md loaded: {'yes' if payload['repo_local_standards']['agents_loaded'] else 'no'}",
            f"- skills loaded: {', '.join(payload['repo_local_standards']['skill_files']) or 'none'}",
        ]
    )


def phase4_research_brief_text(task: dict[str, Any]) -> str:
    title = str(task.get("title") or task.get("id"))
    return "\n".join(
        [
            f"# Research Brief: {task['id']}",
            "",
            f"Task focus: {title}",
            "",
            "## Relevant Patterns",
            "- staged delivery pipelines separate planning, implementation, validation, and acceptance",
            "- CI/CD gate systems require machine-checkable evidence before promotion",
            "- operator tooling benefits from explicit artifacts and replayable run logs",
            "",
            "## What Works",
            "- distinct acceptance authority (judge) separate from implementation",
            "- required artifacts that block optimistic success",
            "- runtime proof that records commands, timestamps, and outputs",
            "",
            "## What Fails",
            "- checklist-only process with no automatic enforcement",
            "- acceptance based on summary text instead of evidence",
            "- retry logic that mutates queue truth without preserving context",
            "",
            "## Why These Patterns Apply Here",
            "- the builder is an orchestration product and needs the same enforcement discipline it asks of product work",
        ]
    )


def phase4_tradeoff_matrix_text(task: dict[str, Any]) -> str:
    lines = [f"# Tradeoff Matrix: {task['id']}", ""]
    for option in PHASE4_OPTION_SET:
        lines.extend(
            [
                f"## {option['name']}",
                f"- Summary: {option['summary']}",
                f"- Complexity: {option['complexity']}",
                f"- Risks: {option['risks']}",
                f"- Maintainability: {option['maintainability']}",
                f"- Runtime implications: {option['runtime']}",
                f"- Product implications: {option['product']}",
                f"- When to choose: {option['decision']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def phase4_proposal_text(task: dict[str, Any], standards: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Proposal: {task['id']}",
            "",
            "## Recommended Approach",
            "Choose the minimal coherent change first, while keeping contracts machine-checkable and reusable.",
            "",
            "## Assumptions",
            f"- Task area: {task.get('area')}",
            f"- Repo-local standards are available: {'yes' if not repo_local_standards_issues(standards) else 'no'}",
            "",
            "## Constraints",
            "- Do not modify JORB product code during builder-only hardening work.",
            "- Preserve accepted backlog truth and stop on first hard failure.",
            "",
            "## Tradeoff Summary",
            "- Prefer explicit artifacts and gates over prose-only policy.",
            "- Escalate to a decision checkpoint only when materially different approaches exist.",
        ]
    )


def write_phase4_preimplementation_artifacts(
    run_dir: Path,
    task: dict[str, Any],
    standards: dict[str, Any],
) -> list[str]:
    created: list[str] = []
    feature_spec_path = write_compiled_feature_spec(run_dir, task, standards)
    if feature_spec_path:
        created.append(feature_spec_path)
    artifacts = {
        "research_brief.md": phase4_research_brief_text(task),
        "tradeoff_matrix.md": phase4_tradeoff_matrix_text(task),
        "proposal.md": phase4_proposal_text(task, standards),
    }
    for name, content in artifacts.items():
        path = run_dir / name
        path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
        created.append(str(path))
    return created


def write_phase4_runtime_proof_log(
    run_dir: Path,
    *,
    local_validation: dict[str, Any] | None,
    vm_validation: dict[str, Any] | None,
    summary: str,
) -> Path:
    lines = ["# Runtime Proof", "", f"summary: {summary}", ""]
    if local_validation is not None:
        lines.append("## Local Validation")
        for result in local_validation.get("results", []):
            lines.append(f"- command: {result.get('command')}")
            lines.append(f"  passed: {result.get('passed')}")
    if vm_validation is not None:
        lines.append("")
        lines.append("## VM Validation")
        for result in vm_validation.get("results", []):
            lines.append(f"- phase: {result.get('phase', 'vm_pull')}")
            lines.append(f"  command: {result.get('command')}")
            lines.append(f"  passed: {result.get('passed')}")
    path = phase4_runtime_proof_path(run_dir)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_phase4_judge_decision(
    run_dir: Path,
    *,
    task: dict[str, Any],
    automation_result: dict[str, Any],
    standards: dict[str, Any],
    judge_memory_bundle: dict[str, Any] | None = None,
) -> Path:
    required_artifacts = phase4_required_artifact_paths(run_dir)
    lines = [
        f"# Judge Decision: {task['id']}",
        "",
        f"classification: {automation_result['classification']}",
        f"summary: {automation_result['summary']}",
        "",
        "## Gate Check",
        f"- required artifacts present: {'yes' if all(path.exists() for path in required_artifacts.values() if path.name != 'judge_decision.md') else 'no'}",
        f"- repo-local standards loaded: {'yes' if not repo_local_standards_issues(standards) else 'no'}",
        f"- runtime proof captured: {'yes' if phase4_runtime_proof_path(run_dir).exists() else 'no'}",
        "",
        "## Decision",
        "Acceptance is based on evidence artifacts and recorded validation results, not on narrative confidence.",
    ]
    if judge_memory_bundle:
        lines.extend(
            [
                "",
                "## Judge Memory Context",
                format_memory_bundle_text(judge_memory_bundle),
            ]
        )
    path = run_dir / "judge_decision.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_phase4_evidence_bundle(
    run_dir: Path,
    *,
    task: dict[str, Any],
    automation_result: dict[str, Any],
    standards: dict[str, Any],
    memory_store: dict[str, Any],
    judge_memory_bundle: dict[str, Any],
    judge_memory_path: Path,
) -> Path:
    evidence_path = run_dir / "evidence_bundle.json"
    evidence_payload = {
        "task_id": task["id"],
        "classification": automation_result.get("classification"),
        "summary": automation_result.get("summary"),
        "artifacts": {
            "compiled_feature_spec": str(run_dir / "compiled_feature_spec.md"),
            "research_brief": str(phase4_research_brief_path(run_dir)),
            "proposal": str(run_dir / "proposal.md"),
            "tradeoff_matrix": str(run_dir / "tradeoff_matrix.md"),
            "runtime_proof": str(phase4_runtime_proof_path(run_dir)),
            "eval_result": str(run_dir / "eval_result.json"),
            "judge_memory_context": str(judge_memory_path),
            "judge_decision": str(run_dir / "judge_decision.md"),
            "postmortem": str(phase4_postmortem_path(run_dir)) if phase4_postmortem_path(run_dir).exists() else None,
        },
        "repo_local_standards": {
            "agents_path": standards.get("agents_path"),
            "skills_dir": standards.get("skills_dir"),
            "skill_files": standards.get("skill_files", []),
        },
        "memory_schema_issues": validate_memory_store_schema(memory_store),
        "judge_memory_selected": [
            {
                "memory_id": entry.get("memory_id"),
                "memory_type": entry.get("memory_type"),
                "selection_score": entry.get("selection_score"),
                "selection_reasons": entry.get("selection_reasons"),
            }
            for entry in judge_memory_bundle.get("selected", [])
        ],
        "steps": automation_result.get("steps", []),
    }
    evidence_path.write_text(json.dumps(evidence_payload, indent=2) + "\n", encoding="utf-8")
    return evidence_path


def write_phase4_postmortem(run_dir: Path, *, summary: str, automation_result: dict[str, Any]) -> Path:
    path = phase4_postmortem_path(run_dir)
    path.write_text(
        "\n".join(
            [
                "# Failure Postmortem",
                "",
                f"summary: {summary}",
                f"category: {phase4_failure_category(summary)}",
                "",
                "## Step Outcomes",
                *[
                    f"- {step.get('name')}: {step.get('outcome')} ({step.get('detail')})"
                    for step in automation_result.get("steps", [])
                ],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def phase4_feature_spec_issues(run_dir: Path, task: dict[str, Any]) -> list[str]:
    path = run_dir / "compiled_feature_spec.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    match = re.search(r"## Machine-Checkable Payload\n```json\n(.*?)\n```", text, re.DOTALL)
    if match is None:
        return ["compiled_feature_spec.md:missing_machine_payload"]
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return ["compiled_feature_spec.md:invalid_machine_payload"]
    issues: list[str] = []
    for key in PHASE4_FEATURE_SPEC_REQUIRED_KEYS:
        value = payload.get(key)
        if key in FEATURE_SPEC_ALLOW_EMPTY_KEYS:
            if value in (None, ""):
                issues.append(f"compiled_feature_spec.md:missing_{key}")
            continue
        if value in (None, "", []):
            issues.append(f"compiled_feature_spec.md:missing_{key}")
    if payload.get("task_id") != task.get("id"):
        issues.append("compiled_feature_spec.md:task_id_mismatch")
    if payload.get("task_title") != task.get("title"):
        issues.append("compiled_feature_spec.md:task_title_mismatch")
    if payload.get("task_nontrivial") is not True:
        issues.append("compiled_feature_spec.md:task_nontrivial_mismatch")
    return issues


def write_compiled_feature_spec(run_dir: Path, task: dict[str, Any], standards: dict[str, Any]) -> str | None:
    if not task_is_nontrivial(task):
        return None
    path = run_dir / "compiled_feature_spec.md"
    path.write_text(phase4_feature_spec_text(task, standards) + "\n", encoding="utf-8")
    return str(path)


def phase4_artifact_issues(run_dir: Path, task: dict[str, Any], *, require_runtime_proof: bool) -> list[str]:
    issues = [name for name, path in phase4_required_artifact_paths(run_dir).items() if not path.exists()]
    issues.extend(phase4_feature_spec_issues(run_dir, task))
    if not phase4_research_brief_path(run_dir).exists():
        issues.append("research_brief.md")
    if require_runtime_proof and not phase4_runtime_proof_path(run_dir).exists():
        issues.append("runtime_proof.log")
    return issues


def persist_result_with_phase4_artifacts(
    run_dir: Path,
    task: dict[str, Any],
    automation_result: dict[str, Any],
    *,
    standards: dict[str, Any],
    require_runtime_proof: bool,
    local_validation_payload: dict[str, Any] | None = None,
    vm_validation_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    eval_result: dict[str, Any] | None = None
    if phase4_requires_artifact_enforcement(task):
        memory_store = build_memory_store(ROOT)
        judge_memory_bundle = retrieve_memory_for_role(task, memory_store, role="judge")
        judge_memory_path = run_dir / "judge_memory_context.json"
        judge_memory_path.write_text(json.dumps(judge_memory_bundle, indent=2) + "\n", encoding="utf-8")
        if not phase4_runtime_proof_path(run_dir).exists():
            write_phase4_runtime_proof_log(
                run_dir,
                local_validation=local_validation_payload,
                vm_validation=vm_validation_payload,
                summary=automation_result.get("summary", ""),
            )
        if automation_result.get("classification") != "accepted":
            write_phase4_postmortem(run_dir, summary=automation_result.get("summary", ""), automation_result=automation_result)
        write_phase4_judge_decision(
            run_dir,
            task=task,
            automation_result=automation_result,
            standards=standards,
            judge_memory_bundle=judge_memory_bundle,
        )
        write_phase4_evidence_bundle(
            run_dir,
            task=task,
            automation_result=automation_result,
            standards=standards,
            memory_store=memory_store,
            judge_memory_bundle=judge_memory_bundle,
            judge_memory_path=judge_memory_path,
        )
        issues = phase4_artifact_issues(run_dir, task, require_runtime_proof=require_runtime_proof)
        if issues and automation_result.get("classification") == "accepted":
            automation_result["classification"] = "blocked"
            automation_result["summary"] = "Phase 4 artifact enforcement failed: " + ", ".join(issues)
            automation_result.setdefault("steps", []).append(
                {
                    "name": "judge",
                    "outcome": "blocked",
                    "detail": "Missing required artifacts: " + ", ".join(issues),
                }
            )
        write_json(run_dir / RESULT_FILE, automation_result)
        write_summary(run_dir, automation_result)
        eval_result = score_run_eval(task, automation_result, run_dir=run_dir, standards=standards)
        prior_eval = latest_comparable_history_eval(task, eval_result, exclude_run_dir=run_dir, root=ROOT)
        if prior_eval is not None:
            eval_result["regression_vs_prior"] = compare_private_eval_results(prior_eval, eval_result)
            eval_result["regression_vs_prior"]["baseline_history_path"] = prior_eval.get("history_path")
        if automation_result.get("classification") == "accepted" and not eval_result.get("passed"):
            automation_result["classification"] = "blocked"
            automation_result["summary"] = f"Eval threshold not met: overall_score={eval_result['overall_score']}"
            automation_result.setdefault("steps", []).append(
                {
                    "name": "eval_gate",
                    "outcome": "blocked",
                    "detail": f"overall_score={eval_result['overall_score']} threshold={eval_result['threshold']}",
                }
            )
            eval_result["blocked_acceptance"] = True
        else:
            eval_result["blocked_acceptance"] = False
        if automation_result.get("classification") != "accepted" and not phase4_postmortem_path(run_dir).exists():
            write_phase4_postmortem(run_dir, summary=automation_result.get("summary", ""), automation_result=automation_result)
        write_eval_result(run_dir, eval_result)
        automation_result["eval_result"] = eval_result
        write_json(run_dir / RESULT_FILE, automation_result)
        write_summary(run_dir, automation_result)
        write_phase4_judge_decision(
            run_dir,
            task=task,
            automation_result=automation_result,
            standards=standards,
            judge_memory_bundle=judge_memory_bundle,
        )
        write_phase4_evidence_bundle(
            run_dir,
            task=task,
            automation_result=automation_result,
            standards=standards,
            memory_store=memory_store,
            judge_memory_bundle=judge_memory_bundle,
            judge_memory_path=judge_memory_path,
        )
    else:
        write_json(run_dir / RESULT_FILE, automation_result)
        write_summary(run_dir, automation_result)
    update_run_ledger(
        task_id=task.get("id"),
        title=task.get("title"),
        run_state=str(automation_result.get("classification")),
        stage_name="judge" if phase4_requires_artifact_enforcement(task) else "classification",
        run_log_dir=run_dir,
        detail=str(automation_result.get("summary")),
        failure_taxonomy=automation_result.get("failure_taxonomy"),
        eval_result=eval_result,
        next_action="Inspect automation_result.json and judge_decision.md.",
    )
    return automation_result


def current_artifact_completeness(run_dir: Path | None) -> dict[str, Any]:
    if run_dir is None:
        return {"present": [], "missing": list(PHASE4_REQUIRED_ARTIFACTS)}
    present: list[str] = []
    missing: list[str] = []
    for name in PHASE4_REQUIRED_ARTIFACTS:
        path = phase4_runtime_proof_path(run_dir) if name == "runtime_proof.log" else run_dir / name
        if path.exists():
            present.append(name)
        else:
            missing.append(name)
    return {"present": present, "missing": missing}


def write_run_ledger(snapshot: dict[str, Any]) -> None:
    previous = load_data(RUN_LEDGER) if RUN_LEDGER.exists() else {"events": []}
    events = list(previous.get("events", []))
    event = snapshot.get("event")
    if event:
        events.append(event)
        events = events[-25:]
    payload = {**previous, **snapshot}
    payload["events"] = events
    payload = derive_phase4_operator_truth(payload)
    write_data(RUN_LEDGER, payload)


def update_run_ledger(
    *,
    task_id: str | None,
    title: str | None,
    run_state: str,
    stage_name: str | None,
    run_log_dir: Path | None,
    detail: str | None = None,
    failure_taxonomy: dict[str, Any] | None = None,
    eval_result: dict[str, Any] | None = None,
    next_action: str | None = None,
) -> None:
    artifact_state = current_artifact_completeness(run_log_dir)
    payload = {
        "updated_at": now_iso(),
        "current_task": task_id,
        "current_title": title,
        "current_stage": stage_name,
        "run_state": run_state,
        "current_blocker": detail if run_state in {"blocked", "preflight_failed"} else None,
        "last_successful_checkpoint": stage_name if run_state in {"task_selected", "preflight_passed", "implementing", "verifying", "completed"} else None,
        "artifact_completeness": artifact_state,
        "failure_taxonomy": failure_taxonomy,
        "eval_result": eval_result,
        "eval_blocked_acceptance": bool((eval_result or {}).get("blocked_acceptance")),
        "runtime_proof_summary": None if run_log_dir is None else (phase4_runtime_proof_path(run_log_dir).read_text(encoding="utf-8")[:400] if phase4_runtime_proof_path(run_log_dir).exists() else None),
        "next_recommended_action": next_action,
        "run_log_dir": str(run_log_dir) if run_log_dir else None,
        "event": {
            "at": now_iso(),
            "task_id": task_id,
            "run_state": run_state,
            "stage_name": stage_name,
            "detail": detail,
        },
    }
    write_run_ledger(payload)


def clear_run_ledger_after_repair(*, next_action: str | None = None) -> None:
    update_run_ledger(
        task_id=None,
        title=None,
        run_state="idle",
        stage_name=None,
        run_log_dir=None,
        detail=None,
        next_action=next_action or "Inspect backlog truth and rerun automation when ready.",
    )


def detect_failure_taxonomy(summary: str, automation_result: dict[str, Any]) -> dict[str, Any]:
    normalized = summary.lower()
    if "auth" in normalized or "interactive prompts" in normalized or "ssh" in normalized or "executor_transport_failure" in normalized:
        failure_class = "auth_connectivity_failure" if "auth" in normalized or "ssh" in normalized else "flaky_nondeterministic_failure"
    elif "dirty before automated execution" in normalized or "allowlist" in normalized:
        failure_class = "repo_state_failure"
    elif "local validation failed" in normalized:
        failure_class = "local_test_failure"
    elif "vm " in normalized:
        failure_class = "runtime_vm_failure"
    elif "artifact" in normalized or "ux conformance evidence is incomplete" in normalized:
        failure_class = "artifact_completeness_failure"
    elif "missing automation configuration" in normalized:
        failure_class = "configuration_defect"
    elif "ambiguity" in normalized or "source of truth" in normalized:
        failure_class = "spec_ambiguity_failure"
    elif "executor completed but no" in normalized or "executor_failure" in normalized:
        failure_class = "implementation_failure"
    else:
        failure_class = "prompt_planning_failure"
    policy = FAILURE_RECOVERY_MAP.get(failure_class, {"action": "replan_required", "retryable": False})
    return {
        "failure_class": failure_class,
        "recovery_action": policy["action"],
        "retryable": policy["retryable"],
    }


def recent_failure_loop_count(task_id: str, failure_class: str, *, limit: int = 5) -> int:
    count = 0
    history_files = sorted(TASK_HISTORY.glob(f"*-{task_id}.yml"), reverse=True)
    for path in history_files[:limit]:
        payload = load_data(path)
        taxonomy = payload.get("failure_taxonomy") or {}
        if taxonomy.get("failure_class") == failure_class:
            count += 1
    return count


def score_run_eval(
    task: dict[str, Any],
    automation_result: dict[str, Any],
    *,
    run_dir: Path,
    standards: dict[str, Any],
) -> dict[str, Any]:
    eval_result = score_private_eval(task, automation_result, run_dir=run_dir, standards=standards, root=ROOT)
    if eval_result.get("mode") != "no_fixture":
        return eval_result
    step_lookup = {step.get("name"): step for step in automation_result.get("steps", [])}
    scores = {
        "planning_quality": 1.0 if (run_dir / "compiled_feature_spec.md").exists() and (run_dir / "proposal.md").exists() else 0.3,
        "implementation_quality": 1.0 if automation_result.get("classification") == "accepted" else 0.5 if step_lookup.get("executor", {}).get("outcome") == "passed" else 0.2,
        "test_adequacy": 1.0 if step_lookup.get("local_validation", {}).get("outcome") in {"passed", "accepted"} or "local_validation" not in step_lookup else 0.0,
        "runtime_proof_quality": 1.0 if phase4_runtime_proof_path(run_dir).exists() else 0.0,
        "evidence_quality": 1.0 if (run_dir / "evidence_bundle.json").exists() and (run_dir / "judge_decision.md").exists() else 0.0,
        "operator_handoff_quality": 1.0 if (standards.get("agents_exists") and standards.get("skills_exists")) else 0.4,
    }
    overall = round(sum(scores.values()) / len(scores), 3)
    return {
        "suite_version": 1,
        "mode": "heuristic_fallback",
        "task_id": task["id"],
        "scores": scores,
        "overall_score": overall,
        "threshold": 0.75,
        "passed": overall >= 0.75,
        "mandatory_artifacts": {"present": [], "missing": []},
        "dimension_failures": [],
    }


def write_eval_result(run_dir: Path, eval_result: dict[str, Any]) -> Path:
    path = run_dir / "eval_result.json"
    path.write_text(json.dumps(eval_result, indent=2) + "\n", encoding="utf-8")
    return path


def preflight_contract_issues(
    *,
    task: dict[str, Any],
    target_kind: str,
    target_repo: Path,
    standards: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    if not target_repo.exists():
        issues.append(f"missing_target_repo:{target_repo}")
    required_dirs = [ROOT / "prompts", ROOT / "run_logs", ROOT / "task_history", ROOT / "blockers"]
    for directory in required_dirs:
        if not directory.exists():
            issues.append(f"missing_required_dir:{directory.name}")
    if phase4_requires_artifact_enforcement(task):
        issues.extend(repo_local_standards_issues(standards))
    return issues


def acquire_run_lock(task_id: str) -> tuple[bool, str | None]:
    current = {
        "pid": os.getpid(),
        "task_id": task_id,
        "acquired_at": now_iso(),
    }
    if RUN_LOCK.exists():
        payload = load_data(RUN_LOCK)
        other_pid = payload.get("pid")
        if isinstance(other_pid, int):
            if other_pid == os.getpid():
                write_data(RUN_LOCK, current)
                return True, None
            try:
                os.kill(other_pid, 0)
                return False, f"run_lock held by pid {other_pid} for task {payload.get('task_id')}"
            except OSError:
                pass
    write_data(RUN_LOCK, current)
    return True, None


def release_run_lock() -> None:
    if not RUN_LOCK.exists():
        return
    payload = load_data(RUN_LOCK)
    if payload.get("pid") == os.getpid():
        RUN_LOCK.unlink(missing_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_task(backlog: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in backlog.get("tasks", []):
        if task.get("id") == task_id:
            return task
    raise KeyError(task_id)


def reset_active() -> dict[str, Any]:
    return {
        "task_id": None,
        "title": None,
        "state": "idle",
        "attempt": 0,
        "started_at": None,
        "handed_to_codex_at": None,
        "prompt_file": None,
        "run_log_dir": None,
        "verification_commands": [],
        "vm_verification_commands": [],
        "vm_bootstrap_commands": [],
        "vm_cleanup_commands": [],
        "allowlist": [],
        "failure_summary": None,
        "notes": [],
        "target_repo": None,
        "target_kind": None,
        "previous_run_log_dir": None,
        "prior_run_log_dirs": [],
    }


def append_memory(line: str) -> None:
    with MEMORY.open("a", encoding="utf-8") as handle:
        handle.write(f"\n- {line}\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_step(run_dir: Path, name: str, payload: dict[str, Any]) -> None:
    write_json(run_dir / f"{name}.json", payload)


def history_evidence_artifacts(run_dir: Path | None, prompt_file: Path | None) -> list[dict[str, str]]:
    candidates: list[tuple[str, Path]] = []
    if prompt_file is not None:
        candidates.append(("prompt", prompt_file))
    if run_dir is not None:
        candidates.extend(
            [
                ("run_log_dir", run_dir),
                ("automation_result", run_dir / RESULT_FILE),
                ("automation_summary", run_dir / SUMMARY_FILE),
                ("progress_log", run_dir / PROGRESS_FILE),
                ("executor_output", run_dir / "codex_last_message.md"),
                ("local_validation", run_dir / "local_validation.json"),
                ("vm_validation", run_dir / "vm_validation.json"),
                ("git", run_dir / "git.json"),
                ("executor", run_dir / "executor.json"),
                ("eval_result", run_dir / "eval_result.json"),
                ("judge_memory_context", run_dir / "judge_memory_context.json"),
                ("judge_decision", run_dir / "judge_decision.md"),
                ("evidence_bundle", run_dir / "evidence_bundle.json"),
            ]
        )
    artifacts: list[dict[str, str]] = []
    for label, path in candidates:
        if path.exists():
            artifacts.append({"label": label, "path": str(path)})
    return artifacts


def extract_labeled_line(text: str, label: str) -> str | None:
    for line in text.splitlines():
        normalized_line = line.lstrip()
        if normalized_line.startswith(label):
            return normalized_line[len(label):].strip()
        # Accept executor responses that prefix sections with ordered-list markers
        # like "1. UX Design Section Mapping: ..." without losing the label.
        stripped = normalized_line
        while True:
            prefix, sep, remainder = stripped.partition(". ")
            if not sep or not prefix.isdigit():
                break
            stripped = remainder.lstrip()
            if stripped.startswith(label):
                return stripped[len(label):].strip()
    return None


def is_retryable_executor_failure(executor_result: dict[str, Any]) -> bool:
    if str(executor_result.get("failure_reason") or "") != "executor_failure":
        return False
    text = "\n".join(
        part for part in (str(executor_result.get("stderr") or ""), str(executor_result.get("stdout") or "")) if part
    ).lower()
    return any(pattern in text for pattern in TRANSIENT_EXECUTOR_FAILURE_PATTERNS)


def summarize_retryable_executor_failure(executor_result: dict[str, Any]) -> str:
    text = "\n".join(
        part for part in (str(executor_result.get("stderr") or ""), str(executor_result.get("stdout") or "")) if part
    ).lower()
    if "failed to lookup address information" in text or "could not resolve host" in text:
        return "executor_transport_failure: DNS/network resolution failed while Codex tried to reach chatgpt.com"
    if "stream disconnected before completion" in text or "error sending request for url" in text:
        return "executor_transport_failure: Codex lost its upstream connection before completion"
    if "attempt to write a readonly database" in text:
        return "executor_transport_failure: Codex could not write its local state database"
    return "executor_transport_failure"


def ux_conformance_result(task: dict[str, Any], executor_output: str) -> dict[str, Any]:
    required = is_product_facing_ux_task(task)
    planning_issues = ux_conformance_planning_issues(task)
    result = {
        "required": required,
        "passed": True,
        "planning_issues": planning_issues,
        "missing_response_fields": [],
        "design_section_mapping": extract_labeled_line(executor_output, UX_MAPPING_LABEL),
        "intentional_design_deviations": extract_labeled_line(executor_output, UX_DEVIATIONS_LABEL),
        "product_first_checklist": extract_labeled_line(executor_output, UX_CHECKLIST_LABEL),
        "primary_ux_prohibited_surfaces": task.get("primary_ux_prohibited_surfaces", []),
    }
    if not required:
        return result

    missing: list[str] = []
    if planning_issues:
        missing.extend(planning_issues)
    if not result["design_section_mapping"]:
        missing.append("response.design_section_mapping")
    elif not references_canonical_figma_source(result["design_section_mapping"]):
        missing.append("response.design_section_mapping.figma_source")
    if result["intentional_design_deviations"] is None:
        missing.append("response.intentional_design_deviations")
    checklist = str(result["product_first_checklist"] or "").lower()
    if not checklist:
        missing.append("response.product_first_checklist")
    else:
        if "hierarchy=yes" not in checklist:
            missing.append("response.product_first_checklist.hierarchy")
        if "prohibited_surfaces=yes" not in checklist:
            missing.append("response.product_first_checklist.prohibited_surfaces")
        if "backend_wiring_only=no" not in checklist:
            missing.append("response.product_first_checklist.backend_wiring_only")
    result["missing_response_fields"] = missing
    result["passed"] = not missing
    return result


def history_operator_diagnostics(task: dict[str, Any], automation_result: dict[str, Any]) -> dict[str, Any]:
    accepted = automation_result.get("classification") == "accepted"
    executor_output = ""
    for step in automation_result.get("steps", []):
        if step.get("name") == "executor":
            executor_output = str(step.get("detail") or "")
            break
    ux_conformance = ux_conformance_result(task, executor_output)
    step_outcomes = [
        {"name": step.get("name"), "outcome": step.get("outcome"), "detail": step.get("detail")}
        for step in automation_result.get("steps", [])
    ]
    return {
        "decision_summary": automation_result.get("summary"),
        "accepted": accepted,
        "acceptance_met": task.get("acceptance", []) if accepted else [],
        "acceptance_unmet": [] if accepted else task.get("acceptance", []),
        "step_outcomes": step_outcomes,
        "changed_files_count": len(automation_result.get("changed_files", [])),
        "changed_files": automation_result.get("changed_files", []),
        "unproven_runtime_gaps": automation_result.get("unproven_runtime_gaps", []),
        "ux_conformance": ux_conformance,
    }


def write_summary(run_dir: Path, payload: dict[str, Any]) -> None:
    lines = [
        f"# Automation Result: {payload['classification']}",
        "",
        f"- task_id: {payload['task_id']}",
        f"- classification: {payload['classification']}",
        f"- finished_at: {payload['finished_at']}",
        f"- summary: {payload['summary']}",
        "",
        "## Step Results",
    ]
    for step in payload.get("steps", []):
        lines.append(f"- {step['name']}: {step['outcome']}")
        if step.get("detail"):
            lines.append(f"  detail: {step['detail']}")
    lines.append("")
    lines.append("## Changed Files")
    changed_files = payload.get("changed_files", [])
    if changed_files:
        for path in changed_files:
            lines.append(f"- {path}")
    else:
        lines.append("- none")
    (run_dir / SUMMARY_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_result(label: str, summary: str, next_action: str | None = None, extra: str | None = None) -> None:
    print(f"{label} {summary}")
    if extra:
        print(extra)
    if next_action:
        print(f"Next action: {next_action}")


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def progress_bar(current: int, total: int, *, width: int = 10) -> str:
    if total <= 0:
        total = 1
    filled = min(width, max(0, round((current / total) * width)))
    return "[" + ("█" * filled) + ("░" * (width - filled)) + "]"


def backlog_progress(backlog: dict[str, Any], active_task_id: str | None = None) -> dict[str, Any]:
    diagnostics = compute_backlog_diagnostics(backlog)
    completed = sum(1 for task in backlog.get("tasks", []) if task.get("status") in {"accepted", "done"})
    remaining_ready = len(diagnostics.get("ordered_ready_queue", []))
    current_index = completed + (1 if active_task_id else 0)
    return {
        "completed": completed,
        "remaining_ready": remaining_ready,
        "total": diagnostics.get("total_tasks", len(backlog.get("tasks", []))),
        "current_index": current_index,
    }


def write_progress(run_dir: Path, payload: dict[str, Any]) -> None:
    with (run_dir / PROGRESS_FILE).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def emit_progress(
    run_dir: Path,
    *,
    task_id: str,
    stage_index: int,
    backlog: dict[str, Any],
    task_started_at: str | None,
    state: str = "running",
    detail: str | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> None:
    if (run_dir / RESULT_FILE).exists():
        raise RuntimeError("Cannot emit running progress after terminal automation_result.json exists.")
    overall = backlog_progress(backlog, active_task_id=task_id)
    elapsed = 0.0
    if task_started_at:
        try:
            elapsed = max(0.0, (datetime.now(timezone.utc) - datetime.fromisoformat(task_started_at)).total_seconds())
        except ValueError:
            elapsed = 0.0
    stage_name = TASK_STAGE_NAMES[max(0, min(stage_index - 1, len(TASK_STAGE_NAMES) - 1))]
    completed_stages = max(0, min(stage_index - (0 if state == "completed" else 1), len(TASK_STAGE_NAMES)))
    bar = progress_bar(completed_stages, len(TASK_STAGE_NAMES))
    percent = int((completed_stages / len(TASK_STAGE_NAMES)) * 100)
    remaining_label = "runnable after current" if task_id else "runnable now"
    overall_line = f"[Overall Progress] {overall['completed']}/{overall['total']} tasks completed | {overall['remaining_ready']} {remaining_label}"
    task_line = (
        f"[Task {task_id}] Step {stage_index}/{len(TASK_STAGE_NAMES)}: {stage_name} "
        f"{bar} {percent}% Complete | Elapsed: {format_duration(elapsed)}"
    )
    if state == "failed":
        task_line = (
            f"[Task {task_id}] FAILED at Step {stage_index}: {stage_name} "
            f"| Elapsed: {format_duration(elapsed)}"
        )
    elif state == "completed":
        task_line = (
            f"[Task {task_id}] Completed Step {stage_index}/{len(TASK_STAGE_NAMES)}: {stage_name} "
            f"| Elapsed: {format_duration(elapsed)}"
        )
    print(overall_line)
    print(task_line)
    if detail:
        print(f"Detail: {detail}")
    write_progress(
        run_dir,
        {
            "timestamp": now_iso(),
            "task_id": task_id,
            "stage_index": stage_index,
            "stage_name": stage_name,
            "state": state,
            "detail": detail,
            "elapsed_seconds": int(elapsed),
            "overall": overall,
            **(extra_payload or {}),
        },
    )
    update_run_ledger(
        task_id=task_id,
        title=None,
        run_state=state,
        stage_name=stage_name,
        run_log_dir=run_dir,
        detail=detail,
    )


def allocate_run_dir(task_id: str) -> Path:
    base = ROOT / "run_logs"
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    candidate = base / f"{stamp}-{task_id}"
    suffix = 1
    while candidate.exists():
        candidate = base / f"{stamp}-{task_id}-{suffix}"
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def sync_run_state(
    active: dict[str, Any],
    status: dict[str, Any],
    state: str,
    *,
    task_id: str | None,
    title: str | None,
    run_log_dir: Path | None,
    failure_summary: str | None = None,
    last_result: str | None = None,
) -> None:
    if state not in CANONICAL_RUN_STATES:
        raise RuntimeError(f"Invalid canonical run state: {state}")
    active["task_id"] = task_id
    active["title"] = title
    active["state"] = state
    active["run_log_dir"] = str(run_log_dir) if run_log_dir else None
    active["failure_summary"] = failure_summary
    status["state"] = state
    status["active_task_id"] = task_id
    status["last_run_at"] = now_iso()
    if task_id:
        status["last_task_id"] = task_id
    if last_result is not None:
        status["last_result"] = last_result
    write_data(ACTIVE, active)
    write_data(STATUS, status)
    update_run_ledger(
        task_id=task_id,
        title=title,
        run_state=state,
        stage_name=None,
        run_log_dir=run_log_dir,
        detail=failure_summary,
    )


def prepare_invocation_run_dir(active: dict[str, Any], task_id: str) -> tuple[Path | None, Path]:
    prior_run_log_dirs: list[str] = []
    seen_prior_run_log_dirs: set[str] = set()

    def add_prior_run_log_dir(value: Any) -> None:
        if not value:
            return
        resolved = str(Path(str(value)).expanduser().resolve())
        if resolved in seen_prior_run_log_dirs:
            return
        seen_prior_run_log_dirs.add(resolved)
        prior_run_log_dirs.append(resolved)

    add_prior_run_log_dir(active.get("run_log_dir"))
    add_prior_run_log_dir(active.get("previous_run_log_dir"))
    for entry in active.get("prior_run_log_dirs", []):
        add_prior_run_log_dir(entry)

    previous = None
    if active.get("run_log_dir"):
        previous = Path(str(active["run_log_dir"])).expanduser().resolve()
    elif active.get("previous_run_log_dir"):
        previous = Path(str(active["previous_run_log_dir"])).expanduser().resolve()
    run_dir = allocate_run_dir(task_id)
    active["prior_run_log_dirs"] = prior_run_log_dirs
    active["previous_run_log_dir"] = str(previous) if previous else None
    active["run_log_dir"] = str(run_dir)
    active["started_at"] = now_iso()
    return previous, run_dir


def render_template(template: str | None, context: dict[str, str]) -> str | None:
    if template is None:
        return None
    return re.sub(
        r"\{([A-Za-z_][A-Za-z0-9_]*)\}",
        lambda match: str(context.get(match.group(1), match.group(0))),
        template,
    )


def task_targets_builder_repo(task: dict[str, Any], active: dict[str, Any]) -> bool:
    allowlist = list(task.get("allowlist", []) or active.get("allowlist", []))
    if task.get("area") == "builder":
        return True
    if any(str(entry).startswith("../jorb-builder") for entry in allowlist):
        return True
    return False


def persist_paused_state(active: dict[str, Any], status: dict[str, Any], note: str) -> None:
    if not active.get("handed_to_codex_at"):
        active["handed_to_codex_at"] = now_iso()
    notes = list(active.get("notes", []))
    if note not in notes:
        notes.append(note)
    active["notes"] = notes
    sync_run_state(
        active,
        status,
        "implementing",
        task_id=active.get("task_id"),
        title=active.get("title"),
        run_log_dir=Path(active["run_log_dir"]).expanduser().resolve() if active.get("run_log_dir") else None,
        last_result=status.get("last_result"),
    )


def persist_failure_state(
    active: dict[str, Any],
    status: dict[str, Any],
    *,
    blocked: bool,
    summary: str,
) -> None:
    sync_run_state(
        active,
        status,
        "blocked" if blocked else "blocked",
        task_id=active.get("task_id"),
        title=active.get("title"),
        run_log_dir=Path(active["run_log_dir"]).expanduser().resolve() if active.get("run_log_dir") else None,
        failure_summary=summary,
        last_result="blocked" if blocked else "refined",
    )


def run_shell(
    command: str,
    cwd: Path,
    shell_executable: str,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
    *,
    heartbeat_seconds: int | None = None,
    heartbeat: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    return run_process(
        command,
        cwd,
        timeout=timeout,
        shell=True,
        shell_executable=shell_executable,
        env=env,
        heartbeat_seconds=heartbeat_seconds,
        heartbeat=heartbeat,
    )


def run_process(
    command: str | list[str],
    cwd: Path,
    *,
    timeout: int | None = None,
    shell: bool = False,
    shell_executable: str | None = None,
    env: dict[str, str] | None = None,
    heartbeat_seconds: int | None = None,
    heartbeat: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    started_at = now_iso()
    display_command = command if isinstance(command, str) else " ".join(shlex.quote(part) for part in command)
    try:
        process = subprocess.Popen(
            command,
            shell=shell,
            executable=shell_executable,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, **(env or {})},
        )
    except FileNotFoundError as exc:
        return {
            "command": display_command,
            "cwd": str(cwd),
            "started_at": started_at,
            "finished_at": now_iso(),
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "passed": False,
        }
    timed_out = False
    started_monotonic = time.monotonic()
    deadline = started_monotonic + timeout if timeout is not None else None
    next_heartbeat = started_monotonic + max(1, heartbeat_seconds or 1)
    while True:
        now = time.monotonic()
        returncode = process.poll()
        if returncode is not None:
            break
        if deadline is not None and now >= deadline:
            timed_out = True
            _cleanup_process(process, {"terminate_sent": False, "kill_sent": False})
            break
        if heartbeat and heartbeat_seconds is not None and now >= next_heartbeat:
            timeout_remaining = None if deadline is None else max(0, int(deadline - now))
            heartbeat(
                {
                    "pid": process.pid,
                    "elapsed_seconds": int(now - started_monotonic),
                    "timeout_remaining_seconds": timeout_remaining,
                    "process_status": "running" if process.poll() is None else f"exit_{process.poll()}",
                    "command": display_command,
                }
            )
            next_heartbeat = now + max(1, heartbeat_seconds)
        time.sleep(0.1)
    stdout, stderr = process.communicate()
    if timed_out:
        stderr = (stderr or "") + ("\n" if stderr else "") + f"Timed out after {timeout} seconds."
        returncode = None
    return {
        "command": display_command,
        "cwd": str(cwd),
        "started_at": started_at,
        "finished_at": now_iso(),
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "passed": returncode == 0 and not timed_out,
    }


def run_argv(
    argv: list[str],
    cwd: Path,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
    *,
    heartbeat_seconds: int | None = None,
    heartbeat: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    return run_process(argv, cwd, timeout=timeout, env=env, heartbeat_seconds=heartbeat_seconds, heartbeat=heartbeat)


def run_argv_input(
    argv: list[str],
    cwd: Path,
    *,
    input_text: str,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started_at = now_iso()
    try:
        process = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            input=input_text,
            timeout=timeout,
            env={**os.environ, **(env or {})},
        )
        return {
            "command": " ".join(shlex.quote(part) for part in argv),
            "cwd": str(cwd),
            "started_at": started_at,
            "finished_at": now_iso(),
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "passed": process.returncode == 0,
        }
    except FileNotFoundError as exc:
        return {
            "command": " ".join(shlex.quote(part) for part in argv),
            "cwd": str(cwd),
            "started_at": started_at,
            "finished_at": now_iso(),
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "passed": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(shlex.quote(part) for part in argv),
            "cwd": str(cwd),
            "started_at": started_at,
            "finished_at": now_iso(),
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"Timed out after {timeout} seconds.",
            "passed": False,
        }


def tail_text(value: str | None, *, limit: int = 800) -> str:
    text = value or ""
    if len(text) <= limit:
        return text
    return text[-limit:]


def _read_stream(stream: Any, sink: list[str]) -> None:
    try:
        sink.append(stream.read())
    finally:
        stream.close()


def _cleanup_process(process: subprocess.Popen[str], cleanup: dict[str, bool], *, wait_seconds: float = 5.0) -> None:
    if process.poll() is not None:
        return
    try:
        cleanup["terminate_sent"] = True
        process.terminate()
        process.wait(timeout=wait_seconds)
        return
    except (ProcessLookupError, subprocess.TimeoutExpired):
        pass
    if process.poll() is not None:
        return
    try:
        cleanup["kill_sent"] = True
        process.kill()
        process.wait(timeout=wait_seconds)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        pass


def run_codex_exec(
    argv: list[str],
    cwd: Path,
    *,
    input_text: str,
    output_path: Path,
    timeout: int,
    heartbeat_seconds: int = 15,
    stall_seconds: int | None = None,
    heartbeat: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    started_at = now_iso()
    command = " ".join(shlex.quote(part) for part in argv)
    process: subprocess.Popen[str] | None = None
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    timed_out = False
    interrupted = False
    cleanup = {"terminate_sent": False, "kill_sent": False}
    pid = None
    stream_activity = {
        "stdout_seen": False,
        "stderr_seen": False,
        "last_stream_activity_monotonic": None,
    }
    try:
        process = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        pid = process.pid
        if process.stdin is not None:
            try:
                process.stdin.write(input_text)
                process.stdin.close()
            except BrokenPipeError:
                pass
        def _stream_reader(stream: Any, sink: list[str], stream_key: str) -> None:
            try:
                while True:
                    chunk = stream.read(1024)
                    if not chunk:
                        break
                    sink.append(chunk)
                    stream_activity[stream_key] = True
                    stream_activity["last_stream_activity_monotonic"] = time.monotonic()
            finally:
                stream.close()

        stdout_thread = threading.Thread(target=_stream_reader, args=(process.stdout, stdout_chunks, "stdout_seen"), daemon=True) if process.stdout is not None else None
        stderr_thread = threading.Thread(target=_stream_reader, args=(process.stderr, stderr_chunks, "stderr_seen"), daemon=True) if process.stderr is not None else None
        if stdout_thread is not None:
            stdout_thread.start()
        if stderr_thread is not None:
            stderr_thread.start()
        started_monotonic = time.monotonic()
        deadline = started_monotonic + timeout
        heartbeat_interval = max(1, heartbeat_seconds)
        stall_threshold = max(heartbeat_interval * 2, stall_seconds or max(heartbeat_interval * 4, 60))
        next_heartbeat = started_monotonic + heartbeat_interval
        last_artifact_signature: tuple[int, int | None] | None = None
        last_artifact_change_monotonic: float | None = None
        try:
            while True:
                now = time.monotonic()
                returncode = process.poll()
                if returncode is not None:
                    break
                if now >= deadline:
                    timed_out = True
                    _cleanup_process(process, cleanup)
                    break
                if heartbeat and now >= next_heartbeat:
                    exists = output_path.exists()
                    size = output_path.stat().st_size if exists else 0
                    mtime = output_path.stat().st_mtime if exists else None
                    signature = (size, mtime)
                    if exists and signature != last_artifact_signature:
                        last_artifact_signature = signature
                        last_artifact_change_monotonic = now
                    timeout_remaining = max(0, int(deadline - now))
                    artifact_age = int(now - last_artifact_change_monotonic) if last_artifact_change_monotonic is not None else None
                    stream_age = (
                        int(now - float(stream_activity["last_stream_activity_monotonic"]))
                        if stream_activity["last_stream_activity_monotonic"] is not None
                        else None
                    )
                    if exists:
                        recent_signal_age = min(value for value in [artifact_age, stream_age] if value is not None) if any(
                            value is not None for value in [artifact_age, stream_age]
                        ) else None
                        heartbeat_status = "healthy"
                        waiting_on = "codex subprocess completion"
                        if recent_signal_age is not None and recent_signal_age >= stall_threshold:
                            heartbeat_status = "possibly_stalled"
                    else:
                        recent_signal_age = stream_age
                        heartbeat_status = "healthy" if (stream_activity["stdout_seen"] or stream_activity["stderr_seen"]) else "waiting_for_first_output"
                        waiting_on = output_path.name
                        if (
                            (recent_signal_age is not None and recent_signal_age >= stall_threshold)
                            or (
                                recent_signal_age is None
                                and int(now - started_monotonic) >= stall_threshold
                                and not (stream_activity["stdout_seen"] or stream_activity["stderr_seen"])
                            )
                        ):
                            heartbeat_status = "possibly_stalled"
                    heartbeat(
                        {
                            "pid": pid,
                            "elapsed_seconds": int(now - started_monotonic),
                            "timeout_remaining_seconds": timeout_remaining,
                            "output_file": str(output_path),
                            "last_message_exists": exists,
                            "last_message_size_bytes": size if exists else 0,
                            "last_message_mtime": datetime.fromtimestamp(mtime, timezone.utc).isoformat() if mtime else None,
                            "seconds_since_artifact_change": artifact_age,
                            "seconds_since_stream_activity": stream_age,
                            "process_status": "running" if process.poll() is None else f"exit_{process.poll()}",
                            "stdout_seen": bool(stream_activity["stdout_seen"]),
                            "stderr_seen": bool(stream_activity["stderr_seen"]),
                            "status": heartbeat_status,
                            "waiting_on": waiting_on,
                            "stall_threshold_seconds": stall_threshold,
                        }
                    )
                    next_heartbeat = now + heartbeat_interval
                sleep_for = min(0.2, max(0.05, deadline - now))
                time.sleep(sleep_for)
        except KeyboardInterrupt:
            interrupted = True
            _cleanup_process(process, cleanup)
        if process.poll() is None:
            process.wait(timeout=5)
        returncode = process.returncode
        if stdout_thread is not None:
            stdout_thread.join(timeout=1)
        if stderr_thread is not None:
            stderr_thread.join(timeout=1)
    except FileNotFoundError as exc:
        return {
            "command": command,
            "cwd": str(cwd),
            "started_at": started_at,
            "finished_at": now_iso(),
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "stdout_tail": "",
            "stderr_tail": str(exc),
            "passed": False,
            "timed_out": False,
            "failure_reason": "executor_failure",
            "cleanup": cleanup,
        }

    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)
    last_message = None
    output_exists = output_path.exists()
    output_nonempty = output_exists and output_path.stat().st_size > 0
    if output_nonempty:
        last_message = output_path.read_text(encoding="utf-8")
    result = {
        "command": command,
        "cwd": str(cwd),
        "pid": pid,
        "started_at": started_at,
        "finished_at": now_iso(),
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_tail": tail_text(stdout),
        "stderr_tail": tail_text(stderr),
        "passed": returncode == 0 and output_nonempty and not timed_out and not interrupted,
        "timed_out": timed_out,
        "interrupted": interrupted,
        "failure_reason": None,
        "cleanup": cleanup,
        "output_file": str(output_path),
        "output_file_exists": output_exists,
        "output_file_nonempty": output_nonempty,
    }
    if last_message is not None:
        result["last_message_file"] = str(output_path)
        result["last_message"] = last_message
    if interrupted:
        result["failure_reason"] = "executor_interrupted"
        result["stderr"] = (stderr + ("\n" if stderr else "")) + "Interrupted by user."
        result["stderr_tail"] = tail_text(result["stderr"])
    elif timed_out:
        result["failure_reason"] = "executor_timeout"
        result["stderr"] = (stderr + ("\n" if stderr else "")) + f"Timed out after {timeout} seconds."
        result["stderr_tail"] = tail_text(result["stderr"])
    elif returncode != 0:
        result["failure_reason"] = "executor_failure"
    elif not output_exists:
        result["failure_reason"] = "executor_failure"
        result["stderr"] = (stderr + ("\n" if stderr else "")) + "Codex executor exited successfully but did not create codex_last_message.md."
        result["stderr_tail"] = tail_text(result["stderr"])
    elif not output_nonempty:
        result["failure_reason"] = "executor_failure"
        result["stderr"] = (stderr + ("\n" if stderr else "")) + "Codex executor exited successfully but codex_last_message.md was empty."
        result["stderr_tail"] = tail_text(result["stderr"])
    return result


def ignored_git_paths_for_target(target_kind: str, git_config: dict[str, Any] | None = None) -> tuple[str, ...]:
    defaults: tuple[str, ...] = ()
    if target_kind == "builder":
        defaults = (
            "active_task.yml",
            "backlog.yml",
            "status.yml",
            "builder_memory.md",
            "backlog_apply_audit.json",
            "backlog_proposals.json",
            "feedback_signals.json",
            "memory_overrides.json",
            "memory_store.json",
            "run_ledger.json",
            "run_lock.json",
            "replay_summary.json",
            "eval_comparison.json",
            "synthesized_backlog_entries.json",
            "task_history/",
            "blockers/",
            "run_logs/",
        )
    config = git_config if isinstance(git_config, dict) else load_config().get("git", {})
    extra: list[str] = []
    ignored_dirty_paths = config.get("ignored_dirty_paths", {})
    if isinstance(ignored_dirty_paths, dict):
        raw_entries = ignored_dirty_paths.get(target_kind, [])
        if isinstance(raw_entries, list):
            extra = [str(entry).strip() for entry in raw_entries if str(entry).strip()]
    return defaults + tuple(extra)


def git_status_porcelain(repo: Path, *, ignored_prefixes: tuple[str, ...] = ()) -> dict[str, Any]:
    result = run_argv(["git", "status", "--porcelain", "--untracked-files=all"], repo)
    files: list[str] = []
    for line in result.get("stdout", "").splitlines():
        if not line.strip():
            continue
        path = line[3:] if len(line) > 3 else line
        if any(path == prefix or path.startswith(prefix) for prefix in ignored_prefixes):
            continue
        files.append(path)
    result["files"] = files
    return result


def changed_files_are_allowlisted(changed_files: list[str], allowlist: list[str]) -> tuple[bool, list[str]]:
    if not changed_files:
        return True, []
    disallowed: list[str] = []
    for changed in changed_files:
        normalized = changed.strip()
        allowed = any(
            normalized == entry
            or entry == "../jorb-builder/**"
            or (
                entry.startswith("../jorb-builder/")
                and (
                    entry.removeprefix("../jorb-builder/") == "**"
                    or normalized.startswith(entry.removeprefix("../jorb-builder/").removesuffix("/**"))
                )
            )
            or (
                entry.endswith("/**")
                and normalized.startswith(entry.removesuffix("/**"))
            )
            or (entry.endswith("/") and normalized.startswith(entry))
            for entry in allowlist
        )
        if not allowed:
            disallowed.append(normalized)
    return len(disallowed) == 0, disallowed


def resolve_product_validation_venv(product_repo: Path) -> Path | None:
    for dirname in (".venv_validation", ".venv", ".venv_j1"):
        candidate = product_repo / dirname
        if candidate.exists():
            return candidate
    return None


def validation_commands_for_target(
    commands: list[str],
    *,
    target_kind: str,
    target_repo: Path,
) -> tuple[list[str], Path | None]:
    if target_kind != "product":
        return commands, None
    venv_path = resolve_product_validation_venv(target_repo)
    if venv_path is None:
        return commands, None
    wrapped = [f"source {shlex.quote(str(venv_path / 'bin' / 'activate'))} && {command}" for command in commands]
    return wrapped, venv_path


def effective_task_command_list(task_commands: Any, active_commands: Any) -> list[str]:
    if isinstance(task_commands, list) and [item for item in task_commands if str(item).strip()]:
        return list(task_commands)
    if isinstance(active_commands, list):
        return list(active_commands)
    return []


def ssh_command(
    target: str,
    options: list[str],
    remote_command: str,
    cwd: Path,
    *,
    timeout: int | None = None,
    heartbeat_seconds: int | None = None,
    heartbeat: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    return run_argv(
        ["ssh", *options, target, remote_command],
        cwd,
        timeout=timeout,
        heartbeat_seconds=heartbeat_seconds,
        heartbeat=heartbeat,
    )


def record_history(task: dict[str, Any], active: dict[str, Any], automation_result: dict[str, Any]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    path = TASK_HISTORY / f"{timestamp}-{task['id']}.yml"
    run_dir = Path(str(active["run_log_dir"])).expanduser().resolve() if active.get("run_log_dir") else None
    prompt_file = Path(str(active["prompt_file"])).expanduser().resolve() if active.get("prompt_file") else None
    operator_diagnostics = history_operator_diagnostics(task, automation_result)
    payload = {
        "task_id": task["id"],
        "title": task["title"],
        "status": automation_result["classification"],
        "attempt": active.get("attempt", 1),
        "started_at": active.get("started_at"),
        "completed_at": automation_result["finished_at"],
        "prompt": str(prompt_file) if prompt_file is not None else None,
        "run_log_dir": str(run_dir) if run_dir is not None else None,
        "evidence_artifacts": history_evidence_artifacts(run_dir, prompt_file),
        "files_changed": automation_result.get("changed_files", []),
        "commands_run": [step.get("command") for step in automation_result.get("steps", []) if step.get("command")],
        "results": [step["outcome"] for step in automation_result.get("steps", [])],
        "acceptance_met": operator_diagnostics["acceptance_met"],
        "acceptance_unmet": operator_diagnostics["acceptance_unmet"],
        "blocker_opened": None,
        "notes": [automation_result["summary"]],
        "operator_diagnostics": operator_diagnostics,
        "unproven_runtime_gaps": automation_result.get("unproven_runtime_gaps", []),
        "failure_taxonomy": automation_result.get("failure_taxonomy"),
        "eval_result": automation_result.get("eval_result"),
    }
    write_data(path, payload)
    return path


def open_blocker(task: dict[str, Any], summary: str, evidence: list[str]) -> Path:
    path = BLOCKERS / f"BLK-{task['id']}.yml"
    payload = {
        "id": f"BLK-{task['id']}",
        "title": f"Task {task['id']} blocked during automated execution",
        "severity": "high",
        "opened_at": now_iso(),
        "related_tasks": [task["id"]],
        "status": "open",
        "symptoms": [summary],
        "diagnosis": summary,
        "evidence": evidence,
        "next_actions": ["Inspect automation_result.json and narrow the next bounded refinement."],
        "human_needed": True,
    }
    write_data(path, payload)
    return path


def validate_active_task_context(
    active: dict[str, Any],
    status: dict[str, Any],
    task: dict[str, Any] | None,
    *,
    resume: bool,
) -> tuple[str, str, str | None] | None:
    if not active.get("task_id"):
        return ("NO_ACTIVE_TASK", "No active task is currently loaded.", "Restore or select a task packet before rerunning automation.")
    if status.get("active_task_id") not in {None, active.get("task_id")}:
        return ("INVALID_ACTIVE_TASK_STATE", "status.yml active_task_id does not match active_task.yml.", "Repair state files before rerunning automation.")
    if status.get("active_task_id") == active.get("task_id") and status.get("state") != active.get("state"):
        return ("INVALID_ACTIVE_TASK_STATE", "active_task.yml and status.yml disagree on the current run state.", "Repair state files before rerunning automation.")
    if task is None:
        return ("INVALID_ACTIVE_TASK_STATE", f"Active task {active.get('task_id')} is missing from backlog.", "Repair backlog/active_task alignment before rerunning automation.")
    if not active.get("run_log_dir"):
        return ("INVALID_ACTIVE_TASK_STATE", "Active task is missing run_log_dir.", "Restore the active task from its existing run log before rerunning automation.")
    if not active.get("prompt_file"):
        return ("MISSING_PACKET", "Active task is missing prompt_file.", "Restore or rerender the packet before rerunning automation.")
    prompt_file = Path(active["prompt_file"]).expanduser().resolve()
    if not prompt_file.exists():
        return ("MISSING_PACKET", f"Prompt file does not exist: {prompt_file}", "Restore or rerender the packet before rerunning automation.")
    current_run_dir = Path(active["run_log_dir"]).expanduser().resolve()
    if (current_run_dir / RESULT_FILE).exists() and active.get("state") not in TERMINAL_RUN_STATES:
        return ("INVALID_ACTIVE_TASK_STATE", "automation_result.json exists but the recorded run state is not terminal.", "Repair or reset the active task state before rerunning automation.")
    if resume and active.get("state") != "implementing":
        return ("INVALID_ACTIVE_TASK_STATE", f"Cannot resume from active state '{active.get('state')}'.", "Run python3 scripts/automate_task_loop.py directly, or restore the paused task state first.")
    if resume and not active.get("handed_to_codex_at"):
        return ("STALE_IMPLEMENTING_STATE", "Active task is implementing but has no recorded handoff time.", "Re-run python3 scripts/automate_task_loop.py to record a fresh pause/handoff before using --resume.")
    if status.get("state") in TERMINAL_RUN_STATES and status.get("active_task_id") is None and active.get("task_id") is not None:
        return ("INVALID_ACTIVE_TASK_STATE", "Global status is blocked but no active task is attached.", "Restore the intended active task before rerunning automation.")
    return None


def is_retry_continuation(active: dict[str, Any], status: dict[str, Any], *, resume: bool) -> bool:
    return (
        not resume
        and active.get("state") == "blocked"
        and status.get("state") == "blocked"
        and status.get("last_result") == "refined"
        and status.get("active_task_id") == active.get("task_id")
    )


def iter_prior_run_dirs(run_dir: Path | None, active: dict[str, Any] | None = None) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()

    def add_candidate(value: Any) -> None:
        if not value:
            return
        resolved = Path(str(value)).expanduser().resolve()
        resolved_key = str(resolved)
        if resolved_key in seen:
            return
        seen.add(resolved_key)
        candidates.append(resolved)

    add_candidate(run_dir)
    if active is not None:
        add_candidate(active.get("previous_run_log_dir"))
        for entry in active.get("prior_run_log_dirs", []):
            add_candidate(entry)
    return candidates


def load_prior_automation_result(run_dir: Path | None, active: dict[str, Any] | None = None) -> dict[str, Any] | None:
    for candidate in iter_prior_run_dirs(run_dir, active):
        path = candidate / RESULT_FILE
        if path.exists():
            return load_data(path)
    return None


def prior_result_supports_vm_retry(run_dir: Path | None, active: dict[str, Any] | None = None) -> dict[str, Any] | None:
    for candidate in iter_prior_run_dirs(run_dir, active):
        prior = load_prior_automation_result(candidate)
        if prior:
            steps = {step.get("name"): step for step in prior.get("steps", [])}
            if (
                steps.get("vm_validation", {}).get("outcome") == "refined"
                and prior.get("changed_files")
                and (
                    (
                        steps.get("local_validation", {}).get("outcome") == "passed"
                        and steps.get("git", {}).get("outcome") == "passed"
                    )
                    or steps.get("retry_check", {}).get("outcome") == "passed"
                )
            ):
                return prior

        local_validation_path = candidate / "local_validation.json"
        git_path = candidate / "git.json"
        vm_validation_path = candidate / "vm_validation.json"
        if not (local_validation_path.exists() and git_path.exists() and vm_validation_path.exists()):
            continue

        local_validation = load_data(local_validation_path)
        git_result = load_data(git_path)
        vm_validation = load_data(vm_validation_path)
        if not local_validation.get("passed"):
            continue
        if not (
            git_result.get("add", {}).get("passed")
            and git_result.get("commit", {}).get("passed")
            and git_result.get("push", {}).get("passed")
        ):
            continue
        if vm_validation.get("passed") is not False:
            continue

        changed_files: list[str] = []
        for result in local_validation.get("results", []):
            stdout = str(result.get("stdout", ""))
            if "== git status --short ==" not in stdout:
                continue
            capture = False
            for line in stdout.splitlines():
                if line.strip() == "== git status --short ==":
                    capture = True
                    continue
                if capture and line.startswith("== "):
                    break
                if not capture:
                    continue
                if not line.strip():
                    continue
                changed_files.append(line[3:] if len(line) > 3 else line.strip())
            if changed_files:
                break
        if not changed_files:
            previous = load_prior_automation_result(candidate, active)
            if previous and previous.get("changed_files"):
                changed_files = list(previous.get("changed_files", []))
        if not changed_files:
            continue

        return {
            "task_id": None,
            "classification": "refined",
            "summary": "VM validation failed after local validation and git push succeeded.",
            "steps": [
                {"name": "local_validation", "outcome": "passed"},
                {"name": "git", "outcome": "passed"},
                {"name": "vm_validation", "outcome": "refined"},
            ],
            "changed_files": changed_files,
        }
    return None


def prior_result_supports_ux_evidence_retry(run_dir: Path | None, active: dict[str, Any] | None = None) -> dict[str, Any] | None:
    for candidate in iter_prior_run_dirs(run_dir, active):
        prior = load_prior_automation_result(candidate)
        if not prior:
            continue
        if prior.get("summary") != "UX conformance evidence is incomplete for this product-facing UX task.":
            continue
        steps = {step.get("name"): step for step in prior.get("steps", [])}
        if steps.get("executor", {}).get("outcome") != "passed":
            continue
        if steps.get("git", {}).get("outcome") != "passed":
            continue
        if prior.get("changed_files"):
            return prior
    return None


def prior_result_supports_executor_retry(run_dir: Path | None) -> bool:
    if run_dir is None:
        return False
    executor_path = run_dir / "executor.json"
    if not executor_path.exists():
        return False
    return is_retryable_executor_failure(load_data(executor_path))


def classify_and_update_state(
    classification: str,
    summary: str,
    task: dict[str, Any],
    backlog: dict[str, Any],
    active: dict[str, Any],
    status: dict[str, Any],
    automation_result: dict[str, Any],
    *,
    terminal_state: str | None = None,
) -> None:
    status.setdefault("stats", {})
    if classification != "accepted":
        taxonomy = detect_failure_taxonomy(summary, automation_result)
        automation_result["failure_taxonomy"] = taxonomy
        if classification == "refined" and recent_failure_loop_count(task["id"], taxonomy["failure_class"]) >= 2:
            classification = "blocked"
            summary = f"{summary} Retry loop detected for failure class {taxonomy['failure_class']}; blocking for replan."
            automation_result["classification"] = "blocked"
            automation_result["summary"] = summary
            automation_result.setdefault("steps", []).append(
                {
                    "name": "recovery_controller",
                    "outcome": "blocked",
                    "detail": "Repeated refined failures of the same class triggered loop protection.",
                }
            )
    else:
        automation_result["failure_taxonomy"] = None
    history_path = record_history(task, active, automation_result)
    generate_backlog_proposals(ROOT, dry_run=False)

    if classification == "interrupted":
        append_memory(f"{task['id']} interrupted by operator. History: {history_path.name}")
        restore_rerunnable_after_interruption(
            task,
            active,
            status,
            run_log_dir=Path(active["run_log_dir"]).expanduser().resolve() if active.get("run_log_dir") else None,
            summary=summary,
        )
        return

    if classification == "accepted":
        task["status"] = "accepted"
        task.setdefault("notes", []).append(summary)
        status["stats"]["completed_tasks"] = int(status["stats"].get("completed_tasks", 0)) + 1
        append_memory(f"{task['id']} accepted by automated loop. History: {history_path.name}")
        active["task_id"] = None
        active["title"] = None
        sync_run_state(
            active,
            status,
            terminal_state or "completed",
            task_id=None,
            title=None,
            run_log_dir=Path(active["run_log_dir"]).expanduser().resolve() if active.get("run_log_dir") else None,
            last_result="accepted",
        )
        return

    if classification == "refined":
        task["retries_used"] = int(task.get("retries_used", 0)) + 1
        task["status"] = "retry_ready"
        task.setdefault("notes", []).append(summary)
        status["stats"]["retry_ready_tasks"] = int(status["stats"].get("retry_ready_tasks", 0)) + 1
        append_memory(f"{task['id']} refined by automated loop. History: {history_path.name}")
        sync_run_state(
            active,
            status,
            terminal_state or "blocked",
            task_id=active.get("task_id"),
            title=active.get("title"),
            run_log_dir=Path(active["run_log_dir"]).expanduser().resolve() if active.get("run_log_dir") else None,
            failure_summary=summary,
            last_result="refined",
        )
        return

    task["status"] = "blocked"
    task.setdefault("notes", []).append(summary)
    blocker_path = open_blocker(task, summary, automation_result.get("blocker_evidence", []))
    status["stats"]["blocked_tasks"] = int(status["stats"].get("blocked_tasks", 0)) + 1
    append_memory(f"{task['id']} blocked by automated loop via {blocker_path.name}. History: {history_path.name}")
    sync_run_state(
        active,
        status,
        terminal_state or "blocked",
        task_id=active.get("task_id"),
        title=active.get("title"),
        run_log_dir=Path(active["run_log_dir"]).expanduser().resolve() if active.get("run_log_dir") else None,
        failure_summary=summary,
        last_result="blocked",
    )


def restore_rerunnable_after_interruption(
    task: dict[str, Any],
    active: dict[str, Any],
    status: dict[str, Any],
    *,
    run_log_dir: Path | None,
    summary: str,
) -> None:
    current_status = str(task.get("status") or "")
    if current_status in {"selected", "packet_rendered", "implementing", "verifying", "ready"}:
        task["status"] = "ready"
    elif current_status == "blocked":
        return
    previous_run_log_dir = str(run_log_dir) if run_log_dir else active.get("run_log_dir")
    active.clear()
    active.update(reset_active())
    active["previous_run_log_dir"] = previous_run_log_dir
    status["state"] = "idle"
    status["active_task_id"] = None
    status["last_task_id"] = task.get("id")
    status["last_result"] = "interrupted"
    status["last_run_at"] = now_iso()
    task.setdefault("notes", []).append(summary)
    write_data(ACTIVE, active)
    write_data(STATUS, status)


def build_context(
    active: dict[str, Any],
    task: dict[str, Any],
    product_repo: Path,
    builder_root_path: Path,
    target_repo: Path,
    target_kind: str,
) -> dict[str, str]:
    return {
        "task_id": task["id"],
        "title": task["title"],
        "prompt_file": active.get("prompt_file") or "",
        "run_log_dir": active.get("run_log_dir") or "",
        "product_repo": str(product_repo),
        "builder_root": str(builder_root_path),
        "target_repo": str(target_repo),
        "target_kind": target_kind,
    }


def is_legacy_failed_state(active: dict[str, Any], status: dict[str, Any]) -> bool:
    return active.get("state") == "failed" or status.get("state") in {"packet_rendered", "retry_ready"}


def load_run_result_for(active: dict[str, Any]) -> dict[str, Any] | None:
    run_log_dir = active.get("run_log_dir")
    if not run_log_dir:
        return None
    result_path = Path(str(run_log_dir)).expanduser().resolve() / RESULT_FILE
    if not result_path.exists():
        return None
    return load_data(result_path)


def resolve_execution_candidate(
    backlog: dict[str, Any],
    active: dict[str, Any],
    status: dict[str, Any],
    *,
    resume: bool,
) -> dict[str, Any]:
    diagnostics = compute_backlog_diagnostics(backlog) if not backlog.get("errors") else {
        "total_tasks": len(backlog.get("tasks", [])),
        "counts_by_status": {},
        "ready_task_ids": [],
        "pending_task_ids": [],
        "retry_ready_task_ids": [],
        "blocked_task_ids": [],
        "open_blocked_task_ids": [],
        "ordered_ready_queue": [],
        "next_selected_task_id": None,
        "selector_filtered_everything": False,
        "roadmap_affected": False,
        "skipped_reasons": {},
    }
    active_task_id = active.get("task_id")
    active_reasons: list[str] = []
    active_candidate_id: str | None = None
    if active_task_id:
        task = next((item for item in backlog.get("tasks", []) if item.get("id") == active_task_id), None)
        if task is None:
            active_reasons.append("missing_from_backlog")
        else:
            task_status = str(task.get("status"))
            active_state = str(active.get("state"))
            skipped = diagnostics.get("skipped_reasons", {}).get(active_task_id, [])
            if task_status in {"blocked", "accepted", "done"}:
                active_reasons.append(f"backlog_status:{task_status}")
            elif "open_blocker" in skipped:
                active_reasons.append("open_blocker")
            elif resume:
                if active_state != "implementing":
                    active_reasons.append(f"resume_requires_implementing:{active_state}")
                else:
                    active_candidate_id = active_task_id
            elif active_state == "blocked":
                if task_status in {"selected", "packet_rendered", "implementing", "verifying", "ready", "retry_ready"} and status.get("last_result") == "refined":
                    active_candidate_id = active_task_id
                else:
                    active_reasons.append(f"blocked_state_not_retry_ready:{task_status}")
            elif active_state in {"selected", "task_selected", "packet_rendered", "implementing", "verifying"}:
                active_candidate_id = active_task_id
            else:
                active_reasons.append(f"non_runnable_active_state:{active_state}")

    effective_queue = list(diagnostics.get("ordered_ready_queue", []))
    if active_candidate_id and active_candidate_id not in effective_queue:
        effective_queue.insert(0, active_candidate_id)
    return {
        "diagnostics": diagnostics,
        "active_candidate_id": active_candidate_id,
        "active_reasons": active_reasons,
        "effective_ready_queue": effective_queue,
        "next_selected_task_id": active_candidate_id or diagnostics.get("next_selected_task_id"),
    }


def is_auth_preflight_only_block(active: dict[str, Any], status: dict[str, Any], run_result: dict[str, Any] | None) -> bool:
    if not run_result:
        return False
    steps = list(run_result.get("steps", []))
    return (
        run_result.get("classification") == "blocked"
        and run_result.get("summary") == "Authentication preflight indicates repeated or interactive prompts are likely."
        and len(steps) == 1
        and steps[0].get("name") == "auth_preflight"
        and not active.get("handed_to_codex_at")
        and status.get("last_result") == "blocked"
    )


def is_executor_interrupted_only_block(active: dict[str, Any], status: dict[str, Any], run_result: dict[str, Any] | None) -> bool:
    if not run_result:
        return False
    steps = list(run_result.get("steps", []))
    return (
        run_result.get("classification") in {"blocked", "interrupted"}
        and run_result.get("summary") == "executor_interrupted"
        and len(steps) == 1
        and steps[0].get("name") == "executor"
        and steps[0].get("outcome") in {"blocked", "interrupted"}
        and status.get("last_result") in {"blocked", "interrupted"}
    )


def is_stale_dry_run_state(active: dict[str, Any], status: dict[str, Any], run_result: dict[str, Any] | None) -> bool:
    return (
        bool(run_result)
        and run_result.get("classification") == "dry_run"
        and active.get("state") == "task_selected"
        and status.get("state") == "task_selected"
    )


def resolve_blocker_for_task(task_id: str, *, resolution: str) -> Path | None:
    blocker_path = BLOCKERS / f"BLK-{task_id}.yml"
    if not blocker_path.exists():
        return None
    blocker = load_data(blocker_path)
    blocker["status"] = "resolved"
    blocker["resolved_at"] = now_iso()
    blocker["resolution"] = resolution
    write_data(blocker_path, blocker)
    return blocker_path


def update_blocker_for_task(
    task_id: str,
    *,
    summary: str,
    evidence: list[str],
    next_actions: list[str],
) -> Path:
    blocker_path = BLOCKERS / f"BLK-{task_id}.yml"
    blocker = load_data(blocker_path) if blocker_path.exists() else {
        "id": f"BLK-{task_id}",
        "title": f"Task {task_id} blocked during automated execution",
        "severity": "high",
        "opened_at": now_iso(),
        "related_tasks": [task_id],
    }
    blocker["status"] = "open"
    blocker["symptoms"] = [summary]
    blocker["diagnosis"] = summary
    blocker["evidence"] = evidence
    blocker["next_actions"] = next_actions
    blocker["human_needed"] = True
    write_data(blocker_path, blocker)
    return blocker_path


def latest_terminal_run_dir(active: dict[str, Any]) -> Path | None:
    candidates: list[Path] = []
    for key in ("run_log_dir", "previous_run_log_dir"):
        value = active.get(key)
        if value:
            path = Path(str(value)).expanduser().resolve()
            if (path / RESULT_FILE).exists():
                candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda item: item.name)
    return candidates[-1]


def blocked_dirty_repo_truth(task: dict[str, Any], active: dict[str, Any]) -> tuple[str, Path, list[str]]:
    target_kind = "builder" if task_targets_builder_repo(task, active) else "product"
    target_repo = builder_path_from_config("builder_root") if target_kind == "builder" else product_repo_path()
    files = git_status_porcelain(target_repo, ignored_prefixes=ignored_git_paths_for_target(target_kind)).get("files", [])
    return target_kind, target_repo, files


def stale_allowlist_block_repaired(task: dict[str, Any], active: dict[str, Any]) -> bool:
    summary = str(active.get("failure_summary") or "").lower()
    if "allowlist" not in summary:
        return False
    active_allowlist = [str(item).strip() for item in active.get("allowlist", []) if str(item).strip()]
    task_allowlist = [str(item).strip() for item in task.get("allowlist", []) if str(item).strip()]
    if active_allowlist:
        return False
    return bool(task_allowlist)


def repair_legacy_state() -> int:
    active = load_data(ACTIVE)
    status = load_data(STATUS)
    backlog = load_data(BACKLOG)
    repaired: list[str] = []

    status["state_legend"] = dict(CANONICAL_STATE_LEGEND)
    repaired.append("status.state_legend -> canonical")

    if active.get("state") == "failed":
        active["state"] = "blocked"
        repaired.append("active_task.state failed -> blocked")

    run_result = load_run_result_for(active)
    task_id = active.get("task_id")
    task = None
    if task_id:
        for item in backlog.get("tasks", []):
            if item.get("id") == task_id:
                task = item
                break
    backlog_diagnostics = compute_backlog_diagnostics({"tasks": backlog.get("tasks", [])})

    if is_auth_preflight_only_block(active, status, run_result):
        repaired_active = reset_active()
        repaired_active["previous_run_log_dir"] = active.get("run_log_dir")
        write_data(ACTIVE, repaired_active)

        status["state"] = "idle"
        status["active_task_id"] = None
        status["last_task_id"] = task_id
        status["last_result"] = "blocked"
        status["last_run_at"] = now_iso()
        write_data(STATUS, status)
        clear_run_ledger_after_repair()
        repaired.append("preflight-only blocked run -> idle fresh rerun state")

        if task is not None and task.get("status") == "blocked":
            task["status"] = "ready"
            task.setdefault("notes", []).append(
                "Repaired from auth-preflight-only blocked attempt; task restored to ready for a truthful fresh rerun."
            )
            write_data(BACKLOG, backlog)
            repaired.append(f"backlog task {task_id} blocked -> ready")

        resolved = resolve_blocker_for_task(
            str(task_id),
            resolution="Resolved by state repair: auth preflight failed before implementation began; task restored for fresh rerun.",
        )
        if resolved is not None:
            repaired.append(f"{resolved.name} resolved")

        print("STATE_REPAIRED")
        for line in repaired:
            print(f"- {line}")
        return 0

    if task is not None and is_stale_dry_run_state(active, status, run_result):
        if task.get("status") in {"selected", "packet_rendered", "ready"}:
            task["status"] = "ready"
            task.setdefault("notes", []).append(
                "Repaired from stale dry-run state; no execution occurred and the task remains runnable."
            )
            write_data(BACKLOG, backlog)
            repaired.append(f"backlog task {task_id} normalized -> ready")
        repaired_active = reset_active()
        repaired_active["previous_run_log_dir"] = active.get("run_log_dir")
        write_data(ACTIVE, repaired_active)
        status["state"] = "idle"
        status["active_task_id"] = None
        status["last_task_id"] = task_id
        status["last_result"] = status.get("last_result")
        status["last_run_at"] = now_iso()
        write_data(STATUS, status)
        clear_run_ledger_after_repair()
        repaired.append("stale dry-run active state -> idle")
        print("STATE_REPAIRED")
        for line in repaired:
            print(f"- {line}")
        return 0

    if (
        task is not None
        and task.get("status") in {"ready", "retry_ready"}
        and active.get("state") == "blocked"
        and str(active.get("failure_summary") or run_result.get("summary") or "")
        == "Retry-ready task has no product repo changes to continue from."
    ):
        task["status"] = "ready"
        repaired_active = reset_active()
        repaired_active["previous_run_log_dir"] = active.get("run_log_dir")
        write_data(ACTIVE, repaired_active)
        status["state"] = "idle"
        status["active_task_id"] = None
        status["last_task_id"] = task_id
        status["last_result"] = "refined"
        status["last_run_at"] = now_iso()
        write_data(STATUS, status)
        clear_run_ledger_after_repair()
        task.setdefault("notes", []).append(
            "Repaired from stale retry-without-changes state; no in-flight repo edits remain, so the task should rerun fresh from ready."
        )
        write_data(BACKLOG, backlog)
        repaired.append(f"stale retry-ready continuation for {task_id} cleared -> fresh ready rerun")
        print("STATE_REPAIRED")
        for line in repaired:
            print(f"- {line}")
        return 0

    if task is not None and task.get("status") == "blocked":
        terminal_run_dir = latest_terminal_run_dir(active) or (Path(str(active["run_log_dir"])).expanduser().resolve() if active.get("run_log_dir") else None)
        if prior_result_supports_executor_retry(terminal_run_dir):
            task["status"] = "ready"
            task.setdefault("notes", []).append(
                "Repaired from transient executor transport failure; task restored to ready for a fresh rerun."
            )
            write_data(BACKLOG, backlog)
            repaired_active = reset_active()
            repaired_active["previous_run_log_dir"] = str(terminal_run_dir) if terminal_run_dir is not None else active.get("run_log_dir")
            write_data(ACTIVE, repaired_active)
            status["state"] = "idle"
            status["active_task_id"] = None
            status["last_task_id"] = task_id
            status["last_result"] = "interrupted"
            status["last_run_at"] = now_iso()
            write_data(STATUS, status)
            clear_run_ledger_after_repair()
            repaired.append(f"backlog task {task_id} blocked -> ready")
            resolved = resolve_blocker_for_task(
                str(task_id),
                resolution="Resolved by state repair: prior executor failure matched a transient Codex transport error and the task is ready for a fresh rerun.",
            )
            if resolved is not None:
                repaired.append(f"{resolved.name} resolved")
            print("STATE_REPAIRED")
            for line in repaired:
                print(f"- {line}")
            return 0

        if stale_allowlist_block_repaired(task, active):
            task["status"] = "ready"
            task.setdefault("notes", []).append(
                "Repaired from stale synthesized allowlist blocker; canonical builder repo bounds are now present and the task is runnable again."
            )
            write_data(BACKLOG, backlog)
            repaired_active = reset_active()
            repaired_active["previous_run_log_dir"] = str(terminal_run_dir) if terminal_run_dir is not None else active.get("run_log_dir")
            write_data(ACTIVE, repaired_active)
            status["state"] = "idle"
            status["active_task_id"] = None
            status["last_task_id"] = task_id
            status["last_result"] = "blocked"
            status["last_run_at"] = now_iso()
            write_data(STATUS, status)
            clear_run_ledger_after_repair()
            repaired.append(f"backlog task {task_id} blocked -> ready")
            resolved = resolve_blocker_for_task(
                str(task_id),
                resolution="Resolved by state repair: prior allowlist blocker came from a stale packet without canonical builder repo bounds.",
            )
            if resolved is not None:
                repaired.append(f"{resolved.name} resolved")
            print("STATE_REPAIRED")
            for line in repaired:
                print(f"- {line}")
            return 0

    if task is not None and task.get("status") == "blocked" and is_executor_interrupted_only_block(active, status, run_result):
        target_kind, target_repo, dirty_files = blocked_dirty_repo_truth(task, active)
        if dirty_files:
            summary = f"{target_kind.title()} repo is dirty before automated execution; refusing to continue."
            blocker_path = update_blocker_for_task(
                str(task_id),
                summary=summary,
                evidence=dirty_files,
                next_actions=[
                    f"cd {target_repo}",
                    "git status --short",
                    "# commit, stash, or remove the in-progress changes before rerunning the builder",
                ],
            )
            terminal_run_dir = latest_terminal_run_dir(active) or (Path(str(active["run_log_dir"])).expanduser().resolve() if active.get("run_log_dir") else None)
            if terminal_run_dir and active.get("run_log_dir") and str(terminal_run_dir) != str(Path(str(active["run_log_dir"])).expanduser().resolve()):
                active["previous_run_log_dir"] = active.get("run_log_dir")
            next_runnable = backlog_diagnostics.get("next_selected_task_id")
            if next_runnable and str(next_runnable) != str(task_id):
                repaired_active = reset_active()
                repaired_active["previous_run_log_dir"] = str(terminal_run_dir) if terminal_run_dir is not None else active.get("run_log_dir")
                write_data(ACTIVE, repaired_active)
                status["state"] = "idle"
                status["active_task_id"] = None
                status["last_task_id"] = task_id
                status["last_result"] = "blocked"
                status["last_run_at"] = now_iso()
                write_data(STATUS, status)
                clear_run_ledger_after_repair()
                write_data(BACKLOG, backlog)
                repaired.append(f"{task_id} remains blocked: current dirty files still exist in {target_repo}")
                repaired.append(f"{blocker_path.name} evidence refreshed")
                repaired.append(f"cleared stale blocked active task so runnable task {next_runnable} can proceed")
                print("STATE_REPAIRED")
                for line in repaired:
                    print(f"- {line}")
                return 0
            sync_run_state(
                active,
                status,
                "blocked",
                task_id=active.get("task_id"),
                title=active.get("title"),
                run_log_dir=terminal_run_dir,
                failure_summary=summary,
                last_result="blocked",
            )
            write_data(BACKLOG, backlog)
            repaired.append(f"{task_id} remains blocked: current dirty files still exist in {target_repo}")
            repaired.append(f"{blocker_path.name} evidence refreshed")
            print("STATE_REPAIRED")
            for line in repaired:
                print(f"- {line}")
            return 0

        task["status"] = "ready"
        task.setdefault("notes", []).append(
            "Repaired from stale executor interruption; no underlying blocker remains and the task is runnable again."
        )
        write_data(BACKLOG, backlog)
        repaired_active = reset_active()
        repaired_active["previous_run_log_dir"] = active.get("run_log_dir")
        write_data(ACTIVE, repaired_active)
        status["state"] = "idle"
        status["active_task_id"] = None
        status["last_task_id"] = task_id
        status["last_result"] = "interrupted"
        status["last_run_at"] = now_iso()
        write_data(STATUS, status)
        clear_run_ledger_after_repair()
        repaired.append(f"backlog task {task_id} blocked -> ready")
        resolved = resolve_blocker_for_task(
            str(task_id),
            resolution="Resolved by state repair: prior executor interruption left no real blocker and the task is runnable again.",
        )
        if resolved is not None:
            repaired.append(f"{resolved.name} resolved")
        print("STATE_REPAIRED")
        for line in repaired:
            print(f"- {line}")
        return 0

    if task is not None and task.get("status") == "blocked":
        target_kind, target_repo, dirty_files = blocked_dirty_repo_truth(task, active)
        summary = f"{target_kind.title()} repo is dirty before automated execution; refusing to continue."
        if dirty_files:
            blocker_path = update_blocker_for_task(
                str(task_id),
                summary=summary,
                evidence=dirty_files,
                next_actions=[
                    f"cd {target_repo}",
                    "git status --short",
                    "# commit, stash, or remove the in-progress changes before rerunning the builder",
                ],
            )
            terminal_run_dir = latest_terminal_run_dir(active) or (Path(str(active["run_log_dir"])).expanduser().resolve() if active.get("run_log_dir") else None)
            if terminal_run_dir and active.get("run_log_dir") and str(terminal_run_dir) != str(Path(str(active["run_log_dir"])).expanduser().resolve()):
                active["previous_run_log_dir"] = active.get("run_log_dir")
            next_runnable = backlog_diagnostics.get("next_selected_task_id")
            if next_runnable and str(next_runnable) != str(task_id):
                repaired_active = reset_active()
                repaired_active["previous_run_log_dir"] = str(terminal_run_dir) if terminal_run_dir is not None else active.get("run_log_dir")
                write_data(ACTIVE, repaired_active)
                status["state"] = "idle"
                status["active_task_id"] = None
                status["last_task_id"] = task_id
                status["last_result"] = "blocked"
                status["last_run_at"] = now_iso()
                write_data(STATUS, status)
                clear_run_ledger_after_repair()
                write_data(BACKLOG, backlog)
                repaired.append(f"{task_id} remains blocked: current dirty files still exist in {target_repo}")
                repaired.append(f"{blocker_path.name} evidence refreshed")
                repaired.append(f"cleared stale blocked active task so runnable task {next_runnable} can proceed")
                print("STATE_REPAIRED")
                for line in repaired:
                    print(f"- {line}")
                return 0
            sync_run_state(
                active,
                status,
                "blocked",
                task_id=active.get("task_id"),
                title=active.get("title"),
                run_log_dir=terminal_run_dir,
                failure_summary=summary,
                last_result="blocked",
            )
            write_data(BACKLOG, backlog)
            repaired.append(f"{task_id} remains blocked: current dirty files still exist in {target_repo}")
            repaired.append(f"{blocker_path.name} evidence refreshed")
            print("STATE_REPAIRED")
            for line in repaired:
                print(f"- {line}")
            return 0

        task["status"] = "ready"
        task.setdefault("notes", []).append(
            "Repaired from stale dirty-repo blocker; repo is now clean and the task is runnable again."
        )
        write_data(BACKLOG, backlog)
        repaired_active = reset_active()
        repaired_active["previous_run_log_dir"] = active.get("run_log_dir")
        write_data(ACTIVE, repaired_active)
        status["state"] = "idle"
        status["active_task_id"] = None
        status["last_task_id"] = task_id
        status["last_result"] = "blocked"
        status["last_run_at"] = now_iso()
        write_data(STATUS, status)
        clear_run_ledger_after_repair()
        repaired.append(f"backlog task {task_id} blocked -> ready")
        resolved = resolve_blocker_for_task(
            str(task_id),
            resolution="Resolved by state repair: prior dirty-repo blocker is no longer current and the task is runnable again.",
        )
        if resolved is not None:
            repaired.append(f"{resolved.name} resolved")
        print("STATE_REPAIRED")
        for line in repaired:
            print(f"- {line}")
        return 0

    if task is not None and task.get("status") in {"pending", "accepted", "ready"} and active.get("task_id"):
        repaired_active = reset_active()
        repaired_active["previous_run_log_dir"] = active.get("run_log_dir")
        write_data(ACTIVE, repaired_active)
        status["state"] = "idle"
        status["active_task_id"] = None
        status["last_task_id"] = task_id
        status["last_result"] = status.get("last_result")
        status["last_run_at"] = now_iso()
        write_data(STATUS, status)
        clear_run_ledger_after_repair()
        repaired.append(
            f"stale active task {task_id} cleared because backlog truth is {task.get('status')}"
        )
        if task.get("status") == "ready":
            resolved = resolve_blocker_for_task(
                str(task_id),
                resolution="Resolved by state repair: canonical backlog truth is ready and the prior blocked run no longer represents the current task state.",
            )
            if resolved is not None:
                repaired.append(f"{resolved.name} resolved")
        print("STATE_REPAIRED")
        for line in repaired:
            print(f"- {line}")
        return 0

    sync_run_state(
        active,
        status,
        "blocked" if status.get("last_result") in {"blocked", "refined"} or is_legacy_failed_state(active, status) else "idle",
        task_id=active.get("task_id"),
        title=active.get("title"),
        run_log_dir=Path(active["run_log_dir"]).expanduser().resolve() if active.get("run_log_dir") else None,
        failure_summary=active.get("failure_summary"),
        last_result=status.get("last_result"),
    )
    repaired.append(f"state normalized -> {load_data(STATUS).get('state')}")
    print("STATE_REPAIRED")
    for line in repaired:
        print(f"- {line}")
    return 0


def inspect_backlog_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    backlog = load_validated_backlog()
    active = load_data(ACTIVE)
    status = load_data(STATUS)
    execution = resolve_execution_candidate(backlog, active, status, resume=False)
    diagnostics = dict(execution["diagnostics"])
    diagnostics["ordered_ready_queue"] = execution["effective_ready_queue"]
    diagnostics["next_selected_task_id"] = execution["next_selected_task_id"]
    diagnostics["active_task_id"] = active.get("task_id")
    diagnostics["active_task_runnable"] = execution["active_candidate_id"] is not None
    diagnostics["active_task_skip_reasons"] = execution["active_reasons"]
    return backlog, diagnostics


def print_backlog_inspection(backlog: dict[str, Any], diagnostics: dict[str, Any]) -> int:
    if backlog.get("errors"):
        print("BACKLOG_INVALID")
        for error in backlog["errors"]:
            print(f"- {error.get('code')}: {error.get('detail')}")
        return 1
    print(f"total_tasks: {diagnostics['total_tasks']}")
    print("counts_by_status: " + json.dumps(diagnostics["counts_by_status"], sort_keys=True))
    print("ready_queue: " + json.dumps(diagnostics["ordered_ready_queue"]))
    print("next_selected_task: " + json.dumps(diagnostics["next_selected_task_id"]))
    print("ready_task_ids: " + json.dumps(diagnostics["ready_task_ids"]))
    print("pending_task_ids: " + json.dumps(diagnostics["pending_task_ids"]))
    print("retry_ready_task_ids: " + json.dumps(diagnostics["retry_ready_task_ids"]))
    print("blocked_task_ids: " + json.dumps(diagnostics["blocked_task_ids"]))
    print("product_facing_ux_task_ids: " + json.dumps(diagnostics.get("product_facing_ux_task_ids", [])))
    if diagnostics.get("product_facing_ux_missing_requirements"):
        print("product_facing_ux_missing_requirements: " + json.dumps(diagnostics["product_facing_ux_missing_requirements"], sort_keys=True))
    print("roadmap_affected: " + json.dumps(diagnostics["roadmap_affected"]))
    print("selector_filtered_everything: " + json.dumps(diagnostics["selector_filtered_everything"]))
    print("active_task_id: " + json.dumps(diagnostics.get("active_task_id")))
    print("active_task_runnable: " + json.dumps(diagnostics.get("active_task_runnable")))
    if diagnostics.get("active_task_skip_reasons"):
        print("active_task_skip_reasons: " + json.dumps(diagnostics["active_task_skip_reasons"]))
    if diagnostics.get("skipped_reasons"):
        print("skipped_reasons: " + json.dumps(diagnostics["skipped_reasons"], sort_keys=True))
    return 0


def effective_ssh_options(vm_config: dict[str, Any]) -> list[str]:
    options = list(vm_config.get("ssh_options", []))
    target = str(vm_config.get("ssh_target") or "vm")
    control_path = f"/tmp/jorb-builder-ssh-{target.replace('@', '_').replace(':', '_')}"
    default_pairs = [
        ("ControlMaster", "auto"),
        ("ControlPersist", "10m"),
        ("ControlPath", control_path),
    ]
    existing = {options[index + 1].split("=", 1)[0] for index, item in enumerate(options[:-1]) if item == "-o"}
    for key, value in default_pairs:
        if key not in existing:
            options.extend(["-o", f"{key}={value}"])
    return options


def noninteractive_vm_ssh_options(vm_config: dict[str, Any]) -> list[str]:
    options = effective_ssh_options(vm_config)
    existing = {options[index + 1].split("=", 1)[0] for index, item in enumerate(options[:-1]) if item == "-o"}
    default_pairs = [
        ("BatchMode", "yes"),
        ("StrictHostKeyChecking", "accept-new"),
    ]
    for key, value in default_pairs:
        if key not in existing:
            options.extend(["-o", f"{key}={value}"])
    return options


def git_auth_status(target_repo: Path) -> dict[str, Any]:
    remote = run_argv(["git", "remote", "get-url", "origin"], target_repo)
    if not remote.get("passed"):
        return {
            "status": "missing_remote",
            "interactive": True,
            "detail": remote.get("stderr") or "git remote origin is unavailable.",
            "remediation": ["git remote add origin git@github.com:<org>/<repo>.git"],
        }
    remote_url = remote.get("stdout", "").strip()
    if remote_url.startswith("git@") or remote_url.startswith("ssh://"):
        return {
            "status": "ssh",
            "interactive": False,
            "detail": f"origin uses SSH: {remote_url}",
            "remote_url": remote_url,
            "remediation": [],
        }
    if remote_url.startswith("http://") or remote_url.startswith("https://"):
        return {
            "status": "https_interactive_likely",
            "interactive": True,
            "detail": f"origin uses HTTPS: {remote_url}",
            "remote_url": remote_url,
            "remediation": [
                "git remote set-url origin git@github.com:<org>/<repo>.git",
                "ssh-add ~/.ssh/id_ed25519",
            ],
        }
    return {
        "status": "local_or_custom",
        "interactive": False,
        "detail": f"origin uses {remote_url}",
        "remote_url": remote_url,
        "remediation": [],
    }


def vm_ssh_auth_status(vm_config: dict[str, Any], cwd: Path) -> dict[str, Any]:
    target = vm_config.get("ssh_target")
    if not target:
        return {
            "status": "missing_ssh_target",
            "interactive": True,
            "detail": "vm.ssh_target is not configured.",
            "remediation": ["Set vm.ssh_target in config.yml"],
        }
    options = noninteractive_vm_ssh_options(vm_config)
    probe = ssh_command(str(target), options, "true", cwd)
    ssh_agent_loaded = bool(os.environ.get("SSH_AUTH_SOCK"))
    stderr = (probe.get("stderr") or "") + "\n" + (probe.get("stdout") or "")
    auth_failure_markers = ("Permission denied", "passphrase", "Host key verification failed", "Could not resolve hostname")
    interactive = False if probe.get("passed") else any(marker in stderr for marker in auth_failure_markers[:3])
    status = "batchmode_ready" if probe.get("passed") else ("interactive_auth_required" if interactive else "connectivity_unknown")
    remediation = []
    if interactive:
        remediation = [
            "ssh-add ~/.ssh/id_ed25519",
            f"ssh {target}",
            f"ssh-keyscan -H {str(target).split('@')[-1]} >> ~/.ssh/known_hosts",
        ]
    return {
        "status": status,
        "interactive": interactive,
        "detail": probe.get("stderr") or probe.get("stdout") or f"ssh batch probe to {target}",
        "ssh_agent_loaded": ssh_agent_loaded,
        "command": probe.get("command"),
        "remediation": remediation,
    }


def check_auth_status(config: dict[str, Any], *, target_kind: str, target_repo: Path, cwd: Path) -> dict[str, Any]:
    git_status = git_auth_status(target_repo)
    vm_status = {"status": "not_required", "interactive": False, "detail": "VM SSH not required for builder-only tasks.", "remediation": []}
    if target_kind == "product":
        vm_status = vm_ssh_auth_status(config.get("vm", {}), cwd)
    interactive = bool(git_status.get("interactive")) or bool(vm_status.get("interactive"))
    return {
        "git": git_status,
        "vm_ssh": vm_status,
        "interactive_run_likely": interactive,
    }


def print_auth_status(auth: dict[str, Any]) -> int:
    print("GitHub auth status: " + json.dumps(auth["git"], sort_keys=True))
    print("VM SSH status: " + json.dumps(auth["vm_ssh"], sort_keys=True))
    print("run_interactive: " + json.dumps(auth["interactive_run_likely"]))
    if auth["git"].get("remediation"):
        print("git_remediation:")
        for command in auth["git"]["remediation"]:
            print(f"- {command}")
    if auth["vm_ssh"].get("remediation"):
        print("vm_remediation:")
        for command in auth["vm_ssh"]["remediation"]:
            print(f"- {command}")
    return 1 if auth["interactive_run_likely"] else 0


def dispatch_standalone_mode(args: argparse.Namespace, config: dict[str, Any]) -> int | None:
    if args.repair_state:
        return repair_legacy_state()

    if args.inspect_backlog:
        backlog, diagnostics = inspect_backlog_payload()
        return print_backlog_inspection(backlog, diagnostics)

    if args.check_auth:
        product_repo = product_repo_path()
        auth = check_auth_status(config, target_kind="product", target_repo=product_repo, cwd=ROOT)
        return print_auth_status(auth)

    return None


def try_bootstrap_active_task() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], bool]:
    backlog = load_validated_backlog()
    active = load_data(ACTIVE)
    status = load_data(STATUS)
    if active.get("task_id"):
        return backlog, active, status, False

    if backlog.get("errors"):
        return backlog, active, status, False

    execution = resolve_execution_candidate(backlog, active, status, resume=False)
    if not execution.get("next_selected_task_id"):
        return backlog, active, status, False
    select_result = run_argv([sys.executable, str(SELECT_TASK)], ROOT)
    if "NO_READY_TASK" in select_result.get("stdout", "") or "SELECTOR_FILTERED_EVERYTHING" in select_result.get("stdout", ""):
        return backlog, active, status, False
    if not select_result.get("passed"):
        return backlog, active, status, False

    render_result = run_argv([sys.executable, str(RENDER_PACKET)], ROOT)
    if not render_result.get("passed"):
        return load_data(BACKLOG), load_data(ACTIVE), load_data(STATUS), False

    return load_validated_backlog(), load_data(ACTIVE), load_data(STATUS), True


def codex_exec_argv(
    executor_config: dict[str, Any],
    *,
    run_dir: Path,
) -> list[str]:
    cli = str(executor_config.get("codex_cli") or "codex")
    argv = [cli, "exec"]
    sandbox_mode = executor_config.get("sandbox")
    if sandbox_mode:
        argv.extend(["--sandbox", str(sandbox_mode)])
    if executor_config.get("full_auto", True):
        argv.append("--full-auto")
    output_path = run_dir / str(executor_config.get("last_message_file") or "codex_last_message.md")
    argv.extend(["-o", str(output_path), "-"])
    return argv


def attach_target_to_active(active: dict[str, Any], *, target_repo: Path, target_kind: str) -> None:
    active["target_repo"] = str(target_repo)
    active["target_kind"] = target_kind


def run_loop(args: argparse.Namespace, *, allow_follow_on: bool) -> int:
    config = load_config()
    standalone_result = dispatch_standalone_mode(args, config)
    if standalone_result is not None:
        return standalone_result

    backlog, active, status, auto_bootstrapped = try_bootstrap_active_task()
    prior_active_state = active.get("state")
    prior_status_state = status.get("state")
    prior_last_result = status.get("last_result")

    product_repo = product_repo_path()
    builder_repo = builder_path_from_config("builder_root")
    task = None
    if active.get("task_id"):
        try:
            task = find_task(backlog, active["task_id"])
        except KeyError:
            task = None
    if task is not None:
        active["verification_commands"] = effective_task_command_list(task.get("verification"), active.get("verification_commands"))
        active["vm_verification_commands"] = list(task.get("vm_verification", []))
        active["vm_bootstrap_commands"] = list(task.get("vm_bootstrap", []))
        active["vm_cleanup_commands"] = list(task.get("vm_cleanup", []))
    execution = resolve_execution_candidate(backlog, active, status, resume=args.resume)
    diagnostics = execution["diagnostics"]
    if active.get("task_id") and execution.get("active_candidate_id") is None and not backlog.get("errors"):
        if execution.get("next_selected_task_id"):
            print_result(
                "ACTIVE_TASK_MISSING_BUT_READY_TASKS_EXIST",
                "Persisted active task is not runnable under current backlog truth.",
                "Run python3 scripts/automate_task_loop.py --repair-state or clear the stale active task before rerunning automation.",
                extra=f"Next runnable task: {execution['next_selected_task_id']}",
            )
            return 1
        if diagnostics.get("selector_filtered_everything"):
            print_result(
                "SELECTOR_FILTERED_EVERYTHING",
                "No runnable task exists under current backlog truth, including the persisted active task.",
                "Inspect backlog blockers/dependencies or run python3 scripts/automate_task_loop.py --inspect-backlog for details.",
                extra=f"Active task skip reasons: {', '.join(execution.get('active_reasons', [])) or 'none'}",
            )
            return 1
        print_result(
            "NO_READY_TASKS_REMAIN",
            "No runnable task exists under current backlog truth.",
            "Inspect backlog.yml for the next task to mark ready, or run python3 scripts/automate_task_loop.py --inspect-backlog for details.",
        )
        return 1
    validation_error = validate_active_task_context(active, status, task, resume=args.resume)
    if validation_error:
        label, summary, next_action = validation_error
        if label == "NO_ACTIVE_TASK" and not auto_bootstrapped:
            if backlog.get("errors"):
                print("BACKLOG_INVALID")
                for error in backlog["errors"]:
                    print(f"- {error.get('code')}: {error.get('detail')}")
                return 1
            if diagnostics and diagnostics.get("next_selected_task_id"):
                print_result(
                    "ACTIVE_TASK_MISSING_BUT_READY_TASKS_EXIST",
                    "No active task is loaded even though ready tasks exist.",
                    "Run python3 scripts/select_task.py and python3 scripts/render_packet.py, or rerun python3 scripts/automate_task_loop.py after repairing state.",
                    extra=f"Next ready task: {diagnostics['next_selected_task_id']}",
                )
                return 1
            if diagnostics and diagnostics.get("selector_filtered_everything"):
                print_result(
                    "SELECTOR_FILTERED_EVERYTHING",
                    "Ready-status tasks exist, but blockers or dependencies filtered every candidate.",
                    "Inspect backlog blockers/dependencies or run python3 scripts/automate_task_loop.py --inspect-backlog for details.",
                )
                return 1
            print_result(
                "NO_READY_TASKS_REMAIN",
                "No ready tasks remain after backlog selection.",
                "Inspect backlog.yml for the next task to mark ready, or run python3 scripts/automate_task_loop.py --inspect-backlog for details.",
            )
            return 1
        print_result(label, summary, next_action)
        return 1

    previous_run_dir, run_dir = prepare_invocation_run_dir(active, active["task_id"])
    target_kind = "builder" if task_targets_builder_repo(task, active) else "product"
    target_repo = builder_repo if target_kind == "builder" else product_repo
    attach_target_to_active(active, target_repo=target_repo, target_kind=target_kind)
    retry_continuation = (
        not args.resume
        and prior_active_state == "blocked"
        and prior_status_state == "blocked"
        and prior_last_result == "refined"
        and status.get("active_task_id") == active.get("task_id")
    )
    sync_run_state(active, status, "task_selected", task_id=active.get("task_id"), title=active.get("title"), run_log_dir=run_dir, last_result=prior_last_result)
    context = build_context(active, task, product_repo, ROOT, target_repo, target_kind)

    executor_config = config.get("executor", {})
    git_config = config.get("git", {})
    vm_config = config.get("vm", {})
    executor_mode = executor_config.get("mode") or "command"
    shell_executable = executor_config.get("shell") or "/bin/zsh"
    progress_heartbeat_seconds = int(executor_config.get("heartbeat_seconds", 15))
    codex_cli = str(executor_config.get("codex_cli") or "codex")
    codex_last_message_path = run_dir / str(executor_config.get("last_message_file") or "codex_last_message.md")
    vm_repo = str(vm_config.get("product_repo", "~/projects/jorb"))
    context["vm_product_repo"] = vm_repo

    vm_validation_commands = list(vm_config.get("validation_commands", []))
    vm_bootstrap_commands = list(active.get("vm_bootstrap_commands", [])) or list(vm_config.get("bootstrap_commands", []))
    vm_smoke_commands = list(vm_config.get("runtime_validation_commands", [])) + list(active.get("vm_verification_commands", []))
    vm_cleanup_commands = list(active.get("vm_cleanup_commands", [])) or list(vm_config.get("cleanup_commands", []))
    local_validation_commands = list(active.get("verification_commands", []))
    prepared_validation_commands, validation_venv = validation_commands_for_target(
        local_validation_commands,
        target_kind=target_kind,
        target_repo=target_repo,
    )
    use_vm_flow = target_kind == "product"
    standards = load_repo_local_standards(ROOT)
    phase4_enforcement = phase4_requires_artifact_enforcement(task)
    effective_vm_ssh_options = noninteractive_vm_ssh_options(vm_config) if use_vm_flow else []
    ignored_git_paths = ignored_git_paths_for_target(target_kind, git_config)
    plan = {
        "task_id": task["id"],
        "prompt_file": active["prompt_file"],
        "run_log_dir": active["run_log_dir"],
        "target_kind": target_kind,
        "target_repo": str(target_repo),
        "executor_mode": executor_mode,
        "executor_command": render_template(executor_config.get("command"), context),
        "executor_codex_argv": codex_exec_argv(executor_config, run_dir=run_dir) if executor_mode == "codex_exec" else None,
        "local_validation_commands": local_validation_commands,
        "prepared_local_validation_commands": prepared_validation_commands,
        "git_push_command": render_template(git_config.get("push_command"), context),
        "vm_pull_command": render_template(vm_config.get("pull_command"), context) if use_vm_flow else None,
        "vm_validation_commands": [render_template(command, context) for command in vm_validation_commands] if use_vm_flow else [],
        "vm_bootstrap_commands": [render_template(command, context) for command in vm_bootstrap_commands] if use_vm_flow else [],
        "vm_smoke_commands": [render_template(command, context) for command in vm_smoke_commands] if use_vm_flow else [],
        "vm_cleanup_commands": [render_template(command, context) for command in vm_cleanup_commands] if use_vm_flow else [],
        "vm_commands": (
            [render_template(command, context) for command in vm_validation_commands]
            + [render_template(command, context) for command in vm_bootstrap_commands]
            + [render_template(command, context) for command in vm_smoke_commands]
            + [render_template(command, context) for command in vm_cleanup_commands]
        ) if use_vm_flow else [],
        "ssh_target": vm_config.get("ssh_target") if use_vm_flow else None,
        "ssh_options": effective_vm_ssh_options if use_vm_flow else [],
        "missing_configuration": [],
        "retry_continuation": retry_continuation,
        "feature_understanding_required": task_is_nontrivial(task),
    }
    if phase4_enforcement:
        plan["phase4_stage_order"] = phase4_stage_order(task, use_vm_flow=use_vm_flow)
        plan["repo_local_standards"] = {
            "agents_path": standards.get("agents_path"),
            "skills_dir": standards.get("skills_dir"),
            "skill_files": standards.get("skill_files", []),
        }
    executor_result: dict[str, Any] = {}
    local_validation_payload: dict[str, Any] | None = None
    vm_validation_payload: dict[str, Any] | None = None
    if executor_mode != "human_gated" and not executor_config.get("command"):
        if executor_mode == "codex_exec":
            if shutil.which(codex_cli) is None and not Path(codex_cli).expanduser().exists():
                plan["missing_configuration"].append("executor.codex_cli")
        else:
            plan["missing_configuration"].append("executor.command")
    if phase4_enforcement:
        plan["missing_configuration"].extend(repo_local_standards_issues(standards))
        checkpoint_issue = phase4_decision_checkpoint_issue(task)
        if checkpoint_issue:
            plan["missing_configuration"].append(checkpoint_issue)
    plan["preflight_contract_issues"] = preflight_contract_issues(
        task=task,
        target_kind=target_kind,
        target_repo=target_repo,
        standards=standards,
    )
    if plan["preflight_contract_issues"]:
        plan["missing_configuration"].extend(plan["preflight_contract_issues"])
    if use_vm_flow and not vm_config.get("ssh_target"):
        plan["missing_configuration"].append("vm.ssh_target")
    if use_vm_flow and not vm_smoke_commands:
        plan["missing_configuration"].append("vm.runtime_validation_commands or task.vm_verification")
    if use_vm_flow and vm_smoke_commands and not vm_bootstrap_commands:
        plan["missing_configuration"].append("vm.bootstrap_commands or task.vm_bootstrap")
    if use_vm_flow and vm_bootstrap_commands and vm_smoke_commands:
        bootstrap_streamlit_port = extract_streamlit_port(vm_bootstrap_commands)
        runtime_self_check_ui_url = extract_runtime_self_check_ui_url(vm_smoke_commands)
        if bootstrap_streamlit_port and runtime_self_check_ui_url:
            expected_ui_url = f"http://127.0.0.1:{bootstrap_streamlit_port}"
            if runtime_self_check_ui_url != expected_ui_url:
                plan["missing_configuration"].append(
                    f"vm runtime UI mismatch: bootstrap uses {expected_ui_url} but runtime_self_check expects {runtime_self_check_ui_url}"
                )

    feature_spec_required = task_is_nontrivial(task)

    if args.dry_run:
        planned_artifacts: list[str] = []
        planned_steps: list[dict[str, Any]] = []
        trailing_planned_steps: list[dict[str, Any]] = []
        if feature_spec_required and not phase4_enforcement:
            feature_spec_path = write_compiled_feature_spec(run_dir, task, standards)
            if feature_spec_path:
                planned_artifacts.append(feature_spec_path)
                trailing_planned_steps.append(
                    {"name": "planner", "outcome": "planned", "detail": f"compiled_feature_spec.md -> {run_dir / 'compiled_feature_spec.md'}"}
                )
        if phase4_enforcement:
            planned_artifacts = write_phase4_preimplementation_artifacts(run_dir, task, standards)
            planned_steps.extend(
                [
                    {"name": "planner", "outcome": "planned", "detail": f"compiled_feature_spec.md -> {run_dir / 'compiled_feature_spec.md'}"},
                    {"name": "architect", "outcome": "planned", "detail": f"tradeoff_matrix.md + proposal.md -> {run_dir}"},
                    {"name": "research_grounding", "outcome": "planned", "detail": f"research_brief.md -> {run_dir / 'research_brief.md'}"},
                    {"name": "decision_checkpoint", "outcome": "planned", "detail": "Decision checkpoint would block if selected_approach were missing while multiple options were declared."},
                    {"name": "implementer", "outcome": "planned", "detail": "Executor would run only after planning artifacts exist."},
                    {"name": "validator", "outcome": "planned", "detail": "Local validation, git, and runtime proof would run according to the task target."},
                    {"name": "judge", "outcome": "planned", "detail": "Acceptance would require judge_decision.md and evidence_bundle.json."},
                ]
            )
        payload = {
            "task_id": task["id"],
            "classification": "dry_run",
            "finished_at": now_iso(),
            "summary": "Dry run only. No executor, git, or VM commands were executed.",
            "steps": planned_steps + [{"name": "plan", "outcome": "planned", "detail": json.dumps(plan, indent=2)}] + trailing_planned_steps,
            "changed_files": [],
            "planned_artifacts": planned_artifacts,
            "unproven_runtime_gaps": ["Automation loop not executed; this was a dry run."],
        }
        write_json(run_dir / RESULT_FILE, payload)
        write_summary(run_dir, payload)
        if task.get("status") in {"selected", "packet_rendered"}:
            task["status"] = "ready"
            write_data(BACKLOG, backlog)
        repaired_active = reset_active()
        repaired_active["previous_run_log_dir"] = str(run_dir)
        write_data(ACTIVE, repaired_active)
        status["state"] = "idle"
        status["active_task_id"] = None
        status["last_task_id"] = task["id"]
        status["last_run_at"] = now_iso()
        write_data(STATUS, status)
        update_run_ledger(
            task_id=task["id"],
            title=task["title"],
            run_state="dry_run",
            stage_name="plan",
            run_log_dir=run_dir,
            detail=payload["summary"],
            next_action="Inspect automation_result.json for the planned stages and artifacts.",
        )
        print_result("DRY_RUN", f"Plan written to {run_dir / RESULT_FILE}")
        return 0

    lock_acquired, lock_issue = acquire_run_lock(task["id"])
    if not lock_acquired:
        summary = f"Missing automation configuration: {lock_issue}"
        automation_result = {
            "task_id": task["id"],
            "classification": "blocked",
            "finished_at": now_iso(),
            "summary": summary,
            "steps": [{"name": "run_lock", "outcome": "blocked", "detail": lock_issue}],
            "changed_files": [],
            "blocker_evidence": [lock_issue] if lock_issue else [],
            "unproven_runtime_gaps": [summary],
        }
        automation_result = persist_result_with_phase4_artifacts(
            run_dir,
            task,
            automation_result,
            standards=standards,
            require_runtime_proof=phase4_enforcement,
            local_validation_payload=local_validation_payload,
            vm_validation_payload=vm_validation_payload,
        )
        classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result)
        write_data(BACKLOG, backlog)
        write_data(STATUS, status)
        print_result("BLOCKED", summary, "Wait for the current controller to finish or clear the stale run lock before rerunning automation.")
        return 2

    auth_status = check_auth_status(config, target_kind=target_kind, target_repo=target_repo, cwd=ROOT)
    write_step(run_dir, "auth_preflight", auth_status)
    if auth_status["interactive_run_likely"]:
        summary = "Authentication preflight indicates repeated or interactive prompts are likely."
        sync_run_state(active, status, "preflight_failed", task_id=active.get("task_id"), title=active.get("title"), run_log_dir=run_dir, failure_summary=summary, last_result="blocked")
        blocker_evidence = [auth_status["git"].get("detail", ""), auth_status["vm_ssh"].get("detail", "")]
        automation_result = {
            "task_id": task["id"],
            "classification": "blocked",
            "finished_at": now_iso(),
            "summary": summary,
            "steps": [{"name": "auth_preflight", "outcome": "blocked", "detail": json.dumps(auth_status, sort_keys=True)}],
            "changed_files": [],
            "blocker_evidence": [item for item in blocker_evidence if item],
            "unproven_runtime_gaps": [summary],
        }
        automation_result = persist_result_with_phase4_artifacts(
            run_dir,
            task,
            automation_result,
            standards=standards,
            require_runtime_proof=phase4_enforcement,
            local_validation_payload=local_validation_payload,
            vm_validation_payload=vm_validation_payload,
        )
        classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result, terminal_state="preflight_failed")
        write_data(BACKLOG, backlog)
        print_result(
            "BLOCKED",
            summary,
            "Run python3 scripts/automate_task_loop.py --check-auth and apply the suggested SSH/Git fixes before rerunning automation.",
        )
        return 2

    active["started_at"] = now_iso()
    sync_run_state(active, status, "preflight_passed", task_id=active.get("task_id"), title=active.get("title"), run_log_dir=run_dir, last_result=status.get("last_result"))
    progress_started_at = active.get("started_at")

    def emit_live_phase_progress(stage_index: int, label: str, command: str) -> Callable[[dict[str, Any]], None]:
        def _emit(payload: dict[str, Any]) -> None:
            detail = (
                f"phase={label} | pid={payload.get('pid')} | elapsed={payload.get('elapsed_seconds')}s | "
                f"timeout_remaining={payload.get('timeout_remaining_seconds')}s | command={command} | "
                f"poll={payload.get('process_status')}"
            )
            emit_progress(
                run_dir,
                task_id=task["id"],
                stage_index=stage_index,
                backlog=backlog,
                task_started_at=progress_started_at,
                detail=detail,
                extra_payload={"command": command, "phase_label": label, **payload},
            )
        return _emit

    emit_progress(run_dir, task_id=task["id"], stage_index=1, backlog=backlog, task_started_at=progress_started_at, detail="Task selected and state loaded.")
    emit_progress(run_dir, task_id=task["id"], stage_index=2, backlog=backlog, task_started_at=progress_started_at, detail=f"Prompt file ready at {active['prompt_file']}.")

    steps: list[dict[str, Any]] = []
    blocker_evidence: list[str] = []
    continue_from_prior_vm_retry = False
    continue_from_prior_ux_evidence_retry = False

    if feature_spec_required and not phase4_enforcement:
        write_compiled_feature_spec(run_dir, task, standards)

    if phase4_enforcement:
        write_phase4_preimplementation_artifacts(run_dir, task, standards)
        steps.extend(
            [
                {"name": "planner", "outcome": "passed", "detail": f"compiled_feature_spec.md written to {run_dir / 'compiled_feature_spec.md'}"},
                {"name": "architect", "outcome": "passed", "detail": f"proposal.md and tradeoff_matrix.md written to {run_dir}"},
                {"name": "research_grounding", "outcome": "passed", "detail": f"research_brief.md written to {run_dir / 'research_brief.md'}"},
            ]
        )

    if plan["missing_configuration"]:
        summary = "Missing automation configuration: " + ", ".join(plan["missing_configuration"])
        emit_progress(run_dir, task_id=task["id"], stage_index=1, backlog=backlog, task_started_at=progress_started_at, state="failed", detail=summary)
        automation_result = {
            "task_id": task["id"],
            "classification": "blocked",
            "finished_at": now_iso(),
            "summary": summary,
            "steps": [{"name": "configuration", "outcome": "blocked", "detail": summary}],
            "changed_files": [],
            "blocker_evidence": plan["missing_configuration"],
            "unproven_runtime_gaps": [summary],
        }
        automation_result = persist_result_with_phase4_artifacts(
            run_dir,
            task,
            automation_result,
            standards=standards,
            require_runtime_proof=phase4_enforcement,
            local_validation_payload=local_validation_payload,
            vm_validation_payload=vm_validation_payload,
        )
        classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result)
        write_data(BACKLOG, backlog)
        write_data(STATUS, status)
        print_result("BLOCKED", summary, "Set the missing config values in config.yml and rerun python3 scripts/automate_task_loop.py.")
        if "vm.runtime_validation_commands or task.vm_verification" in plan["missing_configuration"]:
            return 1
        return 2

    baseline = git_status_porcelain(target_repo, ignored_prefixes=ignored_git_paths)
    if retry_continuation and bool(task.get("allow_noop_completion")) and not baseline.get("files"):
        prior_vm_retry = prior_result_supports_vm_retry(previous_run_dir, active)
        if not prior_vm_retry:
            retry_continuation = False
            active.setdefault("notes", []).append(
                "Retry-ready continuation cleared for allow_noop_completion task because no in-flight repo changes remained; rerunning fresh."
            )
    if retry_continuation and not baseline.get("files") and is_product_facing_ux_task(task):
        prior_ux_evidence_retry = prior_result_supports_ux_evidence_retry(previous_run_dir, active)
        if prior_ux_evidence_retry:
            retry_continuation = False
            continue_from_prior_ux_evidence_retry = True
            active.setdefault("notes", []).append(
                "Retry-ready continuation cleared for UX-evidence-only refine; rerunning executor fresh and allowing verified no-op completion."
            )
    write_step(run_dir, "git_status_before", baseline)
    if not args.resume and not retry_continuation and git_config.get("require_clean_worktree", True) and baseline.get("files"):
        summary = f"{target_kind.title()} repo is dirty before automated execution; refusing to continue."
        emit_progress(run_dir, task_id=task["id"], stage_index=4, backlog=backlog, task_started_at=progress_started_at, state="failed", detail=summary)
        blocker_evidence.extend(baseline.get("files", []))
        automation_result = {
            "task_id": task["id"],
            "classification": "blocked",
            "finished_at": now_iso(),
            "summary": summary,
            "steps": [{"name": "git_status_before", "outcome": "blocked", "detail": "\n".join(baseline.get("files", []))}],
            "changed_files": baseline.get("files", []),
            "blocker_evidence": blocker_evidence,
            "unproven_runtime_gaps": [summary],
        }
        automation_result = persist_result_with_phase4_artifacts(
            run_dir,
            task,
            automation_result,
            standards=standards,
            require_runtime_proof=phase4_enforcement,
            local_validation_payload=local_validation_payload,
            vm_validation_payload=vm_validation_payload,
        )
        classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result)
        write_data(BACKLOG, backlog)
        write_data(STATUS, status)
        print_result("BLOCKED", summary, f"Clean {target_repo} or relax git.require_clean_worktree before rerunning python3 scripts/automate_task_loop.py.")
        return 2

    if not args.resume and not retry_continuation and executor_mode == "human_gated":
        sync_run_state(active, status, "implementing", task_id=active.get("task_id"), title=active.get("title"), run_log_dir=run_dir, last_result=status.get("last_result"))
        emit_progress(run_dir, task_id=task["id"], stage_index=3, backlog=backlog, task_started_at=progress_started_at, detail="Recording manual executor handoff.")
        handoff_note = "Manual JORB Codex execution is required before resume."
        handoff_payload = {
            "mode": "human_gated",
            "task_id": task["id"],
            "prompt_file": active["prompt_file"],
            "run_log_dir": active["run_log_dir"],
            "resume_command": "python3 scripts/automate_task_loop.py --resume",
            "target_kind": target_kind,
            "target_repo": str(target_repo),
            "message": f"Open the packet, run the task in the {'builder' if target_kind == 'builder' else 'JORB'} Codex workspace, then resume after {target_kind} repo changes are present.",
            "started_at": now_iso(),
        }
        write_step(run_dir, "executor_handoff", handoff_payload)
        automation_result = {
            "task_id": task["id"],
            "classification": "paused",
            "finished_at": now_iso(),
            "summary": f"Manual executor handoff recorded. Resume after {target_kind} repo changes are applied.",
            "steps": [
                {
                    "name": "executor_handoff",
                    "outcome": "paused",
                    "detail": f"packet: {active['prompt_file']}; target_repo: {target_repo}; resume: python3 scripts/automate_task_loop.py --resume",
                }
            ],
            "changed_files": [],
            "unproven_runtime_gaps": [f"{target_kind.title()} repo changes have not been applied yet; resume is required after manual Codex execution."],
        }
        persist_paused_state(active, status, handoff_note)
        print_result(
            "PAUSED",
            f"Manual executor handoff recorded for {active['prompt_file']}.",
            "After Codex applies changes in the target repo, run python3 scripts/automate_task_loop.py --resume.",
            extra=f"Target repo: {target_repo}",
        )
        return 0

    if args.resume:
        sync_run_state(active, status, "implementing", task_id=active.get("task_id"), title=active.get("title"), run_log_dir=run_dir, last_result=status.get("last_result"))
        emit_progress(run_dir, task_id=task["id"], stage_index=4, backlog=backlog, task_started_at=progress_started_at, detail=f"Checking {target_kind} repo for resumed task changes.")
        after_executor = baseline
        write_step(run_dir, "resume_check", after_executor)
        steps.append({
            "name": "resume_check",
            "outcome": "passed" if after_executor.get("files") else "paused",
            "detail": f"Detected {target_kind} repo changes after manual execution." if after_executor.get("files") else f"No {target_kind} repo changes detected yet.",
        })
        if not after_executor.get("files"):
            automation_result = {
                "task_id": task["id"],
                "classification": "paused",
                "finished_at": now_iso(),
                "summary": f"Resume requested, but no {target_kind} repo changes were detected yet.",
                "steps": steps,
                "changed_files": [],
                "unproven_runtime_gaps": [f"Manual Codex execution has not produced detectable {target_kind} repo changes yet."],
            }
            persist_paused_state(active, status, f"Resume attempted before {target_kind} repo changes were present.")
            print_result(
                "PAUSED",
                f"No {target_kind} repo changes were detected yet.",
                f"Apply the packet in {target_repo} first, then rerun python3 scripts/automate_task_loop.py --resume.",
                extra=f"Prompt file: {active['prompt_file']}",
            )
            return 0
    elif retry_continuation:
        sync_run_state(active, status, "implementing", task_id=active.get("task_id"), title=active.get("title"), run_log_dir=run_dir, last_result=status.get("last_result"))
        emit_progress(run_dir, task_id=task["id"], stage_index=4, backlog=backlog, task_started_at=progress_started_at, detail=f"Continuing retry-ready task from existing {target_kind} repo changes.")
        after_executor = baseline
        write_step(run_dir, "retry_check", after_executor)
        steps.append({
            "name": "retry_check",
            "outcome": "passed" if after_executor.get("files") else "refined",
            "detail": f"Continuing from existing {target_kind} repo task changes." if after_executor.get("files") else f"No {target_kind} repo changes were found for retry continuation.",
        })
        if not after_executor.get("files"):
            prior_vm_retry = prior_result_supports_vm_retry(previous_run_dir, active)
            if prior_vm_retry:
                steps[-1]["outcome"] = "passed"
                steps[-1]["detail"] = "No current dirty repo changes; continuing from prior post-push VM retry context."
            else:
                summary = f"Retry-ready task has no {target_kind} repo changes to continue from."
                automation_result = {
                    "task_id": task["id"],
                    "classification": "refined",
                    "finished_at": now_iso(),
                    "summary": summary,
                    "steps": steps,
                    "changed_files": [],
                    "blocker_evidence": [],
                    "unproven_runtime_gaps": [summary],
                }
                automation_result = persist_result_with_phase4_artifacts(
                    run_dir,
                    task,
                    automation_result,
                    standards=standards,
                    require_runtime_proof=phase4_enforcement,
                    local_validation_payload=local_validation_payload,
                    vm_validation_payload=vm_validation_payload,
                )
                classify_and_update_state("refined", summary, task, backlog, active, status, automation_result)
                write_data(BACKLOG, backlog)
                write_data(STATUS, status)
                print_result("REFINED", summary, f"Reapply or restore the task changes in {target_repo}, then rerun python3 scripts/automate_task_loop.py.")
                return 1
    else:
        sync_run_state(active, status, "implementing", task_id=active.get("task_id"), title=active.get("title"), run_log_dir=run_dir, last_result=status.get("last_result"))
        initial_timeout = int(executor_config.get("timeout_seconds", 300 if executor_mode == "codex_exec" else 1800))
        initial_output = str(codex_last_message_path) if executor_mode == "codex_exec" else "n/a"
        emit_progress(
            run_dir,
            task_id=task["id"],
            stage_index=3,
            backlog=backlog,
            task_started_at=progress_started_at,
            detail=(
                f"status=waiting_for_first_output | waiting_on={Path(initial_output).name if initial_output != 'n/a' else 'executor completion'} | "
                f"elapsed=0s | timeout_remaining={initial_timeout}s | prompt={active.get('prompt_file')} | "
                f"output={initial_output} | output_exists=false | output_size=0B | output_mtime=none | "
                f"artifact_age=none | stream_age=none | stdout_seen=false | stderr_seen=false | poll=not_started"
            ),
            extra_payload={
                "status": "waiting_for_first_output",
                "waiting_on": Path(initial_output).name if initial_output != "n/a" else "executor completion",
                "timeout_remaining_seconds": initial_timeout,
                "prompt_file": active.get("prompt_file"),
                "output_file": initial_output,
                "last_message_exists": False,
                "last_message_size_bytes": 0,
                "last_message_mtime": None,
                "seconds_since_artifact_change": None,
                "seconds_since_stream_activity": None,
                "stdout_seen": False,
                "stderr_seen": False,
                "process_status": "not_started",
            },
        )
        prompt_text = Path(active["prompt_file"]).read_text(encoding="utf-8")
        if executor_mode == "codex_exec":
            def emit_codex_heartbeat(payload: dict[str, Any]) -> None:
                detail = (
                    f"status={payload.get('status')} | waiting_on={payload.get('waiting_on')} | "
                    f"pid={payload.get('pid')} | elapsed={payload.get('elapsed_seconds')}s | "
                    f"timeout_remaining={payload.get('timeout_remaining_seconds')}s | "
                    f"prompt={active.get('prompt_file')} | output={payload.get('output_file')} | "
                    f"output_exists={str(payload.get('last_message_exists')).lower()} | "
                    f"output_size={payload.get('last_message_size_bytes')}B | "
                    f"output_mtime={payload.get('last_message_mtime') or 'none'} | "
                    f"artifact_age={(str(payload.get('seconds_since_artifact_change')) + 's') if payload.get('seconds_since_artifact_change') is not None else 'none'} | "
                    f"stream_age={(str(payload.get('seconds_since_stream_activity')) + 's') if payload.get('seconds_since_stream_activity') is not None else 'none'} | "
                    f"stdout_seen={str(payload.get('stdout_seen')).lower()} | "
                    f"stderr_seen={str(payload.get('stderr_seen')).lower()} | "
                    f"poll={payload.get('process_status')}"
                )
                emit_progress(
                    run_dir,
                    task_id=task["id"],
                    stage_index=3,
                    backlog=backlog,
                    task_started_at=progress_started_at,
                    detail=detail,
                    extra_payload={"prompt_file": active.get("prompt_file"), **payload},
                )

            executor_result = run_codex_exec(
                codex_exec_argv(executor_config, run_dir=run_dir),
                target_repo,
                input_text=prompt_text,
                output_path=codex_last_message_path,
                timeout=int(executor_config.get("timeout_seconds", 300)),
                heartbeat_seconds=int(executor_config.get("heartbeat_seconds", 15)),
                stall_seconds=int(executor_config.get("stall_threshold_seconds", 0) or 0),
                heartbeat=emit_codex_heartbeat,
            )
        else:
            executor_result = run_shell(
                plan["executor_command"],
                ROOT,
                shell_executable=shell_executable,
                timeout=int(executor_config.get("timeout_seconds", 1800)),
            )
        write_step(run_dir, "executor", executor_result)
        steps.append({
            "name": "executor",
            "outcome": "passed" if executor_result["passed"] else "blocked",
            "detail": executor_result.get("last_message") or executor_result["stderr"] or executor_result["stdout"],
            "command": executor_result["command"],
        })
        if not executor_result["passed"]:
            failure_reason = executor_result.get("failure_reason") or "executor_failure"
            retryable_executor_failure = is_retryable_executor_failure(executor_result)
            if failure_reason == "executor_timeout":
                summary = "executor_timeout"
            elif failure_reason == "executor_interrupted":
                summary = "executor_interrupted"
            elif retryable_executor_failure:
                summary = summarize_retryable_executor_failure(executor_result)
            else:
                summary = "executor_failure"
            emit_progress(run_dir, task_id=task["id"], stage_index=3, backlog=backlog, task_started_at=progress_started_at, state="failed", detail=summary)
            blocker_evidence.extend(
                [
                    failure_reason,
                    executor_result.get("stderr_tail") or executor_result.get("stderr"),
                    executor_result.get("stdout_tail") or executor_result.get("stdout"),
                ]
            )
            automation_result = {
                "task_id": task["id"],
                "classification": "interrupted" if failure_reason == "executor_interrupted" or retryable_executor_failure else "blocked",
                "finished_at": now_iso(),
                "summary": summary,
                "steps": steps,
                "changed_files": [],
                "blocker_evidence": [item for item in blocker_evidence if item],
                "unproven_runtime_gaps": [summary],
            }
            automation_result = persist_result_with_phase4_artifacts(
                run_dir,
                task,
                automation_result,
                standards=standards,
                require_runtime_proof=phase4_enforcement,
                local_validation_payload=local_validation_payload,
                vm_validation_payload=vm_validation_payload,
            )
            classify_and_update_state("interrupted" if failure_reason == "executor_interrupted" or retryable_executor_failure else "blocked", summary, task, backlog, active, status, automation_result)
            write_data(BACKLOG, backlog)
            if failure_reason == "executor_interrupted":
                print_result("INTERRUPTED", "Executor interrupted by user.", "Rerun python3 scripts/automate_task_loop.py when you are ready to try again.")
                return 130
            if retryable_executor_failure:
                write_data(STATUS, status)
                print_result("INTERRUPTED", summary, "Transient Codex executor failure; rerun python3 scripts/automate_task_loop.py.")
                return 1
            write_data(STATUS, status)
            print_result("BLOCKED", summary, "Fix the executor integration or switch back to human_gated mode before rerunning python3 scripts/automate_task_loop.py.")
            return 2
        after_executor = git_status_porcelain(target_repo, ignored_prefixes=ignored_git_paths)
        write_step(run_dir, "git_status_after_executor", after_executor)
        emit_progress(run_dir, task_id=task["id"], stage_index=4, backlog=backlog, task_started_at=progress_started_at, detail=f"Detected {len(after_executor.get('files', []))} changed file(s).")

    changed_files = after_executor.get("files", [])
    noop_completion = False
    allow_noop_completion = bool(task.get("allow_noop_completion"))
    if retry_continuation and not changed_files:
        prior_vm_retry = prior_result_supports_vm_retry(previous_run_dir, active)
        if prior_vm_retry:
            changed_files = list(prior_vm_retry.get("changed_files", []))
            continue_from_prior_vm_retry = True
            steps[-1]["detail"] = "No current dirty repo changes; continuing from prior post-push VM retry context."

    allowlisted, disallowed = changed_files_are_allowlisted(changed_files, active.get("allowlist", []))
    if not allowlisted:
        summary = "Executor changed files outside the task allowlist."
        emit_progress(run_dir, task_id=task["id"], stage_index=4, backlog=backlog, task_started_at=progress_started_at, state="failed", detail=summary)
        automation_result = {
            "task_id": task["id"],
            "classification": "blocked",
            "finished_at": now_iso(),
            "summary": summary,
            "steps": steps + [{"name": "allowlist_check", "outcome": "blocked", "detail": "\n".join(disallowed)}],
            "changed_files": changed_files,
            "blocker_evidence": disallowed,
            "unproven_runtime_gaps": [summary],
        }
        automation_result = persist_result_with_phase4_artifacts(
            run_dir,
            task,
            automation_result,
            standards=standards,
            require_runtime_proof=phase4_enforcement,
            local_validation_payload=local_validation_payload,
            vm_validation_payload=vm_validation_payload,
        )
        classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result)
        write_data(BACKLOG, backlog)
        write_data(STATUS, status)
        print_result("BLOCKED", summary, f"Keep changes within the allowlist or adjust the task packet before rerunning. Current target repo: {target_repo}.")
        return 1 if retry_continuation else 2

    if not changed_files:
        summary = f"Executor completed but no {target_kind} repo changes were detected."
        if continue_from_prior_ux_evidence_retry and executor_result.get("passed"):
            prior_ux_evidence_retry = prior_result_supports_ux_evidence_retry(previous_run_dir, active)
            if prior_ux_evidence_retry:
                changed_files = list(prior_ux_evidence_retry.get("changed_files", []))
                noop_completion = True
                summary = f"Executor completed with no new {target_kind} repo changes because this rerun only repaired UX conformance evidence."
        if allow_noop_completion:
            noop_completion = True
            steps.append(
                {
                    "name": "change_detection",
                    "outcome": "passed",
                    "detail": f"No {target_kind} repo changes detected; continuing because this task allows verified no-op completion.",
                }
            )
            emit_progress(
                run_dir,
                task_id=task["id"],
                stage_index=4,
                backlog=backlog,
                task_started_at=progress_started_at,
                detail=f"No {target_kind} repo changes detected; continuing with verification-only completion.",
            )
        else:
            emit_progress(run_dir, task_id=task["id"], stage_index=4, backlog=backlog, task_started_at=progress_started_at, state="failed", detail=summary)
            automation_result = {
                "task_id": task["id"],
                "classification": "refined",
                "finished_at": now_iso(),
                "summary": summary,
                "steps": steps + [{"name": "change_detection", "outcome": "refined", "detail": summary}],
                "changed_files": [],
                "blocker_evidence": [],
                "unproven_runtime_gaps": [summary],
            }
            automation_result = persist_result_with_phase4_artifacts(
                run_dir,
                task,
                automation_result,
                standards=standards,
                require_runtime_proof=phase4_enforcement,
                local_validation_payload=local_validation_payload,
                vm_validation_payload=vm_validation_payload,
            )
            classify_and_update_state("refined", summary, task, backlog, active, status, automation_result)
            write_data(BACKLOG, backlog)
            write_data(STATUS, status)
            if retry_continuation:
                next_action = f"Fix the task changes already present in {target_repo}, then rerun python3 scripts/automate_task_loop.py."
            else:
                next_action = f"Apply the packet in {target_repo} and rerun python3 scripts/automate_task_loop.py --resume if using human-gated execution."
            print_result("REFINED", summary, next_action)
            return 1

    if target_kind == "product" and local_validation_commands and validation_venv is None and not continue_from_prior_vm_retry:
        summary = "No product validation virtualenv found. Expected one of: .venv_validation, .venv, .venv_j1."
        emit_progress(run_dir, task_id=task["id"], stage_index=5, backlog=backlog, task_started_at=progress_started_at, state="failed", detail=summary)
        automation_result = {
            "task_id": task["id"],
            "classification": "blocked",
            "finished_at": now_iso(),
            "summary": summary,
            "steps": steps + [{"name": "local_validation_environment", "outcome": "blocked", "detail": summary}],
            "changed_files": changed_files,
            "blocker_evidence": [summary],
            "unproven_runtime_gaps": [summary],
        }
        automation_result = persist_result_with_phase4_artifacts(
            run_dir,
            task,
            automation_result,
            standards=standards,
            require_runtime_proof=phase4_enforcement,
            local_validation_payload=local_validation_payload,
            vm_validation_payload=vm_validation_payload,
        )
        classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result)
        write_data(BACKLOG, backlog)
        write_data(STATUS, status)
        print_result("BLOCKED", summary, f"Create one of {target_repo}/.venv_validation, {target_repo}/.venv, or {target_repo}/.venv_j1, then rerun python3 scripts/automate_task_loop.py.")
        return 2

    if not continue_from_prior_vm_retry:
        sync_run_state(active, status, "verifying", task_id=active.get("task_id"), title=active.get("title"), run_log_dir=run_dir, last_result=status.get("last_result"))
        local_results: list[dict[str, Any]] = []
        local_passed = True
        for index, command in enumerate(prepared_validation_commands):
            stage_index = 5 if index == 0 else 6
            emit_progress(
                run_dir,
                task_id=task["id"],
                stage_index=stage_index,
                backlog=backlog,
                task_started_at=progress_started_at,
                detail=command,
            )
            result = run_shell(
                command,
                target_repo,
                shell_executable=shell_executable,
                heartbeat_seconds=progress_heartbeat_seconds,
                heartbeat=emit_live_phase_progress(stage_index, "local_validation", command),
            )
            local_results.append(result)
            if not result["passed"]:
                local_passed = False
        write_step(
            run_dir,
            "local_validation",
            {
                "results": local_results,
                "passed": local_passed,
                "venv_path": str(validation_venv) if validation_venv else None,
            },
        )
        local_validation_payload = {
            "results": local_results,
            "passed": local_passed,
            "venv_path": str(validation_venv) if validation_venv else None,
        }
        steps.append({
            "name": "local_validation",
            "outcome": "passed" if local_passed else "refined",
            "detail": "All local verification commands passed." if local_passed else "At least one local verification command failed.",
        })
        if not local_passed:
            summary = "Local validation failed after executor changes."
            emit_progress(run_dir, task_id=task["id"], stage_index=5, backlog=backlog, task_started_at=progress_started_at, state="failed", detail=summary)
            automation_result = {
                "task_id": task["id"],
                "classification": "refined",
                "finished_at": now_iso(),
                "summary": summary,
                "steps": steps,
                "changed_files": changed_files,
                "blocker_evidence": [],
                "unproven_runtime_gaps": [summary],
            }
            automation_result = persist_result_with_phase4_artifacts(
                run_dir,
                task,
                automation_result,
                standards=standards,
                require_runtime_proof=phase4_enforcement,
                local_validation_payload=local_validation_payload,
                vm_validation_payload=vm_validation_payload,
            )
            classify_and_update_state("refined", summary, task, backlog, active, status, automation_result)
            write_data(BACKLOG, backlog)
            write_data(STATUS, status)
            if retry_continuation:
                next_action = f"Inspect local validation output in {run_dir / RESULT_FILE}, fix the current task changes in {target_repo}, then rerun python3 scripts/automate_task_loop.py."
            else:
                next_action = f"Inspect local validation output in {run_dir / RESULT_FILE}, fix the issue, then rerun python3 scripts/automate_task_loop.py."
            print_result("REFINED", summary, next_action)
            return 1

        if noop_completion:
            emit_progress(
                run_dir,
                task_id=task["id"],
                stage_index=7,
                backlog=backlog,
                task_started_at=progress_started_at,
                detail="No repo changes to commit; skipping git add/commit/push for verified no-op completion.",
            )
            write_step(run_dir, "git", {"skipped": True, "reason": "verified no-op completion"})
            steps.append(
                {
                    "name": "git",
                    "outcome": "passed",
                    "detail": "No repo changes detected; skipped git add/commit/push for verified no-op completion.",
                }
            )
        else:
            emit_progress(run_dir, task_id=task["id"], stage_index=7, backlog=backlog, task_started_at=progress_started_at, detail="Running git add/commit/push.")
            git_add_command = "git add -A"
            git_add = run_argv(
                ["git", "add", "-A"],
                target_repo,
                env=NONINTERACTIVE_GIT_ENV,
                heartbeat_seconds=progress_heartbeat_seconds,
                heartbeat=emit_live_phase_progress(7, "git_add", git_add_command),
            )
            commit_message = render_template(git_config.get("commit_message_template"), context) or f"{task['id']}: {task['title']}"
            git_commit_command = " ".join(shlex.quote(part) for part in ["git", "commit", "-m", commit_message])
            git_commit = run_argv(
                ["git", "commit", "-m", commit_message],
                target_repo,
                env=NONINTERACTIVE_GIT_ENV,
                heartbeat_seconds=progress_heartbeat_seconds,
                heartbeat=emit_live_phase_progress(7, "git_commit", git_commit_command),
            )
            git_push_command = render_template(git_config.get("push_command"), context) or "git push"
            git_push = run_shell(
                git_push_command,
                target_repo,
                shell_executable=shell_executable,
                env=NONINTERACTIVE_GIT_ENV,
                heartbeat_seconds=progress_heartbeat_seconds,
                heartbeat=emit_live_phase_progress(7, "git_push", git_push_command),
            )
            write_step(run_dir, "git", {"add": git_add, "commit": git_commit, "push": git_push})
            steps.append({
                "name": "git",
                "outcome": "passed" if git_add["passed"] and git_commit["passed"] and git_push["passed"] else "blocked",
                "detail": git_push["stderr"] or git_commit["stderr"] or git_add["stderr"],
            })
            if not (git_add["passed"] and git_commit["passed"] and git_push["passed"]):
                summary = "Git add/commit/push failed after local validation passed."
                emit_progress(run_dir, task_id=task["id"], stage_index=7, backlog=backlog, task_started_at=progress_started_at, state="failed", detail=summary)
                blocker_evidence.extend([
                    git_add["stderr"] or git_add["stdout"],
                    git_commit["stderr"] or git_commit["stdout"],
                    git_push["stderr"] or git_push["stdout"],
                ])
                automation_result = {
                    "task_id": task["id"],
                    "classification": "blocked",
                    "finished_at": now_iso(),
                    "summary": summary,
                    "steps": steps,
                    "changed_files": changed_files,
                    "blocker_evidence": [item for item in blocker_evidence if item],
                    "unproven_runtime_gaps": [summary],
                }
                automation_result = persist_result_with_phase4_artifacts(
                    run_dir,
                    task,
                    automation_result,
                    standards=standards,
                    require_runtime_proof=phase4_enforcement,
                    local_validation_payload=local_validation_payload,
                    vm_validation_payload=vm_validation_payload,
                )
                classify_and_update_state("blocked", summary, task, backlog, active, status, automation_result)
                write_data(BACKLOG, backlog)
                write_data(STATUS, status)
                print_result("BLOCKED", summary, f"Inspect git output in {run_dir / RESULT_FILE} and repair repo/push state before rerunning python3 scripts/automate_task_loop.py.")
                return 2

    vm_passed = True
    if use_vm_flow:
        ssh_target = vm_config["ssh_target"]
        ssh_options = effective_vm_ssh_options
        emit_progress(run_dir, task_id=task["id"], stage_index=8, backlog=backlog, task_started_at=progress_started_at, detail=f"Running VM validation on {ssh_target}.")
        vm_pull_command = f"cd {shlex.quote(vm_repo)} && env GIT_TERMINAL_PROMPT=0 {plan['vm_pull_command']}"
        vm_pull = ssh_command(
            ssh_target,
            ssh_options,
            vm_pull_command,
            ROOT,
            heartbeat_seconds=progress_heartbeat_seconds,
            heartbeat=emit_live_phase_progress(8, "vm_pull", vm_pull_command),
        )
        vm_results = [vm_pull]
        vm_passed = vm_pull["passed"]
        vm_failure_phase: str | None = None
        vm_failure_summary = "VM validation failed after local validation and git push succeeded."
        vm_bootstrap_attempted = False

        def run_vm_phase(commands: list[str], phase_label: str, *, ignore_prior_failure: bool = False) -> bool:
            nonlocal vm_passed, vm_failure_phase, vm_failure_summary, vm_bootstrap_attempted
            if not vm_passed and not ignore_prior_failure:
                return False
            if phase_label == "vm_bootstrap" and commands:
                vm_bootstrap_attempted = True
            for command in commands:
                remote = f"cd {shlex.quote(vm_repo)} && {command}"
                result = ssh_command(
                    ssh_target,
                    ssh_options,
                    remote,
                    ROOT,
                    heartbeat_seconds=progress_heartbeat_seconds,
                    heartbeat=emit_live_phase_progress(8, phase_label, remote),
                )
                result["phase"] = phase_label
                vm_results.append(result)
                if not result["passed"]:
                    vm_passed = False
                    if vm_failure_phase is None:
                        vm_failure_phase = phase_label
                        if phase_label == "vm_validation":
                            vm_failure_summary = "VM preflight validation failed after local validation and git push succeeded."
                        elif phase_label == "vm_bootstrap":
                            vm_failure_summary = "VM bootstrap failed after local validation and git push succeeded."
                        elif phase_label == "vm_smoke":
                            vm_failure_summary = "VM smoke validation failed after local validation and git push succeeded."
                        elif phase_label == "vm_cleanup":
                            vm_failure_summary = "VM cleanup failed after validation completed."
                        else:
                            vm_failure_summary = "VM validation failed after local validation and git push succeeded."
                    return False
            return True

        if vm_passed:
            run_vm_phase(plan["vm_validation_commands"], "vm_validation")
        if vm_passed:
            run_vm_phase(plan["vm_bootstrap_commands"], "vm_bootstrap")
        if vm_passed:
            run_vm_phase(plan["vm_smoke_commands"], "vm_smoke")
        if plan["vm_cleanup_commands"] and (vm_bootstrap_attempted or plan["vm_smoke_commands"]):
            run_vm_phase(plan["vm_cleanup_commands"], "vm_cleanup", ignore_prior_failure=True)
        vm_validation_payload = {"results": vm_results, "passed": vm_passed}
        write_step(run_dir, "vm_validation", vm_validation_payload)
        steps.append({
            "name": "vm_validation",
            "outcome": "accepted" if vm_passed else "refined",
            "detail": "All VM validation commands passed." if vm_passed else (
                "VM preflight commands failed." if vm_failure_phase == "vm_validation" else
                "VM bootstrap commands failed." if vm_failure_phase == "vm_bootstrap" else
                "VM smoke commands failed." if vm_failure_phase == "vm_smoke" else
                "VM cleanup commands failed." if vm_failure_phase == "vm_cleanup" else
                "At least one VM validation command failed."
            ),
        })
        classification = "accepted" if vm_passed else "refined"
        summary = "Automated loop completed with VM validation success." if vm_passed else vm_failure_summary
    else:
        classification = "accepted"
        summary = "Automated loop completed with builder-side local validation success."
    executor_output = str(executor_result.get("last_message") or "")
    ux_conformance = ux_conformance_result(task, executor_output)
    if classification == "accepted" and not ux_conformance["passed"]:
        classification = "refined"
        summary = "UX conformance evidence is incomplete for this product-facing UX task."
        steps.append(
            {
                "name": "ux_conformance",
                "outcome": "refined",
                "detail": "Missing UX conformance evidence: " + ", ".join(ux_conformance["missing_response_fields"]),
            }
        )
    automation_result = {
        "task_id": task["id"],
        "classification": classification,
        "finished_at": now_iso(),
        "summary": summary,
        "steps": steps,
        "changed_files": changed_files,
        "blocker_evidence": [],
        "unproven_runtime_gaps": [] if vm_passed else [summary],
    }
    emit_progress(
        run_dir,
        task_id=task["id"],
        stage_index=9,
        backlog=backlog,
        task_started_at=progress_started_at,
        state="completed" if classification == "accepted" else "failed",
        detail=summary,
    )
    automation_result = persist_result_with_phase4_artifacts(
        run_dir,
        task,
        automation_result,
        standards=standards,
        require_runtime_proof=phase4_enforcement,
        local_validation_payload=local_validation_payload,
        vm_validation_payload=vm_validation_payload,
    )
    classification = str(automation_result.get("classification", classification))
    summary = str(automation_result.get("summary", summary))
    classify_and_update_state(classification, summary, task, backlog, active, status, automation_result)
    promoted_followups: list[str] = []
    if classification == "accepted":
        promoted_followups = promote_auto_ready_pending_tasks(backlog)
    write_data(BACKLOG, backlog)
    write_data(STATUS, status)
    if classification == "accepted":
        if allow_follow_on:
            next_backlog, next_active, next_status, next_bootstrapped = try_bootstrap_active_task()
            if next_bootstrapped:
                return run_loop(args, allow_follow_on=False)
            next_diagnostics = compute_backlog_diagnostics(next_backlog) if not next_backlog.get("errors") else None
            if next_backlog.get("errors"):
                print("BACKLOG_INVALID")
                for error in next_backlog["errors"]:
                    print(f"- {error.get('code')}: {error.get('detail')}")
                return 1
            if next_diagnostics and next_diagnostics.get("selector_filtered_everything"):
                print_result(
                    "SELECTOR_FILTERED_EVERYTHING",
                    "Ready-status tasks exist, but blockers or dependencies filtered every candidate after acceptance.",
                    "Run python3 scripts/automate_task_loop.py --inspect-backlog for skip reasons.",
                )
                return 1
            if promoted_followups and next_diagnostics and next_diagnostics.get("next_selected_task_id"):
                print_result(
                    "NEXT_TASK_READY",
                    f"Accepted task completed and auto-promoted {', '.join(promoted_followups)} to ready.",
                    f"Next runnable task: {next_diagnostics['next_selected_task_id']}",
                )
                return 0
            print_result("NO_READY_TASKS_REMAIN", "No ready tasks remain after the accepted task completed.", "Mark the next task ready in backlog.yml before rerunning automation.")
            return 0
        print_result("ACCEPTED", summary, "Review automation_summary.md for evidence and proceed to the next task.")
    elif classification == "blocked":
        print_result("BLOCKED", summary, f"Inspect {run_dir / RESULT_FILE} for enforcement and validation details, then rerun once the issue is fixed.")
    else:
        print_result("REFINED", summary, f"Inspect {run_dir / RESULT_FILE} for VM validation details, then rerun once the issue is fixed.")
    return 0 if classification == "accepted" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--inspect-backlog", action="store_true")
    parser.add_argument("--check-auth", action="store_true")
    parser.add_argument("--repair-state", action="store_true")
    args = parser.parse_args()
    try:
        return run_loop(args, allow_follow_on=True)
    except KeyboardInterrupt:
        print_result("INTERRUPTED", "Run interrupted by user.")
        return 130
    finally:
        release_run_lock()


if __name__ == "__main__":
    raise SystemExit(main())
