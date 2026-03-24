#!/usr/bin/env python3
from __future__ import annotations

from common import load_config, product_repo_path, builder_path_from_config


def main() -> int:
    config = load_config()
    builder_label = config["paths"]["builder_root"]
    product_label = config["paths"]["product_repo"]
    builder = builder_path_from_config("builder_root")
    product = product_repo_path()

    print("=== Builder Bootstrap Check ===")
    print(f"Builder workspace: {builder_label}")
    print(f"Product repo: {product_label}")

    missing = []
    if not builder.exists():
        missing.append(("builder", builder_label))
    if not product.exists():
        missing.append(("product", product_label))

    if not missing:
        print("OK: both builder workspace and product repo exist.")
        print("Next steps:")
        print("1. cd ~/projects/jorb-builder")
        print("2. python3 scripts/show_status.py")
        print("3. ./scripts/run_once.sh")
        return 0

    print("MISSING_PATHS:")
    for label, path in missing:
        print(f"- {label}: {path}")

    print("Next steps:")
    if not builder.exists():
        print("1. Create ~/projects/jorb-builder and rerun this check.")
    if not product.exists():
        print("1. Clone or move the Jorb product repo to ~/projects/jorb.")
    print("2. Rerun: python3 scripts/bootstrap_check.py")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
