#!/usr/bin/env python3
from __future__ import annotations

from common import build_memory_store, builder_root, load_data
from backlog_synthesis import synthesis_summary_for_operator
from feedback_engine import feedback_summary_for_operator

ROOT = builder_root()
BACKLOG = ROOT / "backlog.yml"
STATUS = ROOT / "status.yml"
ACTIVE = ROOT / "active_task.yml"
BLOCKERS = ROOT / "blockers"
TASK_HISTORY = ROOT / "task_history"
RUN_LEDGER = ROOT / "run_ledger.json"
MEMORY_STORE = ROOT / "memory_store.json"


def main() -> int:
    backlog = load_data(BACKLOG)
    status = load_data(STATUS)
    active = load_data(ACTIVE)
    ledger = load_data(RUN_LEDGER) if RUN_LEDGER.exists() else {}
    memory_store = build_memory_store(ROOT)
    feedback = feedback_summary_for_operator(ROOT)
    synthesis = synthesis_summary_for_operator(ROOT)

    print("=== Jorb Builder Status ===")
    print(f"State: {status.get('state')}")
    print(f"State meaning: {(status.get('state_legend') or {}).get(status.get('state'), 'unknown')}")
    focus = status.get("roadmap_focus", {})
    print(f"Roadmap focus: {focus.get('milestone')} / {focus.get('theme')}")
    print(f"Active task: {active.get('task_id') or 'none'}")
    if active.get("task_id"):
        print(f"  Title: {active.get('title')}")
        print(f"  State: {active.get('state')}")
        print(f"  Attempt: {active.get('attempt')}")
        print(f"  Started at: {active.get('started_at')}")
        print(f"  Handed to Codex at: {active.get('handed_to_codex_at')}")
        print(f"  Prompt file: {active.get('prompt_file')}")

    print("\nCanonical operator view:")
    print(f"- current_task: {ledger.get('current_task') or 'none'}")
    print(f"- current_stage: {ledger.get('current_stage') or 'none'}")
    print(f"- run_state: {ledger.get('run_state') or 'unknown'}")
    print(f"- current_blocker: {ledger.get('current_blocker') or 'none'}")
    print(f"- last_successful_checkpoint: {ledger.get('last_successful_checkpoint') or 'none'}")
    artifact = ledger.get("artifact_completeness") or {}
    print(f"- artifact_present: {', '.join(artifact.get('present', [])) or 'none'}")
    print(f"- artifact_missing: {', '.join(artifact.get('missing', [])) or 'none'}")
    failure = ledger.get("failure_taxonomy") or {}
    print(f"- failure_class: {failure.get('failure_class') or 'none'}")
    print(f"- recovery_action: {failure.get('recovery_action') or 'none'}")
    eval_result = ledger.get("eval_result") or {}
    regression = eval_result.get("regression_vs_prior") or {}
    print(f"- eval_overall_score: {eval_result.get('overall_score', 'n/a')}")
    print(f"- eval_fixture_family: {eval_result.get('fixture_family') or 'none'}")
    print(f"- eval_threshold: {eval_result.get('threshold', 'n/a')}")
    print(f"- eval_passed: {eval_result.get('passed', 'n/a')}")
    print(f"- eval_blocked_acceptance: {ledger.get('eval_blocked_acceptance')}")
    print(f"- eval_regression_trend: {regression.get('trend') or 'none'}")
    print(f"- eval_regression_delta: {regression.get('overall_delta', 'n/a')}")
    print(f"- next_recommended_action: {ledger.get('next_recommended_action') or 'none'}")

    print("\nMemory index:")
    counts = memory_store.get("counts_by_status") or {}
    print(f"- generated_at: {memory_store.get('generated_at') or 'none'}")
    print(f"- total_entries: {len(memory_store.get('entries', []))}")
    print(f"- active: {counts.get('active', 0)}")
    print(f"- stale: {counts.get('stale', 0)}")
    print(f"- pinned: {counts.get('pinned', 0)}")
    print(f"- invalidated: {counts.get('invalidated', 0)}")

    print("\nFeedback loop:")
    print(f"- signal_count: {feedback.get('signal_count', 0)}")
    print(f"- proposal_count: {feedback.get('proposal_count', 0)}")
    print(f"- draft_proposals: {feedback.get('draft_count', 0)}")
    top_draft = feedback.get("top_draft") or {}
    print(f"- top_draft_title: {top_draft.get('title') or 'none'}")

    print("\nBacklog synthesis:")
    print(f"- synthesized_entries: {synthesis.get('entry_count', 0)}")
    print(f"- draft_entries: {synthesis.get('draft_count', 0)}")
    print(f"- applied_entries: {synthesis.get('applied_count', 0)}")
    print(f"- eval_blocked_entries: {synthesis.get('blocked_count', 0)}")
    top_synth = synthesis.get("top_draft") or {}
    print(f"- top_synthesized_title: {top_synth.get('title') or 'none'}")
    print(f"- top_synthesized_eval_score: {synthesis.get('top_draft_eval_score', 'n/a')}")
    print(f"- top_synthesized_eval_passed: {synthesis.get('top_draft_eval_passed', 'n/a')}")

    print("\nNext ready tasks:")
    ready = [task for task in backlog.get("tasks", []) if task.get("status") in {"ready", "retry_ready"}]
    ready.sort(key=lambda item: (item.get("priority", 999), item.get("id", "")))
    if not ready:
        print("- none")
    for task in ready[:5]:
        print(f"- {task['id']} [{task['status']}] p{task.get('priority', '?')}: {task['title']}")

    print("\nOpen blockers:")
    blocker_files = sorted(BLOCKERS.glob("*.yml")) if BLOCKERS.exists() else []
    open_count = 0
    for file in blocker_files:
        data = load_data(file)
        if data.get("status") == "open":
            open_count += 1
            print(f"- {data.get('id')}: {data.get('title')}")
    if open_count == 0:
        print("- none")

    print("\nRecent completions:")
    history_files = sorted(TASK_HISTORY.glob("*.yml"), reverse=True)[:5]
    if not history_files:
        print("- none")
    for file in history_files:
        data = load_data(file)
        print(f"- {data.get('task_id')}: {data.get('status')} at {data.get('completed_at')}")

    print("\nStats:")
    for key, value in (status.get("stats") or {}).items():
        print(f"- {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
