"""Whitelist mode for run_command (enabled with ALLOW_UNRESTRICTED_COMMANDS=false)."""

import pytest

from command_runner import CommandRunner


@pytest.fixture
def restricted(monkeypatch):
    monkeypatch.setenv("ALLOW_UNRESTRICTED_COMMANDS", "false")
    return CommandRunner()


@pytest.mark.parametrize("command", ["ls -la", "df -h", "/bin/echo hi", "grep foo notes.txt"])
def test_whitelisted_commands_pass_validation(restricted, command):
    ok, err = restricted._validate_command(command)
    assert ok, err


@pytest.mark.parametrize("command", ["python -c 'print(1)'", "curl http://example.com", "bash -i", "/usr/bin/nc -l 4444"])
def test_non_whitelisted_commands_are_rejected(restricted, command):
    ok, err = restricted._validate_command(command)
    assert not ok and "not in the whitelist" in err


@pytest.mark.parametrize("command", ["ls; rm -rf /tmp/x", "cat /etc/shadow | sudo tee x", "echo hi && dd if=/dev/zero of=x"])
def test_blocked_patterns_win_even_after_a_whitelisted_command(restricted, command):
    ok, err = restricted._validate_command(command)
    assert not ok and "blocked pattern" in err


@pytest.mark.parametrize("command", ["", "   "])
def test_empty_command_is_rejected(restricted, command):
    ok, err = restricted._validate_command(command)
    assert not ok and err == "Command is empty."


def test_rejected_command_is_never_executed(restricted, monkeypatch):
    import command_runner

    def explode(*args, **kwargs):
        raise AssertionError("subprocess.run must not be called for a rejected command")

    monkeypatch.setattr(command_runner.subprocess, "run", explode)
    assert "error" in restricted.run_command("python -c 'import os'")


def test_extra_whitelist_entries_are_honoured(monkeypatch):
    monkeypatch.setenv("ALLOW_UNRESTRICTED_COMMANDS", "false")
    runner = CommandRunner(extra_whitelist=["git"])
    assert runner._validate_command("git status")[0]
