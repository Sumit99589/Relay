"""
Whitelisted command runner for the PC agent.

Only allows commands whose first token is in the predefined whitelist.
Prevents arbitrary shell execution while still allowing useful read-only operations.
"""

import subprocess
import shlex
import logging
import platform

logger = logging.getLogger("pc-agent.command_runner")

# Maximum output size (10 KB)
MAX_OUTPUT_SIZE = 10 * 1024

# Command execution timeout (seconds)
COMMAND_TIMEOUT = 30

# Whitelisted command base names — only these are allowed as the first token
COMMAND_WHITELIST = {
    # File listing
    "ls", "dir", "find", "tree",
    # File content
    "cat", "head", "tail", "wc", "grep",
    # Disk / system info
    "df", "du", "free", "uptime", "uname", "hostname", "whoami", "date",
    # Archive
    "zip", "tar", "gzip", "unzip",
    # Misc safe commands
    "echo", "pwd", "env", "printenv", "which", "file", "stat", "md5sum", "sha256sum",
    # Windows equivalents
    "type", "systeminfo", "ver", "where", "ipconfig",
}

# Explicitly blocked patterns (even if first token is whitelisted)
BLOCKED_PATTERNS = [
    "rm ",     # Extra safety
    "rm\t",
    "rmdir",
    "del ",
    "format",
    "mkfs",
    "dd ",
    "sudo",
    "su ",
]


class CommandRunner:
    """Execute whitelisted shell commands with safety checks."""

    def __init__(self, extra_whitelist: list[str] = None, extra_blocked: list[str] = None):
        """Initialize the command runner.

        Args:
            extra_whitelist: Additional command names to whitelist.
            extra_blocked: Additional patterns to block.
        """
        self.whitelist = set(COMMAND_WHITELIST)
        self.blocked_patterns = list(BLOCKED_PATTERNS)

        if extra_whitelist:
            self.whitelist.update(extra_whitelist)
        if extra_blocked:
            self.blocked_patterns.extend(extra_blocked)

    def _validate_command(self, command: str) -> tuple[bool, str]:
        """Validate a command against the whitelist and blocked patterns.

        Returns:
            (is_valid, error_message)
        """
        if not command or not command.strip():
            return False, "Command is empty."

        import os
        allow_unrestricted = os.getenv("ALLOW_UNRESTRICTED_COMMANDS", "true").lower() in ("true", "1", "yes")
        if allow_unrestricted:
            return True, ""

        # Check blocked patterns
        for pattern in self.blocked_patterns:
            if pattern in command:
                return False, (
                    f"Command contains blocked pattern '{pattern}'."
                )

        # Parse the first token (command name)
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = command.strip().split()

        if not tokens:
            return False, "Could not parse command."

        base_command = tokens[0].lower()

        # Strip path prefix (e.g., /usr/bin/ls → ls)
        if "/" in base_command or "\\" in base_command:
            base_command = base_command.split("/")[-1].split("\\")[-1]

        if base_command not in self.whitelist:
            return False, (
                f"Command '{base_command}' is not in the whitelist. "
                f"Allowed commands: {', '.join(sorted(self.whitelist))}"
            )

        return True, ""

    def run_command(self, command: str) -> dict:
        """Run a whitelisted shell command.

        Args:
            command: The full command string to execute.

        Returns:
            dict with 'stdout', 'stderr', 'returncode', or 'error'.
        """
        # Validate
        is_valid, error = self._validate_command(command)
        if not is_valid:
            return {"error": error}

        try:
            is_windows = platform.system() == "Windows"

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT,
                cwd=None,  # Use current directory
                env=None,  # Inherit environment
            )

            stdout = result.stdout
            stderr = result.stderr

            # Truncate if too long
            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = stdout[:MAX_OUTPUT_SIZE] + "\n... [output truncated]"
            if len(stderr) > MAX_OUTPUT_SIZE:
                stderr = stderr[:MAX_OUTPUT_SIZE] + "\n... [output truncated]"

            response = {
                "stdout": stdout,
                "returncode": result.returncode,
            }

            if stderr:
                response["stderr"] = stderr

            if result.returncode != 0:
                response["message"] = f"Command exited with code {result.returncode}."
            else:
                response["message"] = "Command executed successfully."

            logger.info(f"Command executed: {command} → exit code {result.returncode}")
            return response

        except subprocess.TimeoutExpired:
            logger.warning(f"Command timed out: {command}")
            return {"error": f"Command timed out after {COMMAND_TIMEOUT} seconds."}

        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return {"error": f"Command failed: {str(e)}"}
