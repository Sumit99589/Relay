"""Command templates: arguments must never be able to break out of their placeholder."""

import shlex
import subprocess
import shutil

import pytest

import app_commands
from app_commands import AppCommandRunner, ALLOWED_COMMAND_TEMPLATES

INJECTION_PAYLOADS = [
    "repo; touch PWNED",
    "repo && touch PWNED",
    "repo | touch PWNED",
    "$(touch PWNED)",
    "`touch PWNED`",
    "repo\ntouch PWNED",
    "'; touch PWNED; echo '",
]


@pytest.fixture
def runner():
    return AppCommandRunner()


def test_every_template_declares_its_placeholders():
    for name, template in ALLOWED_COMMAND_TEMPLATES.items():
        args = {a: "x" for a in template.get("required_args", [])}
        ok, _, err = AppCommandRunner()._build_command(name, args)
        assert ok, f"{name}: {err}"


def test_unknown_template_is_rejected(runner):
    result = runner.run_app_command("rm_everything", {})
    assert "Unknown command template" in result["error"]


def test_missing_required_argument_is_rejected(runner):
    result = runner.run_app_command("git_status", {})
    assert "Missing required argument 'repo_path'" in result["error"]


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_injection_payload_stays_a_single_argument(runner, payload):
    ok, command, _ = runner._build_command("git_status", {"repo_path": payload})
    assert ok
    # Whatever the payload, the shell sees exactly: git -C <one argument> status
    assert shlex.split(command) == ["git", "-C", payload, "status"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_injection_payload_does_not_execute_in_a_real_shell(runner, payload, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.run_app_command("git_status", {"repo_path": payload})
    assert result["returncode"] != 0  # git fails on the bogus path...
    assert not (tmp_path / "PWNED").exists()  # ...and the injected command never ran


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_status_runs_against_a_real_repo(runner, tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    result = runner.run_app_command("git_status", {"repo_path": str(tmp_path)})
    assert result["returncode"] == 0
    assert "executed successfully" in result["message"]


def test_long_output_is_truncated(runner, monkeypatch):
    fake = subprocess.CompletedProcess(args="", returncode=0, stdout="x" * 50_000, stderr="")
    monkeypatch.setattr(app_commands.subprocess, "run", lambda *a, **k: fake)
    result = runner.run_app_command("git_status", {"repo_path": "."})
    assert len(result["stdout"]) < 11 * 1024
    assert result["stdout"].endswith("[output truncated]")


def test_timeout_is_reported_not_raised(runner, monkeypatch):
    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=app_commands.COMMAND_TIMEOUT)

    monkeypatch.setattr(app_commands.subprocess, "run", hang)
    result = runner.run_app_command("git_status", {"repo_path": "."})
    assert "timed out" in result["error"]
