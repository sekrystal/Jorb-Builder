# Operator TUI

Launch the terminal operator surface with:

```bash
python3 scripts/operator_tui.py
```

For a single snapshot without entering fullscreen mode:

```bash
python3 scripts/operator_tui.py --once
```

Supported safe operator actions:

- `r`: refresh canonical snapshot
- `b`: inspect current blocker detail
- `p`: approve a proposal by id
- `a`: apply a synthesized entry by id
- `t`: retry blocked task recovery through `--repair-state`
- `o`: show latest run directory
- `i`: inspect current artifact panel
- `q`: quit

Design constraints:

- reads canonical repo state only
- does not maintain separate task truth
- highlights blocker and next recommended action first
- uses stage progression instead of percent bars as the primary progress model
