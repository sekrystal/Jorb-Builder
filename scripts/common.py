#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json


def expand_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def builder_root() -> Path:
    return Path(__file__).resolve().parents[1]


def config_path() -> Path:
    return builder_root() / "config.yml"


def load_data(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_data(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_config() -> dict:
    return load_data(config_path())


def product_repo_path() -> Path:
    return expand_path(load_config()["paths"]["product_repo"])


def builder_path_from_config(key: str) -> Path:
    return expand_path(load_config()["paths"][key])
