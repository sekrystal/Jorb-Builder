# Operator TUI

Launch the terminal operator surface with:

```bash
python3 scripts/operator_tui.py
```

For a single snapshot without entering fullscreen mode:

```bash
python3 scripts/operator_tui.py --once
```

You can also preselect the visible loop mode for snapshot rendering:

```bash
python3 scripts/operator_tui.py --once --loop-mode until-failure
```

Supported safe operator actions:

- `r`: refresh canonical snapshot
- `x`: run the builder using the current loop mode
- `m`: toggle loop mode between `single-run` and `until-failure`
- `b`: inspect an open blocker from a numbered selector
- `p`: approve a draft proposal from a numbered selector
- `a`: apply a synthesized draft entry from a numbered selector
- `t`: retry blocked task recovery through `--repair-state`
- `o`: show latest run directory
- `i`: inspect current artifact panel
- `q`: quit

Design constraints:

- reads canonical repo state only
- does not maintain separate task truth
- highlights blocker and next recommended action first
- uses stage progression instead of percent bars as the primary progress model
- exposes loop mode and explicit stop conditions in the operator header
- normalizes event feed rows while preserving timestamps and provenance
