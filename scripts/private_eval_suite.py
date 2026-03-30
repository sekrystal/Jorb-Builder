#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
from typing import Any

from common import (
    builder_root,
    is_product_facing_ux_task,
    load_data,
    load_repo_local_standards,
    task_family,
)


ROOT = builder_root()
FIXTURES_DIR = ROOT / "eval_fixtures"
SUPPORTED_DIMENSIONS = {
    "planning_quality",
    "implementation_quality",
    "test_adequacy",
    "runtime_proof_quality",
    "evidence_quality",
    "recovery_quality",
    "operator_handoff_quality",
    "ui_validation_quality",
    "data_contract_compliance",
    "backlog_synthesis_quality",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def validate_fixture_schema(fixture: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for field in ("fixture_id", "fixture_family", "description", "selector", "mandatory_artifacts", "rubric_dimensions", "pass_threshold"):
        if field not in fixture:
            issues.append(f"missing:{field}")
    if issues:
        return issues
    if not isinstance(fixture.get("selector"), dict):
        issues.append("selector:not_object")
    if not isinstance(fixture.get("mandatory_artifacts"), list):
        issues.append("mandatory_artifacts:not_list")
    if not isinstance(fixture.get("rubric_dimensions"), list) or not fixture.get("rubric_dimensions"):
        issues.append("rubric_dimensions:not_nonempty_list")
    threshold = fixture.get("pass_threshold")
    if not isinstance(threshold, (int, float)) or not 0 <= float(threshold) <= 1:
        issues.append("pass_threshold:out_of_range")
    for index, dimension in enumerate(fixture.get("rubric_dimensions", [])):
        if not isinstance(dimension, dict):
            issues.append(f"rubric_dimensions[{index}]:not_object")
            continue
        name = dimension.get("name")
        if name not in SUPPORTED_DIMENSIONS:
            issues.append(f"rubric_dimensions[{index}]:unsupported_name:{name}")
        weight = dimension.get("weight")
        if not isinstance(weight, (int, float)) or float(weight) <= 0:
            issues.append(f"rubric_dimensions[{index}]:invalid_weight")
        dim_threshold = dimension.get("threshold")
        if not isinstance(dim_threshold, (int, float)) or not 0 <= float(dim_threshold) <= 1:
            issues.append(f"rubric_dimensions[{index}]:invalid_threshold")
    return issues


def load_eval_fixtures(root: Path | None = None) -> list[dict[str, Any]]:
    repo_root = Path(root or builder_root()).expanduser().resolve()
    fixtures_dir = repo_root / "eval_fixtures"
    fixtures: list[dict[str, Any]] = []
    for path in sorted(fixtures_dir.glob("*.json")) if fixtures_dir.exists() else []:
        fixture = load_json(path)
        fixture["_path"] = str(path)
        fixture["_issues"] = validate_fixture_schema(fixture)
        fixtures.append(fixture)
    return fixtures


def _task_has_runtime_contract(task: dict[str, Any]) -> bool:
    if task.get("requires_vm_runtime_proof"):
        return True
    for field in ("vm_verification", "vm_bootstrap", "vm_cleanup"):
        value = task.get(field) or []
        if isinstance(value, list) and any(str(item).strip() for item in value):
            return True
    return False


def fixture_matches_task(fixture: dict[str, Any], task: dict[str, Any], automation_result: dict[str, Any] | None = None) -> bool:
    selector = fixture.get("selector", {})
    if not isinstance(selector, dict):
        return False
    if selector.get("task_family") and selector["task_family"] != task_family(str(task.get("id") or "")):
        return False
    if selector.get("area") and str(selector["area"]).lower() != str(task.get("area") or "").lower():
        return False
    if "product_facing_ux" in selector and bool(selector["product_facing_ux"]) != is_product_facing_ux_task(task):
        return False
    if "requires_vm_runtime_proof" in selector and bool(selector["requires_vm_runtime_proof"]) != _task_has_runtime_contract(task):
        return False
    title = str(task.get("title") or "").lower()
    if selector.get("title_contains"):
        patterns = [str(item).lower() for item in selector.get("title_contains", [])]
        if not any(pattern in title for pattern in patterns):
            return False
    if selector.get("failure_classes"):
        failure_class = str((automation_result or {}).get("failure_taxonomy", {}).get("failure_class") or "")
        if failure_class not in {str(item) for item in selector.get("failure_classes", [])}:
            return False
    return True


def select_fixture_for_task(
    task: dict[str, Any],
    *,
    automation_result: dict[str, Any] | None = None,
    fixtures: list[dict[str, Any]] | None = None,
    root: Path | None = None,
) -> dict[str, Any] | None:
    candidates = fixtures if fixtures is not None else load_eval_fixtures(root)
    ranked: list[tuple[int, dict[str, Any]]] = []
    for fixture in candidates:
        if fixture.get("_issues"):
            continue
        if fixture_matches_task(fixture, task, automation_result):
            selector = fixture.get("selector", {})
            specificity = len(selector)
            if selector.get("failure_classes"):
                specificity += 100
            ranked.append((specificity, fixture))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1] if ranked else None


def _step_lookup(automation_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(step.get("name")): step for step in automation_result.get("steps", []) if isinstance(step, dict)}


def _artifact_presence(run_dir: Path, names: list[str]) -> tuple[list[str], list[str]]:
    present: list[str] = []
    missing: list[str] = []
    for name in names:
        if (run_dir / name).exists():
            present.append(name)
        else:
            missing.append(name)
    return present, missing


def _score_dimension(name: str, subject: dict[str, Any]) -> float:
    step_lookup = subject["step_lookup"]
    run_dir = subject["run_dir"]
    automation_result = subject["automation_result"]
    ux = automation_result.get("ux_conformance") or {}
    accepted = automation_result.get("classification") == "accepted"
    synthesized = subject.get("synthesized_entry") or {}
    if name == "planning_quality":
        if synthesized:
            score = 0.0
            if synthesized.get("rationale"):
                score += 0.5
            if synthesized.get("acceptance_criteria"):
                score += 0.5
            return round(score, 3)
        required = ("compiled_feature_spec.md", "proposal.md", "tradeoff_matrix.md", "research_brief.md")
        present = sum(1 for item in required if (run_dir / item).exists())
        return round(present / len(required), 3)
    if name == "implementation_quality":
        executor = step_lookup.get("executor", {})
        if accepted and (automation_result.get("changed_files") or executor.get("outcome") == "passed"):
            return 1.0
        if executor.get("outcome") == "passed":
            return 0.7
        return 0.2
    if name == "test_adequacy":
        local_step = step_lookup.get("local_validation", {})
        if local_step.get("outcome") in {"passed", "accepted"} and (run_dir / "local_validation.json").exists():
            return 1.0
        if local_step.get("outcome") in {"passed", "accepted"}:
            return 0.8
        return 0.2
    if name == "runtime_proof_quality":
        vm_step = step_lookup.get("vm_validation", {})
        if (run_dir / "runtime_proof.log").exists() and vm_step.get("outcome") in {"accepted", "passed"}:
            return 1.0
        if (run_dir / "runtime_proof.log").exists():
            return 0.6
        return 0.0
    if name == "evidence_quality":
        if synthesized:
            score = 0.0
            if synthesized.get("provenance", {}).get("evidence_links"):
                score += 0.5
            if synthesized.get("provenance", {}).get("source_proposal_id"):
                score += 0.5
            return round(score, 3)
        score = 0.0
        for item in ("evidence_bundle.json", "judge_decision.md", "automation_result.json", "automation_summary.md"):
            if (run_dir / item).exists():
                score += 0.25
        return round(score, 3)
    if name == "recovery_quality":
        taxonomy = automation_result.get("failure_taxonomy") or {}
        if accepted:
            return 0.8
        if taxonomy.get("failure_class") and taxonomy.get("recovery_action") and (run_dir / "postmortem.md").exists():
            return 1.0
        if taxonomy.get("failure_class") and taxonomy.get("recovery_action"):
            return 0.7
        return 0.2
    if name == "operator_handoff_quality":
        if synthesized:
            score = 0.0
            if synthesized.get("title") and synthesized.get("evidence_summary"):
                score += 0.5
            if synthesized.get("operator_approval", {}).get("review_status"):
                score += 0.5
            return round(score, 3)
        summary = str(automation_result.get("summary") or "").strip()
        if summary and (run_dir / "automation_summary.md").exists() and (run_dir / "evidence_bundle.json").exists():
            return 1.0
        if summary:
            return 0.6
        return 0.2
    if name == "ui_validation_quality":
        if not ux.get("required"):
            return 0.5
        if ux.get("passed") and not ux.get("missing_response_fields"):
            return 1.0
        if ux.get("design_section_mapping"):
            return 0.4
        return 0.0
    if name == "data_contract_compliance":
        local_step = step_lookup.get("local_validation", {})
        vm_step = step_lookup.get("vm_validation", {})
        if accepted and local_step.get("outcome") in {"passed", "accepted"}:
            return 1.0 if vm_step.get("outcome") in {"accepted", "passed"} or not vm_step else 0.8
        return 0.3
    if name == "backlog_synthesis_quality":
        synthesis = subject.get("synthesized_entry") or {}
        validation = synthesis.get("validation") or {}
        operator = synthesis.get("operator_approval") or {}
        score = 0.0
        if synthesis.get("acceptance_criteria") and len(synthesis.get("acceptance_criteria", [])) >= 3:
            score += 0.25
        if synthesis.get("required_artifacts") and synthesis.get("validation_expectations"):
            score += 0.25
        if not validation.get("issues") and not validation.get("duplicate_matches"):
            score += 0.25
        if operator.get("approved") and synthesis.get("provenance", {}).get("evidence_links"):
            score += 0.25
        return round(score, 3)
    return 0.0


def score_fixture_subject(fixture: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
    mandatory_artifacts = [str(item) for item in fixture.get("mandatory_artifacts", [])]
    present, missing = _artifact_presence(subject["run_dir"], mandatory_artifacts)
    scores: dict[str, float] = {}
    dimension_failures: list[str] = []
    weighted_total = 0.0
    total_weight = 0.0
    for dimension in fixture.get("rubric_dimensions", []):
        name = str(dimension["name"])
        weight = float(dimension["weight"])
        threshold = float(dimension["threshold"])
        score = _score_dimension(name, subject)
        scores[name] = score
        weighted_total += score * weight
        total_weight += weight
        if score < threshold:
            dimension_failures.append(name)
    overall = round(weighted_total / total_weight, 3) if total_weight else 0.0
    pass_threshold = float(fixture["pass_threshold"])
    passed = not missing and overall >= pass_threshold and not dimension_failures
    return {
        "suite_version": 1,
        "mode": "private_fixture",
        "fixture_id": fixture["fixture_id"],
        "fixture_family": fixture["fixture_family"],
        "task_id": subject["task"].get("id"),
        "scores": scores,
        "overall_score": overall,
        "threshold": pass_threshold,
        "passed": passed,
        "mandatory_artifacts": {"present": present, "missing": missing},
        "dimension_failures": dimension_failures,
    }


def build_eval_subject(
    task: dict[str, Any],
    automation_result: dict[str, Any],
    *,
    run_dir: Path,
    standards: dict[str, Any],
) -> dict[str, Any]:
    return {
        "task": task,
        "automation_result": automation_result,
        "run_dir": run_dir,
        "standards": standards,
        "step_lookup": _step_lookup(automation_result),
    }


def score_private_eval(
    task: dict[str, Any],
    automation_result: dict[str, Any],
    *,
    run_dir: Path,
    standards: dict[str, Any],
    root: Path | None = None,
) -> dict[str, Any]:
    fixtures = load_eval_fixtures(root)
    fixture = select_fixture_for_task(task, automation_result=automation_result, fixtures=fixtures, root=root)
    if fixture is None:
        return {
            "suite_version": 1,
            "mode": "no_fixture",
            "fixture_id": None,
            "fixture_family": None,
            "task_id": task.get("id"),
            "scores": {},
            "overall_score": 0.0,
            "threshold": 0.0,
            "passed": True,
            "mandatory_artifacts": {"present": [], "missing": []},
            "dimension_failures": [],
        }
    subject = build_eval_subject(task, automation_result, run_dir=run_dir, standards=standards)
    result = score_fixture_subject(fixture, subject)
    result["fixture_path"] = fixture.get("_path")
    return result


def _load_task_for_history(task_id: str, root: Path) -> dict[str, Any]:
    backlog = load_data(root / "backlog.yml")
    for task in backlog.get("tasks", []):
        if task.get("id") == task_id:
            return task
    return {"id": task_id, "title": task_id, "area": "builder" if task_id.startswith("JORB-INFRA") else "unknown"}


def replay_history_eval(history_path: Path, *, root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root or builder_root()).expanduser().resolve()
    history = load_data(history_path)
    task = _load_task_for_history(str(history.get("task_id") or ""), repo_root)
    run_dir = Path(str(history.get("run_log_dir") or "")).expanduser()
    automation_result_path = run_dir / "automation_result.json"
    if automation_result_path.exists():
        automation_result = load_json(automation_result_path)
    else:
        automation_result = {
            "task_id": history.get("task_id"),
            "classification": history.get("status"),
            "summary": (history.get("notes") or [""])[0],
            "steps": (history.get("operator_diagnostics") or {}).get("step_outcomes", []),
            "changed_files": history.get("files_changed", []),
            "failure_taxonomy": history.get("failure_taxonomy"),
            "ux_conformance": (history.get("operator_diagnostics") or {}).get("ux_conformance", {}),
        }
    standards = load_repo_local_standards(repo_root)
    result = score_private_eval(task, automation_result, run_dir=run_dir, standards=standards, root=repo_root)
    result["history_path"] = str(history_path)
    result["history_status"] = history.get("status")
    return result


def compare_eval_results(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    dimensions = sorted(set((previous.get("scores") or {}).keys()) | set((current.get("scores") or {}).keys()))
    category_deltas = {
        name: round(float((current.get("scores") or {}).get(name, 0.0)) - float((previous.get("scores") or {}).get(name, 0.0)), 3)
        for name in dimensions
    }
    overall_delta = round(float(current.get("overall_score") or 0.0) - float(previous.get("overall_score") or 0.0), 3)
    if overall_delta > 0.02:
        trend = "improved"
    elif overall_delta < -0.02:
        trend = "regressed"
    else:
        trend = "unchanged"
    return {
        "previous_task_id": previous.get("task_id"),
        "current_task_id": current.get("task_id"),
        "overall_delta": overall_delta,
        "category_deltas": category_deltas,
        "trend": trend,
    }


def score_synthesized_entry(
    synthesized_entry: dict[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    fixtures = load_eval_fixtures(root)
    fixture = next((item for item in fixtures if item.get("fixture_family") == "proposal_backlog_synthesis" and not item.get("_issues")), None)
    if fixture is None:
        return {
            "suite_version": 1,
            "mode": "no_fixture",
            "fixture_id": None,
            "fixture_family": None,
            "task_id": synthesized_entry.get("ticket_id_placeholder"),
            "scores": {},
            "overall_score": 0.0,
            "threshold": 0.0,
            "passed": True,
            "mandatory_artifacts": {"present": [], "missing": []},
            "dimension_failures": [],
        }
    subject = {
        "task": {
            "id": synthesized_entry.get("ticket_id_placeholder"),
            "area": synthesized_entry.get("area"),
        },
        "automation_result": {
            "classification": "accepted" if synthesized_entry.get("operator_approval", {}).get("approved") else "draft",
            "summary": synthesized_entry.get("rationale"),
            "steps": [],
            "changed_files": [],
        },
        "run_dir": Path(synthesized_entry.get("artifact_dir") or ROOT),
        "standards": load_repo_local_standards(Path(root or builder_root()).expanduser().resolve()),
        "step_lookup": {},
        "synthesized_entry": synthesized_entry,
    }
    result = score_fixture_subject(fixture, subject)
    result["fixture_path"] = fixture.get("_path")
    result["mode"] = "synthesis_fixture"
    result["task_id"] = synthesized_entry.get("ticket_id_placeholder")
    return result


def aggregate_replay_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    families: dict[str, dict[str, Any]] = {}
    for result in results:
        family = str(result.get("fixture_family") or "unknown")
        bucket = families.setdefault(
            family,
            {"fixture_family": family, "runs": 0, "passes": 0, "overall_scores": [], "category_totals": {}},
        )
        bucket["runs"] += 1
        if result.get("passed"):
            bucket["passes"] += 1
        bucket["overall_scores"].append(float(result.get("overall_score") or 0.0))
        for name, score in (result.get("scores") or {}).items():
            bucket["category_totals"].setdefault(name, []).append(float(score))
    for bucket in families.values():
        scores = bucket.pop("overall_scores")
        bucket["average_overall_score"] = round(sum(scores) / len(scores), 3) if scores else 0.0
        bucket["pass_rate"] = round(bucket["passes"] / bucket["runs"], 3) if bucket["runs"] else 0.0
        bucket["average_category_scores"] = {
            name: round(sum(values) / len(values), 3)
            for name, values in sorted(bucket.pop("category_totals").items())
        }
    return {"generated_at": None, "families": sorted(families.values(), key=lambda item: item["fixture_family"])}


def latest_comparable_history_eval(
    task: dict[str, Any],
    current_eval: dict[str, Any],
    *,
    exclude_run_dir: Path | None = None,
    root: Path | None = None,
) -> dict[str, Any] | None:
    repo_root = Path(root or builder_root()).expanduser().resolve()
    history_dir = repo_root / "task_history"
    current_family = current_eval.get("fixture_family")
    current_task_family = task_family(str(task.get("id") or ""))
    for history_path in sorted(history_dir.glob("*.yml"), reverse=True):
        payload = load_data(history_path)
        history_run_dir = payload.get("run_log_dir")
        if exclude_run_dir is not None and history_run_dir and str(exclude_run_dir) == str(history_run_dir):
            continue
        if task_family(str(payload.get("task_id") or "")) != current_task_family:
            continue
        replay = replay_history_eval(history_path, root=repo_root)
        if replay.get("fixture_family") == current_family:
            return replay
    return None


def _emit_payload(payload: dict[str, Any], output_path: str | None) -> int:
    if output_path:
        write_json(Path(output_path), payload)
    print(json.dumps(payload, indent=2))
    return 0


def _cli_replay(paths: list[str], *, output_path: str | None = None) -> int:
    results = [replay_history_eval(Path(path), root=ROOT) for path in paths]
    payload = {"results": results, "aggregate": aggregate_replay_results(results)}
    return _emit_payload(payload, output_path)


def _cli_compare(paths: list[str], *, output_path: str | None = None) -> int:
    if len(paths) != 2:
        raise SystemExit("--compare requires exactly two task_history files")
    previous = replay_history_eval(Path(paths[0]), root=ROOT)
    current = replay_history_eval(Path(paths[1]), root=ROOT)
    payload = {"previous": previous, "current": current, "comparison": compare_eval_results(previous, current)}
    return _emit_payload(payload, output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Private builder eval suite")
    parser.add_argument("--replay", nargs="+", help="Replay one or more task_history files through the private eval suite.")
    parser.add_argument("--compare", nargs="+", help="Compare two task_history files.")
    parser.add_argument("--output", help="Optional JSON output path for replay or compare results.")
    args = parser.parse_args()
    if args.replay:
        return _cli_replay(args.replay, output_path=args.output)
    if args.compare:
        return _cli_compare(args.compare, output_path=args.output)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
