#!/bin/zsh
set -euo pipefail

ROOT="${HOME}/projects/jorb-builder"

ACTIVE_STATE=$(python3 - <<'PY'
from pathlib import Path
import json
path = Path.home() / 'projects' / 'jorb-builder' / 'active_task.yml'
active = json.loads(path.read_text(encoding='utf-8'))
print(active.get('state') or 'idle')
PY
)

ACTIVE_TASK=$(python3 - <<'PY'
from pathlib import Path
import json
path = Path.home() / 'projects' / 'jorb-builder' / 'active_task.yml'
active = json.loads(path.read_text(encoding='utf-8'))
print(active.get('task_id') or '')
PY
)

if [[ -n "$ACTIVE_TASK" && "$ACTIVE_STATE" != "idle" ]]; then
  echo "ACTIVE_TASK_ALREADY_EXISTS $ACTIVE_TASK ($ACTIVE_STATE)"
  echo "Next steps:"
  echo "- If you have not rendered a packet yet: python3 ~/projects/jorb-builder/scripts/render_packet.py"
  echo "- If you already handed the packet to Codex: python3 ~/projects/jorb-builder/scripts/mark_in_progress.py"
  echo "- If Codex finished: python3 ~/projects/jorb-builder/scripts/verify_task.py"
  echo '- If the task is stale: python3 ~/projects/jorb-builder/scripts/abandon_task.py --reason "why"'
  echo "- If you need to verify paths first: python3 ~/projects/jorb-builder/scripts/bootstrap_check.py"
  exit 0
fi

python3 "$ROOT/scripts/bootstrap_check.py"
python3 "$ROOT/scripts/select_task.py"
PROMPT_FILE=$(python3 "$ROOT/scripts/render_packet.py")

echo
echo "=== GIVE THIS PACKET TO CODEX ==="
echo "Packet file: $PROMPT_FILE"
echo
echo "After you hand it to Codex, run: python3 ~/projects/jorb-builder/scripts/mark_in_progress.py"
echo
cat "$PROMPT_FILE"
