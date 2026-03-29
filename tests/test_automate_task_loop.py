from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


SCRIPT = Path("/Users/samuelkrystal/projects/jorb-builder/scripts/automate_task_loop.py")
LIVE_BUILDER_ROOT = Path("/Users/samuelkrystal/projects/jorb-builder")
CANONICAL_FIGMA_SOURCE = "/Users/samuelkrystal/projects/jorb/design/figma"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def _write_json(path: Path, payload) -> None:
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
        "vm": {"ssh_target": "vm.example", "ssh_options": [], "product_repo": str(product_repo), "pull_command": "git pull --ff-only", "validation_commands": ["echo ok"], "runtime_validation_commands": []},
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
                "UX conformance requirements:",
                "{ux_conformance_requirements}",
                "",
                "Failure summary:",
                "{failure_summary}",
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

    assert result.returncode == 1
    assert "BACKLOG_INVALID" in result.stdout
    assert "design_section_mapping.figma_source" in result.stdout


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

    assert result.returncode == 2
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


def test_vm_smoke_failure_surfaces_clear_summary_without_bootstrap(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(
        tmp_path,
        task_id="TASK-PRODUCT",
        area="discovery",
        allowlist=["services/company_discovery.py"],
    )
    _mark_retry_ready(builder_root)
    _write_prior_vm_refined_result(run_log_dir, changed_files=["services/company_discovery.py"])

    backlog = _json(builder_root / "backlog.yml")
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
        "FAKE_SSH_FAIL_MATCH": "echo smoke-check",
    }

    result = _run([sys.executable, str(SCRIPT)], builder_root, extra_env=env)

    assert result.returncode == 1
    assert "VM smoke validation failed after local validation and git push succeeded." in result.stdout
    payload = _json(_active_run_dir(builder_root) / "automation_result.json")
    assert payload["summary"] == "VM smoke validation failed after local validation and git push succeeded."
    assert any(step["name"] == "vm_validation" and step["detail"] == "VM smoke commands failed." for step in payload["steps"])


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
    assert payload["summary"] == "executor_transport_failure"


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
