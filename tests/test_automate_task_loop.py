from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


SCRIPT = Path("/Users/samuelkrystal/projects/jorb-builder/scripts/automate_task_loop.py")


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["JORB_BUILDER_ROOT"] = str(cwd)
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, env=env)


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
    _write_json(builder_root / "status.yml", _base_status())
    _write_json(builder_root / "active_task.yml", _base_active(task_id, prompt_file, run_log_dir, allowlist))
    _write_json(builder_root / "config.yml", _base_config(product_repo, builder_root))
    (builder_root / "builder_memory.md").write_text("# Memory\n", encoding="utf-8")
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
    assert "NO_ACTIVE_TASK" in result.stdout


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
    assert active["state"] == "paused"
    assert active["target_kind"] == "builder"
    assert active["target_repo"] == str(builder_root)

    resume = _run([sys.executable, str(SCRIPT), "--resume"], builder_root)
    assert resume.returncode == 0
    assert "PAUSED" in resume.stdout
    assert "builder repo changes" in resume.stdout
    result = _json(run_log_dir / "automation_result.json")
    assert result["classification"] == "paused"
    assert "builder repo changes" in result["summary"]


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
    builder_root, product_repo, run_log_dir, _ = _setup_builder_fixture(
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
    result = _json(run_log_dir / "automation_result.json")
    assert result["classification"] == "paused"
    assert "product repo changes" in result["summary"]


def test_resume_allows_expected_dirty_builder_task_files(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(tmp_path, task_id="TASK-BUILDER", area="builder", allowlist=["../jorb-builder/**"])

    pause = _run([sys.executable, str(SCRIPT)], builder_root)
    assert pause.returncode == 0

    (builder_root / "worker.py").write_text("print('ok')\n", encoding="utf-8")

    resume = _run([sys.executable, str(SCRIPT), "--resume"], builder_root)

    assert resume.returncode == 0
    assert "BLOCKED Builder repo is dirty before automated execution" not in resume.stdout
    payload = _json(run_log_dir / "automation_result.json")
    assert payload["classification"] == "accepted"
    assert "worker.py" in payload["changed_files"]


def test_resume_blocks_out_of_allowlist_dirty_files(tmp_path: Path) -> None:
    builder_root, product_repo, run_log_dir, _ = _setup_builder_fixture(
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
    payload = _json(run_log_dir / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert "wrong.txt" in payload["blocker_evidence"]


def test_product_validation_uses_venv_validation_when_present(tmp_path: Path) -> None:
    builder_root, product_repo, run_log_dir, _ = _setup_builder_fixture(
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
    validation = _json(run_log_dir / "local_validation.json")
    assert validation["passed"] is True
    assert validation["venv_path"] == str(product_repo / ".venv_validation")


def test_product_validation_fails_clearly_without_venv(tmp_path: Path) -> None:
    builder_root, product_repo, run_log_dir, _ = _setup_builder_fixture(
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
    payload = _json(run_log_dir / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert "No product validation virtualenv found" in payload["summary"]


def test_dirty_repo_blocks_and_preserves_active_task(tmp_path: Path) -> None:
    builder_root, _, run_log_dir, _ = _setup_builder_fixture(tmp_path, task_id="TASK-DIRTY", area="builder", allowlist=["../jorb-builder/**"])
    (builder_root / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    result = _run([sys.executable, str(SCRIPT)], builder_root)

    assert result.returncode == 2
    assert "BLOCKED" in result.stdout
    assert "Clean" in result.stdout
    active = _json(builder_root / "active_task.yml")
    assert active["task_id"] == "TASK-DIRTY"
    assert active["state"] == "failed"
    payload = _json(run_log_dir / "automation_result.json")
    assert payload["classification"] == "blocked"
    assert "Builder repo is dirty" in payload["summary"]
