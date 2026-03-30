# Operator Review Flow

Operator review happens through the proposal queue, not by silent autonomous edits.

## Flow

1. builder writes `feedback_signals.json`
2. builder writes or refreshes `backlog_proposals.json`
3. operator inspects proposals through:
   - `scripts/show_status.py`
   - `scripts/feedback_engine.py --status`
4. operator updates proposal status with:
   - `scripts/feedback_engine.py --review <proposal_id> <status>`

## Outcomes

- accepted proposals become structured memory lessons
- rejected proposals are marked invalidated in memory
- draft proposals remain advisory until reviewed
