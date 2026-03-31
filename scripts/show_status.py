#!/usr/bin/env python3
from __future__ import annotations

from operator_state import build_operator_snapshot


def _render_stage_line(stages: list[dict]) -> str:
    status_icon = {
        "complete": "[x]",
        "current": "[>]",
        "failed": "[!]",
        "skipped": "[-]",
        "pending": "[ ]",
    }
    return " ".join(f"{status_icon.get(item['status'], '[ ]')} {item['label']}" for item in stages)


def main() -> int:
    snapshot = build_operator_snapshot()
    backlog_diag = snapshot["backlog_diagnostics"]
    status = snapshot["status"]
    active = snapshot["active"]
    ledger = snapshot["ledger"]
    memory_store = snapshot["memory_store"]
    feedback = snapshot["feedback"]
    proposals = snapshot["proposals"]
    synthesis = snapshot["synthesis"]
    artifact = snapshot["artifact_panel"]
    eval_result = snapshot["eval_result"]
    latest_blocker = snapshot["latest_blocker"] or {}

    print("=== Jorb Builder Status ===")
    print(f"State: {status.get('state')}")
    print(f"State meaning: {(status.get('state_legend') or {}).get(status.get('state'), 'unknown')}")
    focus = status.get("roadmap_focus", {})
    print(f"Roadmap focus: {focus.get('milestone')} / {focus.get('theme')}")
    print(f"Active task: {active.get('task_id') or 'none'}")
    print(f"Last task: {status.get('last_task_id') or 'none'}")
    if active.get("task_id"):
        print(f"  Title: {active.get('title')}")
        print(f"  State: {active.get('state')}")
        print(f"  Attempt: {active.get('attempt')}")
        print(f"  Started at: {active.get('started_at')}")
        print(f"  Prompt file: {active.get('prompt_file')}")

    print("\nCurrent run summary:")
    print(f"- current_task: {ledger.get('current_task') or active.get('task_id') or 'none'}")
    print(f"- current_stage: {ledger.get('current_stage') or 'none'}")
    print(f"- run_state: {ledger.get('run_state') or status.get('state') or 'unknown'}")
    print(f"- current_blocker: {ledger.get('current_blocker') or latest_blocker.get('diagnosis') or 'none'}")
    print(f"- last_successful_checkpoint: {ledger.get('last_successful_checkpoint') or 'none'}")
    print(f"- latest_run_dir: {snapshot.get('latest_run_dir') or 'none'}")
    print(f"- next_recommended_action: {snapshot.get('next_recommended_action') or 'none'}")

    print("\nStage progress:")
    print(f"- {_render_stage_line(snapshot['stage_progress'])}")

    print("\nArtifacts and eval:")
    print(f"- expected_artifacts: {', '.join(artifact.get('expected', [])) or 'none'}")
    print(f"- present_artifacts: {', '.join(artifact.get('present', [])) or 'none'}")
    print(f"- missing_artifacts: {', '.join(artifact.get('missing', [])) or 'none'}")
    print(f"- eval_overall_score: {eval_result.get('overall_score', 'n/a')}")
    print(f"- eval_fixture_family: {eval_result.get('fixture_family') or 'none'}")
    print(f"- eval_threshold: {eval_result.get('threshold', 'n/a')}")
    print(f"- eval_passed: {eval_result.get('passed', 'n/a')}")
    print(f"- judge_result: {snapshot.get('judge_result') or 'none'}")
    print(f"- runtime_proof_expected: {bool((snapshot.get('task') or {}).get('requires_vm_runtime_proof'))}")

    print("\nQueue and backlog evolution:")
    print(f"- ready_tasks: {', '.join(backlog_diag.get('ready_task_ids', [])) or 'none'}")
    print(f"- blocked_tasks: {', '.join(backlog_diag.get('blocked_task_ids', [])) or 'none'}")
    print(f"- accepted_proposals: {proposals.get('accepted_count', 0)}")
    print(f"- draft_proposals: {feedback.get('draft_count', 0)}")
    print(f"- synthesized_entries: {synthesis.get('entry_count', 0)}")
    print(f"- applied_entries: {synthesis.get('applied_count', 0)}")
    print(f"- next_execution_target: {synthesis.get('next_execution_target') or 'none'}")

    print("\nMemory index:")
    counts = memory_store.get("counts_by_status") or {}
    print(f"- generated_at: {memory_store.get('generated_at') or 'none'}")
    print(f"- total_entries: {len(memory_store.get('entries', []))}")
    print(f"- active: {counts.get('active', 0)}")
    print(f"- stale: {counts.get('stale', 0)}")
    print(f"- pinned: {counts.get('pinned', 0)}")
    print(f"- invalidated: {counts.get('invalidated', 0)}")

    print("\nOpen blocker detail:")
    print(f"- blocker_id: {latest_blocker.get('id') or 'none'}")
    print(f"- diagnosis: {latest_blocker.get('diagnosis') or 'none'}")
    print(f"- next_actions: {', '.join(latest_blocker.get('next_actions', [])) or 'none'}")

    print("\nRecent events:")
    if not snapshot["event_feed"]:
        print("- none")
    for item in snapshot["event_feed"][:5]:
        print(f"- {item.get('at') or 'unknown'} | {item.get('source')} | {item.get('summary')}")

    print("\nStats:")
    for key, value in snapshot["stats"].items():
        print(f"- {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
