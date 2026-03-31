from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time


SCRIPT = Path("/Users/samuelkrystal/projects/jorb-builder/scripts/automate_task_loop.py")
PRIVATE_EVAL_SCRIPT = Path("/Users/samuelkrystal/projects/jorb-builder/scripts/private_eval_suite.py")
MEMORY_CONTROLS_SCRIPT = Path("/Users/samuelkrystal/projects/jorb-builder/scripts/memory_controls.py")
FEEDBACK_ENGINE_SCRIPT = Path("/Users/samuelkrystal/projects/jorb-builder/scripts/feedback_engine.py")
BACKLOG_SYNTHESIS_SCRIPT = Path("/Users/samuelkrystal/projects/jorb-builder/scripts/backlog_synthesis.py")
LIVE_BUILDER_ROOT = Path("/Users/samuelkrystal/projects/jorb-builder")
CANONICAL_FIGMA_SOURCE = "/Users/samuelkrystal/projects/jorb/design/figma"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_valid_phase4_feature_spec(module, run_dir: Path, task: dict, standards: dict) -> None:
    if not hasattr(module, "phase4_feature_spec_text"):
        module = _load_script_module(run_dir.parents[2] if len(run_dir.parents) >= 3 else None)
    (run_dir / "compiled_feature_spec.md").write_text(
        module.phase4_feature_spec_text(task, standards),
        encoding="utf-8",
    )


def _repo_local_standards_payload(tmp_path: Path) -> dict:
    return {
        "agents_exists": True,
        "agents_path": str(tmp_path / "AGENTS.md"),
        "agents_core_expectations": [
            "Treat backlog truth, config, run logs, and generated artifacts as first-class system inputs."
        ],
        "agents_execution_roles": {
            "Planner": "compile the feature/system understanding artifact.",
            "Judge": "accept or reject only from evidence.",
        },
        "skills_exists": True,
        "skills_dir": str(tmp_path / "skills"),
        "skill_files": ["skills/README.md"],
        "skill_entries": [
            {
                "file": "skills/README.md",
                "name": "phase4_enforcement",
                "summary": "require planner/architect/judge artifacts and evidence before acceptance.",
            }
        ],
    }


def _active_run_dir(builder_root: Path) -> Path:
    active = _json(builder_root / "active_task.yml")
    run_log_dir = active.get("run_log_dir")
    if not run_log_dir:
        status = _json(builder_root / "status.yml")
        if status.get("state") == "completed":
            run_dirs = sorted((builder_root / "run_logs").glob("*"))
            return run_dirs[-1]
        raise AssertionError("active_task.yml has no run_log_dir")
    return Path(run_log_dir)


def _load_script_module(builder_root: Path | None = None):
    common_dir = str(SCRIPT.parent)
    inserted = False
    previous_root = os.environ.get("JORB_BUILDER_ROOT")
    if builder_root is not None:
        os.environ["JORB_BUILDER_ROOT"] = str(builder_root)
    if common_dir not in sys.path:
        sys.path.insert(0, common_dir)
        inserted = True
    try:
        sys.modules.pop("common", None)
        sys.modules.pop("automate_task_loop_test_module", None)
        spec = importlib.util.spec_from_file_location("automate_task_loop_test_module", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted and sys.path and sys.path[0] == common_dir:
            sys.path.pop(0)
        if builder_root is not None:
            if previous_root is None:
                os.environ.pop("JORB_BUILDER_ROOT", None)
            else:
                os.environ["JORB_BUILDER_ROOT"] = previous_root


def _load_common_module(builder_root: Path | None = None):
    common_path = SCRIPT.parent / "common.py"
    common_dir = str(SCRIPT.parent)
    inserted = False
    previous_root = os.environ.get("JORB_BUILDER_ROOT")
    if builder_root is not None:
        os.environ["JORB_BUILDER_ROOT"] = str(builder_root)
    if common_dir not in sys.path:
        sys.path.insert(0, common_dir)
        inserted = True
    try:
        sys.modules.pop("common", None)
        spec = importlib.util.spec_from_file_location("common_test_module", common_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted and sys.path and sys.path[0] == common_dir:
            sys.path.pop(0)
        if builder_root is not None:
            if previous_root is None:
                os.environ.pop("JORB_BUILDER_ROOT", None)
            else:
                os.environ["JORB_BUILDER_ROOT"] = previous_root


def _load_private_eval_module(builder_root: Path | None = None):
    common_dir = str(SCRIPT.parent)
    inserted = False
    previous_root = os.environ.get("JORB_BUILDER_ROOT")
    if builder_root is not None:
        os.environ["JORB_BUILDER_ROOT"] = str(builder_root)
    if common_dir not in sys.path:
        sys.path.insert(0, common_dir)
        inserted = True
    try:
        sys.modules.pop("common", None)
        sys.modules.pop("private_eval_suite_test_module", None)
        spec = importlib.util.spec_from_file_location("private_eval_suite_test_module", PRIVATE_EVAL_SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted and sys.path and sys.path[0] == common_dir:
            sys.path.pop(0)
        if builder_root is not None:
            if previous_root is None:
                os.environ.pop("JORB_BUILDER_ROOT", None)
            else:
                os.environ["JORB_BUILDER_ROOT"] = previous_root


def _load_feedback_module(builder_root: Path | None = None):
    common_dir = str(SCRIPT.parent)
    inserted = False
    previous_root = os.environ.get("JORB_BUILDER_ROOT")
    if builder_root is not None:
        os.environ["JORB_BUILDER_ROOT"] = str(builder_root)
    if common_dir not in sys.path:
        sys.path.insert(0, common_dir)
        inserted = True
    try:
        sys.modules.pop("common", None)
        sys.modules.pop("feedback_engine_test_module", None)
        spec = importlib.util.spec_from_file_location("feedback_engine_test_module", FEEDBACK_ENGINE_SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted and sys.path and sys.path[0] == common_dir:
            sys.path.pop(0)
        if builder_root is not None:
            if previous_root is None:
                os.environ.pop("JORB_BUILDER_ROOT", None)
            else:
                os.environ["JORB_BUILDER_ROOT"] = previous_root


def _load_backlog_synthesis_module(builder_root: Path | None = None):
    common_dir = str(SCRIPT.parent)
    inserted = False
    previous_root = os.environ.get("JORB_BUILDER_ROOT")
    if builder_root is not None:
        os.environ["JORB_BUILDER_ROOT"] = str(builder_root)
    if common_dir not in sys.path:
        sys.path.insert(0, common_dir)
        inserted = True
    try:
        sys.modules.pop("common", None)
        sys.modules.pop("private_eval_suite", None)
        sys.modules.pop("backlog_synthesis_test_module", None)
        spec = importlib.util.spec_from_file_location("backlog_synthesis_test_module", BACKLOG_SYNTHESIS_SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted and sys.path and sys.path[0] == common_dir:
            sys.path.pop(0)
        if builder_root is not None:
            if previous_root is None:
                os.environ.pop("JORB_BUILDER_ROOT", None)
            else:
                os.environ["JORB_BUILDER_ROOT"] = previous_root


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_eval_fixture(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run(cmd: list[str], cwd: Path, *, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["JORB_BUILDER_ROOT"] = str(cwd)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, env=env)


def _run_interruptible(cmd: list[str], cwd: Path, *, extra_env: dict[str, str] | None = None) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["JORB_BUILDER_ROOT"] = str(cwd)
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen(cmd, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)


def _git(cmd: list[str], cwd: Path) -> None:
    subprocess.run(["git", *cmd], cwd=str(cwd), check=True, capture_output=True, text=True)


def _init_bare_remote(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare", str(path)], check=True, capture_output=True, text=True)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(["init"], path)
    _git(["config", "user.name", "Builder Test"], path)
    _git(["config", "user.email", "builder@example.com"], path)
    (path / ".gitignore").write_text(".pytest_cache\n", encoding="utf-8")
    _git(["add", ".gitignore"], path)
    _git(["commit", "-m", "init"], path)


def _write_activate_script(venv_dir: Path) -> None:
    activate = venv_dir / "bin" / "activate"
    activate.parent.mkdir(parents=True, exist_ok=True)
    activate.write_text(
        "\n".join(
            [
                f'export VIRTUAL_ENV="{venv_dir}"',
                'export PATH="$VIRTUAL_ENV/bin:$PATH"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_fake_codex(path: Path, *, relative_output: str, last_message: str = "fake codex applied change\n") -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                "",
                "argv = sys.argv[1:]",
                "output_file = None",
                "for index, item in enumerate(argv):",
                "    if item == '-o' and index + 1 < len(argv):",
                "        output_file = Path(argv[index + 1])",
                "prompt = sys.stdin.read()",
                f"target = Path.cwd() / {relative_output!r}",
                "target.parent.mkdir(parents=True, exist_ok=True)",
                "target.write_text('applied by fake codex\\n' + prompt, encoding='utf-8')",
                "if output_file is not None:",
                f"    output_file.write_text({last_message!r}, encoding='utf-8')",
                "sys.stdout.write(prompt[:80])",
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_fake_ssh(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os",
                "import sys",
                "from pathlib import Path",
                "remote = sys.argv[-1] if len(sys.argv) > 1 else ''",
                "log_path = os.environ.get('FAKE_SSH_LOG')",
                "if log_path:",
                "    with Path(log_path).open('a', encoding='utf-8') as handle:",
                "        handle.write(remote + '\\n')",
                "fail_match = os.environ.get('FAKE_SSH_FAIL_MATCH')",
                "if fail_match and fail_match in remote:",
                "    sys.stderr.write(f'simulated ssh failure for: {fail_match}\\n')",
                "    sys.exit(int(os.environ.get('FAKE_SSH_FAIL_CODE', '1')))",
                "sys.stdout.write('fake ssh ok\\n')",
                "sys.exit(0)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_fake_codex_without_output(path: Path, *, relative_output: str) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                "prompt = sys.stdin.read()",
                f"target = Path.cwd() / {relative_output!r}",
                "target.parent.mkdir(parents=True, exist_ok=True)",
                "target.write_text('applied without output\\n' + prompt, encoding='utf-8')",
                "sys.stdout.write('ok')",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_fake_codex_no_change(path: Path, *, last_message: str = "verified existing state\n") -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                "",
                "argv = sys.argv[1:]",
                "output_file = None",
                "for index, item in enumerate(argv):",
                "    if item == '-o' and index + 1 < len(argv):",
                "        output_file = Path(argv[index + 1])",
                "sys.stdin.read()",
                "if output_file is not None:",
                f"    output_file.write_text({last_message!r}, encoding='utf-8')",
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_fake_codex_hung(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import signal",
                "import sys",
                "import time",
                "",
                "def _handle(signum, frame):",
                "    sys.stderr.write(f'terminated by signal {signum}\\n')",
                "    sys.stderr.flush()",
                "    sys.exit(0)",
                "",
                "signal.signal(signal.SIGTERM, _handle)",
                "signal.signal(signal.SIGINT, _handle)",
                "sys.stdin.read()",
                "time.sleep(3600)",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_fake_codex_transport_failure(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import sys",
                "sys.stdin.read()",
                "sys.stderr.write('to read backfill state at /Users/test/.codex: error returned from database: (code: 8) attempt to write a readonly database\\n')",
                "sys.stderr.write('ERROR: stream disconnected before completion: error sending request for url (https://chatgpt.com/backend-api/codex/responses)\\n')",
                "sys.stderr.write('channel closed\\n')",
                "sys.exit(1)",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_fake_codex_slow(path: Path, *, relative_output: str, sleep_seconds: int = 2, last_message: str = "slow codex ok\n") -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                "import time",
                "",
                "argv = sys.argv[1:]",
                "output_file = None",
                "for index, item in enumerate(argv):",
                "    if item == '-o' and index + 1 < len(argv):",
                "        output_file = Path(argv[index + 1])",
                "prompt = sys.stdin.read()",
                f"time.sleep({sleep_seconds})",
                f"target = Path.cwd() / {relative_output!r}",
                "target.parent.mkdir(parents=True, exist_ok=True)",
                "target.write_text('applied by slow codex\\n' + prompt, encoding='utf-8')",
                "if output_file is not None:",
                f"    output_file.write_text({last_message!r}, encoding='utf-8')",
                "sys.stdout.write('done')",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def _apply_product_facing_ux_fields(task: dict, *, mapping: list[str] | None = None, deviations: list[str] | None = None) -> None:
    task["product_facing_ux"] = True
    task["design_section_mapping"] = mapping or [f"Hero section in {CANONICAL_FIGMA_SOURCE} -> jobs list"]
    task["intentional_design_deviations"] = deviations if deviations is not None else ["none"]
    task["product_first_acceptance_checks"] = [
        "confirm hierarchy keeps core jobs value ahead of secondary controls",
        "confirm prohibited surfaces stay out of the primary user-facing shell",
        "confirm backend wiring or real data alone is not treated as sufficient UX acceptance evidence",
    ]
    task["primary_ux_prohibited_surfaces"] = [
        "source matrix",
        "discovery internals",
        "learning",
        "autonomy ops",
        "agent activity",
        "investigations",
        "diagnostics",
        "operator controls",
    ]


def _progress_events(run_dir: Path) -> list[dict]:
    return [json.loads(line) for line in (run_dir / "progress.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def _ignore_path_in_git_status(repo: Path, pattern: str) -> None:
    exclude = repo / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write(f"{pattern}\n")


def _commit_allowlisted_product_file(product_repo: Path, relative_path: str, content: str) -> None:
    path = product_repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(["add", relative_path], product_repo)
    _git(["commit", "-m", f"seed {relative_path}"], product_repo)
    _git(["push", "origin", "HEAD"], product_repo)


def _base_status() -> dict:
    return {
        "version": 1,
        "state": "packet_rendered",
        "state_legend": {
            "idle": "No active task is currently in flight.",
            "task_selected": "A task has been selected but no packet has been rendered yet.",
            "packet_rendered": "A Codex packet exists and is ready to hand to Codex.",
            "implementing": "The packet has been handed to Codex and code changes are in progress.",
            "verifying": "Deterministic verification is currently running or expected next.",
            "retry_ready": "The task failed verification and is ready for a bounded retry.",
            "blocked": "The task is blocked and waiting for human intervention.",
        },
        "active_task_id": "TASK-1",
        "last_task_id": None,
        "last_result": None,
        "last_run_at": None,
        "roadmap_focus": {"milestone": "M0", "theme": "builder"},
        "stats": {"completed_tasks": 0, "blocked_tasks": 0, "retry_ready_tasks": 0},
        "notes": [],
    }


def _base_active(task_id: str, prompt_file: Path, run_log_dir: Path, allowlist: list[str]) -> dict:
    return {
        "task_id": task_id,
        "title": task_id,
        "state": "packet_rendered",
        "attempt": 1,
        "started_at": "2026-03-24T00:00:00+00:00",
        "handed_to_codex_at": None,
        "prompt_file": str(prompt_file),
        "run_log_dir": str(run_log_dir),
        "verification_commands": [],
        "allowlist": allowlist,
        "failure_summary": None,
        "notes": [],
    }


def _mark_retry_ready(builder_root: Path, *, handed_to_codex_at: str = "2026-03-24T00:10:00+00:00") -> None:
    active = _json(builder_root / "active_task.yml")
    active["state"] = "blocked"
    active["handed_to_codex_at"] = handed_to_codex_at
    _write_json(builder_root / "active_task.yml", active)

    status = _json(builder_root / "status.yml")
    status["state"] = "blocked"
    status["active_task_id"] = active["task_id"]
    status["last_task_id"] = active["task_id"]
    status["last_result"] = "refined"
    _write_json(builder_root / "status.yml", status)


def _write_prior_vm_refined_result(run_log_dir: Path, *, changed_files: list[str]) -> None:
    _write_json(
        run_log_dir / "automation_result.json",
        {
            "task_id": "TASK-PRODUCT",
            "classification": "refined",
            "finished_at": "2026-03-24T00:20:00+00:00",
            "summary": "VM validation failed after local validation and git push succeeded.",
            "steps": [
                {"name": "retry_check", "outcome": "passed", "detail": "Continuing from existing product repo task changes."},
                {"name": "local_validation", "outcome": "passed", "detail": "All local verification commands passed."},
                {"name": "git", "outcome": "passed", "detail": "git ok"},
                {"name": "vm_validation", "outcome": "refined", "detail": "At least one VM validation command failed."},
            ],
            "changed_files": changed_files,
            "blocker_evidence": [],
            "unproven_runtime_gaps": [
                "VM validation failed after local validation and git push succeeded."
            ],
        },
    )


def _seed_legacy_auth_preflight_blocked_state(builder_root: Path, *, task_id: str) -> None:
    active = _json(builder_root / "active_task.yml")
    active["state"] = "failed"
    active["handed_to_codex_at"] = None
    active["failure_summary"] = "Authentication preflight indicates repeated or interactive prompts are likely."
    _write_json(builder_root / "active_task.yml", active)

    status = _json(builder_root / "status.yml")
    status["state"] = "implementing"
    status["active_task_id"] = task_id
    status["last_task_id"] = task_id
    status["last_result"] = "blocked"
    _write_json(builder_root / "status.yml", status)

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "blocked"
    _write_json(builder_root / "backlog.yml", backlog)

    run_dir = Path(active["run_log_dir"])
    _write_json(
        run_dir / "automation_result.json",
        {
            "task_id": task_id,
            "classification": "blocked",
            "finished_at": "2026-03-25T05:09:25.511690+00:00",
            "summary": "Authentication preflight indicates repeated or interactive prompts are likely.",
            "steps": [{"name": "auth_preflight", "outcome": "blocked", "detail": "auth blocked"}],
            "changed_files": [],
            "blocker_evidence": ["vm ssh auth required"],
            "unproven_runtime_gaps": ["Authentication preflight indicates repeated or interactive prompts are likely."],
        },
    )
    _write_json(
        builder_root / "blockers" / f"BLK-{task_id}.yml",
        {
            "id": f"BLK-{task_id}",
            "title": f"Task {task_id} blocked during automated execution",
            "related_tasks": [task_id],
            "status": "open",
            "diagnosis": "Authentication preflight indicates repeated or interactive prompts are likely.",
        },
    )


def _write_no_changes_refined_result(run_log_dir: Path) -> None:
    _write_json(
        run_log_dir / "automation_result.json",
        {
            "task_id": "TASK-PRODUCT",
            "classification": "refined",
            "finished_at": "2026-03-24T00:21:00+00:00",
            "summary": "Retry-ready task has no product repo changes to continue from.",
            "steps": [
                {"name": "retry_check", "outcome": "refined", "detail": "No product repo changes were found for retry continuation."},
            ],
            "changed_files": [],
            "blocker_evidence": [],
            "unproven_runtime_gaps": [
                "Retry-ready task has no product repo changes to continue from."
            ],
        },
    )


def _base_config(product_repo: Path, builder_root: Path) -> dict:
    return {
        "builder": {"name": "jorb-builder-v1", "version": 1},
        "paths": {
            "product_repo": str(product_repo),
            "builder_root": str(builder_root),
            "run_logs": str(builder_root / "run_logs"),
            "task_history": str(builder_root / "task_history"),
            "blockers": str(builder_root / "blockers"),
        },
        "execution": {"max_retries_per_task": 2, "default_prompt": "implement_feature", "debug_prompt": "debug_failure"},
        "automation": {"mode": "explicit_script", "preserve_step_logs": True},
        "executor": {"mode": "human_gated", "command": None, "shell": "/bin/zsh", "timeout_seconds": 1800},
        "git": {"require_clean_worktree": True, "commit_message_template": "{task_id}: {title}", "push_command": "git push origin HEAD"},
        "vm": {"ssh_target": "vm.example", "ssh_options": [], "product_repo": str(product_repo), "pull_command": "git pull --ff-only", "validation_commands": ["echo ok"], "runtime_validation_commands": ["echo runtime-ok"]},
        "verification": {"default_check_group": "targeted", "required_on_completion": ["preflight"]},
        "rules": {"forbid_builder_code_in_product_repo": True, "require_explicit_allowlist": True, "require_explicit_verification": True, "require_exact_return_format": True, "allow_only_jorb_repo_edits": True},
        "codex": {"worker": "vscode", "mode": "manual_packet"},
    }


def _setup_builder_fixture(tmp_path: Path, *, task_id: str, area: str, allowlist: list[str]) -> tuple[Path, Path, Path, Path]:
    builder_root = tmp_path / "builder"
    product_repo = tmp_path / "jorb"
    builder_remote = tmp_path / "builder-remote.git"
    product_remote = tmp_path / "jorb-remote.git"
    _init_repo(builder_root)
    _init_repo(product_repo)
    _init_bare_remote(builder_remote)
    _init_bare_remote(product_remote)
    _git(["remote", "add", "origin", str(builder_remote)], builder_root)
    _git(["remote", "add", "origin", str(product_remote)], product_repo)
    _git(["push", "-u", "origin", "HEAD"], builder_root)
    _git(["push", "-u", "origin", "HEAD"], product_repo)

    run_log_dir = builder_root / "run_logs" / "run-1"
    run_log_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = run_log_dir / "codex_prompt.md"
    prompt_file.write_text("packet\n", encoding="utf-8")

    backlog = {
        "version": 1,
        "tasks": [
            {
                "id": task_id,
                "title": task_id,
                "type": "infrastructure",
                "area": area,
                "milestone": "M0",
                "priority": 0,
                "status": "selected",
                "retries_used": 0,
                "depends_on": [],
                "prompt": "implement_feature",
                "objective": "obj",
                "why_it_matters": "why",
                "allowlist": allowlist,
                "forbid": [],
                "verification": [],
                "vm_bootstrap": ["echo bootstrap-default"],
                "acceptance": ["a"],
                "notes": [],
            }
        ],
    }
    _write_json(builder_root / "backlog.yml", backlog)
    status = _base_status()
    status["active_task_id"] = task_id
    _write_json(builder_root / "status.yml", status)
    _write_json(builder_root / "active_task.yml", _base_active(task_id, prompt_file, run_log_dir, allowlist))
    _write_json(builder_root / "config.yml", _base_config(product_repo, builder_root))
    (builder_root / "builder_memory.md").write_text("# Memory\n", encoding="utf-8")
    prompts = builder_root / "prompts"
    prompts.mkdir(exist_ok=True)
    (prompts / "implement_feature.md").write_text(
        "\n".join(
            [
                "You are patching the Jorb {target_kind} repo at {target_repo}.",
                "",
                "Task: {task_id}",
                "Title: {title}",
                "",
                "Objective:",
                "{objective}",
                "",
                "Allowed files:",
                "{allowlist}",
                "",
                "Forbidden files:",
                "{forbidlist}",
                "",
                "Verification commands:",
                "{verification_commands}",
                "",
                "Repo-local standards:",
                "{repo_local_standards}",
                "",
                "UX conformance requirements:",
                "{ux_conformance_requirements}",
                "",
                "Failure summary:",
                "{failure_summary}",
                "",
                "Retrieved memory:",
                "{memory_context}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (builder_root / "task_history").mkdir(exist_ok=True)
    (builder_root / "blockers").mkdir(exist_ok=True)
    _git(["add", "."], builder_root)
    _git(["commit", "-m", "builder fixture"], builder_root)
    return builder_root, product_repo, run_log_dir, prompt_file


def test_no_active_task(tmp_path: Path) -> None:
    builder_root = tmp_path / "builder"
    product_repo = tmp_path / "jorb"
    _init_repo(builder_root)
    _init_repo(product_repo)
    _write_json(builder_root / "config.yml", _base_config(product_repo, builder_root))
    _write_json(builder_root / "backlog.yml", {"version": 1, "tasks": []})
    _write_json(builder_root / "status.yml", _base_status())
    _write_json(builder_root / "active_task.yml", {"task_id": None, "title": None, "state": "idle", "attempt": 0, "started_at": None, "handed_to_codex_at": None, "prompt_file": None, "run_log_dir": None, "verification_commands": [], "allowlist": [], "failure_summary": None, "notes": []})
    (builder_root / "builder_memory.md").write_text("# Memory\n", encoding="utf-8")
    (builder_root / "task_history").mkdir(exist_ok=True)
    (builder_root / "blockers").mkdir(exist_ok=True)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert "NO_READY_TASKS_REMAIN" in result.stdout


def test_no_active_task_autoselects_and_executes_ready_task(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-auto"
    _write_fake_codex(fake_codex, relative_output="worker.py", last_message="auto codex ok\n")

    active = _json(builder_root / "active_task.yml")
    active.update(
        {
            "task_id": None,
            "title": None,
            "state": "idle",
            "attempt": 0,
            "started_at": None,
            "handed_to_codex_at": None,
            "prompt_file": None,
            "run_log_dir": None,
            "verification_commands": [],
            "allowlist": [],
            "failure_summary": None,
            "notes": [],
            "target_repo": None,
            "target_kind": None,
        }
    )
    _write_json(builder_root / "active_task.yml", active)

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "active_task.yml", "backlog.yml", "config.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "prepare auto bootstrap"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    assert "NO_READY_TASKS_REMAIN" in result.stdout
    assert (builder_root / "worker.py").exists()
    active_after = _json(builder_root / "active_task.yml")
    assert active_after["task_id"] is None
    task_history = list((builder_root / "task_history").glob("*.yml"))
    assert task_history


def test_no_active_task_with_no_ready_tasks_stays_no_active_task(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    active = _json(builder_root / "active_task.yml")
    active.update(
        {
            "task_id": None,
            "title": None,
            "state": "idle",
            "attempt": 0,
            "started_at": None,
            "handed_to_codex_at": None,
            "prompt_file": None,
            "run_log_dir": None,
            "verification_commands": [],
            "allowlist": [],
            "failure_summary": None,
            "notes": [],
            "target_repo": None,
            "target_kind": None,
        }
    )
    _write_json(builder_root / "active_task.yml", active)

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "accepted"
    _write_json(builder_root / "backlog.yml", backlog)
    _git(["add", "active_task.yml", "backlog.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "prepare no ready task"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert "NO_READY_TASKS_REMAIN" in result.stdout


def test_product_task_can_accept_verified_noop_completion(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-noop"
    _write_fake_codex_no_change(fake_codex)

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    backlog["tasks"][0]["allow_noop_completion"] = True
    backlog["tasks"][0]["verification"] = ["python3 -c \"print('ok')\""]
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)

    _git(["add", "backlog.yml", "config.yml"], builder_root)
    _git(["commit", "-m", "enable verified noop fixture"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "accepted"
    assert payload["summary"] == "Automated loop completed with builder-side local validation success."
    assert any(
        step["name"] == "change_detection"
        and "verified no-op completion" in step["detail"]
        for step in payload["steps"]
    )
    assert any(
        step["name"] == "git"
        and "skipped git add/commit/push for verified no-op completion" in step["detail"]
        for step in payload["steps"]
    )


def test_retry_ready_allow_noop_task_reruns_fresh_without_dirty_changes(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-noop-retry"
    _write_fake_codex_no_change(fake_codex)

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "retry_ready"
    backlog["tasks"][0]["allow_noop_completion"] = True
    backlog["tasks"][0]["verification"] = ["python3 -c \"print('ok')\""]
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)

    _mark_retry_ready(builder_root)
    _git(["add", "backlog.yml", "config.yml", "active_task.yml", "status.yml"], builder_root)
    _git(["commit", "-m", "prepare retry-ready noop fixture"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    assert "Retry-ready task has no builder repo changes to continue from." not in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "accepted"
    assert any(step["name"] == "change_detection" and "verified no-op completion" in step["detail"] for step in payload["steps"])


def test_task_selected_active_state_is_runnable_for_normal_run(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    _write_json(builder_root / "backlog.yml", backlog)
    active = _json(builder_root / "active_task.yml")
    active["state"] = "task_selected"
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "task_selected"
    status["active_task_id"] = "TASK-BUILDER"
    _write_json(builder_root / "status.yml", status)
    _git(["add", "active_task.yml", "backlog.yml", "status.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "prepare task selected run"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    assert "ACTIVE_TASK_MISSING_BUT_READY_TASKS_EXIST" not in result.stdout
    assert "PAUSED" in result.stdout or "Step 1/9: Task selected" in result.stdout


def test_normal_run_does_not_start_when_selector_has_no_runnable_task(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    _seed_legacy_auth_preflight_blocked_state(builder_root, task_id="TASK-BUILDER")
    active = _json(builder_root / "active_task.yml")
    active["state"] = "implementing"
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "implementing"
    _write_json(builder_root / "status.yml", status)

    inspect = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)
    run = _run([sys.executable, str(SCRIPT)], builder_root)

    assert '"next_selected_task: null"' in inspect.stdout.lower() or 'next_selected_task: null' in inspect.stdout
    assert run.returncode == 1
    assert "SELECTOR_FILTERED_EVERYTHING" in run.stdout or "NO_READY_TASKS_REMAIN" in run.stdout
    assert "[Task TASK-BUILDER] Step 1/9" not in run.stdout


def test_blocked_backlog_task_is_never_auto_started(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "blocked"
    _write_json(builder_root / "backlog.yml", backlog)
    active = _json(builder_root / "active_task.yml")
    active["state"] = "packet_rendered"
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "packet_rendered"
    _write_json(builder_root / "status.yml", status)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert "SELECTOR_FILTERED_EVERYTHING" in result.stdout or "NO_READY_TASKS_REMAIN" in result.stdout
    assert "[Task TASK-BUILDER] Step 1/9" not in result.stdout


def test_inspect_and_normal_run_agree_on_next_selected_task(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    active = _json(builder_root / "active_task.yml")
    active.update(
        {
            "task_id": None,
            "title": None,
            "state": "idle",
            "attempt": 0,
            "started_at": None,
            "handed_to_codex_at": None,
            "prompt_file": None,
            "run_log_dir": None,
            "verification_commands": [],
            "allowlist": [],
            "failure_summary": None,
            "notes": [],
            "target_repo": None,
            "target_kind": None,
        }
    )
    _write_json(builder_root / "active_task.yml", active)
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    _write_json(builder_root / "backlog.yml", backlog)
    _git(["add", "active_task.yml", "backlog.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "prepare selector agreement"], builder_root)

    inspect = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)
    run = _run([sys.executable, str(SCRIPT)], builder_root)

    assert '"TASK-BUILDER"' in inspect.stdout
    assert run.returncode == 0
    assert "[Task TASK-BUILDER] Step 1/9" in run.stdout


def test_accepted_task_autoselects_next_task(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-1",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-chain"
    _write_fake_codex(fake_codex, relative_output="worker.py", last_message="chain codex ok\n")

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "selected"
    backlog["tasks"].append(
        {
            "id": "TASK-2",
            "title": "TASK-2",
            "type": "infrastructure",
            "area": "builder",
            "milestone": "M0",
            "priority": 1,
            "status": "ready",
            "retries_used": 0,
            "depends_on": [],
            "prompt": "implement_feature",
            "objective": "obj2",
            "why_it_matters": "why2",
            "allowlist": ["../jorb-builder/**"],
            "forbid": [],
            "verification": [],
            "acceptance": ["a"],
            "notes": [],
        }
    )
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "backlog.yml", "config.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "prepare accepted chain"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    assert "ACCEPTED" in result.stdout
    backlog_after = _json(builder_root / "backlog.yml")
    statuses = {task["id"]: task["status"] for task in backlog_after["tasks"]}
    assert statuses["TASK-1"] == "accepted"
    assert statuses["TASK-2"] == "accepted"
    assert len(list((builder_root / "task_history").glob("*.yml"))) == 2


def test_accepted_task_with_no_ready_tasks_returns_no_active_task(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-1",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-finish"
    _write_fake_codex(fake_codex, relative_output="worker.py", last_message="finish codex ok\n")

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "prepare accepted finish"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    assert "NO_READY_TASKS_REMAIN" in result.stdout
    backlog_after = _json(builder_root / "backlog.yml")
    assert backlog_after["tasks"][0]["status"] == "accepted"
    active_after = _json(builder_root / "active_task.yml")
    assert active_after["task_id"] is None


def test_accepted_task_history_links_evidence_and_diagnostics(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-1",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-history"
    _write_fake_codex(fake_codex, relative_output="worker.py", last_message="history codex ok\n")

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "prepare accepted history"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    history_path = next((builder_root / "task_history").glob("*.yml"))
    history = _json(history_path)
    run_dir = Path(history["run_log_dir"])
    evidence_by_label = {item["label"]: item["path"] for item in history["evidence_artifacts"]}

    assert history["status"] == "accepted"
    assert history["prompt"].endswith("codex_prompt.md")
    assert evidence_by_label["prompt"] == history["prompt"]
    assert evidence_by_label["run_log_dir"] == str(run_dir)
    assert evidence_by_label["automation_result"] == str(run_dir / "automation_result.json")
    assert evidence_by_label["automation_summary"] == str(run_dir / "automation_summary.md")
    assert evidence_by_label["progress_log"] == str(run_dir / "progress.jsonl")
    assert evidence_by_label["executor_output"] == str(run_dir / "codex_last_message.md")
    assert evidence_by_label["local_validation"] == str(run_dir / "local_validation.json")

    diagnostics = history["operator_diagnostics"]
    assert diagnostics["accepted"] is True
    assert diagnostics["decision_summary"] == "Automated loop completed with builder-side local validation success."
    assert diagnostics["acceptance_met"] == ["a"]
    assert diagnostics["acceptance_unmet"] == []
    assert diagnostics["changed_files_count"] == len(history["files_changed"])
    assert diagnostics["changed_files"] == history["files_changed"]
    assert diagnostics["unproven_runtime_gaps"] == []
    assert any(step["name"] == "local_validation" and step["outcome"] == "passed" for step in diagnostics["step_outcomes"])


def test_product_facing_ux_task_requires_explicit_planning_fields_in_backlog_inspection(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-UX",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["product_facing_ux"] = True
    _write_json(builder_root / "backlog.yml", backlog)

    result = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)

    assert result.returncode == 1
    assert "BACKLOG_INVALID" in result.stdout
    assert "invalid_product_facing_ux_task" in result.stdout
    assert "design_section_mapping" in result.stdout


def test_product_facing_ux_task_refines_without_explicit_ux_conformance_evidence(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-UX",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    _apply_product_facing_ux_fields(backlog["tasks"][0])
    _write_json(builder_root / "backlog.yml", backlog)

    fake_codex = tmp_path / "fake-codex-ux-missing"
    _write_fake_codex(fake_codex, relative_output="worker.py", last_message="1. Concise summary without UX evidence\n")
    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "backlog.yml", "config.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "require ux conformance evidence"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "refined"
    assert payload["summary"] == "UX conformance evidence is incomplete for this product-facing UX task."
    assert any(step["name"] == "ux_conformance" and step["outcome"] == "refined" for step in payload["steps"])
    history = _json(next((builder_root / "task_history").glob("*.yml")))
    assert history["operator_diagnostics"]["ux_conformance"]["passed"] is False
    assert "response.design_section_mapping" in history["operator_diagnostics"]["ux_conformance"]["missing_response_fields"]


def test_product_facing_ux_task_requires_canonical_figma_source_in_backlog_inspection(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-UX",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    _apply_product_facing_ux_fields(backlog["tasks"][0], mapping=["Hero -> jobs list"])
    _write_json(builder_root / "backlog.yml", backlog)

    result = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)

    assert result.returncode == 0
    assert "BACKLOG_INVALID" not in result.stdout


def test_product_facing_ux_task_backfills_canonical_figma_source_when_mapping_exists(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-UX",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    _apply_product_facing_ux_fields(backlog["tasks"][0], mapping=["Hero -> jobs list"])
    _write_json(builder_root / "backlog.yml", backlog)

    module = _load_script_module(builder_root)
    validated = module.load_validated_backlog()

    assert validated["errors"] == []


def test_product_facing_ux_task_refines_without_canonical_figma_mapping_evidence(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-UX",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    _apply_product_facing_ux_fields(backlog["tasks"][0], mapping=[f"Hero in {CANONICAL_FIGMA_SOURCE} -> jobs list"])
    _write_json(builder_root / "backlog.yml", backlog)

    fake_codex = tmp_path / "fake-codex-ux-no-figma"
    _write_fake_codex(
        fake_codex,
        relative_output="worker.py",
        last_message=(
            "1. Concise summary of exactly what changed\n"
            "UX Design Section Mapping: Hero -> jobs list; Sidebar -> filters\n"
            "UX Intentional Design Deviations: none\n"
            "UX Product-First Checklist: hierarchy=yes; prohibited_surfaces=yes; backend_wiring_only=no\n"
        ),
    )
    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "backlog.yml", "config.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "reject ux evidence without figma source"], builder_root)

    _run([sys.executable, str(SCRIPT)], builder_root)

    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "refined"
    assert any(step["name"] == "ux_conformance" and step["outcome"] == "refined" for step in payload["steps"])
    history = _json(next((builder_root / "task_history").glob("*.yml")))
    assert "response.design_section_mapping.figma_source" in history["operator_diagnostics"]["ux_conformance"]["missing_response_fields"]


def test_product_facing_ux_task_accepts_with_explicit_ux_conformance_evidence(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-UX",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    _apply_product_facing_ux_fields(
        backlog["tasks"][0],
        mapping=[f"Hero in {CANONICAL_FIGMA_SOURCE} -> jobs list", f"Sidebar in {CANONICAL_FIGMA_SOURCE} -> filters"],
    )
    _write_json(builder_root / "backlog.yml", backlog)

    fake_codex = tmp_path / "fake-codex-ux-ok"
    _write_fake_codex(
        fake_codex,
        relative_output="worker.py",
        last_message=(
            "1. Concise summary of exactly what changed\n"
            f"UX Design Section Mapping: Hero and Sidebar in {CANONICAL_FIGMA_SOURCE} -> jobs list and filters\n"
            "UX Intentional Design Deviations: none\n"
            "UX Product-First Checklist: hierarchy=yes; prohibited_surfaces=yes; backend_wiring_only=no\n"
        ),
    )
    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "backlog.yml", "config.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "accept ux conformance evidence"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    history = _json(next((builder_root / "task_history").glob("*.yml")))
    assert history["status"] == "accepted"
    ux = history["operator_diagnostics"]["ux_conformance"]
    assert ux["passed"] is True
    assert ux["design_section_mapping"] == f"Hero and Sidebar in {CANONICAL_FIGMA_SOURCE} -> jobs list and filters"
    assert ux["intentional_design_deviations"] == "none"
    assert ux["product_first_checklist"] == "hierarchy=yes; prohibited_surfaces=yes; backend_wiring_only=no"


def test_product_facing_ux_task_accepts_with_numbered_ux_conformance_labels(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-UX",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    _apply_product_facing_ux_fields(
        backlog["tasks"][0],
        mapping=[f"Hero in {CANONICAL_FIGMA_SOURCE} -> jobs list", f"Sidebar in {CANONICAL_FIGMA_SOURCE} -> filters"],
    )
    _write_json(builder_root / "backlog.yml", backlog)

    fake_codex = tmp_path / "fake-codex-ux-numbered"
    _write_fake_codex(
        fake_codex,
        relative_output="worker.py",
        last_message=(
            f"1. UX Design Section Mapping: Hero and Sidebar in {CANONICAL_FIGMA_SOURCE} -> jobs list and filters\n"
            "2. UX Intentional Design Deviations: none\n"
            "3. UX Product-First Checklist: hierarchy=yes; prohibited_surfaces=yes; backend_wiring_only=no\n"
        ),
    )
    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "backlog.yml", "config.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "accept numbered ux conformance evidence"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    history = _json(next((builder_root / "task_history").glob("*.yml")))
    ux = history["operator_diagnostics"]["ux_conformance"]
    assert ux["passed"] is True
    assert ux["design_section_mapping"] == f"Hero and Sidebar in {CANONICAL_FIGMA_SOURCE} -> jobs list and filters"
    assert ux["intentional_design_deviations"] == "none"
    assert ux["product_first_checklist"] == "hierarchy=yes; prohibited_surfaces=yes; backend_wiring_only=no"


def test_missing_packet(tmp_path: Path) -> None:
    builder_root, _, _, prompt_file = _setup_builder_fixture(tmp_path, task_id="TASK-1", area="builder", allowlist=["../jorb-builder/**"])
    prompt_file.unlink()

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert "MISSING_PACKET" in result.stdout


def test_stale_implementing_state(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="TASK-1", area="builder", allowlist=["../jorb-builder/**"])
    active = _json(builder_root / "active_task.yml")
    active["state"] = "implementing"
    active["handed_to_codex_at"] = None
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "implementing"
    _write_json(builder_root / "status.yml", status)

    result = _run([sys.executable, str(SCRIPT), "--resume"], builder_root)

    assert result.returncode == 1
    assert "STALE_IMPLEMENTING_STATE" in result.stdout


def test_builder_side_pause_and_resume(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(tmp_path, task_id="TASK-BUILDER", area="builder", allowlist=["../jorb-builder/**"])

    pause = _run([sys.executable, str(SCRIPT)], builder_root)
    assert pause.returncode == 0
    assert "PAUSED" in pause.stdout
    active = _json(builder_root / "active_task.yml")
    assert active["task_id"] == "TASK-BUILDER"
    assert active["state"] == "implementing"
    assert active["target_kind"] == "builder"
    assert active["target_repo"] == str(builder_root)
    assert Path(active["run_log_dir"]) != run_log_dir
    first_run_dir = Path(active["run_log_dir"])
    assert not (first_run_dir / "automation_result.json").exists()

    resume = _run([sys.executable, str(SCRIPT), "--resume"], builder_root)
    assert resume.returncode == 0
    assert "PAUSED" in resume.stdout
    assert "builder repo changes" in resume.stdout
    second_run_dir = _active_run_dir(builder_root)
    assert second_run_dir != first_run_dir
    assert not (second_run_dir / "automation_result.json").exists()
    resume_check = _json(second_run_dir / "resume_check.json")
    assert resume_check["files"] == []


def test_builder_side_ignores_backlog_dirt_when_pausing(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="TASK-BUILDER", area="builder", allowlist=["../jorb-builder/**"])
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["notes"].append("local builder retry note")
    _write_json(builder_root / "backlog.yml", backlog)

    pause = _run([sys.executable, str(SCRIPT)], builder_root)

    assert pause.returncode == 0
    assert "PAUSED" in pause.stdout
    assert "dirty before automated execution" not in pause.stdout


def test_product_side_pause_and_resume(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )

    pause = _run([sys.executable, str(SCRIPT)], builder_root)
    assert pause.returncode == 0
    assert "PAUSED" in pause.stdout
    active = _json(builder_root / "active_task.yml")
    assert active["target_kind"] == "product"
    assert active["target_repo"] == str(product_repo)

    resume = _run([sys.executable, str(SCRIPT), "--resume"], builder_root)
    assert resume.returncode == 0
    assert "product repo changes" in resume.stdout
    run_dir = _active_run_dir(builder_root)
    assert not (run_dir / "automation_result.json").exists()
    resume_check = _json(run_dir / "resume_check.json")
    assert resume_check["files"] == []


def test_resume_allows_expected_dirty_builder_task_files(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="TASK-BUILDER", area="builder", allowlist=["../jorb-builder/**"])

    pause = _run([sys.executable, str(SCRIPT)], builder_root)
    assert pause.returncode == 0

    (builder_root / "worker.py").write_text("print('ok')\n", encoding="utf-8")

    resume = _run([sys.executable, str(SCRIPT), "--resume"], builder_root)

    assert resume.returncode == 0
    assert "BLOCKED Builder repo is dirty before automated execution" not in resume.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "accepted"
    assert "worker.py" in payload["changed_files"]


def test_resume_blocks_out_of_allowlist_dirty_files(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )

    pause = _run([sys.executable, str(SCRIPT)], builder_root)
    assert pause.returncode == 0

    (product_repo / "wrong.txt").write_text("wrong file\n", encoding="utf-8")

    resume = _run([sys.executable, str(SCRIPT), "--resume"], builder_root)

    assert resume.returncode in {1, 2}
    assert "outside the task allowlist" in resume.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert "wrong.txt" in payload["blocker_evidence"]


def test_product_validation_uses_venv_validation_when_present(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _commit_allowlisted_product_file(product_repo, "services/company_discovery.py", "print('seed')\n")

    active = _json(builder_root / "active_task.yml")
    active["verification_commands"] = [f'test "$VIRTUAL_ENV" = "{product_repo / ".venv_validation"}"']
    _write_json(builder_root / "active_task.yml", active)

    pause = _run([sys.executable, str(SCRIPT)], builder_root)
    assert pause.returncode == 0

    _ignore_path_in_git_status(product_repo, ".venv_validation")
    _write_activate_script(product_repo / ".venv_validation")
    (product_repo / "services" / "company_discovery.py").write_text("print('changed')\n", encoding="utf-8")

    resume = _run([sys.executable, str(SCRIPT), "--resume"], builder_root)

    assert resume.returncode in {1, 2}
    assert "No product validation virtualenv found" not in resume.stdout
    validation = _json(_active_run_dir(builder_root) / "local_validation.json")
    assert validation["passed"] is True
    assert validation["venv_path"] == str(product_repo / ".venv_validation")


def test_product_validation_fails_clearly_without_venv(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _commit_allowlisted_product_file(product_repo, "services/company_discovery.py", "print('seed')\n")

    active = _json(builder_root / "active_task.yml")
    active["verification_commands"] = ["echo validation"]
    _write_json(builder_root / "active_task.yml", active)

    pause = _run([sys.executable, str(SCRIPT)], builder_root)
    assert pause.returncode == 0

    (product_repo / "services" / "company_discovery.py").write_text("print('changed')\n", encoding="utf-8")

    resume = _run([sys.executable, str(SCRIPT), "--resume"], builder_root)

    assert resume.returncode == 2
    assert "No product validation virtualenv found" in resume.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert "No product validation virtualenv found" in payload["summary"]


def test_product_task_blocks_when_vm_runtime_proof_is_not_configured(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _commit_allowlisted_product_file(product_repo, "services/company_discovery.py", "print('seed')\n")

    config = _json(builder_root / "config.yml")
    config["vm"]["runtime_validation_commands"] = []
    _write_json(builder_root / "config.yml", config)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert "Missing automation configuration: vm.runtime_validation_commands or task.vm_verification" in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert payload["summary"] == "Missing automation configuration: vm.runtime_validation_commands or task.vm_verification"
    assert payload["unproven_runtime_gaps"] == ["Missing automation configuration: vm.runtime_validation_commands or task.vm_verification"]


def test_retry_ready_product_task_continues_from_expected_dirty_files(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _commit_allowlisted_product_file(product_repo, "services/company_discovery.py", "print('seed')\n")
    _ignore_path_in_git_status(product_repo, ".venv_validation")
    _write_activate_script(product_repo / ".venv_validation")

    active = _json(builder_root / "active_task.yml")
    active["verification_commands"] = [f'test "$VIRTUAL_ENV" = "{product_repo / ".venv_validation"}"']
    _write_json(builder_root / "active_task.yml", active)
    _mark_retry_ready(builder_root)

    (product_repo / "services" / "company_discovery.py").write_text("print('changed')\n", encoding="utf-8")

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode in {1, 2}
    assert "dirty before automated execution" not in result.stdout
    run_dir = _active_run_dir(builder_root)
    payload = _json(run_dir / "automation_result.json")
    step_names = [step["name"] for step in payload["steps"]]
    assert "retry_check" in step_names
    assert "local_validation" in step_names
    validation = _json(run_dir / "local_validation.json")
    assert validation["passed"] is True
    assert validation["venv_path"] == str(product_repo / ".venv_validation")


def test_retry_ready_product_task_blocks_out_of_allowlist_dirty_files(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _mark_retry_ready(builder_root)
    (product_repo / "wrong.txt").write_text("wrong file\n", encoding="utf-8")

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert "dirty before automated execution" not in result.stdout
    assert "outside the task allowlist" in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    step_names = [step["name"] for step in payload["steps"]]
    assert "retry_check" in step_names
    assert payload["classification"] == "blocked"
    assert "wrong.txt" in payload["blocker_evidence"]


def test_retry_ready_product_task_retries_vm_without_dirty_files(tmp_path: Path) -> None:
    builder_root, product_repo, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _mark_retry_ready(builder_root)
    _write_prior_vm_refined_result(run_log_dir, changed_files=["services/company_discovery.py"])

    config = _json(builder_root / "config.yml")
    config["vm"]["ssh_target"] = "127.0.0.1"
    config["vm"]["ssh_options"] = ["-o", "ConnectTimeout=1"]
    _write_json(builder_root / "config.yml", config)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert "Retry-ready task has no product repo changes to continue from." not in result.stdout
    current_run_dir = _active_run_dir(builder_root)
    payload = _json(current_run_dir / "automation_result.json")
    step_names = [step["name"] for step in payload["steps"]]
    assert "retry_check" in step_names
    assert "vm_validation" in step_names
    assert payload["summary"] == "VM validation failed after local validation and git push succeeded."
    vm_validation = _json(current_run_dir / "vm_validation.json")
    assert "ssh -o ConnectTimeout=1 " in vm_validation["results"][0]["command"]
    assert "ControlMaster=auto" in vm_validation["results"][0]["command"]
    assert "BatchMode=yes" in vm_validation["results"][0]["command"]
    assert "StrictHostKeyChecking=accept-new" in vm_validation["results"][0]["command"]
    assert "cd " + str(product_repo) + " && env GIT_TERMINAL_PROMPT=0 git pull --ff-only" in vm_validation["results"][0]["command"]


def test_vm_remote_home_path_is_preserved_in_ssh_command(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _mark_retry_ready(builder_root)
    _write_prior_vm_refined_result(run_log_dir, changed_files=["services/company_discovery.py"])

    config = _json(builder_root / "config.yml")
    config["vm"]["ssh_target"] = "127.0.0.1"
    config["vm"]["ssh_options"] = ["-o", "ConnectTimeout=1"]
    config["vm"]["product_repo"] = "/home/gargantua1/projects/jorb"
    _write_json(builder_root / "config.yml", config)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    vm_validation = _json(_active_run_dir(builder_root) / "vm_validation.json")
    assert "ssh -o ConnectTimeout=1 " in vm_validation["results"][0]["command"]
    assert "ControlMaster=auto" in vm_validation["results"][0]["command"]
    assert "BatchMode=yes" in vm_validation["results"][0]["command"]
    assert "StrictHostKeyChecking=accept-new" in vm_validation["results"][0]["command"]
    assert "env GIT_TERMINAL_PROMPT=0 git pull --ff-only" in vm_validation["results"][0]["command"]
    assert "cd /home/gargantua1/projects/jorb && env GIT_TERMINAL_PROMPT=0 git pull --ff-only" in vm_validation["results"][0]["command"]
    assert "/System/Volumes/Data/home/gargantua1/projects/jorb" not in vm_validation["results"][0]["command"]


def test_vm_bootstrap_commands_run_before_smoke_check(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _mark_retry_ready(builder_root)
    _write_prior_vm_refined_result(run_log_dir, changed_files=["services/company_discovery.py"])

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["vm_bootstrap"] = ["echo bootstrap-api", "echo bootstrap-ui"]
    backlog["tasks"][0]["vm_verification"] = ["echo smoke-check"]
    backlog["tasks"][0]["vm_cleanup"] = ["echo cleanup"]
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["vm"]["ssh_target"] = "vm.example"
    config["vm"]["ssh_options"] = []
    config["vm"]["validation_commands"] = ["echo vm-preflight"]
    config["vm"]["runtime_validation_commands"] = []
    _write_json(builder_root / "config.yml", config)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    fake_ssh = fake_bin / "ssh"
    _write_fake_ssh(fake_ssh)
    ssh_log = tmp_path / "fake-ssh.log"
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_SSH_LOG": str(ssh_log),
    }

    result = _run([sys.executable, str(SCRIPT)], builder_root, extra_env=env)

    assert result.returncode == 0
    vm_validation = _json(_active_run_dir(builder_root) / "vm_validation.json")
    commands = [item["command"] for item in vm_validation["results"]]
    assert "git pull --ff-only" in commands[0]
    assert "echo vm-preflight" in commands[1]
    assert "echo bootstrap-api" in commands[2]
    assert "echo bootstrap-ui" in commands[3]
    assert "echo smoke-check" in commands[4]
    assert "echo cleanup" in commands[5]
    phases = [item.get("phase") for item in vm_validation["results"][1:]]
    assert phases == ["vm_validation", "vm_bootstrap", "vm_bootstrap", "vm_smoke", "vm_cleanup"]


def test_vm_uses_config_default_bootstrap_when_task_does_not_override(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _mark_retry_ready(builder_root)
    _write_prior_vm_refined_result(run_log_dir, changed_files=["services/company_discovery.py"])

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["vm_bootstrap"] = []
    backlog["tasks"][0]["vm_verification"] = ["echo smoke-check"]
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["vm"]["ssh_target"] = "vm.example"
    config["vm"]["ssh_options"] = []
    config["vm"]["validation_commands"] = ["echo vm-preflight"]
    config["vm"]["bootstrap_commands"] = ["echo config-bootstrap"]
    config["vm"]["runtime_validation_commands"] = ["echo runtime-default"]
    config["vm"]["cleanup_commands"] = ["echo cleanup-default"]
    _write_json(builder_root / "config.yml", config)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    fake_ssh = fake_bin / "ssh"
    _write_fake_ssh(fake_ssh)
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }

    result = _run([sys.executable, str(SCRIPT)], builder_root, extra_env=env)

    assert result.returncode == 0
    vm_validation = _json(_active_run_dir(builder_root) / "vm_validation.json")
    commands = [item["command"] for item in vm_validation["results"]]
    assert "echo config-bootstrap" in commands[2]
    assert "echo runtime-default" in commands[3]
    assert "echo smoke-check" in commands[4]
    assert "echo cleanup-default" in commands[5]


def test_vm_bootstrap_failure_surfaces_clear_summary(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _mark_retry_ready(builder_root)
    _write_prior_vm_refined_result(run_log_dir, changed_files=["services/company_discovery.py"])

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["vm_bootstrap"] = ["echo bootstrap-api"]
    backlog["tasks"][0]["vm_verification"] = ["echo smoke-check"]
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["vm"]["ssh_target"] = "vm.example"
    config["vm"]["validation_commands"] = ["echo vm-preflight"]
    config["vm"]["runtime_validation_commands"] = []
    _write_json(builder_root / "config.yml", config)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    fake_ssh = fake_bin / "ssh"
    _write_fake_ssh(fake_ssh)
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_SSH_FAIL_MATCH": "echo bootstrap-api",
    }

    result = _run([sys.executable, str(SCRIPT)], builder_root, extra_env=env)

    assert result.returncode == 1
    assert "VM bootstrap failed after local validation and git push succeeded." in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["summary"] == "VM bootstrap failed after local validation and git push succeeded."
    assert payload["classification"] == "refined"
    assert any(step["name"] == "vm_validation" and step["detail"] == "VM bootstrap commands failed." for step in payload["steps"])


def test_product_task_blocks_when_vm_bootstrap_is_not_configured(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _mark_retry_ready(builder_root)
    _write_prior_vm_refined_result(run_log_dir, changed_files=["services/company_discovery.py"])

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["vm_bootstrap"] = []
    backlog["tasks"][0]["vm_verification"] = ["echo smoke-check"]
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["vm"]["ssh_target"] = "vm.example"
    config["vm"]["validation_commands"] = ["echo vm-preflight"]
    config["vm"]["runtime_validation_commands"] = []
    _write_json(builder_root / "config.yml", config)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    fake_ssh = fake_bin / "ssh"
    _write_fake_ssh(fake_ssh)
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }

    result = _run([sys.executable, str(SCRIPT)], builder_root, extra_env=env)

    assert result.returncode == 2
    assert "Missing automation configuration: vm.bootstrap_commands or task.vm_bootstrap" in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert payload["summary"] == "Missing automation configuration: vm.bootstrap_commands or task.vm_bootstrap"
    assert payload["unproven_runtime_gaps"] == ["Missing automation configuration: vm.bootstrap_commands or task.vm_bootstrap"]


def test_inspect_backlog_rejects_ready_task_missing_vm_runtime_contract(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    backlog["tasks"][0]["requires_vm_runtime_proof"] = True
    backlog["tasks"][0]["verification"] = ["echo local-ok"]
    backlog["tasks"][0]["vm_bootstrap"] = []
    backlog["tasks"][0]["vm_verification"] = []
    _write_json(builder_root / "backlog.yml", backlog)

    active = _json(builder_root / "active_task.yml")
    active["task_id"] = None
    active["state"] = "idle"
    active["title"] = None
    active["prompt_file"] = None
    active["run_log_dir"] = None
    _write_json(builder_root / "active_task.yml", active)

    status = _json(builder_root / "status.yml")
    status["active_task_id"] = None
    status["state"] = "idle"
    _write_json(builder_root / "status.yml", status)

    config = _json(builder_root / "config.yml")
    config["vm"]["runtime_validation_commands"] = []
    config["vm"]["bootstrap_commands"] = []
    _write_json(builder_root / "config.yml", config)

    result = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)

    assert result.returncode == 1
    assert "BACKLOG_INVALID" in result.stdout
    assert "missing VM runtime proof fields: vm_verification, vm_bootstrap_or_config_vm.bootstrap_commands" in result.stdout


def test_inspect_backlog_rejects_ready_task_with_vm_ui_port_drift(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    backlog["tasks"][0]["requires_vm_runtime_proof"] = True
    backlog["tasks"][0]["verification"] = ["echo local-ok"]
    backlog["tasks"][0]["vm_bootstrap"] = []
    backlog["tasks"][0]["vm_verification"] = ["curl -I http://127.0.0.1:8501"]
    _write_json(builder_root / "backlog.yml", backlog)

    active = _json(builder_root / "active_task.yml")
    active["task_id"] = None
    active["state"] = "idle"
    active["title"] = None
    active["prompt_file"] = None
    active["run_log_dir"] = None
    _write_json(builder_root / "active_task.yml", active)

    status = _json(builder_root / "status.yml")
    status["active_task_id"] = None
    status["state"] = "idle"
    _write_json(builder_root / "status.yml", status)

    config = _json(builder_root / "config.yml")
    config["vm"]["bootstrap_commands"] = ["streamlit run ui/app.py --server.port 8500 --server.address 0.0.0.0"]
    _write_json(builder_root / "config.yml", config)

    result = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)

    assert result.returncode == 1
    assert "BACKLOG_INVALID" in result.stdout
    assert "missing VM runtime proof fields: vm_ui_port_mismatch:http://127.0.0.1:8500!=http://127.0.0.1:8501" in result.stdout


def test_vm_cleanup_does_not_override_prior_bootstrap_failure(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _mark_retry_ready(builder_root)
    _write_prior_vm_refined_result(run_log_dir, changed_files=["services/company_discovery.py"])

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["vm_bootstrap"] = ["echo bootstrap-api"]
    backlog["tasks"][0]["vm_verification"] = ["echo smoke-check"]
    backlog["tasks"][0]["vm_cleanup"] = ["echo cleanup"]
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["vm"]["ssh_target"] = "vm.example"
    config["vm"]["validation_commands"] = ["echo vm-preflight"]
    config["vm"]["runtime_validation_commands"] = []
    _write_json(builder_root / "config.yml", config)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(parents=True, exist_ok=True)
    fake_ssh = fake_bin / "ssh"
    _write_fake_ssh(fake_ssh)
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_SSH_FAIL_MATCH": "echo bootstrap-api",
    }

    result = _run([sys.executable, str(SCRIPT)], builder_root, extra_env=env)

    assert result.returncode == 1
    assert "VM bootstrap failed after local validation and git push succeeded." in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["summary"] == "VM bootstrap failed after local validation and git push succeeded."
    assert any(step["name"] == "vm_validation" and step["detail"] == "VM bootstrap commands failed." for step in payload["steps"])


def test_run_shell_passes_noninteractive_git_env(tmp_path: Path) -> None:
    module = _load_script_module()

    result = module.run_shell(
        "python3 -c \"import os, sys; sys.exit(0 if os.environ.get('GIT_TERMINAL_PROMPT') == '0' else 1)\"",
        tmp_path,
        shell_executable="/bin/zsh",
        env=module.NONINTERACTIVE_GIT_ENV,
    )

    assert result["passed"] is True


def test_render_template_preserves_literal_shell_braces_while_expanding_known_placeholders(tmp_path: Path) -> None:
    module = _load_script_module()

    rendered = module.render_template(
        "echo {task_id}; pgrep foo >/dev/null || { tail -n 20 /tmp/foo.log >&2; exit 1; }",
        {"task_id": "TASK-1"},
    )

    assert rendered == "echo TASK-1; pgrep foo >/dev/null || { tail -n 20 /tmp/foo.log >&2; exit 1; }"


def test_noninteractive_vm_ssh_options_add_batch_guards(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    module = _load_script_module(builder_root)
    options = module.noninteractive_vm_ssh_options({"ssh_target": "builder@example", "ssh_options": ["-o", "ConnectTimeout=1"]})

    assert options.count("-o") >= 5
    assert "ConnectTimeout=1" in options
    assert "ControlMaster=auto" in options
    assert "BatchMode=yes" in options
    assert "StrictHostKeyChecking=accept-new" in options


def test_retry_ready_product_task_recovers_vm_retry_from_stage_files(tmp_path: Path) -> None:
    builder_root, product_repo, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _mark_retry_ready(builder_root)
    _write_prior_vm_refined_result(run_log_dir, changed_files=["services/company_discovery.py"])
    _write_no_changes_refined_result(run_log_dir)
    _write_json(
        run_log_dir / "local_validation.json",
        {
            "results": [
                {
                    "stdout": "== git status --short ==\n M services/company_discovery.py\n\n== compileall ==\n",
                    "passed": True,
                }
            ],
            "passed": True,
            "venv_path": str(product_repo / ".venv_validation"),
        },
    )
    _write_json(
        run_log_dir / "git.json",
        {
            "add": {"passed": True},
            "commit": {"passed": True, "stdout": "[main abc123] test\n 1 file changed, 1 insertion(+)\n"},
            "push": {"passed": True},
        },
    )
    _write_json(
        run_log_dir / "vm_validation.json",
        {
            "results": [{"passed": False, "stderr": "vm failed"}],
            "passed": False,
        },
    )

    config = _json(builder_root / "config.yml")
    config["vm"]["ssh_target"] = "127.0.0.1"
    config["vm"]["ssh_options"] = ["-o", "ConnectTimeout=1"]
    _write_json(builder_root / "config.yml", config)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert "Retry-ready task has no product repo changes to continue from." not in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    step_names = [step["name"] for step in payload["steps"]]
    assert "vm_validation" in step_names
    assert payload["summary"] == "VM validation failed after local validation and git push succeeded."


def test_retry_ready_product_task_recovers_second_vm_retry_from_prior_retry_result(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _mark_retry_ready(builder_root)
    _write_json(
        run_log_dir / "automation_result.json",
        {
            "task_id": "TASK-PRODUCT",
            "classification": "refined",
            "finished_at": "2026-03-29T00:00:00+00:00",
            "summary": "VM smoke validation failed after local validation and git push succeeded.",
            "steps": [
                {"name": "retry_check", "outcome": "passed", "detail": "No current dirty repo changes; continuing from prior post-push VM retry context."},
                {"name": "vm_validation", "outcome": "refined", "detail": "VM smoke commands failed."},
            ],
            "changed_files": ["services/company_discovery.py"],
            "blocker_evidence": [],
            "unproven_runtime_gaps": ["VM smoke validation failed after local validation and git push succeeded."],
        },
    )

    config = _json(builder_root / "config.yml")
    config["vm"]["ssh_target"] = "127.0.0.1"
    config["vm"]["ssh_options"] = ["-o", "ConnectTimeout=1"]
    _write_json(builder_root / "config.yml", config)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert "Retry-ready task has no product repo changes to continue from." not in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    step_names = [step["name"] for step in payload["steps"]]
    assert "retry_check" in step_names
    assert "vm_validation" in step_names
    assert payload["summary"] == "VM validation failed after local validation and git push succeeded."


def test_retry_ready_product_facing_ux_task_recovers_from_prior_ux_evidence_retry_chain(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-UX",
        area="discovery",
        allowlist=["ui/screens/jobs.py", "tests/test_workbench.py"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "retry_ready"
    _apply_product_facing_ux_fields(
        backlog["tasks"][0],
        mapping=[f"Jobs screen in {CANONICAL_FIGMA_SOURCE} -> search status region and jobs list"],
    )
    _write_json(builder_root / "backlog.yml", backlog)

    fake_codex = tmp_path / "fake-codex-ux-retry-noop"
    _write_fake_codex_no_change(
        fake_codex,
        last_message=(
            "1. Concise summary of exactly what changed\n"
            f"UX Design Section Mapping: Jobs screen in {CANONICAL_FIGMA_SOURCE} -> search status region and jobs list\n"
            "UX Intentional Design Deviations: none\n"
            "UX Product-First Checklist: hierarchy=yes; prohibited_surfaces=yes; backend_wiring_only=no\n"
        ),
    )
    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    config["vm"]["ssh_target"] = "127.0.0.1"
    config["vm"]["ssh_options"] = ["-o", "ConnectTimeout=1"]
    _write_json(builder_root / "config.yml", config)

    prior_ux_run_dir = builder_root / "run_logs" / "run-0"
    prior_ux_run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        prior_ux_run_dir / "automation_result.json",
        {
            "task_id": "TASK-UX",
            "classification": "refined",
            "finished_at": "2026-03-29T23:46:56+00:00",
            "summary": "UX conformance evidence is incomplete for this product-facing UX task.",
            "steps": [
                {"name": "executor", "outcome": "passed", "detail": "executor ok"},
                {"name": "local_validation", "outcome": "passed", "detail": "local ok"},
                {"name": "git", "outcome": "passed", "detail": "git ok"},
                {"name": "vm_validation", "outcome": "accepted", "detail": "vm ok"},
                {"name": "ux_conformance", "outcome": "refined", "detail": "Missing figma source"},
            ],
            "changed_files": ["ui/screens/jobs.py", "tests/test_workbench.py"],
            "blocker_evidence": [],
            "unproven_runtime_gaps": [],
        },
    )

    _mark_retry_ready(builder_root)
    active = _json(builder_root / "active_task.yml")
    active["previous_run_log_dir"] = str(prior_ux_run_dir)
    active["failure_summary"] = "Retry-ready task has no product repo changes to continue from."
    _write_json(builder_root / "active_task.yml", active)
    _write_no_changes_refined_result(run_log_dir)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert "Retry-ready task has no product repo changes to continue from." not in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["summary"] != "Retry-ready task has no product repo changes to continue from."
    assert payload["summary"] == "Executor completed with no new product repo changes because this rerun only repaired UX conformance evidence."


def test_active_task_vm_commands_are_resynced_from_current_backlog_truth(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "selected"
    backlog["tasks"][0]["verification"] = []
    backlog["tasks"][0]["vm_bootstrap"] = []
    backlog["tasks"][0]["vm_verification"] = ["echo task-smoke"]
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["vm"]["bootstrap_commands"] = ["echo default-bootstrap"]
    config["vm"]["runtime_validation_commands"] = []
    _write_json(builder_root / "config.yml", config)

    active = _json(builder_root / "active_task.yml")
    active["vm_bootstrap_commands"] = ["echo stale-bootstrap"]
    active["vm_verification_commands"] = ["echo stale-smoke"]
    _write_json(builder_root / "active_task.yml", active)

    result = _run([sys.executable, str(SCRIPT), "--dry-run"], builder_root)

    assert result.returncode == 0
    run_dir = sorted(
        (path for path in (builder_root / "run_logs").glob("*") if (path / "automation_result.json").exists()),
        key=lambda path: path.name,
    )[-1]
    payload = _json(run_dir / "automation_result.json")
    plan = json.loads(payload["steps"][0]["detail"])
    assert plan["vm_bootstrap_commands"] == ["echo default-bootstrap"]
    assert plan["vm_smoke_commands"] == ["echo task-smoke"]


def test_fresh_product_execution_still_blocks_on_dirty_repo(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    (product_repo / "services").mkdir(exist_ok=True)
    (product_repo / "services" / "company_discovery.py").write_text("print('changed')\n", encoding="utf-8")

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 2
    assert "dirty before automated execution" in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert "Product repo is dirty before automated execution" in payload["summary"]


def test_product_dirty_repo_ignores_configured_scratch_paths(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    fake_codex = tmp_path / "fake-codex-product-ignore"
    _write_fake_codex(fake_codex, relative_output="services/company_discovery.py", last_message="product ignore ok\n")

    active = _json(builder_root / "active_task.yml")
    active.update(
        {
            "task_id": None,
            "title": None,
            "state": "idle",
            "attempt": 0,
            "started_at": None,
            "handed_to_codex_at": None,
            "prompt_file": None,
            "run_log_dir": None,
            "verification_commands": [],
            "allowlist": [],
            "failure_summary": None,
            "notes": [],
            "target_repo": None,
            "target_kind": None,
        }
    )
    _write_json(builder_root / "active_task.yml", active)

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    config["git"]["ignored_dirty_paths"] = {"product": ["design/figma_old/"]}
    _write_json(builder_root / "config.yml", config)

    scratch = product_repo / "design" / "figma_old"
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "backup.txt").write_text("scratch\n", encoding="utf-8")

    _git(["add", "active_task.yml", "backlog.yml", "config.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "prepare product ignore test"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode in {0, 1}
    assert "dirty before automated execution" not in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert "dirty before automated execution" not in payload["summary"]


def test_dirty_repo_blocks_and_preserves_active_task(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(tmp_path, task_id="TASK-DIRTY", area="builder", allowlist=["../jorb-builder/**"])
    (builder_root / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 2
    assert "BLOCKED" in result.stdout
    assert "Clean" in result.stdout
    assert "FAILED at Step 4" in result.stdout
    active = _json(builder_root / "active_task.yml")
    assert active["task_id"] == "TASK-DIRTY"
    assert active["state"] == "blocked"
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert "Builder repo is dirty" in payload["summary"]


def test_builder_dirty_repo_ignores_generated_state_files(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-builder-ignore"
    _write_fake_codex(fake_codex, relative_output="worker.py", last_message="builder ignore ok\n")

    active = _json(builder_root / "active_task.yml")
    active.update(
        {
            "task_id": None,
            "title": None,
            "state": "idle",
            "attempt": 0,
            "started_at": None,
            "handed_to_codex_at": None,
            "prompt_file": None,
            "run_log_dir": None,
            "verification_commands": [],
            "allowlist": [],
            "failure_summary": None,
            "notes": [],
            "target_repo": None,
            "target_kind": None,
        }
    )
    _write_json(builder_root / "active_task.yml", active)

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)

    (builder_root / "run_ledger.json").write_text('{"state":"idle"}\n', encoding="utf-8")
    (builder_root / "backlog_proposals.json").write_text('{"proposals":[]}\n', encoding="utf-8")
    (builder_root / "synthesized_backlog_entries.json").write_text('{"entries":[]}\n', encoding="utf-8")

    _git(["add", "active_task.yml", "backlog.yml", "config.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "prepare builder ignore test"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    assert "dirty before automated execution" not in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert "dirty before automated execution" not in payload["summary"]


def test_codex_exec_builder_task_runs_in_builder_repo(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-builder"
    _write_fake_codex(fake_codex, relative_output="worker.py", last_message="builder codex ok\n")

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml"], builder_root)
    _git(["commit", "-m", "configure codex exec"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    assert "NO_READY_TASKS_REMAIN" in result.stdout
    assert (builder_root / "worker.py").exists()
    run_dir = _active_run_dir(builder_root)
    executor = _json(run_dir / "executor.json")
    assert executor["cwd"] == str(builder_root)
    assert executor["last_message"] == "builder codex ok\n"
    assert executor["output_file_nonempty"] is True
    payload = _json(run_dir / "automation_result.json")
    assert payload["classification"] == "accepted"
    assert "worker.py" in payload["changed_files"]
    progress_events = (run_dir / "progress.jsonl").read_text(encoding="utf-8").splitlines()
    assert any('"stage_name": "Git commit and push"' in line for line in progress_events)


def test_codex_exec_emits_heartbeat_progress_updates(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-slow"
    _write_fake_codex_slow(fake_codex, relative_output="worker.py", sleep_seconds=2, last_message="slow codex ok\n")

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    config["executor"]["heartbeat_seconds"] = 1
    config["executor"]["timeout_seconds"] = 10
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml"], builder_root)
    _git(["commit", "-m", "configure codex heartbeat"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    assert "Step 3/9: Codex execution running" in result.stdout
    assert "Elapsed:" in result.stdout
    assert "pid=" in result.stdout
    assert "output_exists=" in result.stdout
    run_dir = _active_run_dir(builder_root)
    progress_events = _progress_events(run_dir)
    heartbeat_events = [event for event in progress_events if event["stage_name"] == "Codex execution running" and "last_message_exists" in event]
    assert heartbeat_events
    assert all(event["elapsed_seconds"] >= 0 for event in heartbeat_events)
    assert any(event.get("status") == "waiting_for_first_output" for event in heartbeat_events)
    assert any("timeout_remaining_seconds" in event for event in heartbeat_events)
    assert "runnable after current" in result.stdout


def test_local_validation_emits_live_progress_with_elapsed_time(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-validation"
    _write_fake_codex(fake_codex, relative_output="worker.py", last_message="validation progress ok\n")

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    config["executor"]["heartbeat_seconds"] = 1
    _write_json(builder_root / "config.yml", config)

    active = _json(builder_root / "active_task.yml")
    active["verification_commands"] = ["python3 -c 'import time; time.sleep(2)'"]
    _write_json(builder_root / "active_task.yml", active)

    _git(["add", "config.yml", "active_task.yml"], builder_root)
    _git(["commit", "-m", "configure local validation progress"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    assert "Step 5/9: Local validation (pytest)" in result.stdout
    assert "phase=local_validation" in result.stdout
    assert "Elapsed:" in result.stdout
    run_dir = _active_run_dir(builder_root)
    progress_events = _progress_events(run_dir)
    validation_events = [
        event
        for event in progress_events
        if event["stage_name"] == "Local validation (pytest)" and event.get("phase_label") == "local_validation"
    ]
    assert validation_events
    assert all(event["elapsed_seconds"] >= 0 for event in validation_events)
    assert any(event.get("command") == "python3 -c 'import time; time.sleep(2)'" for event in validation_events)


def test_long_running_codex_survives_multiple_heartbeat_intervals(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-long"
    _write_fake_codex_slow(fake_codex, relative_output="worker.py", sleep_seconds=3, last_message="long codex ok\n")

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    config["executor"]["heartbeat_seconds"] = 1
    config["executor"]["timeout_seconds"] = 10
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml"], builder_root)
    _git(["commit", "-m", "configure long codex"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    assert "TimeoutExpired" not in result.stderr
    run_dir = _active_run_dir(builder_root)
    heartbeat_events = [event for event in _progress_events(run_dir) if event["stage_name"] == "Codex execution running" and event["state"] == "running"]
    assert len(heartbeat_events) >= 2
    assert heartbeat_events[0]["elapsed_seconds"] < heartbeat_events[-1]["elapsed_seconds"]
    assert all("waiting_on" in event for event in heartbeat_events)
    assert any(event.get("status") == "waiting_for_first_output" for event in heartbeat_events)


def test_fresh_run_progress_starts_near_zero_elapsed(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-fast"
    _write_fake_codex(fake_codex, relative_output="worker.py", last_message="fresh progress ok\n")

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml"], builder_root)
    _git(["commit", "-m", "configure fresh progress"], builder_root)

    active = _json(builder_root / "active_task.yml")
    active["started_at"] = "2020-01-01T00:00:00+00:00"
    _write_json(builder_root / "active_task.yml", active)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    run_dir = _active_run_dir(builder_root)
    first_event = _progress_events(run_dir)[0]
    assert first_event["stage_name"] == "Task selected"
    assert first_event["elapsed_seconds"] <= 1
    assert "Elapsed: 0s" in result.stdout or "Elapsed: 1s" in result.stdout
    assert "Step 1/9: Task selected [░░░░░░░░░░] 0% Complete" in result.stdout


def test_codex_exec_reports_possibly_stalled_status(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-stalled"
    _write_fake_codex_slow(fake_codex, relative_output="worker.py", sleep_seconds=3, last_message="stalled codex ok\n")

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    config["executor"]["heartbeat_seconds"] = 1
    config["executor"]["stall_threshold_seconds"] = 1
    config["executor"]["timeout_seconds"] = 10
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml"], builder_root)
    _git(["commit", "-m", "configure stalled codex"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    assert "status=possibly_stalled" in result.stdout
    run_dir = _active_run_dir(builder_root)
    progress_events = _progress_events(run_dir)
    assert any(event.get("status") == "possibly_stalled" for event in progress_events if event["stage_name"] == "Codex execution running")


def test_codex_exec_stdin_is_not_resent_on_each_heartbeat(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-stdin-once"
    fake_codex.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                "import time",
                "argv = sys.argv[1:]",
                "output_file = None",
                "for index, item in enumerate(argv):",
                "    if item == '-o' and index + 1 < len(argv):",
                "        output_file = Path(argv[index + 1])",
                "prompt = sys.stdin.read()",
                "target = Path.cwd() / 'worker.py'",
                "target.write_text(prompt, encoding='utf-8')",
                "time.sleep(2)",
                "if output_file is not None:",
                "    output_file.write_text('stdin once ok\\n', encoding='utf-8')",
                "sys.stdout.write('done')",
            ]
        ),
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    config["executor"]["heartbeat_seconds"] = 1
    config["executor"]["timeout_seconds"] = 10
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml"], builder_root)
    _git(["commit", "-m", "configure stdin once"], builder_root)
    prompt_path = Path(_json(builder_root / "active_task.yml")["prompt_file"])
    prompt_contents = prompt_path.read_text(encoding="utf-8")

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 0
    applied = (builder_root / "worker.py").read_text(encoding="utf-8")
    assert applied == prompt_contents


def test_keyboard_interrupt_cleans_up_codex_process(tmp_path: Path) -> None:
    module = _load_script_module()
    fake_codex = tmp_path / "fake-codex-hung"
    _write_fake_codex_hung(fake_codex)
    output_path = tmp_path / "codex_last_message.md"
    heartbeat_calls = {"count": 0}

    def _interrupt(_: dict) -> None:
        heartbeat_calls["count"] += 1
        raise KeyboardInterrupt

    result = module.run_codex_exec(
        [str(fake_codex), "exec", "-o", str(output_path), "-"],
        tmp_path,
        input_text="prompt\n",
        output_path=output_path,
        timeout=10,
        heartbeat_seconds=1,
        heartbeat=_interrupt,
    )

    assert heartbeat_calls["count"] == 1
    assert result["passed"] is False
    assert result["failure_reason"] == "executor_interrupted"
    assert result["cleanup"]["terminate_sent"] is True
    assert result["stderr_tail"].endswith("Interrupted by user.")


def test_interrupted_run_becomes_rerunnable_again(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-hung"
    _write_fake_codex_hung(fake_codex)

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    config["executor"]["heartbeat_seconds"] = 1
    config["executor"]["timeout_seconds"] = 30
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml"], builder_root)
    _git(["commit", "-m", "configure interrupt rerun"], builder_root)

    module = _load_script_module(builder_root)
    backlog = _json(builder_root / "backlog.yml")
    task = backlog["tasks"][0]
    active = _json(builder_root / "active_task.yml")
    status = _json(builder_root / "status.yml")
    active["state"] = "implementing"
    status["state"] = "implementing"
    automation_result = {
        "task_id": task["id"],
        "classification": "interrupted",
        "finished_at": "2026-03-24T00:00:01+00:00",
        "summary": "executor_interrupted",
        "steps": [{"name": "executor", "outcome": "interrupted", "detail": "Interrupted by user."}],
        "changed_files": [],
        "blocker_evidence": [],
        "unproven_runtime_gaps": ["executor_interrupted"],
    }
    module.classify_and_update_state("interrupted", "executor_interrupted", task, backlog, active, status, automation_result)
    module.write_data(module.BACKLOG, backlog)

    backlog = _json(builder_root / "backlog.yml")
    assert backlog["tasks"][0]["status"] == "ready"
    active = _json(builder_root / "active_task.yml")
    assert active["task_id"] is None
    assert active["state"] == "idle"
    status = _json(builder_root / "status.yml")
    assert status["state"] == "idle"
    assert status["active_task_id"] is None
    inspect = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)
    assert 'next_selected_task: "TASK-BUILDER"' in inspect.stdout
    rerun = _run([sys.executable, str(SCRIPT)], builder_root)
    assert "Step 1/9: Task selected" in rerun.stdout


def test_interruption_does_not_override_real_blocker(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    dirty = product_repo / "services" / "company_discovery.py"
    dirty.parent.mkdir(parents=True, exist_ok=True)
    dirty.write_text("dirty\n", encoding="utf-8")

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 2
    assert "repo is dirty before automated execution" in result.stdout
    backlog = _json(builder_root / "backlog.yml")
    assert backlog["tasks"][0]["status"] == "blocked"


def test_codex_exec_product_task_runs_in_product_repo(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _commit_allowlisted_product_file(product_repo, "services/company_discovery.py", "print('seed')\n")
    fake_codex = tmp_path / "fake-codex-product"
    _write_fake_codex(fake_codex, relative_output="services/company_discovery.py", last_message="product codex ok\n")

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    config["vm"]["ssh_target"] = "127.0.0.1"
    config["vm"]["ssh_options"] = ["-o", "ConnectTimeout=1"]
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml"], builder_root)
    _git(["commit", "-m", "configure codex exec"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert (product_repo / "services" / "company_discovery.py").exists()
    run_dir = _active_run_dir(builder_root)
    executor = _json(run_dir / "executor.json")
    assert executor["cwd"] == str(product_repo)
    assert executor["last_message"] == "product codex ok\n"
    payload = _json(run_dir / "automation_result.json")
    step_names = [step["name"] for step in payload["steps"]]
    assert payload["classification"] == "refined"
    assert "executor" in step_names
    assert "local_validation" in step_names
    assert "git" in step_names
    assert "vm_validation" in step_names
    assert "services/company_discovery.py" in payload["changed_files"]


def test_local_product_repo_path_still_behaves_as_expected(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _commit_allowlisted_product_file(product_repo, "services/company_discovery.py", "print('seed')\n")
    _ignore_path_in_git_status(product_repo, ".venv_validation")
    _write_activate_script(product_repo / ".venv_validation")

    active = _json(builder_root / "active_task.yml")
    active["verification_commands"] = [f'test "$VIRTUAL_ENV" = "{product_repo / ".venv_validation"}"']
    _write_json(builder_root / "active_task.yml", active)

    pause = _run([sys.executable, str(SCRIPT)], builder_root)
    assert pause.returncode == 0

    (product_repo / "services" / "company_discovery.py").write_text("print('changed')\n", encoding="utf-8")

    resume = _run([sys.executable, str(SCRIPT), "--resume"], builder_root)

    assert resume.returncode in {1, 2}
    updated_active = _json(builder_root / "active_task.yml")
    assert updated_active["target_repo"] == str(product_repo)
    validation = _json(_active_run_dir(builder_root) / "local_validation.json")
    assert validation["venv_path"] == str(product_repo / ".venv_validation")


def test_inspect_backlog_reports_validation_errors(tmp_path: Path) -> None:
    builder_root = tmp_path / "builder"
    product_repo = tmp_path / "jorb"
    _init_repo(builder_root)
    _init_repo(product_repo)
    _write_json(builder_root / "config.yml", _base_config(product_repo, builder_root))
    _write_json(
        builder_root / "backlog.yml",
        {
            "version": 1,
            "tasks": [
                {
                    "id": "TASK-1",
                    "title": "Bad task",
                    "priority": "p1",
                    "status": "ready",
                    "type": "feature",
                    "area": "discovery",
                    "repo_path": str(product_repo),
                    "description": "bad",
                    "verification": [],
                },
                {
                    "id": "TASK-1",
                    "title": "Duplicate task",
                    "priority": 1,
                    "status": "nope",
                    "type": "feature",
                    "area": "discovery",
                    "repo_path": str(product_repo),
                    "description": "bad",
                    "acceptance_criteria": [],
                    "verification": [],
                },
            ],
        },
    )
    _write_json(builder_root / "status.yml", _base_status())
    _write_json(builder_root / "active_task.yml", {"task_id": None, "title": None, "state": "idle", "attempt": 0, "started_at": None, "handed_to_codex_at": None, "prompt_file": None, "run_log_dir": None, "verification_commands": [], "allowlist": [], "failure_summary": None, "notes": []})
    (builder_root / "builder_memory.md").write_text("# Memory\n", encoding="utf-8")
    (builder_root / "blockers").mkdir(exist_ok=True)

    result = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)

    assert result.returncode == 1
    assert "BACKLOG_INVALID" in result.stdout
    assert "duplicate_task_id" in result.stdout
    assert "invalid_priority" in result.stdout


def test_check_auth_reports_interactive_https_remote(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _git(["remote", "set-url", "origin", "https://github.com/example/jorb.git"], product_repo)
    config = _json(builder_root / "config.yml")
    config["vm"]["ssh_target"] = "127.0.0.1"
    config["vm"]["ssh_options"] = ["-o", "ConnectTimeout=1"]
    _write_json(builder_root / "config.yml", config)

    result = _run([sys.executable, str(SCRIPT), "--check-auth"], builder_root)

    assert result.returncode == 1
    assert "GitHub auth status:" in result.stdout
    assert "https_interactive_likely" in result.stdout
    assert "run_interactive: true" in result.stdout.lower()


def test_inspect_backlog_shows_ready_queue(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    backlog["tasks"].append(
        {
            "id": "TASK-LATER",
            "title": "TASK-LATER",
            "type": "infrastructure",
            "area": "builder",
            "milestone": "M0",
            "priority": 2,
            "status": "pending",
            "retries_used": 0,
            "depends_on": [],
            "prompt": "implement_feature",
            "objective": "obj2",
            "why_it_matters": "why2",
            "allowlist": ["../jorb-builder/**"],
            "forbid": [],
            "verification": [],
            "acceptance": ["a"],
            "notes": [],
        }
    )
    _write_json(builder_root / "backlog.yml", backlog)

    result = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)

    assert result.returncode == 0
    assert "ready_queue:" in result.stdout
    assert '"TASK-BUILDER"' in result.stdout
    assert "next_selected_task" in result.stdout


def test_check_auth_runs_without_ready_tasks(tmp_path: Path) -> None:
    builder_root = tmp_path / "builder"
    product_repo = tmp_path / "jorb"
    _init_repo(builder_root)
    _init_repo(product_repo)
    _write_json(builder_root / "config.yml", _base_config(product_repo, builder_root))
    _write_json(builder_root / "backlog.yml", {"version": 1, "tasks": []})
    _write_json(builder_root / "status.yml", _base_status())
    _write_json(builder_root / "active_task.yml", {"task_id": None, "title": None, "state": "idle", "attempt": 0, "started_at": None, "handed_to_codex_at": None, "prompt_file": None, "run_log_dir": None, "verification_commands": [], "allowlist": [], "failure_summary": None, "notes": []})
    (builder_root / "builder_memory.md").write_text("# Memory\n", encoding="utf-8")
    (builder_root / "task_history").mkdir(exist_ok=True)
    (builder_root / "blockers").mkdir(exist_ok=True)
    _git(["remote", "add", "origin", "https://github.com/example/jorb.git"], product_repo)

    result = _run([sys.executable, str(SCRIPT), "--check-auth"], builder_root)

    assert result.returncode == 1
    assert "GitHub auth status:" in result.stdout
    assert "VM SSH status:" in result.stdout
    assert "NO_READY_TASKS_REMAIN" not in result.stdout


def test_mode_dispatch_order_keeps_check_auth_out_of_bootstrap(tmp_path: Path) -> None:
    builder_root = tmp_path / "builder"
    product_repo = tmp_path / "jorb"
    _init_repo(builder_root)
    _init_repo(product_repo)
    _write_json(builder_root / "config.yml", _base_config(product_repo, builder_root))
    _write_json(
        builder_root / "backlog.yml",
        {
            "version": 1,
            "tasks": [
                {
                    "id": "TASK-READY",
                    "title": "TASK-READY",
                    "type": "feature",
                    "area": "discovery",
                    "repo_path": str(product_repo),
                    "description": "desc",
                    "priority": 1,
                    "status": "ready",
                    "acceptance_criteria": [],
                    "verification": [],
                }
            ],
        },
    )
    _write_json(builder_root / "status.yml", _base_status())
    _write_json(builder_root / "active_task.yml", {"task_id": None, "title": None, "state": "idle", "attempt": 0, "started_at": None, "handed_to_codex_at": None, "prompt_file": None, "run_log_dir": None, "verification_commands": [], "allowlist": [], "failure_summary": None, "notes": []})
    (builder_root / "builder_memory.md").write_text("# Memory\n", encoding="utf-8")
    (builder_root / "task_history").mkdir(exist_ok=True)
    (builder_root / "blockers").mkdir(exist_ok=True)
    _git(["remote", "add", "origin", "https://github.com/example/jorb.git"], product_repo)

    result = _run([sys.executable, str(SCRIPT), "--check-auth"], builder_root)

    assert result.returncode == 1
    active_after = _json(builder_root / "active_task.yml")
    assert active_after["task_id"] is None
    assert "GitHub auth status:" in result.stdout
    assert "NO_READY_TASKS_REMAIN" not in result.stdout


def test_live_backlog_file_is_canonical_json_and_contains_new_tasks() -> None:
    backlog = json.loads((LIVE_BUILDER_ROOT / "backlog.yml").read_text(encoding="utf-8"))
    tasks = {task["id"]: task for task in backlog["tasks"]}

    assert len(backlog["tasks"]) >= 23
    for task_id in [
        "JORB-V1-006",
        "JORB-V1-007",
        "JORB-V1-015",
        "JORB-V1-016",
        "JORB-V1-017",
        "JORB-INFRA-003",
        "JORB-INFRA-004",
        "JORB-INFRA-005",
    ]:
        assert task_id in tasks
        assert tasks[task_id]["status"] in {
            "pending",
            "ready",
            "retry_ready",
            "selected",
            "packet_rendered",
            "implementing",
            "verifying",
            "blocked",
            "accepted",
            "done",
        }


def test_auth_preflight_failure_does_not_launch_executor_or_running_progress(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-auth"
    _write_fake_codex(fake_codex, relative_output="worker.py", last_message="should not run\n")

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["remote", "set-url", "origin", "https://github.com/example/builder.git"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 2
    run_dir = _active_run_dir(builder_root)
    assert not (run_dir / "executor.json").exists()
    assert not (builder_root / "worker.py").exists()
    progress_path = run_dir / "progress.jsonl"
    if progress_path.exists():
        progress_events = [json.loads(line) for line in progress_path.read_text(encoding="utf-8").splitlines()]
        assert progress_events
        assert all(event["state"] == "failed" for event in progress_events)
    active = _json(builder_root / "active_task.yml")
    status = _json(builder_root / "status.yml")
    assert active["state"] == "preflight_failed"
    assert status["state"] == "preflight_failed"
    assert status["last_result"] == "blocked"


def test_fresh_invocation_after_terminal_state_uses_new_run_dir(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-fresh"
    _write_fake_codex(fake_codex, relative_output="worker.py", last_message="fresh run ok\n")

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml"], builder_root)
    _git(["commit", "-m", "configure fresh run"], builder_root)

    _seed_legacy_auth_preflight_blocked_state(builder_root, task_id="TASK-BUILDER")
    first_run_dir = _active_run_dir(builder_root)
    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)
    assert repair.returncode == 0

    second = _run([sys.executable, str(SCRIPT)], builder_root)
    assert second.returncode == 0
    second_run_dir = _active_run_dir(builder_root)
    assert second_run_dir != first_run_dir


def test_missing_codex_last_message_triggers_executor_failure(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-no-output"
    _write_fake_codex_without_output(fake_codex, relative_output="worker.py")

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml"], builder_root)
    _git(["commit", "-m", "configure missing output"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 2
    run_dir = _active_run_dir(builder_root)
    executor = _json(run_dir / "executor.json")
    assert executor["failure_reason"] == "executor_failure"
    assert executor["output_file_exists"] is False
    payload = _json(run_dir / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert payload["summary"] == "executor_failure"
    assert "did not create codex_last_message.md" in payload["steps"][0]["detail"]
    assert "executor_failure" in payload["blocker_evidence"]


def test_transient_codex_transport_failure_reopens_task(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-transport-failure"
    _write_fake_codex_transport_failure(fake_codex)

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml"], builder_root)
    _git(["commit", "-m", "configure transport failure"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert "INTERRUPTED" in result.stdout
    assert "executor_transport_failure" in result.stdout
    assert "Codex lost its upstream connection before completion" in result.stdout
    backlog = _json(builder_root / "backlog.yml")
    assert backlog["tasks"][0]["status"] == "ready"
    active = _json(builder_root / "active_task.yml")
    assert active["task_id"] is None
    status = _json(builder_root / "status.yml")
    assert status["active_task_id"] is None
    assert status["last_result"] == "interrupted"
    run_dir = sorted(
        (path for path in (builder_root / "run_logs").glob("*") if (path / "automation_result.json").exists()),
        key=lambda item: item.name,
    )[-1]
    payload = _json(run_dir / "automation_result.json")
    assert payload["classification"] == "interrupted"
    assert payload["summary"] == "executor_transport_failure: Codex lost its upstream connection before completion"


def test_repair_state_reopens_transient_executor_failure(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "blocked"
    _write_json(builder_root / "backlog.yml", backlog)

    active = _json(builder_root / "active_task.yml")
    active["state"] = "blocked"
    active["failure_summary"] = "executor_failure"
    _write_json(builder_root / "active_task.yml", active)

    status = _json(builder_root / "status.yml")
    status["state"] = "blocked"
    status["active_task_id"] = "TASK-BUILDER"
    status["last_task_id"] = "TASK-BUILDER"
    status["last_result"] = "blocked"
    _write_json(builder_root / "status.yml", status)

    _write_json(
        run_log_dir / "executor.json",
        {
            "passed": False,
            "failure_reason": "executor_failure",
            "stderr": "ERROR: stream disconnected before completion: error sending request for url (https://chatgpt.com/backend-api/codex/responses)\nchannel closed\n",
            "stdout": "",
        },
    )
    _write_json(
        builder_root / "blockers" / "BLK-TASK-BUILDER.yml",
        {
            "id": "BLK-TASK-BUILDER",
            "title": "Task TASK-BUILDER blocked during automated execution",
            "related_tasks": ["TASK-BUILDER"],
            "status": "open",
            "diagnosis": "executor_failure",
        },
    )

    result = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)

    assert result.returncode == 0
    assert "blocked -> ready" in result.stdout
    backlog = _json(builder_root / "backlog.yml")
    assert backlog["tasks"][0]["status"] == "ready"
    active = _json(builder_root / "active_task.yml")
    assert active["task_id"] is None
    status = _json(builder_root / "status.yml")
    assert status["active_task_id"] is None
    assert status["last_result"] == "interrupted"


def test_hung_codex_subprocess_times_out_and_is_blocked(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    fake_codex = tmp_path / "fake-codex-hung"
    _write_fake_codex_hung(fake_codex)

    config = _json(builder_root / "config.yml")
    config["executor"]["mode"] = "codex_exec"
    config["executor"]["codex_cli"] = str(fake_codex)
    config["executor"]["timeout_seconds"] = 1
    _write_json(builder_root / "config.yml", config)
    _git(["add", "config.yml"], builder_root)
    _git(["commit", "-m", "configure codex timeout"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 2
    run_dir = _active_run_dir(builder_root)
    executor = _json(run_dir / "executor.json")
    assert executor["timed_out"] is True
    assert executor["failure_reason"] == "executor_timeout"
    assert executor["cleanup"]["terminate_sent"] is True
    payload = _json(run_dir / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert payload["summary"] == "executor_timeout"
    assert "executor_timeout" in payload["blocker_evidence"]


def test_state_consistency_mismatch_fails_fast(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    status = _json(builder_root / "status.yml")
    status["state"] = "implementing"
    status["active_task_id"] = "OTHER-TASK"
    _write_json(builder_root / "status.yml", status)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 1
    assert "INVALID_ACTIVE_TASK_STATE" in result.stdout


def test_repair_state_migrates_legacy_failed_preflight_to_idle_ready(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _seed_legacy_auth_preflight_blocked_state(builder_root, task_id="TASK-PRODUCT")

    result = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)

    assert result.returncode == 0
    assert "STATE_REPAIRED" in result.stdout
    active = _json(builder_root / "active_task.yml")
    status = _json(builder_root / "status.yml")
    backlog = _json(builder_root / "backlog.yml")
    blocker = _json(builder_root / "blockers" / "BLK-TASK-PRODUCT.yml")
    assert active["task_id"] is None
    assert active["state"] == "idle"
    assert active["previous_run_log_dir"] is not None
    assert status["state"] == "idle"
    assert status["active_task_id"] is None
    assert set(status["state_legend"]) == {
        "idle",
        "task_selected",
        "preflight_passed",
        "preflight_failed",
        "implementing",
        "verifying",
        "completed",
        "blocked",
    }
    assert backlog["tasks"][0]["status"] == "ready"
    assert blocker["status"] == "resolved"


def test_repair_state_allows_clean_fresh_invocation(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    _seed_legacy_auth_preflight_blocked_state(builder_root, task_id="TASK-BUILDER")

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)
    assert repair.returncode == 0

    run = _run([sys.executable, str(SCRIPT)], builder_root)

    assert run.returncode == 0
    assert "INVALID_ACTIVE_TASK_STATE" not in run.stdout
    assert "PAUSED" in run.stdout


def test_repair_state_does_not_introduce_false_resume_semantics(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    _seed_legacy_auth_preflight_blocked_state(builder_root, task_id="TASK-BUILDER")

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)
    assert repair.returncode == 0

    resume = _run([sys.executable, str(SCRIPT), "--resume"], builder_root)

    assert resume.returncode == 1
    assert "ACTIVE_TASK_MISSING_BUT_READY_TASKS_EXIST" in resume.stdout


def test_repair_state_reopens_stale_dirty_repo_blocker_when_repo_is_clean(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "blocked"
    _write_json(builder_root / "backlog.yml", backlog)
    active = _json(builder_root / "active_task.yml")
    active["state"] = "implementing"
    active["target_repo"] = str(product_repo)
    active["target_kind"] = "product"
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "implementing"
    status["last_result"] = "blocked"
    _write_json(builder_root / "status.yml", status)
    _write_json(
        builder_root / "blockers" / "BLK-TASK-PRODUCT.yml",
        {
            "id": "BLK-TASK-PRODUCT",
            "title": "Task TASK-PRODUCT blocked during automated execution",
            "related_tasks": ["TASK-PRODUCT"],
            "status": "open",
            "diagnosis": "Product repo is dirty before automated execution; refusing to continue.",
        },
    )

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)
    inspect = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)

    assert repair.returncode == 0
    assert "blocked -> ready" in repair.stdout
    backlog_after = _json(builder_root / "backlog.yml")
    assert backlog_after["tasks"][0]["status"] == "ready"
    blocker_after = _json(builder_root / "blockers" / "BLK-TASK-PRODUCT.yml")
    assert blocker_after["status"] == "resolved"
    assert '"next_selected_task: "TASK-PRODUCT""' in inspect.stdout.lower() or 'next_selected_task: "TASK-PRODUCT"' in inspect.stdout


def test_repair_state_keeps_current_dirty_repo_blocker_blocked(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "blocked"
    _write_json(builder_root / "backlog.yml", backlog)
    active = _json(builder_root / "active_task.yml")
    active["state"] = "implementing"
    active["target_repo"] = str(product_repo)
    active["target_kind"] = "product"
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "implementing"
    status["last_result"] = "blocked"
    _write_json(builder_root / "status.yml", status)
    (product_repo / "services").mkdir(exist_ok=True)
    (product_repo / "services" / "company_discovery.py").write_text("print('changed')\n", encoding="utf-8")

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)

    assert repair.returncode == 0
    assert "remains blocked" in repair.stdout


def test_repair_state_reopens_stale_executor_interruption_when_no_real_blocker_remains(tmp_path: Path) -> None:
    builder_root, product_repo, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "blocked"
    _write_json(builder_root / "backlog.yml", backlog)
    active = _json(builder_root / "active_task.yml")
    active["state"] = "blocked"
    active["target_repo"] = str(product_repo)
    active["target_kind"] = "product"
    active["failure_summary"] = "executor_interrupted"
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "blocked"
    status["last_result"] = "blocked"
    _write_json(builder_root / "status.yml", status)
    _write_json(
        run_log_dir / "automation_result.json",
        {
            "task_id": "TASK-PRODUCT",
            "classification": "interrupted",
            "finished_at": "2026-03-24T00:20:00+00:00",
            "summary": "executor_interrupted",
            "steps": [{"name": "executor", "outcome": "interrupted", "detail": "Interrupted by user."}],
            "changed_files": [],
            "blocker_evidence": [],
            "unproven_runtime_gaps": ["executor_interrupted"],
        },
    )
    _write_json(
        builder_root / "blockers" / "BLK-TASK-PRODUCT.yml",
        {
            "id": "BLK-TASK-PRODUCT",
            "title": "Task TASK-PRODUCT blocked during automated execution",
            "related_tasks": ["TASK-PRODUCT"],
            "status": "open",
            "diagnosis": "executor_interrupted",
        },
    )

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)
    inspect = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)

    assert repair.returncode == 0
    assert "blocked -> ready" in repair.stdout
    backlog_after = _json(builder_root / "backlog.yml")
    assert backlog_after["tasks"][0]["status"] == "ready"
    active_after = _json(builder_root / "active_task.yml")
    assert active_after["task_id"] is None
    assert active_after["state"] == "idle"
    status_after = _json(builder_root / "status.yml")
    assert status_after["state"] == "idle"
    blocker_after = _json(builder_root / "blockers" / "BLK-TASK-PRODUCT.yml")
    assert blocker_after["status"] == "resolved"
    assert 'next_selected_task: "TASK-PRODUCT"' in inspect.stdout


def test_repair_state_finalizes_terminal_result_after_late_crash(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-023",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    _write_json(builder_root / "backlog.yml", backlog)

    active = _json(builder_root / "active_task.yml")
    active["state"] = "implementing"
    active["run_log_dir"] = str(run_log_dir)
    _write_json(builder_root / "active_task.yml", active)

    status = _json(builder_root / "status.yml")
    status["state"] = "implementing"
    status["active_task_id"] = "JORB-INFRA-023"
    status["last_task_id"] = "JORB-INFRA-023"
    _write_json(builder_root / "status.yml", status)

    _write_json(
        run_log_dir / "automation_result.json",
        {
            "task_id": "JORB-INFRA-023",
            "classification": "accepted",
            "finished_at": "2026-03-30T00:00:00+00:00",
            "summary": "Implemented direct run scoring for the private builder eval suite.",
            "steps": [{"name": "local_validation", "outcome": "passed", "detail": "ok"}],
            "changed_files": ["scripts/private_eval_suite.py"],
            "blocker_evidence": [],
            "unproven_runtime_gaps": [],
        },
    )

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)
    backlog_after = _json(builder_root / "backlog.yml")
    active_after = _json(builder_root / "active_task.yml")
    status_after = _json(builder_root / "status.yml")

    assert repair.returncode == 0
    assert "finalized from terminal automation_result -> accepted" in repair.stdout
    assert backlog_after["tasks"][0]["status"] == "accepted"
    assert active_after["task_id"] is None
    assert status_after["last_result"] == "accepted"


def test_emit_progress_ignores_running_heartbeat_after_terminal_result_exists(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    module = _load_script_module(builder_root)
    _write_json(
        run_log_dir / "automation_result.json",
        {
            "task_id": "TASK-BUILDER",
            "classification": "accepted",
            "finished_at": "2026-03-30T00:00:00+00:00",
            "summary": "done",
            "steps": [],
            "changed_files": [],
        },
    )
    progress_path = run_log_dir / "progress.jsonl"
    before = progress_path.read_text(encoding="utf-8") if progress_path.exists() else ""

    module.emit_progress(
        run_log_dir,
        task_id="TASK-BUILDER",
        stage_index=3,
        backlog=_json(builder_root / "backlog.yml"),
        task_started_at="2026-03-30T00:00:00+00:00",
        state="running",
        detail="heartbeat",
    )

    after = progress_path.read_text(encoding="utf-8") if progress_path.exists() else ""
    assert after == before


def test_dry_run_does_not_leave_stale_task_selected_state(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    _write_json(builder_root / "backlog.yml", backlog)
    active = _json(builder_root / "active_task.yml")
    active["state"] = "task_selected"
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "task_selected"
    status["active_task_id"] = "TASK-BUILDER"
    _write_json(builder_root / "status.yml", status)
    _git(["add", "active_task.yml", "backlog.yml", "status.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "prepare dry run state"], builder_root)

    dry_run = _run([sys.executable, str(SCRIPT), "--dry-run"], builder_root)
    assert dry_run.returncode == 0
    active_after = _json(builder_root / "active_task.yml")
    status_after = _json(builder_root / "status.yml")
    assert active_after["task_id"] is None
    assert active_after["state"] == "idle"
    assert status_after["state"] == "idle"
    run = _run([sys.executable, str(SCRIPT)], builder_root)
    assert "INVALID_ACTIVE_TASK_STATE" not in run.stdout


def test_dry_run_routes_task_vm_verification_to_vm_plan_only(tmp_path: Path) -> None:
    builder_root, product_repo, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    backlog["tasks"][0]["verification"] = ["pytest tests/test_workbench.py"]
    backlog["tasks"][0]["vm_verification"] = ["bash scripts/runtime_self_check.sh"]
    _write_json(builder_root / "backlog.yml", backlog)
    active = _json(builder_root / "active_task.yml")
    active["state"] = "task_selected"
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "task_selected"
    status["active_task_id"] = "TASK-PRODUCT"
    _write_json(builder_root / "status.yml", status)
    _git(["add", "active_task.yml", "backlog.yml", "status.yml", "prompts/implement_feature.md"], builder_root)
    _git(["commit", "-m", "prepare dry run vm verification state"], builder_root)

    dry_run = _run([sys.executable, str(SCRIPT), "--dry-run"], builder_root)

    assert dry_run.returncode == 0
    active_after = _json(builder_root / "active_task.yml")
    run_dir = Path(active_after["previous_run_log_dir"])
    payload = _json(run_dir / "automation_result.json")
    plan = json.loads(payload["steps"][0]["detail"])
    assert plan["local_validation_commands"] == ["pytest tests/test_workbench.py"]
    assert plan["prepared_local_validation_commands"] == ["pytest tests/test_workbench.py"]
    assert "bash scripts/runtime_self_check.sh" in plan["vm_commands"]
    assert plan["local_validation_commands"] != plan["vm_commands"]


def test_product_task_blocks_when_runtime_self_check_ui_port_mismatches_bootstrap(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _mark_retry_ready(builder_root)
    _write_prior_vm_refined_result(run_log_dir, changed_files=["services/company_discovery.py"])

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["vm_bootstrap"] = []
    backlog["tasks"][0]["vm_verification"] = ["bash scripts/runtime_self_check.sh"]
    _write_json(builder_root / "backlog.yml", backlog)

    config = _json(builder_root / "config.yml")
    config["vm"]["ssh_target"] = "vm.example"
    config["vm"]["validation_commands"] = ["echo vm-preflight"]
    config["vm"]["bootstrap_commands"] = [
        "nohup streamlit run ui/app.py --server.port 8501 --server.address 0.0.0.0 >/tmp/jorb_ui.log 2>&1 &"
    ]
    config["vm"]["runtime_validation_commands"] = []
    _write_json(builder_root / "config.yml", config)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 2
    assert "vm runtime UI mismatch: bootstrap uses http://127.0.0.1:8501 but runtime_self_check expects http://127.0.0.1:8500" in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert payload["summary"] == "Missing automation configuration: vm runtime UI mismatch: bootstrap uses http://127.0.0.1:8501 but runtime_self_check expects http://127.0.0.1:8500"


def test_repair_state_clears_stale_dry_run_active_state(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    _write_json(builder_root / "backlog.yml", backlog)
    active = _json(builder_root / "active_task.yml")
    active["state"] = "task_selected"
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "task_selected"
    status["active_task_id"] = "TASK-BUILDER"
    _write_json(builder_root / "status.yml", status)
    _write_json(
        run_log_dir / "automation_result.json",
        {
            "task_id": "TASK-BUILDER",
            "classification": "dry_run",
            "finished_at": "2026-03-25T07:01:48.098517+00:00",
            "summary": "Dry run only. No executor, git, or VM commands were executed.",
            "steps": [{"name": "plan", "outcome": "planned", "detail": "plan"}],
            "changed_files": [],
            "unproven_runtime_gaps": ["Automation loop not executed; this was a dry run."],
        },
    )

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)

    assert repair.returncode == 0
    active_after = _json(builder_root / "active_task.yml")
    status_after = _json(builder_root / "status.yml")
    backlog_after = _json(builder_root / "backlog.yml")
    assert active_after["state"] == "idle"
    assert active_after["task_id"] is None
    assert status_after["state"] == "idle"
    assert backlog_after["tasks"][0]["status"] == "ready"


def test_repair_state_clears_stale_blocked_active_task_when_backlog_truth_is_pending(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "pending"
    backlog["tasks"].append(
        {
            "id": "TASK-NEXT",
            "title": "Next runnable task",
            "status": "ready",
            "priority": 1,
            "type": "infrastructure",
            "area": "builder",
            "description": "A valid next runnable task.",
            "verification": ["python3 -m py_compile scripts/*.py"],
            "allowlist": ["../jorb-builder/**"],
            "repo_path": "~/projects/jorb-builder",
        }
    )
    _write_json(builder_root / "backlog.yml", backlog)
    active = _json(builder_root / "active_task.yml")
    active["state"] = "blocked"
    active["failure_summary"] = "Local validation failed after executor changes."
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "blocked"
    status["last_result"] = "refined"
    _write_json(builder_root / "status.yml", status)
    _write_json(
        run_log_dir / "automation_result.json",
        {
            "task_id": "TASK-PRODUCT",
            "classification": "blocked",
            "finished_at": "2026-03-26T17:49:14+00:00",
            "summary": "Local validation failed after executor changes.",
            "steps": [{"name": "local_validation", "outcome": "failed", "detail": "validation failed"}],
            "changed_files": [],
            "blocker_evidence": [],
            "unproven_runtime_gaps": [],
        },
    )

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)
    active_after = _json(builder_root / "active_task.yml")
    status_after = _json(builder_root / "status.yml")
    inspect = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)
    rerun = _run([sys.executable, str(SCRIPT)], builder_root)

    assert repair.returncode == 0
    assert "stale active task TASK-PRODUCT cleared because backlog truth is pending" in repair.stdout
    assert active_after["task_id"] is None
    assert active_after["state"] == "idle"
    assert status_after["state"] == "idle"
    assert status_after["active_task_id"] is None
    assert 'next_selected_task: "TASK-NEXT"' in inspect.stdout
    assert "ACTIVE_TASK_MISSING_BUT_READY_TASKS_EXIST" not in rerun.stdout


def test_repair_state_clears_stale_retry_without_changes_when_task_is_ready(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "ready"
    _write_json(builder_root / "backlog.yml", backlog)
    active = _json(builder_root / "active_task.yml")
    active["state"] = "blocked"
    active["failure_summary"] = "Retry-ready task has no product repo changes to continue from."
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "blocked"
    status["last_result"] = "refined"
    _write_json(builder_root / "status.yml", status)
    _write_no_changes_refined_result(run_log_dir)

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)
    active_after = _json(builder_root / "active_task.yml")
    status_after = _json(builder_root / "status.yml")
    backlog_after = _json(builder_root / "backlog.yml")
    inspect = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)

    assert repair.returncode == 0
    assert "stale retry-ready continuation for TASK-PRODUCT cleared -> fresh ready rerun" in repair.stdout
    assert active_after["task_id"] is None
    assert active_after["state"] == "idle"
    assert status_after["state"] == "idle"
    assert status_after["active_task_id"] is None
    assert status_after["last_result"] == "refined"
    assert backlog_after["tasks"][0]["status"] == "ready"
    assert 'next_selected_task: "TASK-PRODUCT"' in inspect.stdout


def test_repair_state_clears_stale_retry_without_changes_when_task_is_retry_ready(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "retry_ready"
    _write_json(builder_root / "backlog.yml", backlog)
    active = _json(builder_root / "active_task.yml")
    active["state"] = "blocked"
    active["failure_summary"] = "Retry-ready task has no product repo changes to continue from."
    _write_json(builder_root / "active_task.yml", active)
    status = _json(builder_root / "status.yml")
    status["state"] = "blocked"
    status["last_result"] = "refined"
    _write_json(builder_root / "status.yml", status)
    _write_no_changes_refined_result(run_log_dir)

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)
    active_after = _json(builder_root / "active_task.yml")
    status_after = _json(builder_root / "status.yml")
    inspect = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)

    assert repair.returncode == 0
    assert "stale retry-ready continuation for TASK-PRODUCT cleared -> fresh ready rerun" in repair.stdout
    assert active_after["task_id"] is None
    assert active_after["state"] == "idle"
    assert status_after["state"] == "idle"
    assert status_after["active_task_id"] is None
    backlog_after = _json(builder_root / "backlog.yml")
    assert backlog_after["tasks"][0]["status"] == "ready"
    assert 'next_selected_task: "TASK-PRODUCT"' in inspect.stdout


def test_repair_state_clears_blocked_active_slot_when_other_task_is_runnable(tmp_path: Path) -> None:
    builder_root, product_repo, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BLOCKED",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "blocked"
    backlog["tasks"].append(
        {
            "id": "TASK-NEXT",
            "title": "Next runnable task",
            "priority": 1,
            "status": "ready",
            "type": "feature",
            "area": "builder",
            "repo_path": "~/projects/jorb-builder",
            "description": "A runnable follow-on task.",
            "acceptance_criteria": ["next task runs"],
            "verification": ["python3 -m py_compile scripts/*.py"],
            "allowlist": ["../jorb-builder/**"],
            "forbid": [],
            "depends_on": [],
        },
    )
    _write_json(builder_root / "backlog.yml", backlog)

    dirty_file = product_repo / "services" / "company_discovery.py"
    dirty_file.parent.mkdir(parents=True, exist_ok=True)
    dirty_file.write_text("dirty\n", encoding="utf-8")

    active = _json(builder_root / "active_task.yml")
    active["state"] = "blocked"
    active["failure_summary"] = "Product repo is dirty before automated execution; refusing to continue."
    _write_json(builder_root / "active_task.yml", active)

    status = _json(builder_root / "status.yml")
    status["state"] = "blocked"
    status["last_result"] = "blocked"
    _write_json(builder_root / "status.yml", status)

    _write_json(
        run_log_dir / "automation_result.json",
        {
            "task_id": "TASK-BLOCKED",
            "classification": "blocked",
            "finished_at": "2026-03-27T00:00:00+00:00",
            "summary": "Product repo is dirty before automated execution; refusing to continue.",
            "steps": [{"name": "git_status_before", "outcome": "blocked", "detail": "services/company_discovery.py"}],
            "changed_files": ["services/company_discovery.py"],
            "blocker_evidence": ["services/company_discovery.py"],
            "unproven_runtime_gaps": ["Product repo is dirty before automated execution; refusing to continue."],
        },
    )

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)
    active_after = _json(builder_root / "active_task.yml")
    status_after = _json(builder_root / "status.yml")
    inspect = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)

    assert repair.returncode == 0
    assert "cleared stale blocked active task so runnable task TASK-NEXT can proceed" in repair.stdout
    assert active_after["task_id"] is None
    assert active_after["state"] == "idle"
    assert status_after["state"] == "idle"
    assert status_after["active_task_id"] is None
    assert 'next_selected_task: "TASK-NEXT"' in inspect.stdout


def test_repair_state_reopens_builder_task_when_only_generated_state_files_remain(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "blocked"
    _write_json(builder_root / "backlog.yml", backlog)

    active = _json(builder_root / "active_task.yml")
    active["state"] = "blocked"
    active["failure_summary"] = "Builder repo is dirty before automated execution; refusing to continue."
    _write_json(builder_root / "active_task.yml", active)

    status = _json(builder_root / "status.yml")
    status["state"] = "blocked"
    status["last_result"] = "blocked"
    _write_json(builder_root / "status.yml", status)

    _write_json(
        run_log_dir / "automation_result.json",
        {
            "task_id": "TASK-BUILDER",
            "classification": "blocked",
            "finished_at": "2026-03-27T00:00:00+00:00",
            "summary": "Builder repo is dirty before automated execution; refusing to continue.",
            "steps": [{"name": "git_status_before", "outcome": "blocked", "detail": "run_ledger.json"}],
            "changed_files": ["run_ledger.json"],
            "blocker_evidence": ["run_ledger.json"],
            "unproven_runtime_gaps": ["Builder repo is dirty before automated execution; refusing to continue."],
        },
    )

    (builder_root / "run_ledger.json").write_text('{"state":"idle"}\n', encoding="utf-8")
    (builder_root / "backlog_proposals.json").write_text('{"proposals":[]}\n', encoding="utf-8")

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)
    active_after = _json(builder_root / "active_task.yml")
    status_after = _json(builder_root / "status.yml")
    backlog_after = _json(builder_root / "backlog.yml")
    inspect = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)
    status_view = _run([sys.executable, str(SCRIPT.parent / "show_status.py")], builder_root)

    assert repair.returncode == 0
    assert "backlog task TASK-BUILDER blocked -> ready" in repair.stdout
    assert active_after["task_id"] is None
    assert active_after["state"] == "idle"
    assert status_after["state"] == "idle"
    assert status_after["active_task_id"] is None
    assert backlog_after["tasks"][0]["status"] == "ready"
    assert 'next_selected_task: "TASK-BUILDER"' in inspect.stdout
    assert "- run_state: idle" in status_view.stdout
    assert "- current_blocker: none" in status_view.stdout


def test_phase4_dry_run_emits_stage_plan_and_repo_local_standards(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    (builder_root / "AGENTS.md").write_text(
        "# Builder Agents\n\nCore expectations:\n- Treat backlog truth, config, run logs, and generated artifacts as first-class system inputs.\n\nExecution roles:\n- Planner: compile the feature/system understanding artifact.\n- Judge: accept or reject only from evidence.\n",
        encoding="utf-8",
    )
    skills_dir = builder_root / "skills"
    skills_dir.mkdir(exist_ok=True)
    (skills_dir / "README.md").write_text(
        "# Builder Skills\n\nCurrent skills:\n- `phase4_enforcement`: require planner/architect/judge artifacts and evidence before acceptance.\n",
        encoding="utf-8",
    )

    dry_run = _run([sys.executable, str(SCRIPT), "--dry-run"], builder_root)
    assert dry_run.returncode == 0, dry_run.stdout + dry_run.stderr

    run_dir = max((builder_root / "run_logs").glob("*"), key=lambda path: path.stat().st_mtime)
    payload = _json(run_dir / "automation_result.json")
    planned_steps = [step["name"] for step in payload["steps"]]
    assert planned_steps[:7] == [
        "planner",
        "architect",
        "research_grounding",
        "decision_checkpoint",
        "implementer",
        "validator",
        "judge",
    ]
    assert any(path.endswith("compiled_feature_spec.md") for path in payload["planned_artifacts"])
    plan_detail = next(step["detail"] for step in payload["steps"] if step["name"] == "plan")
    assert '"phase4_stage_order"' in plan_detail
    assert '"repo_local_standards"' in plan_detail
    feature_spec = (run_dir / "compiled_feature_spec.md").read_text(encoding="utf-8")
    match = re.search(r"## Machine-Checkable Payload\n```json\n(.*?)\n```", feature_spec, re.DOTALL)
    assert match is not None
    machine_payload = json.loads(match.group(1))
    assert machine_payload["task_id"] == "JORB-INFRA-010"
    assert machine_payload["task_title"] == "JORB-INFRA-010"
    assert machine_payload["task_nontrivial"] is True
    assert machine_payload["objective"] == "obj"
    assert machine_payload["why_it_matters"] == "why"
    assert machine_payload["user_story"] == "obj"
    assert machine_payload["structured_objective"]["objective_statement"] == "obj"
    assert machine_payload["structured_objective"]["raw_intent"] == {
        "title": "JORB-INFRA-010",
        "objective": "obj",
        "why_it_matters": "why",
    }
    assert machine_payload["structured_objective"]["success_criteria"][0] == "a"
    assert any(
        "Phase-4 acceptance artifacts exist and judge/evidence enforcement passes before the run can be accepted."
        == item
        for item in machine_payload["structured_objective"]["success_criteria"]
    )
    assert any(
        item.startswith("Builder-only scope: do not modify the JORB product repo")
        for item in machine_payload["structured_objective"]["constraints"]
    )
    assert machine_payload["structured_objective"]["unknowns"] == ["Deterministic verification commands are not explicitly declared."]
    assert machine_payload["state_transitions"]
    assert machine_payload["observability_requirements"]
    assert machine_payload["repo_bounds"]["allowlist"] == ["../jorb-builder/**"]
    assert machine_payload["verification_commands"] == []
    assert machine_payload["repo_local_standards"]["core_expectations"] == [
        "Treat backlog truth, config, run logs, and generated artifacts as first-class system inputs."
    ]
    assert machine_payload["repo_local_standards"]["execution_roles"]["Planner"] == "compile the feature/system understanding artifact."
    assert machine_payload["repo_local_standards"]["skill_entries"][0]["name"] == "phase4_enforcement"
    research_brief = (run_dir / "research_brief.md").read_text(encoding="utf-8")
    assert "## Grounded Solution Directions" in research_brief
    assert "### Inline builder hook" in research_brief
    assert "- Repo-local standards loaded: yes" in research_brief
    tradeoff_matrix = (run_dir / "tradeoff_matrix.md").read_text(encoding="utf-8")
    assert "## Inline builder hook" in tradeoff_matrix
    assert "## Helper-backed artifact planner" in tradeoff_matrix
    proposal = (run_dir / "proposal.md").read_text(encoding="utf-8")
    assert "## Recommended Direction" in proposal
    assert "Inline builder hook" in proposal
    assert "- Decision checkpoint status: not required" in proposal


def test_non_phase4_nontrivial_task_compiles_feature_spec_before_implementation(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["verification"] = ["python3 -m py_compile scripts/*.py"]
    _write_json(builder_root / "backlog.yml", backlog)
    _git(["add", "backlog.yml"], builder_root)
    _git(["commit", "-m", "seed non phase4 feature understanding task"], builder_root)

    dry_run = _run([sys.executable, str(SCRIPT), "--dry-run"], builder_root)

    assert dry_run.returncode == 0, dry_run.stdout + dry_run.stderr
    run_dir = max((builder_root / "run_logs").glob("*"), key=lambda path: path.stat().st_mtime)
    payload = _json(run_dir / "automation_result.json")
    assert any(path.endswith("compiled_feature_spec.md") for path in payload["planned_artifacts"])
    assert not any(path.endswith("proposal.md") for path in payload["planned_artifacts"])
    assert (run_dir / "compiled_feature_spec.md").exists()
    feature_spec = (run_dir / "compiled_feature_spec.md").read_text(encoding="utf-8")
    match = re.search(r"## Machine-Checkable Payload\n```json\n(.*?)\n```", feature_spec, re.DOTALL)
    assert match is not None
    machine_payload = json.loads(match.group(1))
    assert machine_payload["task_id"] == "TASK-BUILDER"
    assert machine_payload["task_nontrivial"] is True
    assert machine_payload["structured_objective"]["objective_statement"] == "obj"
    assert machine_payload["structured_objective"]["success_criteria"][0] == "a"
    assert "Deterministic local verification passes: python3 -m py_compile scripts/*.py" in machine_payload["structured_objective"]["success_criteria"]
    assert machine_payload["structured_objective"]["unknowns"] == []
    assert machine_payload["verification_commands"] == ["python3 -m py_compile scripts/*.py"]


def test_compiled_feature_spec_structured_objective_flags_decision_checkpoint_unknown(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-027",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["title"] = "Objective compiler"
    backlog["tasks"][0]["objective"] = ""
    backlog["tasks"][0]["why_it_matters"] = ""
    backlog["tasks"][0]["implementation_options"] = ["minimal", "framework"]
    backlog["tasks"][0]["selected_approach"] = ""
    _write_json(builder_root / "backlog.yml", backlog)
    _git(["add", "backlog.yml"], builder_root)
    _git(["commit", "-m", "seed structured objective decision checkpoint fixture"], builder_root)

    dry_run = _run([sys.executable, str(SCRIPT), "--dry-run"], builder_root)

    assert dry_run.returncode == 0, dry_run.stdout + dry_run.stderr
    run_dir = max((builder_root / "run_logs").glob("*"), key=lambda path: path.stat().st_mtime)
    feature_spec = (run_dir / "compiled_feature_spec.md").read_text(encoding="utf-8")
    match = re.search(r"## Machine-Checkable Payload\n```json\n(.*?)\n```", feature_spec, re.DOTALL)
    assert match is not None
    machine_payload = json.loads(match.group(1))
    assert machine_payload["structured_objective"]["objective_statement"] == "Objective compiler"
    assert "Multiple implementation options are declared without a selected approach." in machine_payload["structured_objective"]["unknowns"]
    assert "Objective detail is not explicitly stated in backlog metadata." in machine_payload["structured_objective"]["unknowns"]
    assert "Why-it-matters context is not explicitly stated in backlog metadata." in machine_payload["structured_objective"]["unknowns"]
    tradeoff_matrix = (run_dir / "tradeoff_matrix.md").read_text(encoding="utf-8")
    assert "## Minimal" in tradeoff_matrix
    assert "## Framework" in tradeoff_matrix
    research_brief = (run_dir / "research_brief.md").read_text(encoding="utf-8")
    assert "Use the declared `minimal` direction" in research_brief
    assert "Use the declared `framework` direction" in research_brief
    proposal = (run_dir / "proposal.md").read_text(encoding="utf-8")
    assert "## Recommended Direction" in proposal
    assert "- Decision checkpoint status: Decision checkpoint required: multiple implementation options are declared but no selected_approach is recorded." in proposal


def test_phase4_proposal_uses_selected_declared_approach_when_present(tmp_path: Path) -> None:
    module = _load_script_module()
    task = {
        "id": "JORB-INFRA-028",
        "title": "Solution space generator + research briefs",
        "objective": "Generate grounded solution directions before implementation.",
        "why_it_matters": "Builder should compare plausible approaches before commitment.",
        "area": "builder",
        "implementation_options": ["minimal", "framework"],
        "selected_approach": "framework",
    }
    standards = _repo_local_standards_payload(tmp_path)

    proposal = module.phase4_proposal_text(task, standards)

    assert "## Selected Approach" in proposal
    assert "Framework" in proposal
    assert "Decision checkpoint status: not required" in proposal


def test_phase4_material_decision_checkpoint_blocks_before_executor_handoff(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-029",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["title"] = "Decision proposal + human checkpoint engine"
    backlog["tasks"][0]["objective"] = "Pause for human approval when architecture tradeoffs are material."
    backlog["tasks"][0]["why_it_matters"] = "SPRE must not silently choose materially different directions."
    backlog["tasks"][0]["implementation_options"] = ["minimal", "framework"]
    backlog["tasks"][0]["selected_approach"] = ""
    backlog["tasks"][0]["verification"] = ["python3 -m py_compile scripts/*.py"]
    _write_json(builder_root / "backlog.yml", backlog)
    _git(["add", "backlog.yml"], builder_root)
    _git(["commit", "-m", "seed decision checkpoint fixture"], builder_root)

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 2
    assert "BLOCKED Decision checkpoint required before implementation:" in result.stdout
    run_dir = _active_run_dir(builder_root)
    payload = _json(run_dir / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert any(
        step["name"] == "decision_checkpoint" and step["outcome"] == "blocked"
        for step in payload["steps"]
    )
    assert not any(step["name"] == "executor_handoff" for step in payload["steps"])
    checkpoint = _json(run_dir / "decision_checkpoint.json")
    assert checkpoint["requires_human_approval"] is True
    assert checkpoint["status"] == "awaiting_human_approval"
    assert checkpoint["selected_approach"] is None
    assert checkpoint["recommended_direction"] == "Minimal"
    evidence_bundle = _json(run_dir / "evidence_bundle.json")
    assert evidence_bundle["artifacts"]["decision_checkpoint"].endswith("decision_checkpoint.json")


def test_phase4_result_persistence_blocks_accepted_run_when_required_artifacts_are_missing(tmp_path: Path) -> None:
    module = _load_script_module()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    task = {"id": "JORB-INFRA-010", "title": "Feature understanding compiler", "area": "builder"}
    automation_result = {
        "task_id": "JORB-INFRA-010",
        "classification": "accepted",
        "finished_at": "2026-03-30T00:00:00+00:00",
        "summary": "ok",
        "steps": [],
        "changed_files": [],
    }
    standards = {
        "agents_exists": True,
        "agents_path": str(tmp_path / "AGENTS.md"),
        "skills_exists": True,
        "skills_dir": str(tmp_path / "skills"),
        "skill_files": ["skills/README.md"],
    }

    persisted = module.persist_result_with_phase4_artifacts(
        run_dir,
        task,
        automation_result,
        standards=standards,
        require_runtime_proof=True,
        local_validation_payload=None,
        vm_validation_payload=None,
    )

    assert persisted["classification"] == "blocked"
    assert persisted["summary"].startswith("Phase 4 artifact enforcement failed:")
    assert (run_dir / "evidence_bundle.json").exists()
    assert (run_dir / "judge_decision.md").exists()
    assert (run_dir / "runtime_proof.log").exists()


def test_phase4_result_persistence_blocks_invalid_machine_checkable_feature_spec(tmp_path: Path) -> None:
    module = _load_script_module()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    task = {"id": "JORB-INFRA-010", "title": "Feature understanding compiler", "area": "builder"}
    for name in ("proposal.md", "tradeoff_matrix.md", "research_brief.md"):
        (run_dir / name).write_text("ok\n", encoding="utf-8")
    (run_dir / "compiled_feature_spec.md").write_text("# Compiled Feature Spec\n\nmissing machine payload\n", encoding="utf-8")
    automation_result = {
        "task_id": "JORB-INFRA-010",
        "classification": "accepted",
        "finished_at": "2026-03-30T00:00:00+00:00",
        "summary": "ok",
        "steps": [],
        "changed_files": [],
    }
    standards = {
        "agents_exists": True,
        "agents_path": str(tmp_path / "AGENTS.md"),
        "skills_exists": True,
        "skills_dir": str(tmp_path / "skills"),
        "skill_files": ["skills/README.md"],
    }

    persisted = module.persist_result_with_phase4_artifacts(
        run_dir,
        task,
        automation_result,
        standards=standards,
        require_runtime_proof=False,
        local_validation_payload=None,
        vm_validation_payload=None,
    )

    assert persisted["classification"] == "blocked"
    assert "compiled_feature_spec.md:missing_machine_payload" in persisted["summary"]


def test_phase4_infra_task_blocks_without_repo_local_standards(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )

    result = _run([sys.executable, str(SCRIPT)], builder_root)
    assert result.returncode == 2
    assert "Missing automation configuration: AGENTS.md, skills/" in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert "Missing automation configuration: AGENTS.md, skills/" in payload["summary"]


def test_memory_store_retrieval_is_relevant_and_has_provenance(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    common = _load_common_module(builder_root)
    history_path = builder_root / "task_history" / "2026-03-30T000000Z-JORB-INFRA-011.yml"
    _write_json(
        history_path,
        {
            "task_id": "JORB-INFRA-011",
            "status": "accepted",
            "completed_at": "2026-03-30T00:00:00+00:00",
            "notes": ["proposal engine landed cleanly"],
            "operator_diagnostics": {"accepted": True, "decision_summary": "proposal engine landed cleanly"},
        },
    )
    blocker_path = builder_root / "blockers" / "BLK-JORB-INFRA-010.yml"
    _write_json(
        blocker_path,
        {
            "related_tasks": ["JORB-INFRA-010"],
            "status": "open",
            "opened_at": "2026-03-30T00:00:00+00:00",
            "diagnosis": "known blocker pattern",
        },
    )

    store = common.build_memory_store(builder_root)
    retrieved = common.retrieve_memory_for_role({"id": "JORB-INFRA-010", "area": "builder"}, store, role="planner", limit=5)

    assert retrieved["selected"]
    assert all(entry["provenance"] for entry in retrieved["selected"])
    assert retrieved["selected"][0]["ticket_family"] == "JORB-INFRA"
    assert retrieved["selected"][0]["selection_reasons"]


def test_memory_store_schema_and_observation_inference_are_explicit(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    common = _load_common_module(builder_root)
    _write_json(
        builder_root / "task_history" / "2026-03-30T000000Z-JORB-INFRA-010.yml",
        {
            "task_id": "JORB-INFRA-010",
            "status": "blocked",
            "completed_at": "2026-03-30T00:00:00+00:00",
            "notes": ["VM smoke validation failed after local validation and git push succeeded."],
            "failure_taxonomy": {"failure_class": "runtime_vm_failure"},
            "operator_diagnostics": {"accepted": False, "decision_summary": "VM smoke validation failed after local validation and git push succeeded."},
        },
    )

    store = common.build_memory_store(builder_root)
    issues = common.validate_memory_store_schema(store)

    assert issues == []
    entry = store["entries"][0]
    assert entry["observation"]
    assert entry["inference"]
    assert entry["primary_basis"] == "observation"
    assert entry["source_artifact"].endswith(".yml")


def test_memory_store_builds_artifact_metadata_index_from_task_history(tmp_path: Path) -> None:
    builder_root, _, run_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-024",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    common = _load_common_module(builder_root)
    prompt_path = builder_root / "run_logs" / "packet" / "codex_prompt.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("prompt\n", encoding="utf-8")
    (run_dir / "automation_result.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "compiled_feature_spec.md").write_text("spec\n", encoding="utf-8")
    (run_dir / "judge_decision.md").write_text("judge\n", encoding="utf-8")
    _write_json(
        builder_root / "task_history" / "2026-03-30T000000Z-JORB-INFRA-024.yml",
        {
            "task_id": "JORB-INFRA-024",
            "status": "accepted",
            "completed_at": "2026-03-30T00:00:00+00:00",
            "prompt": str(prompt_path),
            "run_log_dir": str(run_dir),
            "evidence_artifacts": [
                {"label": "automation_result", "path": str(run_dir / "automation_result.json")},
                {"label": "judge_decision", "path": str(run_dir / "judge_decision.md")},
            ],
            "operator_diagnostics": {"accepted": True, "decision_summary": "artifact index landed"},
        },
    )

    store = common.build_memory_store(builder_root)
    issues = common.validate_memory_store_schema(store)

    assert issues == []
    artifact_index = store["artifact_index"]
    assert artifact_index["by_task_id"]["JORB-INFRA-024"]
    assert artifact_index["by_label"]["automation_result"]
    assert artifact_index["by_name"]["compiled_feature_spec.md"]
    entries_by_name = {entry["artifact_name"]: entry for entry in artifact_index["entries"]}
    assert entries_by_name["compiled_feature_spec.md"]["phase4_artifact"] is True
    assert "phase4:compiled_feature_spec.md" in entries_by_name["compiled_feature_spec.md"]["labels"]
    assert entries_by_name["automation_result.json"]["run_log_dir"] == str(run_dir)
    assert "jorb-infra-024" in entries_by_name["automation_result.json"]["search_tokens"]


def test_memory_store_deduplicates_similar_entries_and_preserves_provenance(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    common = _load_common_module(builder_root)
    for suffix in ("a", "b"):
        _write_json(
            builder_root / "task_history" / f"2026-03-30T00000{suffix}Z-JORB-INFRA-010.yml",
            {
                "task_id": "JORB-INFRA-010",
                "status": "blocked",
                "completed_at": "2026-03-30T00:00:00+00:00",
                "notes": ["Builder repo is dirty before automated execution; refusing to continue."],
                "operator_diagnostics": {"accepted": False, "decision_summary": "Builder repo is dirty before automated execution; refusing to continue."},
            },
        )

    store = common.build_memory_store(builder_root)
    matching = [entry for entry in store["entries"] if "dirty before automated execution" in entry["observation"]]

    assert len(matching) == 1
    assert matching[0]["support_count"] == 2
    assert len(matching[0]["provenance"]) == 2


def test_memory_decay_and_operator_invalidation_change_retrieval(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    common = _load_common_module(builder_root)
    _write_json(
        builder_root / "task_history" / "2026-01-01T000000Z-JORB-INFRA-010.yml",
        {
            "task_id": "JORB-INFRA-010",
            "status": "accepted",
            "completed_at": "2026-01-01T00:00:00+00:00",
            "notes": ["old accepted pattern"],
            "operator_diagnostics": {"accepted": True, "decision_summary": "old accepted pattern"},
        },
    )
    _write_json(
        builder_root / "task_history" / "2026-03-30T000000Z-JORB-INFRA-010.yml",
        {
            "task_id": "JORB-INFRA-010",
            "status": "accepted",
            "completed_at": "2026-03-30T00:00:00+00:00",
            "notes": ["fresh accepted pattern"],
            "operator_diagnostics": {"accepted": True, "decision_summary": "fresh accepted pattern"},
        },
    )

    store = common.build_memory_store(builder_root)
    selected_before = common.retrieve_memory_for_role({"id": "JORB-INFRA-010", "area": "builder"}, store, role="planner")["selected"]
    stale_entry = next(entry for entry in store["entries"] if entry["observation"] == "old accepted pattern")
    fresh_entry = next(entry for entry in store["entries"] if entry["observation"] == "fresh accepted pattern")

    assert stale_entry["freshness"]["freshness_state"] == "stale"
    assert fresh_entry["freshness"]["freshness_state"] == "fresh"
    assert selected_before[0]["observation"] == "fresh accepted pattern"

    invalidate = _run([sys.executable, str(MEMORY_CONTROLS_SCRIPT), "invalidate", fresh_entry["memory_id"], "--reason", "bad memory"], builder_root)
    assert invalidate.returncode == 0

    store_after = common.build_memory_store(builder_root)
    selected_after = common.retrieve_memory_for_role({"id": "JORB-INFRA-010", "area": "builder"}, store_after, role="planner")["selected"]
    assert all(entry["memory_id"] != fresh_entry["memory_id"] for entry in selected_after)


def test_role_specific_retrieval_differs_between_planner_architect_and_judge(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-V3-003",
        area="frontend",
        allowlist=["../jorb-builder/**"],
    )
    common = _load_common_module(builder_root)
    _write_json(
        builder_root / "task_history" / "2026-03-30T000000Z-JORB-V3-003.yml",
        {
            "task_id": "JORB-V3-003",
            "status": "refined",
            "completed_at": "2026-03-30T00:00:00+00:00",
            "notes": ["UX conformance evidence is incomplete for this product-facing UX task."],
            "failure_taxonomy": {"failure_class": "artifact_completeness_failure"},
            "operator_diagnostics": {
                "accepted": False,
                "decision_summary": "UX conformance evidence is incomplete for this product-facing UX task.",
                "ux_conformance": {"required": True},
            },
        },
    )
    _write_json(
        builder_root / "memory_overrides.json",
        {
            "memory_status": {},
            "manual_entries": [
                {
                    "memory_id": "mem-playbook-ux",
                    "memory_type": "playbook",
                    "ticket_family": "JORB-V3",
                    "observation": "Jobs-first UI work must carry explicit figma-source mapping.",
                    "inference": "Treat figma mapping as a hard acceptance boundary.",
                    "primary_basis": "inference",
                    "origin": "operator",
                    "role_fit": ["planner", "judge"],
                    "relevance_tags": ["ux", "playbook", "acceptance_boundary"],
                    "status": "pinned"
                }
            ],
            "pins": []
        },
    )

    store = common.build_memory_store(builder_root)
    planner = common.retrieve_memory_for_role({"id": "JORB-V3-003", "area": "frontend", "product_facing_ux": True}, store, role="planner")
    architect = common.retrieve_memory_for_role({"id": "JORB-V3-003", "area": "frontend", "product_facing_ux": True}, store, role="architect")
    judge = common.retrieve_memory_for_role({"id": "JORB-V3-003", "area": "frontend", "product_facing_ux": True}, store, role="judge")

    assert planner["selected"]
    assert architect["selected"]
    assert judge["selected"]
    assert planner["selected"][0]["memory_type"] in {"playbook", "failure_mode"}
    assert judge["selected"][0]["memory_type"] in {"playbook", "failure_mode"}
    assert planner["profile"]["preferred_types"] != architect["profile"]["preferred_types"]


def test_role_specific_artifact_retrieval_differs_between_planner_architect_and_judge(tmp_path: Path) -> None:
    builder_root, _, run_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-024",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    common = _load_common_module(builder_root)
    prompt_path = builder_root / "run_logs" / "packet" / "codex_prompt.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("prompt\n", encoding="utf-8")
    for name in (
        "compiled_feature_spec.md",
        "research_brief.md",
        "proposal.md",
        "tradeoff_matrix.md",
        "runtime_proof.log",
        "evidence_bundle.json",
        "judge_decision.md",
        "eval_result.json",
    ):
        (run_dir / name).write_text(f"{name}\n", encoding="utf-8")
    _write_json(
        builder_root / "task_history" / "2026-03-30T000000Z-JORB-INFRA-024.yml",
        {
            "task_id": "JORB-INFRA-024",
            "status": "accepted",
            "completed_at": "2026-03-30T00:00:00+00:00",
            "prompt": str(prompt_path),
            "run_log_dir": str(run_dir),
            "operator_diagnostics": {"accepted": True, "decision_summary": "phase4 artifacts captured cleanly"},
        },
    )

    store = common.build_memory_store(builder_root)
    planner = common.retrieve_artifacts_for_role({"id": "JORB-INFRA-024", "area": "builder"}, store, role="planner")
    architect = common.retrieve_artifacts_for_role({"id": "JORB-INFRA-024", "area": "builder"}, store, role="architect")
    judge = common.retrieve_artifacts_for_role({"id": "JORB-INFRA-024", "area": "builder"}, store, role="judge")

    assert planner["selected"]
    assert architect["selected"]
    assert judge["selected"]
    planner_names = {entry["artifact_name"] for entry in planner["selected"]}
    architect_names = {entry["artifact_name"] for entry in architect["selected"]}
    judge_names = {entry["artifact_name"] for entry in judge["selected"]}
    assert {"compiled_feature_spec.md", "research_brief.md"} & planner_names
    assert {"proposal.md", "tradeoff_matrix.md"} & architect_names
    assert {"judge_decision.md", "evidence_bundle.json", "runtime_proof.log", "eval_result.json"} & judge_names
    assert planner["profile"]["preferred_names"] != architect["profile"]["preferred_names"]
    assert architect["profile"]["preferred_names"] != judge["profile"]["preferred_names"]


def test_render_packet_emits_role_specific_memory_bundles_and_bounded_prompt_context(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    _write_json(builder_root / "active_task.yml", _base_active("JORB-INFRA-010", builder_root / "run_logs" / "run-1" / "codex_prompt.md", builder_root / "run_logs" / "run-1", ["../jorb-builder/**"]))
    _write_json(
        builder_root / "task_history" / "2026-03-30T000000Z-JORB-INFRA-010.yml",
        {
            "task_id": "JORB-INFRA-010",
            "status": "accepted",
            "completed_at": "2026-03-30T00:00:00+00:00",
            "notes": ["feature spec compiler landed"],
            "operator_diagnostics": {"accepted": True, "decision_summary": "feature spec compiler landed"},
        },
    )
    (builder_root / "AGENTS.md").write_text(
        "# Builder Agents\n\nCore expectations:\n- Treat backlog truth, config, run logs, and generated artifacts as first-class system inputs.\n\nExecution roles:\n- Planner: compile the feature/system understanding artifact.\n",
        encoding="utf-8",
    )
    skills_dir = builder_root / "skills"
    skills_dir.mkdir(exist_ok=True)
    (skills_dir / "README.md").write_text(
        "# Builder Skills\n\nCurrent skills:\n- `phase4_enforcement`: require planner/architect/judge artifacts and evidence before acceptance.\n",
        encoding="utf-8",
    )

    result = _run([sys.executable, str(SCRIPT.parent / "render_packet.py")], builder_root)

    assert result.returncode == 0
    active = _json(builder_root / "active_task.yml")
    run_dir = Path(active["run_log_dir"])
    memory_context = _json(run_dir / "memory_context.json")
    prompt_text = (run_dir / "codex_prompt.md").read_text(encoding="utf-8")
    assert "planner_bundle" in memory_context
    assert "planner_artifacts" in memory_context
    assert "architect_bundle" in memory_context
    assert "architect_artifacts" in memory_context
    assert len(memory_context["planner_bundle"]["selected"]) <= memory_context["planner_bundle"]["profile"]["limit"]
    assert "Planner memory bundle:" in prompt_text
    assert "Planner artifact retrieval:" in prompt_text
    assert "Architect memory bundle:" in prompt_text
    assert "Architect artifact retrieval:" in prompt_text
    assert "AGENTS core expectation: Treat backlog truth, config, run logs, and generated artifacts as first-class system inputs." in prompt_text
    assert "repo skill: phase4_enforcement => require planner/architect/judge artifacts and evidence before acceptance." in prompt_text


def test_memory_controls_can_supersede_and_pin_entries(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    common = _load_common_module(builder_root)
    _write_json(
        builder_root / "task_history" / "2026-03-30T000000Z-JORB-INFRA-010.yml",
        {
            "task_id": "JORB-INFRA-010",
            "status": "accepted",
            "completed_at": "2026-03-30T00:00:00+00:00",
            "notes": ["feature spec compiler landed"],
            "operator_diagnostics": {"accepted": True, "decision_summary": "feature spec compiler landed"},
        },
    )
    entry = common.build_memory_store(builder_root)["entries"][0]

    pin = _run([sys.executable, str(MEMORY_CONTROLS_SCRIPT), "pin", entry["memory_id"]], builder_root)
    supersede = _run([sys.executable, str(MEMORY_CONTROLS_SCRIPT), "supersede", entry["memory_id"], "--by", "manual-playbook"], builder_root)

    assert pin.returncode == 0
    assert supersede.returncode == 0
    store = common.build_memory_store(builder_root)
    updated = next(item for item in store["entries"] if item["memory_id"] == entry["memory_id"])
    assert updated["status"] == "superseded"
    assert updated["superseded_by"] == "manual-playbook"


def test_judge_path_emits_role_specific_memory_context(tmp_path: Path) -> None:
    builder_root, _, run_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    module = _load_script_module(builder_root)
    _write_json(
        builder_root / "task_history" / "2026-03-30T000000Z-JORB-INFRA-010.yml",
        {
            "task_id": "JORB-INFRA-010",
            "status": "refined",
            "completed_at": "2026-03-30T00:00:00+00:00",
            "notes": ["Local validation failed after executor changes."],
            "failure_taxonomy": {"failure_class": "local_test_failure"},
            "operator_diagnostics": {"accepted": False, "decision_summary": "Local validation failed after executor changes."},
        },
    )
    task = _json(builder_root / "backlog.yml")["tasks"][0]
    standards = _repo_local_standards_payload(tmp_path)
    _write_valid_phase4_feature_spec(module, run_dir, task, standards)
    for name in ("proposal.md", "tradeoff_matrix.md", "research_brief.md"):
        (run_dir / name).write_text("ok\n", encoding="utf-8")
    automation_result = {
        "task_id": "JORB-INFRA-010",
        "classification": "blocked",
        "summary": "Local validation failed after executor changes.",
        "finished_at": "2026-03-30T00:00:00+00:00",
        "steps": [{"name": "local_validation", "outcome": "refined", "detail": "failed"}],
        "changed_files": [],
    }

    module.persist_result_with_phase4_artifacts(
        run_dir,
        task,
        automation_result,
        standards=standards,
        require_runtime_proof=False,
        local_validation_payload={"results": [{"command": "pytest", "passed": False}]},
        vm_validation_payload=None,
    )

    judge_memory = _json(run_dir / "judge_memory_context.json")
    evidence_bundle = _json(run_dir / "evidence_bundle.json")
    assert judge_memory["role"] == "judge"
    assert "artifact_bundle" in judge_memory
    assert "judge_memory_selected" in evidence_bundle
    assert "judge_artifact_selected" in evidence_bundle
    assert evidence_bundle["repo_local_standards"]["execution_roles"]["Judge"] == "accept or reject only from evidence."
    assert evidence_bundle["repo_local_standards"]["skill_entries"][0]["name"] == "phase4_enforcement"


def test_eval_scoring_writes_machine_readable_result_with_threshold(tmp_path: Path) -> None:
    builder_root, _, run_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-BUILDER",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    module = _load_script_module(builder_root)
    task = {"id": "JORB-INFRA-010", "title": "Feature understanding compiler", "area": "builder"}
    standards = {"agents_exists": True, "skills_exists": True}
    _write_valid_phase4_feature_spec(module, run_dir, task, standards)
    for name in ("proposal.md", "tradeoff_matrix.md", "research_brief.md", "evidence_bundle.json", "judge_decision.md"):
        (run_dir / name).write_text("ok\n", encoding="utf-8")
    (run_dir / "runtime_proof.log").write_text("ok\n", encoding="utf-8")

    eval_result = module.score_run_eval(
        task,
        {"classification": "accepted", "steps": [{"name": "local_validation", "outcome": "passed"}]},
        run_dir=run_dir,
        standards=standards,
    )
    module.write_eval_result(run_dir, eval_result)

    assert eval_result["passed"] is True
    assert eval_result["overall_score"] >= eval_result["threshold"]
    assert _json(run_dir / "eval_result.json")["scores"]["planning_quality"] == 1.0


def test_retry_loop_detection_blocks_repeated_same_failure_class(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    module = _load_script_module(builder_root)
    task = _json(builder_root / "backlog.yml")["tasks"][0]
    task["status"] = "selected"
    active = _json(builder_root / "active_task.yml")
    status = _json(builder_root / "status.yml")
    for index in range(2):
        _write_json(
            builder_root / "task_history" / f"2026-03-30T00000{index}Z-JORB-INFRA-010.yml",
            {
                "task_id": "JORB-INFRA-010",
                "status": "refined",
                "failure_taxonomy": {"failure_class": "local_test_failure"},
                "operator_diagnostics": {"accepted": False},
            },
        )
    automation_result = {
        "task_id": "JORB-INFRA-010",
        "classification": "refined",
        "finished_at": "2026-03-30T00:00:00+00:00",
        "summary": "Local validation failed after executor changes.",
        "steps": [{"name": "local_validation", "outcome": "refined", "detail": "failed"}],
        "changed_files": [],
    }

    module.classify_and_update_state("refined", automation_result["summary"], task, {"tasks": [task]}, active, status, automation_result)

    assert task["status"] == "blocked"
    assert "Retry loop detected" in task["notes"][-1]


def test_run_lock_blocks_second_controller(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    (builder_root / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    skills_dir = builder_root / "skills"
    skills_dir.mkdir(exist_ok=True)
    (skills_dir / "README.md").write_text("# Skills\n", encoding="utf-8")
    _write_json(builder_root / "run_lock.json", {"pid": os.getpid(), "task_id": "OTHER", "acquired_at": "2026-03-30T00:00:00+00:00"})

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 2
    assert "run_lock held by pid" in result.stdout


def test_show_status_reads_canonical_run_ledger(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    _write_json(
        builder_root / "run_ledger.json",
        {
            "current_task": "JORB-INFRA-010",
            "current_stage": "judge",
            "run_state": "blocked",
            "current_blocker": "artifact gate",
            "last_successful_checkpoint": "validator",
            "artifact_completeness": {"present": ["compiled_feature_spec.md"], "missing": ["judge_decision.md"]},
            "failure_taxonomy": {"failure_class": "artifact_completeness_failure", "recovery_action": "replan_required"},
            "eval_result": {
                "overall_score": 0.5,
                "fixture_family": "infra_hardening",
                "threshold": 0.78,
                "passed": False,
                "regression_vs_prior": {"trend": "regressed", "overall_delta": -0.2},
            },
            "eval_blocked_acceptance": True,
            "next_recommended_action": "Inspect judge artifact",
        },
    )

    result = _run([sys.executable, str(SCRIPT.parent / "show_status.py")], builder_root)

    assert result.returncode == 0
    assert "Canonical operator view:" in result.stdout
    assert "- current_stage: judge" in result.stdout
    assert "- failure_class: artifact_completeness_failure" in result.stdout
    assert "- eval_fixture_family: infra_hardening" in result.stdout
    assert "- eval_regression_trend: regressed" in result.stdout
    assert "- eval_blocked_acceptance: True" in result.stdout


def test_update_run_ledger_preserves_recent_phase4_artifact_blocker_truth_across_dry_run(tmp_path: Path) -> None:
    builder_root, _, run_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    module = _load_script_module(builder_root)
    for name in ("compiled_feature_spec.md", "proposal.md", "tradeoff_matrix.md", "research_brief.md"):
        (run_dir / name).write_text(f"{name}\n", encoding="utf-8")
    _write_json(
        builder_root / "run_ledger.json",
        {
            "current_task": "JORB-INFRA-010",
            "current_stage": "judge",
            "run_state": "blocked",
            "current_blocker": "Phase 4 artifact enforcement failed: compiled_feature_spec.md, proposal.md, tradeoff_matrix.md, research_brief.md",
            "artifact_completeness": {
                "present": [],
                "missing": ["compiled_feature_spec.md", "proposal.md", "tradeoff_matrix.md", "research_brief.md"],
            },
            "events": [
                {
                    "at": "2026-03-30T20:21:35+00:00",
                    "task_id": "JORB-INFRA-010",
                    "run_state": "blocked",
                    "stage_name": "judge",
                    "detail": "Phase 4 artifact enforcement failed: compiled_feature_spec.md, proposal.md, tradeoff_matrix.md, research_brief.md",
                }
            ],
        },
    )

    module.update_run_ledger(
        task_id="JORB-INFRA-010",
        title="Feature understanding compiler",
        run_state="dry_run",
        stage_name="plan",
        run_log_dir=run_dir,
        detail="Dry run only. No executor, git, or VM commands were executed.",
        next_action="Inspect automation_result.json for the planned stages and artifacts.",
    )

    ledger = _json(builder_root / "run_ledger.json")
    assert ledger["run_state"] == "blocked"
    assert ledger["current_stage"] == "judge"
    assert ledger["current_blocker"] == "Phase 4 artifact enforcement failed: compiled_feature_spec.md, proposal.md, tradeoff_matrix.md, research_brief.md"
    assert ledger["failure_taxonomy"]["failure_class"] == "artifact_completeness_failure"
    assert ledger["artifact_completeness"]["missing"] == [
        "compiled_feature_spec.md",
        "proposal.md",
        "tradeoff_matrix.md",
        "research_brief.md",
        "judge_decision.md",
        "evidence_bundle.json",
        "runtime_proof.log",
    ]


def test_show_status_prefers_recent_phase4_artifact_blocker_truth_over_stale_dry_run_surface(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    _write_json(
        builder_root / "run_ledger.json",
        {
            "current_task": "JORB-INFRA-010",
            "current_stage": "plan",
            "run_state": "dry_run",
            "current_blocker": None,
            "artifact_completeness": {
                "present": [
                    "compiled_feature_spec.md",
                    "proposal.md",
                    "tradeoff_matrix.md",
                    "research_brief.md",
                ],
                "missing": [
                    "judge_decision.md",
                    "evidence_bundle.json",
                    "runtime_proof.log",
                ],
            },
            "events": [
                {
                    "at": "2026-03-30T20:21:35+00:00",
                    "task_id": "JORB-INFRA-010",
                    "run_state": "blocked",
                    "stage_name": "judge",
                    "detail": "Phase 4 artifact enforcement failed: compiled_feature_spec.md, proposal.md, tradeoff_matrix.md, research_brief.md",
                },
                {
                    "at": "2026-03-30T20:30:00+00:00",
                    "task_id": "JORB-INFRA-010",
                    "run_state": "dry_run",
                    "stage_name": "plan",
                    "detail": "Dry run only. No executor, git, or VM commands were executed.",
                },
            ],
        },
    )

    result = _run([sys.executable, str(SCRIPT.parent / "show_status.py")], builder_root)

    assert result.returncode == 0
    assert "- current_stage: judge" in result.stdout
    assert "- run_state: blocked" in result.stdout
    assert "- current_blocker: Phase 4 artifact enforcement failed: compiled_feature_spec.md, proposal.md, tradeoff_matrix.md, research_brief.md" in result.stdout
    assert "- artifact_missing: compiled_feature_spec.md, proposal.md, tradeoff_matrix.md, research_brief.md, judge_decision.md, evidence_bundle.json, runtime_proof.log" in result.stdout


def test_show_status_synthesizes_strongest_recent_phase4_blocker_from_repeated_judge_failures(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    _write_json(
        builder_root / "run_ledger.json",
        {
            "current_task": "JORB-INFRA-010",
            "current_stage": "plan",
            "run_state": "dry_run",
            "current_blocker": None,
            "artifact_completeness": {
                "present": [
                    "proposal.md",
                    "tradeoff_matrix.md",
                    "research_brief.md",
                ],
                "missing": [
                    "compiled_feature_spec.md",
                    "judge_decision.md",
                    "evidence_bundle.json",
                    "runtime_proof.log",
                ],
            },
            "events": [
                {
                    "at": "2026-03-30T20:21:35+00:00",
                    "task_id": "JORB-INFRA-010",
                    "run_state": "blocked",
                    "stage_name": "judge",
                    "detail": "Phase 4 artifact enforcement failed: compiled_feature_spec.md, proposal.md, tradeoff_matrix.md, research_brief.md",
                },
                {
                    "at": "2026-03-30T20:57:12+00:00",
                    "task_id": "JORB-INFRA-010",
                    "run_state": "blocked",
                    "stage_name": "judge",
                    "detail": "Phase 4 artifact enforcement failed: compiled_feature_spec.md:missing_machine_payload",
                },
                {
                    "at": "2026-03-30T21:00:00+00:00",
                    "task_id": "JORB-INFRA-010",
                    "run_state": "dry_run",
                    "stage_name": "plan",
                    "detail": "Dry run only. No executor, git, or VM commands were executed.",
                },
            ],
        },
    )

    result = _run([sys.executable, str(SCRIPT.parent / "show_status.py")], builder_root)

    assert result.returncode == 0
    assert "- current_stage: judge" in result.stdout
    assert "- run_state: blocked" in result.stdout
    assert "- current_blocker: Phase 4 artifact enforcement failed: compiled_feature_spec.md, proposal.md, tradeoff_matrix.md, research_brief.md" in result.stdout
    assert "- artifact_missing: compiled_feature_spec.md, proposal.md, tradeoff_matrix.md, research_brief.md, judge_decision.md, evidence_bundle.json, runtime_proof.log" in result.stdout


def test_private_eval_fixture_schema_validation_rejects_missing_fields(tmp_path: Path) -> None:
    module = _load_private_eval_module(tmp_path)

    issues = module.validate_fixture_schema({"fixture_id": "bad"})

    assert "missing:fixture_family" in issues
    assert "missing:selector" in issues


def test_private_eval_scores_fixture_with_real_rubric_dimensions(tmp_path: Path) -> None:
    builder_root, _, run_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    module = _load_private_eval_module(builder_root)
    fixture = {
        "fixture_id": "infra_test",
        "fixture_family": "infra_hardening",
        "description": "test fixture",
        "selector": {"task_family": "JORB-INFRA", "area": "builder"},
        "mandatory_artifacts": ["compiled_feature_spec.md", "proposal.md", "judge_decision.md", "evidence_bundle.json", "runtime_proof.log"],
        "rubric_dimensions": [
            {"name": "planning_quality", "weight": 0.3, "threshold": 0.6, "description": "plan"},
            {"name": "evidence_quality", "weight": 0.3, "threshold": 0.6, "description": "evidence"},
            {"name": "operator_handoff_quality", "weight": 0.4, "threshold": 0.6, "description": "handoff"},
        ],
        "pass_threshold": 0.7,
    }
    task = {"id": "JORB-INFRA-010", "title": "Feature understanding compiler", "area": "builder"}
    standards = {"agents_exists": True, "skills_exists": True}
    _write_valid_phase4_feature_spec(module, run_dir, task, standards)
    for name in ("proposal.md", "tradeoff_matrix.md", "research_brief.md", "judge_decision.md", "evidence_bundle.json", "runtime_proof.log", "automation_summary.md"):
        (run_dir / name).write_text("ok\n", encoding="utf-8")

    subject = module.build_eval_subject(
        task,
        {"classification": "accepted", "summary": "ok", "steps": [], "changed_files": ["scripts/foo.py"]},
        run_dir=run_dir,
        standards=standards,
    )
    result = module.score_fixture_subject(fixture, subject)

    assert result["passed"] is True
    assert result["scores"]["planning_quality"] >= 0.6
    assert result["overall_score"] >= result["threshold"]


def test_private_eval_replay_scores_historical_artifacts_and_aggregates(tmp_path: Path) -> None:
    builder_root, _, run_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    module = _load_private_eval_module(builder_root)
    _write_eval_fixture(
        builder_root / "eval_fixtures" / "infra.json",
        {
            "fixture_id": "infra_hardening_v1",
            "fixture_family": "infra_hardening",
            "description": "infra fixture",
            "selector": {"task_family": "JORB-INFRA", "area": "builder"},
            "mandatory_artifacts": ["compiled_feature_spec.md", "proposal.md", "tradeoff_matrix.md", "judge_decision.md", "evidence_bundle.json", "runtime_proof.log"],
            "rubric_dimensions": [
                {"name": "planning_quality", "weight": 0.2, "threshold": 0.7, "description": "plan"},
                {"name": "test_adequacy", "weight": 0.2, "threshold": 0.7, "description": "tests"},
                {"name": "runtime_proof_quality", "weight": 0.2, "threshold": 0.7, "description": "runtime"},
                {"name": "evidence_quality", "weight": 0.2, "threshold": 0.7, "description": "evidence"},
                {"name": "operator_handoff_quality", "weight": 0.2, "threshold": 0.6, "description": "handoff"},
            ],
            "pass_threshold": 0.78,
        },
    )
    task = {"id": "JORB-INFRA-010", "title": "Feature understanding compiler", "area": "builder"}
    _write_valid_phase4_feature_spec(_load_script_module(builder_root), run_dir, task, {"agents_exists": True, "skills_exists": True})
    for name in ("proposal.md", "tradeoff_matrix.md", "research_brief.md", "judge_decision.md", "evidence_bundle.json", "runtime_proof.log", "automation_summary.md", "local_validation.json"):
        (run_dir / name).write_text("{}\n" if name.endswith(".json") else "ok\n", encoding="utf-8")
    _write_json(
        run_dir / "automation_result.json",
        {
            "task_id": "JORB-INFRA-010",
            "classification": "accepted",
            "summary": "ok",
            "steps": [
                {"name": "local_validation", "outcome": "passed"},
                {"name": "vm_validation", "outcome": "accepted"},
            ],
            "changed_files": ["scripts/automate_task_loop.py"],
        },
    )
    history_path = builder_root / "task_history" / "2026-03-30T000000Z-JORB-INFRA-010.yml"
    _write_json(
        history_path,
        {
            "task_id": "JORB-INFRA-010",
            "title": "Feature understanding compiler",
            "status": "accepted",
            "run_log_dir": str(run_dir),
            "notes": ["ok"],
            "operator_diagnostics": {"step_outcomes": [{"name": "local_validation", "outcome": "passed"}]},
        },
    )

    replay = module.replay_history_eval(history_path, root=builder_root)
    aggregate = module.aggregate_replay_results([replay])

    assert replay["fixture_family"] == "infra_hardening"
    assert replay["passed"] is True
    assert aggregate["families"][0]["pass_rate"] == 1.0


def test_private_eval_compare_two_attempts_reports_regression(tmp_path: Path) -> None:
    module = _load_private_eval_module(tmp_path)

    comparison = module.compare_eval_results(
        {"task_id": "A", "scores": {"planning_quality": 1.0, "evidence_quality": 1.0}, "overall_score": 0.9},
        {"task_id": "B", "scores": {"planning_quality": 0.6, "evidence_quality": 0.7}, "overall_score": 0.65},
    )

    assert comparison["trend"] == "regressed"
    assert comparison["category_deltas"]["planning_quality"] == -0.4


def test_private_eval_scores_existing_run_dir_and_compares_against_prior_history(tmp_path: Path) -> None:
    builder_root, _, run_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-023",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    module = _load_private_eval_module(builder_root)
    task = _json(builder_root / "backlog.yml")["tasks"][0]
    task["title"] = "Private builder eval suite"
    task["status"] = "selected"
    _write_eval_fixture(
        builder_root / "eval_fixtures" / "infra.json",
        {
            "fixture_id": "infra_hardening_v1",
            "fixture_family": "infra_hardening",
            "description": "infra fixture",
            "selector": {"task_family": "JORB-INFRA", "area": "builder"},
            "mandatory_artifacts": ["compiled_feature_spec.md", "proposal.md", "tradeoff_matrix.md", "judge_decision.md", "evidence_bundle.json", "runtime_proof.log"],
            "rubric_dimensions": [
                {"name": "planning_quality", "weight": 0.2, "threshold": 0.7, "description": "plan"},
                {"name": "test_adequacy", "weight": 0.2, "threshold": 0.7, "description": "tests"},
                {"name": "runtime_proof_quality", "weight": 0.2, "threshold": 0.7, "description": "runtime"},
                {"name": "evidence_quality", "weight": 0.2, "threshold": 0.7, "description": "evidence"},
                {"name": "operator_handoff_quality", "weight": 0.2, "threshold": 0.6, "description": "handoff"},
            ],
            "pass_threshold": 0.78,
        },
    )
    standards = {"agents_exists": True, "skills_exists": True, "agents_path": "AGENTS.md", "skills_dir": "skills", "skill_files": []}
    _write_valid_phase4_feature_spec(_load_script_module(builder_root), run_dir, task, standards)
    for name in (
        "proposal.md",
        "tradeoff_matrix.md",
        "research_brief.md",
        "judge_decision.md",
        "evidence_bundle.json",
        "runtime_proof.log",
        "automation_summary.md",
        "local_validation.json",
    ):
        (run_dir / name).write_text("{}\n" if name.endswith(".json") else "ok\n", encoding="utf-8")
    prior_run_dir = builder_root / "run_logs" / "2026-03-29T210000Z-JORB-INFRA-023"
    prior_run_dir.mkdir(parents=True, exist_ok=True)
    _write_valid_phase4_feature_spec(_load_script_module(builder_root), prior_run_dir, task, standards)
    for name in ("proposal.md", "tradeoff_matrix.md", "research_brief.md", "automation_summary.md"):
        (prior_run_dir / name).write_text("{}\n" if name.endswith(".json") else "ok\n", encoding="utf-8")
    _write_json(
        prior_run_dir / "automation_result.json",
        {
            "task_id": "JORB-INFRA-023",
            "classification": "accepted",
            "summary": "prior run",
            "steps": [],
            "changed_files": [],
        },
    )
    _write_json(
        builder_root / "task_history" / "2026-03-29T210000Z-JORB-INFRA-023.yml",
        {
            "task_id": "JORB-INFRA-023",
            "title": "Private builder eval suite",
            "status": "accepted",
            "run_log_dir": str(prior_run_dir),
            "notes": ["prior run"],
            "operator_diagnostics": {"step_outcomes": []},
        },
    )

    result = module.score_run_directory(run_dir, root=builder_root)

    assert result["task"]["id"] == "JORB-INFRA-023"
    assert result["passed"] is True
    assert result["regression_vs_prior"]["trend"] == "improved"
    assert result["regression_vs_prior"]["baseline_history_path"].endswith("2026-03-29T210000Z-JORB-INFRA-023.yml")


def test_private_eval_cli_scores_existing_run_dir_to_output_file(tmp_path: Path) -> None:
    builder_root, _, run_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-023",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    task = _json(builder_root / "backlog.yml")["tasks"][0]
    task["title"] = "Private builder eval suite"
    standards = {"agents_exists": True, "skills_exists": True, "agents_path": "AGENTS.md", "skills_dir": "skills", "skill_files": []}
    _write_valid_phase4_feature_spec(_load_script_module(builder_root), run_dir, task, standards)
    for name in (
        "proposal.md",
        "tradeoff_matrix.md",
        "research_brief.md",
        "judge_decision.md",
        "evidence_bundle.json",
        "runtime_proof.log",
    ):
        (run_dir / name).write_text("{}\n" if name.endswith(".json") else "ok\n", encoding="utf-8")
    output_path = builder_root / "run_score.json"

    result = _run(
        [sys.executable, str(PRIVATE_EVAL_SCRIPT), "--score-run", str(run_dir), "--output", str(output_path)],
        builder_root,
    )

    assert result.returncode == 0
    payload = _json(output_path)
    assert payload["eval_result"]["task"]["id"] == "JORB-INFRA-023"
    assert payload["eval_result"]["run_dir"] == str(run_dir)


def test_eval_gate_blocks_acceptance_when_fixture_threshold_fails(tmp_path: Path) -> None:
    builder_root, _, run_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    module = _load_script_module(builder_root)
    _write_eval_fixture(
        builder_root / "eval_fixtures" / "infra.json",
        {
            "fixture_id": "infra_hardening_v1",
            "fixture_family": "infra_hardening",
            "description": "infra fixture",
            "selector": {"task_family": "JORB-INFRA", "area": "builder"},
            "mandatory_artifacts": ["compiled_feature_spec.md", "proposal.md", "tradeoff_matrix.md", "judge_decision.md", "evidence_bundle.json", "runtime_proof.log"],
            "rubric_dimensions": [
                {"name": "planning_quality", "weight": 0.2, "threshold": 0.7, "description": "plan"},
                {"name": "implementation_quality", "weight": 0.3, "threshold": 0.9, "description": "impl"},
                {"name": "test_adequacy", "weight": 0.2, "threshold": 0.9, "description": "tests"},
                {"name": "evidence_quality", "weight": 0.2, "threshold": 0.7, "description": "evidence"},
                {"name": "operator_handoff_quality", "weight": 0.1, "threshold": 0.6, "description": "handoff"},
            ],
            "pass_threshold": 0.85,
        },
    )
    task = _json(builder_root / "backlog.yml")["tasks"][0]
    standards = {"agents_exists": True, "skills_exists": True, "agents_path": "AGENTS.md", "skills_dir": "skills", "skill_files": []}
    _write_valid_phase4_feature_spec(module, run_dir, task, standards)
    for name in ("proposal.md", "tradeoff_matrix.md", "research_brief.md"):
        (run_dir / name).write_text("ok\n", encoding="utf-8")
    automation_result = {
        "task_id": "JORB-INFRA-010",
        "classification": "accepted",
        "summary": "accepted in narrative only",
        "finished_at": "2026-03-30T00:00:00+00:00",
        "steps": [],
        "changed_files": [],
    }

    persisted = module.persist_result_with_phase4_artifacts(
        run_dir,
        task,
        automation_result,
        standards=standards,
        require_runtime_proof=False,
        local_validation_payload=None,
        vm_validation_payload=None,
    )

    assert persisted["classification"] == "blocked"
    assert "Eval threshold not met" in persisted["summary"]
    assert _json(run_dir / "eval_result.json")["blocked_acceptance"] is True


def test_phase4_eval_scores_final_operator_handoff_and_evidence_artifacts(tmp_path: Path) -> None:
    builder_root, _, run_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    module = _load_script_module(builder_root)
    _write_eval_fixture(
        builder_root / "eval_fixtures" / "infra.json",
        {
            "fixture_id": "infra_hardening_v1",
            "fixture_family": "infra_hardening",
            "description": "infra fixture",
            "selector": {"task_family": "JORB-INFRA", "area": "builder"},
            "mandatory_artifacts": ["compiled_feature_spec.md", "proposal.md", "tradeoff_matrix.md", "judge_decision.md", "evidence_bundle.json", "runtime_proof.log"],
            "rubric_dimensions": [
                {"name": "planning_quality", "weight": 0.2, "threshold": 0.7, "description": "plan"},
                {"name": "implementation_quality", "weight": 0.2, "threshold": 0.7, "description": "impl"},
                {"name": "test_adequacy", "weight": 0.2, "threshold": 0.7, "description": "tests"},
                {"name": "evidence_quality", "weight": 0.2, "threshold": 0.8, "description": "evidence"},
                {"name": "operator_handoff_quality", "weight": 0.2, "threshold": 0.7, "description": "handoff"},
            ],
            "pass_threshold": 0.78,
        },
    )
    task = _json(builder_root / "backlog.yml")["tasks"][0]
    standards = {"agents_exists": True, "skills_exists": True, "agents_path": "AGENTS.md", "skills_dir": "skills", "skill_files": []}
    _write_valid_phase4_feature_spec(module, run_dir, task, standards)
    for name in ("proposal.md", "tradeoff_matrix.md", "research_brief.md"):
        (run_dir / name).write_text("ok\n", encoding="utf-8")
    _write_json(run_dir / "local_validation.json", {"results": [{"command": "pytest", "passed": True}]})
    automation_result = {
        "task_id": "JORB-INFRA-010",
        "classification": "accepted",
        "summary": "Automated loop completed with builder-side local validation success.",
        "finished_at": "2026-03-30T00:00:00+00:00",
        "steps": [{"name": "local_validation", "outcome": "passed", "detail": "All local verification commands passed."}],
        "changed_files": ["scripts/automate_task_loop.py"],
    }

    persisted = module.persist_result_with_phase4_artifacts(
        run_dir,
        task,
        automation_result,
        standards=standards,
        require_runtime_proof=False,
        local_validation_payload={"results": [{"command": "pytest", "passed": True}]},
        vm_validation_payload=None,
    )

    eval_result = _json(run_dir / "eval_result.json")
    judge_text = (run_dir / "judge_decision.md").read_text(encoding="utf-8")

    assert persisted["classification"] == "accepted"
    assert eval_result["passed"] is True
    assert eval_result["scores"]["evidence_quality"] == 1.0
    assert eval_result["scores"]["operator_handoff_quality"] == 1.0
    assert "required artifacts present: yes" in judge_text


def test_feedback_normalization_separates_observation_inference_and_recommendation(tmp_path: Path) -> None:
    module = _load_feedback_module(tmp_path)

    signal = module.normalize_operator_feedback(
        {
            "feedback": "This UX is wrong and the builder keeps missing the real structure.",
            "subsystem": "ui",
            "ticket_family": "JORB-V3",
            "recommendation": "Create a focused refinement ticket.",
        }
    )

    assert signal["raw_observation"] == "This UX is wrong and the builder keeps missing the real structure."
    assert signal["observation"] == signal["raw_observation"]
    assert signal["interpreted_issue"] == "ux_mismatch"
    assert "suggests ux mismatch" in signal["inference"]
    assert signal["recommendation"] == "Create a focused refinement ticket."


def test_feedback_duplicate_proposals_are_suppressed(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-031", area="builder", allowlist=["scripts/**"])
    module = _load_feedback_module(builder_root)
    _write_json(
        builder_root / "task_history" / "2026-03-30T000000Z-JORB-INFRA-031.yml",
        {
            "task_id": "JORB-INFRA-031",
            "status": "refined",
            "completed_at": "2026-03-30T00:00:00+00:00",
            "notes": ["Artifact enforcement failed for the same reason."],
            "failure_taxonomy": {"failure_class": "artifact_completeness_failure"},
        },
    )
    _write_json(
        builder_root / "task_history" / "2026-03-30T010000Z-JORB-INFRA-031.yml",
        {
            "task_id": "JORB-INFRA-031",
            "status": "refined",
            "completed_at": "2026-03-30T01:00:00+00:00",
            "notes": ["Artifact enforcement failed for the same reason."],
            "failure_taxonomy": {"failure_class": "artifact_completeness_failure"},
        },
    )

    first = module.generate_backlog_proposals(builder_root, dry_run=False)
    second = module.generate_backlog_proposals(builder_root, dry_run=False)

    assert len(first["proposals"]["proposals"]) >= 1
    assert len(second["proposals"]["proposals"]) == len(first["proposals"]["proposals"])


def test_feedback_recurrence_threshold_and_weak_evidence_are_enforced(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-031", area="builder", allowlist=["scripts/**"])
    module = _load_feedback_module(builder_root)
    backlog = _json(builder_root / "backlog.yml")

    low_signal = {
        "signal_id": "sig-low",
        "interpreted_issue": "artifact_gap_pattern",
        "affected_ticket_family": "JORB-INFRA",
        "proposed_action_type": "add_missing_acceptance_criteria",
        "recommendation": "Tighten acceptance criteria.",
        "inference": "Observed once with low confidence.",
        "evidence_links": ["task_history/one.yml"],
        "confidence": 0.55,
        "recurrence_count": 1,
        "severity": "medium",
    }
    assert module._proposal_from_signal(low_signal, backlog) is None

    severe_signal = {
        "signal_id": "sig-severe",
        "interpreted_issue": "eval_regression",
        "affected_ticket_family": "JORB-INFRA",
        "proposed_action_type": "add_missing_eval_coverage",
        "recommendation": "Strengthen eval coverage.",
        "inference": "A high-severity regression was observed.",
        "evidence_links": ["task_history/two.yml"],
        "confidence": 0.8,
        "recurrence_count": 1,
        "severity": "high",
    }
    proposal = module._proposal_from_signal(severe_signal, backlog)
    assert proposal is not None
    assert proposal["priority_recommendation"] == "high"


def test_feedback_generates_evidence_backed_backlog_proposal_from_repeated_pattern(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-031", area="builder", allowlist=["scripts/**"])
    module = _load_feedback_module(builder_root)
    for index in range(2):
        _write_json(
            builder_root / "task_history" / f"2026-03-30T0{index}0000Z-JORB-INFRA-031.yml",
            {
                "task_id": "JORB-INFRA-031",
                "status": "refined",
                "completed_at": f"2026-03-30T0{index}:00:00+00:00",
                "notes": ["Retry loop detected after repeated planner failure."],
                "failure_taxonomy": {"failure_class": "prompt_or_planning_failure"},
            },
        )

    payload = module.generate_backlog_proposals(builder_root, dry_run=False)
    proposals = payload["proposals"]["proposals"]
    assert len(proposals) >= 1
    retry_loop_proposals = [proposal for proposal in proposals if proposal["proposed_action_type"] == "split_oversized_ticket"]
    assert retry_loop_proposals
    proposal = retry_loop_proposals[0]
    assert proposal["source_signal_id"].startswith("sig-")
    assert proposal["status"] == "draft"
    assert proposal["evidence_links"]
    assert proposal["draft_ticket"]["id_placeholder"].startswith("DRAFT-JORB-INFRA")


def test_feedback_operator_review_status_transitions_persist_to_memory(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-031", area="builder", allowlist=["scripts/**"])
    module = _load_feedback_module(builder_root)
    common = _load_common_module(builder_root)
    _write_json(
        builder_root / "backlog_proposals.json",
        {
            "generated_at": "2026-03-30T00:00:00+00:00",
            "proposals": [
                {
                    "proposal_id": "prop-1",
                    "status": "draft",
                    "title": "Harden builder retries",
                    "confidence": 0.8,
                    "affected_ticket_family": "JORB-INFRA",
                    "evidence_summary": "Repeated retry loop.",
                    "rationale": "Create a hardening task.",
                }
            ],
        },
    )

    updated = module.update_proposal_status("prop-1", "accepted", note="good proposal", root=builder_root)
    assert updated["status"] == "accepted"
    assert updated["review_note"] == "good proposal"

    store = common.build_memory_store(builder_root)
    proposal_entries = [entry for entry in store["entries"] if entry["memory_id"] == "proposal-prop-1"]
    assert proposal_entries
    assert proposal_entries[0]["status"] == "active"
    assert "accepted" in proposal_entries[0]["relevance_tags"]


def test_feedback_dry_run_does_not_mutate_canonical_files(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-031", area="builder", allowlist=["scripts/**"])
    module = _load_feedback_module(builder_root)
    backlog_before = (builder_root / "backlog.yml").read_text(encoding="utf-8")

    _write_json(
        builder_root / "task_history" / "2026-03-30T000000Z-JORB-INFRA-031.yml",
        {
            "task_id": "JORB-INFRA-031",
            "status": "refined",
            "completed_at": "2026-03-30T00:00:00+00:00",
            "notes": ["Artifact enforcement failed for the same reason."],
            "failure_taxonomy": {"failure_class": "artifact_completeness_failure"},
        },
    )
    _write_json(
        builder_root / "task_history" / "2026-03-30T010000Z-JORB-INFRA-031.yml",
        {
            "task_id": "JORB-INFRA-031",
            "status": "refined",
            "completed_at": "2026-03-30T01:00:00+00:00",
            "notes": ["Artifact enforcement failed for the same reason."],
            "failure_taxonomy": {"failure_class": "artifact_completeness_failure"},
        },
    )

    payload = module.generate_backlog_proposals(builder_root, dry_run=True)
    assert payload["proposals"]["proposals"]
    assert not (builder_root / "feedback_signals.json").exists()
    assert not (builder_root / "backlog_proposals.json").exists()
    assert (builder_root / "backlog.yml").read_text(encoding="utf-8") == backlog_before


def test_feedback_summary_appears_in_operator_surface(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-031", area="builder", allowlist=["scripts/**"])
    _write_json(
        builder_root / "feedback_signals.json",
        {"generated_at": "2026-03-30T00:00:00+00:00", "signals": [{"signal_id": "sig-1"}]},
    )
    _write_json(
        builder_root / "backlog_proposals.json",
        {
            "generated_at": "2026-03-30T00:00:00+00:00",
            "proposals": [{"proposal_id": "prop-1", "status": "draft", "title": "Harden retries"}],
        },
    )

    result = _run([sys.executable, str(SCRIPT.parent / "show_status.py")], builder_root)

    assert result.returncode == 0
    assert "Feedback loop:" in result.stdout
    assert "- signal_count: 1" in result.stdout
    assert "- proposal_count: 1" in result.stdout
    assert "- draft_proposals: 1" in result.stdout
    assert "- top_draft_title: Harden retries" in result.stdout


def test_feedback_engine_integration_emits_proposals_without_backlog_mutation(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-031", area="builder", allowlist=["scripts/**"])
    module = _load_script_module(builder_root)
    backlog_before = (builder_root / "backlog.yml").read_text(encoding="utf-8")
    _write_json(
        builder_root / "task_history" / "2026-03-30T000000Z-JORB-INFRA-031.yml",
        {
            "task_id": "JORB-INFRA-031",
            "status": "refined",
            "completed_at": "2026-03-30T00:00:00+00:00",
            "notes": ["Retry loop detected after repeated planner failure."],
            "failure_taxonomy": {"failure_class": "prompt_or_planning_failure"},
        },
    )
    _write_json(
        builder_root / "task_history" / "2026-03-30T010000Z-JORB-INFRA-031.yml",
        {
            "task_id": "JORB-INFRA-031",
            "status": "refined",
            "completed_at": "2026-03-30T01:00:00+00:00",
            "notes": ["Retry loop detected after repeated planner failure."],
            "failure_taxonomy": {"failure_class": "prompt_or_planning_failure"},
        },
    )
    _write_json(
        builder_root / "task_history" / "2026-03-30T020000Z-JORB-INFRA-031.yml",
        {
            "task_id": "JORB-INFRA-031",
            "status": "refined",
            "completed_at": "2026-03-30T02:00:00+00:00",
            "notes": ["Retry loop detected after repeated planner failure."],
            "failure_taxonomy": {"failure_class": "prompt_or_planning_failure"},
        },
    )

    module.generate_backlog_proposals(builder_root, dry_run=False)

    proposals = _json(builder_root / "backlog_proposals.json")["proposals"]
    assert proposals
    assert (builder_root / "backlog.yml").read_text(encoding="utf-8") == backlog_before


def test_private_eval_fixture_schema_accepts_backlog_synthesis_dimension(tmp_path: Path) -> None:
    module = _load_private_eval_module(tmp_path)
    fixture = {
        "fixture_id": "proposal_backlog_synthesis_v1",
        "fixture_family": "proposal_backlog_synthesis",
        "description": "synthesis",
        "selector": {"task_family": "JORB-INFRA", "area": "builder"},
        "mandatory_artifacts": [],
        "rubric_dimensions": [
            {"name": "backlog_synthesis_quality", "weight": 1.0, "threshold": 0.8, "description": "quality"},
        ],
        "pass_threshold": 0.8,
    }
    assert module.validate_fixture_schema(fixture) == []


def test_approved_proposal_becomes_structured_synthesized_entry(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-030", area="builder", allowlist=["scripts/**"])
    module = _load_backlog_synthesis_module(builder_root)
    _write_json(
        builder_root / "backlog_proposals.json",
        {
            "generated_at": "2026-03-30T00:00:00+00:00",
            "proposals": [
                {
                    "proposal_id": "prop-1",
                    "status": "accepted",
                    "title": "Harden builder retries",
                    "rationale": "Add a follow-up hardening task.",
                    "evidence_summary": "Repeated retry loop observed 3 times.",
                    "evidence_links": ["task_history/one.yml", "task_history/two.yml"],
                    "affected_ticket_family": "JORB-INFRA",
                    "priority_recommendation": "high",
                    "confidence": 0.9,
                    "recurrence_count": 3,
                    "proposed_action_type": "create_follow_up_hardening_ticket",
                    "dependencies": ["JORB-INFRA-030"],
                    "reviewed_at": "2026-03-30T01:00:00+00:00",
                    "review_note": "approved",
                }
            ],
        },
    )

    payload = module.generate_synthesized_entries(builder_root, dry_run=False)
    assert len(payload["entries"]) == 1
    entry = payload["entries"][0]
    assert entry["ticket_id_placeholder"].startswith("DRAFT-JORB-INFRA")
    assert len(entry["acceptance_criteria"]) >= 3
    assert entry["provenance"]["source_proposal_id"] == "prop-1"
    assert entry["operator_approval"]["approved"] is True
    assert entry["repo_path"] == "~/projects/jorb-builder"
    assert entry["allowlist"] == ["../jorb-builder/**"]
    assert entry["forbid"] == ["../jorb/**"]
    assert payload["dependency_graph"]["nodes"][0]["ticket_id"] == entry["ticket_id_placeholder"]
    assert payload["dependency_graph"]["edges"][0]["from_ticket_id"] == "JORB-INFRA-030"
    assert payload["execution_order"][0]["ticket_id"] == entry["ticket_id_placeholder"]
    assert payload["execution_order"][0]["plan_state"] == "blocked"


def test_unapproved_proposal_does_not_synthesize_entry(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-030", area="builder", allowlist=["scripts/**"])
    module = _load_backlog_synthesis_module(builder_root)
    _write_json(
        builder_root / "backlog_proposals.json",
        {
            "generated_at": "2026-03-30T00:00:00+00:00",
            "proposals": [
                {
                    "proposal_id": "prop-1",
                    "status": "draft",
                    "title": "Harden builder retries",
                    "rationale": "Add a follow-up hardening task.",
                    "evidence_summary": "Repeated retry loop observed 3 times.",
                    "evidence_links": ["task_history/one.yml"],
                    "affected_ticket_family": "JORB-INFRA",
                    "priority_recommendation": "high",
                    "confidence": 0.9,
                    "recurrence_count": 3,
                    "proposed_action_type": "create_follow_up_hardening_ticket",
                    "dependencies": ["JORB-INFRA-030"],
                }
            ],
        },
    )

    payload = module.generate_synthesized_entries(builder_root, dry_run=False)
    assert payload["entries"] == []


def test_non_builder_family_proposal_is_not_synthesized_in_minimal_slice(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-030", area="builder", allowlist=["scripts/**"])
    module = _load_backlog_synthesis_module(builder_root)
    _write_json(
        builder_root / "backlog_proposals.json",
        {
            "generated_at": "2026-03-30T00:00:00+00:00",
            "proposals": [
                {
                    "proposal_id": "prop-1",
                    "status": "accepted",
                    "title": "Refine product UX follow-up",
                    "rationale": "product follow-up",
                    "evidence_summary": "Repeated UX mismatch observed.",
                    "evidence_links": ["task_history/one.yml"],
                    "affected_ticket_family": "JORB-V3",
                    "priority_recommendation": "high",
                    "confidence": 0.9,
                    "recurrence_count": 3,
                    "proposed_action_type": "refine_existing_ticket",
                    "dependencies": ["JORB-INFRA-030"],
                    "reviewed_at": "2026-03-30T01:00:00+00:00",
                }
            ],
        },
    )

    payload = module.generate_synthesized_entries(builder_root, dry_run=False)
    assert payload["entries"] == []


def test_synthesized_entry_duplicate_and_dependency_validation(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-030", area="builder", allowlist=["scripts/**"])
    module = _load_backlog_synthesis_module(builder_root)
    backlog = _json(builder_root / "backlog.yml")
    entry = {
        "synthesis_id": "syn-1",
        "ticket_id_placeholder": "JORB-INFRA-030",
        "title": "JORB-INFRA-030",
        "status_default": "pending",
        "priority_recommendation": "high",
        "rationale": "reason",
        "evidence_summary": "evidence",
        "evidence_links": ["task_history/one.yml"],
        "dependencies": ["MISSING-ID"],
        "affected_ticket_family": "JORB-INFRA",
        "acceptance_criteria": ["works correctly"],
        "required_artifacts": ["judge_decision.md"],
        "validation_expectations": ["pytest tests/test_automate_task_loop.py"],
        "requires_vm_runtime_proof": False,
        "provenance": {"source_proposal_id": "prop-1", "evidence_links": ["task_history/one.yml"]},
        "operator_approval": {"approved": True},
    }
    validation = module.validate_synthesized_entry(entry, backlog=backlog, synthesized_payload={"entries": []})
    assert "acceptance_criteria:generic" in validation["issues"]
    assert "invalid_dependency:MISSING-ID" in validation["issues"]
    assert validation["duplicate_matches"]


def test_synthesis_dry_run_does_not_mutate_canonical_files(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-030", area="builder", allowlist=["scripts/**"])
    module = _load_backlog_synthesis_module(builder_root)
    backlog_before = (builder_root / "backlog.yml").read_text(encoding="utf-8")
    _write_json(
        builder_root / "backlog_proposals.json",
        {
            "generated_at": "2026-03-30T00:00:00+00:00",
            "proposals": [
                {
                    "proposal_id": "prop-1",
                    "status": "accepted",
                    "title": "Harden builder retries",
                    "rationale": "Add a follow-up hardening task.",
                    "evidence_summary": "Repeated retry loop observed 3 times.",
                    "evidence_links": ["task_history/one.yml", "task_history/two.yml"],
                    "affected_ticket_family": "JORB-INFRA",
                    "priority_recommendation": "high",
                    "confidence": 0.9,
                    "recurrence_count": 3,
                    "proposed_action_type": "create_follow_up_hardening_ticket",
                    "dependencies": ["JORB-INFRA-030"],
                    "reviewed_at": "2026-03-30T01:00:00+00:00",
                    "review_note": "approved",
                }
            ],
        },
    )

    payload = module.generate_synthesized_entries(builder_root, dry_run=True)
    assert payload["entries"]
    assert not (builder_root / "synthesized_backlog_entries.json").exists()
    assert (builder_root / "backlog.yml").read_text(encoding="utf-8") == backlog_before


def test_synthesis_outputs_dependency_graph_and_execution_order_for_selected_approaches(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-030", area="builder", allowlist=["scripts/**"])
    module = _load_backlog_synthesis_module(builder_root)
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "accepted"
    _write_json(builder_root / "backlog.yml", backlog)
    _write_json(
        builder_root / "backlog_proposals.json",
        {
            "generated_at": "2026-03-30T00:00:00+00:00",
            "proposals": [
                {
                    "proposal_id": "prop-graph-1",
                    "status": "accepted",
                    "title": "Normalize proposal selection",
                    "rationale": "Create a first synthesized step.",
                    "evidence_summary": "Planner needs a normalized selected-approach contract.",
                    "evidence_links": ["task_history/one.yml"],
                    "affected_ticket_family": "JORB-INFRA",
                    "priority_recommendation": "high",
                    "confidence": 0.9,
                    "recurrence_count": 2,
                    "proposed_action_type": "create_follow_up_hardening_ticket",
                    "dependencies": ["JORB-INFRA-030"],
                    "draft_ticket": {"id_placeholder": "DRAFT-JORB-INFRA-SELECT-APPROACH"},
                    "reviewed_at": "2026-03-30T01:00:00+00:00",
                    "review_note": "approved",
                },
                {
                    "proposal_id": "prop-graph-2",
                    "status": "accepted",
                    "title": "Emit synthesis execution plan",
                    "rationale": "Create a dependent synthesized step.",
                    "evidence_summary": "Operators need explicit execution order after selected approaches are accepted.",
                    "evidence_links": ["task_history/two.yml"],
                    "affected_ticket_family": "JORB-INFRA",
                    "priority_recommendation": "medium",
                    "confidence": 0.9,
                    "recurrence_count": 2,
                    "proposed_action_type": "create_follow_up_hardening_ticket",
                    "dependencies": ["DRAFT-JORB-INFRA-SELECT-APPROACH"],
                    "draft_ticket": {"id_placeholder": "DRAFT-JORB-INFRA-EXECUTION-PLAN"},
                    "reviewed_at": "2026-03-30T01:05:00+00:00",
                    "review_note": "approved",
                },
            ],
        },
    )

    payload = module.generate_synthesized_entries(builder_root, dry_run=False)
    entry_by_ticket = {entry["ticket_id_placeholder"]: entry for entry in payload["entries"]}
    select_entry = entry_by_ticket["DRAFT-JORB-INFRA-SELECT-APPROACH"]
    plan_entry = entry_by_ticket["DRAFT-JORB-INFRA-EXECUTION-PLAN"]

    assert [item["ticket_id"] for item in payload["execution_order"]] == [
        "DRAFT-JORB-INFRA-SELECT-APPROACH",
        "DRAFT-JORB-INFRA-EXECUTION-PLAN",
    ]
    assert payload["execution_order"][0]["plan_state"] == "ready"
    assert payload["execution_order"][1]["plan_state"] == "ready"
    assert payload["dependency_graph"]["cycles"] == []
    node_by_ticket = {node["ticket_id"]: node for node in payload["dependency_graph"]["nodes"]}
    assert node_by_ticket["DRAFT-JORB-INFRA-EXECUTION-PLAN"]["internal_dependencies"] == [select_entry["synthesis_id"]]
    assert node_by_ticket["DRAFT-JORB-INFRA-SELECT-APPROACH"]["external_dependencies"][0]["ticket_id"] == "JORB-INFRA-030"
    assert payload["dependency_graph"]["edges"] == [
        {
            "from_ticket_id": "DRAFT-JORB-INFRA-SELECT-APPROACH",
            "from_synthesis_id": select_entry["synthesis_id"],
            "to_ticket_id": "DRAFT-JORB-INFRA-EXECUTION-PLAN",
            "to_synthesis_id": plan_entry["synthesis_id"],
            "kind": "synthesized_dependency",
        },
        {
            "from_ticket_id": "JORB-INFRA-030",
            "from_synthesis_id": None,
            "to_ticket_id": "DRAFT-JORB-INFRA-SELECT-APPROACH",
            "to_synthesis_id": select_entry["synthesis_id"],
            "kind": "backlog_dependency",
        },
    ]


def test_accepted_task_auto_promotes_dependency_satisfied_synthesized_followup(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(
        tmp_path,
        task_id="JORB-INFRA-010",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )
    module = _load_script_module(builder_root)
    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "accepted"
    backlog["tasks"].append(
        {
            "id": "DRAFT-JORB-INFRA-STATUS-TRUTH",
            "title": "Harden operator truth for Phase 4 artifact enforcement state",
            "type": "infrastructure",
            "area": "builder",
            "priority": 2,
            "status": "pending",
            "depends_on": ["JORB-INFRA-010"],
            "operator_approval": {"approved": True, "review_status": "accepted"},
            "notes": ["Synthesized from proposal prop-1"],
        }
    )

    promoted = module.promote_auto_ready_pending_tasks(backlog)

    assert promoted == ["DRAFT-JORB-INFRA-STATUS-TRUTH"]
    assert backlog["tasks"][-1]["status"] == "ready"
    assert any("Auto-promoted to ready" in note for note in backlog["tasks"][-1]["notes"])


def test_apply_synthesized_entry_requires_explicit_approval_and_audit(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-030", area="builder", allowlist=["scripts/**"])
    module = _load_backlog_synthesis_module(builder_root)
    status_before = _json(builder_root / "status.yml")
    active_before = _json(builder_root / "active_task.yml")
    _write_json(
        builder_root / "backlog_proposals.json",
        {
            "generated_at": "2026-03-30T00:00:00+00:00",
            "proposals": [
                {
                    "proposal_id": "prop-1",
                    "status": "accepted",
                    "title": "Harden builder retries",
                    "rationale": "Add a follow-up hardening task.",
                    "evidence_summary": "Repeated retry loop observed 3 times.",
                    "evidence_links": ["task_history/one.yml", "task_history/two.yml"],
                    "affected_ticket_family": "JORB-INFRA",
                    "priority_recommendation": "high",
                    "confidence": 0.9,
                    "recurrence_count": 3,
                    "proposed_action_type": "create_follow_up_hardening_ticket",
                    "dependencies": ["JORB-INFRA-030"],
                    "reviewed_at": "2026-03-30T01:00:00+00:00",
                    "review_note": "approved",
                }
            ],
        },
    )
    payload = module.generate_synthesized_entries(builder_root, dry_run=False)
    entry = payload["entries"][0]

    applied = module.apply_synthesized_entry(entry["synthesis_id"], root=builder_root)

    backlog = _json(builder_root / "backlog.yml")
    applied_task = next(task for task in backlog["tasks"] if task["id"] == applied["ticket_id_placeholder"])
    assert applied_task["repo_path"] == "~/projects/jorb-builder"
    assert applied_task["allowlist"] == ["../jorb-builder/**"]
    assert applied_task["forbid"] == ["../jorb/**"]
    audit = _json(builder_root / "backlog_apply_audit.json")
    assert audit["events"]
    assert audit["events"][0]["synthesis_id"] == entry["synthesis_id"]
    assert audit["events"][0]["synthesized_entry_sha1"]
    assert _json(builder_root / "status.yml") == status_before
    assert _json(builder_root / "active_task.yml") == active_before


def test_repair_state_reopens_stale_allowlist_blocker_when_canonical_task_has_repo_bounds(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="DRAFT-JORB-INFRA-STATUS-TRUTH",
        area="builder",
        allowlist=["../jorb-builder/**"],
    )

    backlog = _json(builder_root / "backlog.yml")
    backlog["tasks"][0]["status"] = "blocked"
    backlog["tasks"][0]["allowlist"] = ["../jorb-builder/**"]
    backlog["tasks"][0]["forbid"] = ["../jorb/**"]
    backlog["tasks"][0]["repo_path"] = "~/projects/jorb-builder"
    _write_json(builder_root / "backlog.yml", backlog)

    active = _json(builder_root / "active_task.yml")
    active["state"] = "blocked"
    active["failure_summary"] = "Executor changed files outside the task allowlist."
    active["allowlist"] = []
    _write_json(builder_root / "active_task.yml", active)

    status = _json(builder_root / "status.yml")
    status["state"] = "blocked"
    status["last_result"] = "blocked"
    _write_json(builder_root / "status.yml", status)

    _write_json(
        run_log_dir / "automation_result.json",
        {
            "task_id": "DRAFT-JORB-INFRA-STATUS-TRUTH",
            "classification": "blocked",
            "finished_at": "2026-03-30T00:00:00+00:00",
            "summary": "Executor changed files outside the task allowlist.",
            "steps": [{"name": "allowlist_check", "outcome": "blocked", "detail": "scripts/show_status.py"}],
            "changed_files": ["scripts/show_status.py"],
            "blocker_evidence": ["scripts/show_status.py"],
            "unproven_runtime_gaps": ["Executor changed files outside the task allowlist."],
        },
    )
    _write_json(
        builder_root / "blockers" / "BLK-DRAFT-JORB-INFRA-STATUS-TRUTH.yml",
        {
            "id": "BLK-DRAFT-JORB-INFRA-STATUS-TRUTH",
            "title": "Task DRAFT-JORB-INFRA-STATUS-TRUTH blocked during automated execution",
            "status": "open",
            "related_tasks": ["DRAFT-JORB-INFRA-STATUS-TRUTH"],
            "symptoms": ["Executor changed files outside the task allowlist."],
        },
    )

    repair = _run([sys.executable, str(SCRIPT), "--repair-state"], builder_root)
    active_after = _json(builder_root / "active_task.yml")
    status_after = _json(builder_root / "status.yml")
    backlog_after = _json(builder_root / "backlog.yml")
    blocker_after = _json(builder_root / "blockers" / "BLK-DRAFT-JORB-INFRA-STATUS-TRUTH.yml")
    inspect = _run([sys.executable, str(SCRIPT), "--inspect-backlog"], builder_root)
    status_view = _run([sys.executable, str(SCRIPT.parent / "show_status.py")], builder_root)

    assert repair.returncode == 0
    assert "backlog task DRAFT-JORB-INFRA-STATUS-TRUTH blocked -> ready" in repair.stdout
    assert active_after["task_id"] is None
    assert active_after["state"] == "idle"
    assert status_after["state"] == "idle"
    assert status_after["active_task_id"] is None
    assert backlog_after["tasks"][0]["status"] == "ready"
    assert blocker_after["status"] == "resolved"
    assert 'next_selected_task: "DRAFT-JORB-INFRA-STATUS-TRUTH"' in inspect.stdout
    assert "- run_state: idle" in status_view.stdout
    assert "- current_blocker: none" in status_view.stdout


def test_low_quality_synthesized_entry_is_eval_blocked(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-030", area="builder", allowlist=["scripts/**"])
    synthesis = _load_backlog_synthesis_module(builder_root)
    _write_eval_fixture(
        builder_root / "eval_fixtures" / "proposal_backlog_synthesis.json",
        {
            "fixture_id": "proposal_backlog_synthesis_v1",
            "fixture_family": "proposal_backlog_synthesis",
            "description": "synthesis",
            "selector": {"task_family": "JORB-INFRA", "area": "builder"},
            "mandatory_artifacts": [],
            "rubric_dimensions": [
                {"name": "backlog_synthesis_quality", "weight": 0.4, "threshold": 0.75, "description": "quality"},
                {"name": "evidence_quality", "weight": 0.25, "threshold": 0.75, "description": "evidence"},
                {"name": "operator_handoff_quality", "weight": 0.2, "threshold": 0.7, "description": "handoff"},
                {"name": "planning_quality", "weight": 0.15, "threshold": 0.6, "description": "planning"},
            ],
            "pass_threshold": 0.8,
        },
    )
    _write_json(
        builder_root / "backlog_proposals.json",
        {
            "generated_at": "2026-03-30T00:00:00+00:00",
            "proposals": [
                    {
                        "proposal_id": "prop-1",
                        "status": "accepted",
                        "title": "Weak ticket",
                        "rationale": "",
                        "evidence_summary": "",
                        "evidence_links": ["task_history/one.yml"],
                        "affected_ticket_family": "JORB-INFRA",
                        "priority_recommendation": "high",
                    "confidence": 0.9,
                    "recurrence_count": 3,
                    "proposed_action_type": "create_follow_up_hardening_ticket",
                    "dependencies": ["JORB-INFRA-030"],
                    "reviewed_at": "2026-03-30T01:00:00+00:00",
                }
            ],
        },
    )

    payload = synthesis.generate_synthesized_entries(builder_root, dry_run=False)
    entry = payload["entries"][0]
    assert entry["synthesis_eval_blocked"] is True
    assert entry["synthesis_eval"]["passed"] is False


def test_operator_surface_shows_synthesis_truth(tmp_path: Path) -> None:
    builder_root, _, _, _ = _setup_builder_fixture(tmp_path, task_id="JORB-INFRA-030", area="builder", allowlist=["scripts/**"])
    _write_json(
        builder_root / "synthesized_backlog_entries.json",
        {
                "generated_at": "2026-03-30T00:00:00+00:00",
                "entries": [
                {
                    "synthesis_id": "syn-1",
                    "ticket_id_placeholder": "DRAFT-JORB-INFRA-ONE",
                    "status": "draft",
                    "title": "Draft follow-up",
                    "priority_recommendation": "high",
                    "dependencies": [],
                    "operator_approval": {"approved": True},
                    "validation": {"passed": True, "issues": [], "duplicate_matches": []},
                    "synthesis_eval_blocked": False,
                    "synthesis_eval": {"overall_score": 0.92},
                },
                {"synthesis_id": "syn-2", "status": "applied", "title": "Applied follow-up", "synthesis_eval_blocked": False},
                {"synthesis_id": "syn-3", "status": "draft", "title": "Blocked follow-up", "synthesis_eval_blocked": True},
            ],
        },
    )
    result = _run([sys.executable, str(SCRIPT.parent / "show_status.py")], builder_root)
    assert result.returncode == 0
    assert "Backlog synthesis:" in result.stdout
    assert "- synthesized_entries: 3" in result.stdout
    assert "- draft_entries: 2" in result.stdout
    assert "- applied_entries: 1" in result.stdout
    assert "- eval_blocked_entries: 1" in result.stdout
    assert "- dependency_edges: 0" in result.stdout
    assert "- dependency_cycles: 0" in result.stdout
    assert "- next_execution_target: DRAFT-JORB-INFRA-ONE" in result.stdout
    assert "- top_synthesized_eval_score: 0.92" in result.stdout
    assert "- top_synthesized_eval_passed: True" in result.stdout


def test_replay_can_compare_synthesis_quality_between_attempts(tmp_path: Path) -> None:
    module = _load_private_eval_module(tmp_path)
    previous = {
        "task_id": "DRAFT-JORB-INFRA-ONE",
        "scores": {"backlog_synthesis_quality": 0.5, "evidence_quality": 0.5},
        "overall_score": 0.5,
    }
    current = {
        "task_id": "DRAFT-JORB-INFRA-ONE",
        "scores": {"backlog_synthesis_quality": 0.9, "evidence_quality": 0.8},
        "overall_score": 0.85,
    }
    comparison = module.compare_eval_results(previous, current)
    assert comparison["trend"] == "improved"
    assert comparison["category_deltas"]["backlog_synthesis_quality"] > 0
