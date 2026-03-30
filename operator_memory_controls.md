# Operator Memory Controls

Operator controls live in:

- `scripts/memory_controls.py`

Supported actions:

- `list`
- `show <memory_id>`
- `invalidate <memory_id>`
- `supersede <memory_id> --by <memory_id-or-note>`
- `pin <memory_id>`

These commands update `memory_overrides.json`, which is applied on top of derived memory from task history and blockers.

This design avoids mutating canonical historical artifacts while still allowing operator correction.
