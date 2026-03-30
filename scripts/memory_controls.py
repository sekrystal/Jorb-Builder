#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import MEMORY_OVERRIDES_FILE, builder_root, build_memory_store, load_data, write_data


ROOT = builder_root()
OVERRIDES = ROOT / MEMORY_OVERRIDES_FILE
STORE = ROOT / "memory_store.json"


def load_overrides() -> dict[str, Any]:
    if not OVERRIDES.exists():
        return {"memory_status": {}, "manual_entries": [], "pins": []}
    payload = load_data(OVERRIDES)
    payload.setdefault("memory_status", {})
    payload.setdefault("manual_entries", [])
    payload.setdefault("pins", [])
    return payload


def save_overrides(payload: dict[str, Any]) -> None:
    write_data(OVERRIDES, payload)


def find_entry(store: dict[str, Any], memory_id: str) -> dict[str, Any] | None:
    for entry in store.get("entries", []):
        if entry.get("memory_id") == memory_id:
            return entry
    return None


def cmd_list(args: argparse.Namespace) -> int:
    store = build_memory_store(ROOT)
    write_data(STORE, store)
    entries = [entry for entry in store.get("entries", []) if not args.status or entry.get("status") == args.status]
    entries = entries[: args.limit]
    print(json.dumps({"generated_at": store.get("generated_at"), "entries": entries}, indent=2))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    store = build_memory_store(ROOT)
    write_data(STORE, store)
    entry = find_entry(store, args.memory_id)
    if entry is None:
        print(json.dumps({"error": f"unknown memory_id: {args.memory_id}"}, indent=2))
        return 1
    print(json.dumps(entry, indent=2))
    return 0


def cmd_invalidate(args: argparse.Namespace) -> int:
    overrides = load_overrides()
    overrides.setdefault("memory_status", {})
    overrides["memory_status"][args.memory_id] = {
        "status": "invalidated",
        "status_reason": args.reason or "operator_invalidated",
        "pinned": False,
    }
    save_overrides(overrides)
    write_data(STORE, build_memory_store(ROOT))
    print(json.dumps({"updated": args.memory_id, "status": "invalidated"}, indent=2))
    return 0


def cmd_supersede(args: argparse.Namespace) -> int:
    overrides = load_overrides()
    overrides.setdefault("memory_status", {})
    overrides["memory_status"][args.memory_id] = {
        "status": "superseded",
        "status_reason": args.reason or "operator_superseded",
        "superseded_by": args.by,
        "pinned": False,
    }
    save_overrides(overrides)
    write_data(STORE, build_memory_store(ROOT))
    print(json.dumps({"updated": args.memory_id, "status": "superseded", "superseded_by": args.by}, indent=2))
    return 0


def cmd_pin(args: argparse.Namespace) -> int:
    overrides = load_overrides()
    overrides.setdefault("memory_status", {})
    current = overrides["memory_status"].get(args.memory_id, {})
    current.update({"pinned": True, "status": "pinned", "status_reason": args.reason or "operator_pinned"})
    overrides["memory_status"][args.memory_id] = current
    save_overrides(overrides)
    write_data(STORE, build_memory_store(ROOT))
    print(json.dumps({"updated": args.memory_id, "status": "pinned"}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and correct builder memory state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--status", default=None)
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.set_defaults(func=cmd_list)

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("memory_id")
    show_parser.set_defaults(func=cmd_show)

    invalidate_parser = subparsers.add_parser("invalidate")
    invalidate_parser.add_argument("memory_id")
    invalidate_parser.add_argument("--reason", default=None)
    invalidate_parser.set_defaults(func=cmd_invalidate)

    supersede_parser = subparsers.add_parser("supersede")
    supersede_parser.add_argument("memory_id")
    supersede_parser.add_argument("--by", required=True)
    supersede_parser.add_argument("--reason", default=None)
    supersede_parser.set_defaults(func=cmd_supersede)

    pin_parser = subparsers.add_parser("pin")
    pin_parser.add_argument("memory_id")
    pin_parser.add_argument("--reason", default=None)
    pin_parser.set_defaults(func=cmd_pin)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
