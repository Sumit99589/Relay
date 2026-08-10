"""
Pre-approved app/dev command runner for the PC agent.

Uses parameterized command templates with shlex.quote() sanitization
to prevent injection while enabling real developer workflows
(git, docker, npm, process management).
"""

import subprocess
import shlex
import logging
import platform
import os
import signal

logger = logging.getLogger("pc-agent.app_commands")

# Maximum output size (10 KB)
MAX_OUTPUT_SIZE = 10 * 1024

# Command execution timeout (seconds)
COMMAND_TIMEOUT = 30

# ─── Allowed Command Templates ──────────────────────────────────────────────
# Each template uses {placeholders} that will be filled with sanitized args.
# Templates marked with _detached: True run as background processes.

ALLOWED_COMMAND_TEMPLATES = {
    # Git operations
    "git_status": {
        "cmd": "git -C {repo_path} status",
        "required_args": ["repo_path"],
        "description": "Check git status of a repository",
    },
    "git_add": {
        "cmd": "git -C {repo_path} add .",
        "required_args": ["repo_path"],
        "description": "Stage all changes in a repository",
    },
    "git_commit": {
        "cmd": "git -C {repo_path} commit -m {message}",
        "required_args": ["repo_path", "message"],
        "description": "Commit staged changes with a message",
    },
    "git_log": {
        "cmd": "git -C {repo_path} log --oneline -n {count}",
        "required_args": ["repo_path"],
        "optional_args": {"count": "10"},
        "description": "Show recent git commits",
    },
    "git_push": {
        "cmd": "git -C {repo_path} push",
        "required_args": ["repo_path"],
        "description": "Push commits to remote",
    },
    "git_pull": {
        "cmd": "git -C {repo_path} pull",
        "required_args": ["repo_path"],
        "description": "Pull latest changes from remote",
    },
    "git_diff": {
        "cmd": "git -C {repo_path} diff --stat",
        "required_args": ["repo_path"],
        "description": "Show changed files summary",
    },
    "git_branch": {
        "cmd": "git -C {repo_path} branch -a",
        "required_args": ["repo_path"],
        "description": "List all git branches",
    },

    # Docker operations
    "docker_ps": {
        "cmd": "docker ps --format 'table {{.ID}}\\t{{.Names}}\\t{{.Status}}\\t{{.Ports}}'",
        "required_args": [],
        "description": "List running Docker containers",
    },
    "docker_ps_all": {
        "cmd": "docker ps -a --format 'table {{.ID}}\\t{{.Names}}\\t{{.Status}}'",
        "required_args": [],
        "description": "List all Docker containers including stopped",
    },
    "docker_restart": {
        "cmd": "docker restart {container_name}",
        "required_args": ["container_name"],
        "description": "Restart a Docker container",
    },
    "docker_logs": {
        "cmd": "docker logs --tail {lines} {container_name}",
        "required_args": ["container_name"],
        "optional_args": {"lines": "50"},
        "description": "Show recent Docker container logs",
    },
    "docker_stop": {
        "cmd": "docker stop {container_name}",
        "required_args": ["container_name"],
        "description": "Stop a Docker container",
    },
    "docker_start": {
        "cmd": "docker start {container_name}",
        "required_args": ["container_name"],
        "description": "Start a stopped Docker container",
    },

    # NPM / Node.js
    "npm_dev_start": {
        "cmd": "cd {project_path} && npm run dev",
        "required_args": ["project_path"],
        "detached": True,
        "description": "Start npm dev server (runs in background)",
    },
    "npm_install": {
        "cmd": "cd {project_path} && npm install",
        "required_args": ["project_path"],
        "description": "Install npm dependencies",
    },
    "npm_test": {
        "cmd": "cd {project_path} && npm test",
        "required_args": ["project_path"],
        "description": "Run npm tests",
    },
    "npm_build": {
        "cmd": "cd {project_path} && npm run build",
        "required_args": ["project_path"],
        "description": "Build the npm project",
    },

    # Process management
    "process_check": {
        "cmd": "pgrep -fl {process_name}",
        "required_args": ["process_name"],
        "description": "Check if a process is running",
    },
    "process_kill": {
        "cmd": "pkill -f {process_name}",
        "required_args": ["process_name"],
        "description": "Kill a process by name",
    },
    "port_check": {
        "cmd": "lsof -i :{port}",
        "required_args": ["port"],
        "description": "Check what's using a specific port",
    },
}


class AppCommandRunner:
    """Execute pre-approved app/developer commands with safe arg substitution."""

    def __init__(self):
        """Initialize the app command runner."""
        self.templates = dict(ALLOWED_COMMAND_TEMPLATES)

    def _sanitize_arg(self, value: str) -> str:
        """Sanitize a user-provided argument value using shlex.quote().

        This prevents shell injection by properly escaping special characters.
        """
        return shlex.quote(str(value))

    def _build_command(self, template_name: str, args: dict) -> tuple[bool, str, str]:
        """Build a command string from a template and sanitized args.

        Returns:
            (is_valid, command_string, error_message)
        """
        if template_name not in self.templates:
            available = ", ".join(sorted(self.templates.keys()))
            return False, "", (
                f"Unknown command template '{template_name}'. "
                f"Available templates: {available}"
            )

        template = self.templates[template_name]
        cmd_template = template["cmd"]
        required_args = template.get("required_args", [])
        optional_args = template.get("optional_args", {})

        # Check required args
        provided_args = args or {}
        for arg_name in required_args:
            if arg_name not in provided_args:
                return False, "", (
                    f"Missing required argument '{arg_name}' for template '{template_name}'. "
                    f"Required: {required_args}"
                )

        # Build sanitized substitution dict
        safe_args = {}
        for key, value in provided_args.items():
            safe_args[key] = self._sanitize_arg(value)

        # Fill in optional defaults (also sanitized)
        for key, default_val in optional_args.items():
            if key not in safe_args:
                safe_args[key] = self._sanitize_arg(default_val)

        # Substitute into template
        try:
            command = cmd_template.format(**safe_args)
        except KeyError as e:
            return False, "", f"Missing argument for placeholder: {e}"

        return True, command, ""

    def run_app_command(self, template: str, args: dict = None) -> dict:
        """Run a pre-approved app command.

        Args:
            template: Name of the command template (e.g. 'git_status', 'docker_ps').
            args: Dict of argument values to fill into the template.

        Returns:
            dict with 'stdout', 'stderr', 'returncode', or 'error'.
        """
        if args is None:
            args = {}

        # Build the command
        is_valid, command, error = self._build_command(template, args)
        if not is_valid:
            return {"error": error}

        template_config = self.templates[template]
        is_detached = template_config.get("detached", False)

        logger.info(f"App command: [{template}] → {command}")

        try:
            if is_detached:
                return self._run_detached(command, template)
            else:
                return self._run_blocking(command, template)

        except Exception as e:
            logger.error(f"App command error: {e}")
            return {"error": f"Command failed: {str(e)}"}

    def _run_blocking(self, command: str, template: str) -> dict:
        """Run a command and wait for completion."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT,
            )

            stdout = result.stdout
            stderr = result.stderr

            # Truncate if too long
            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = stdout[:MAX_OUTPUT_SIZE] + "\n... [output truncated]"
            if len(stderr) > MAX_OUTPUT_SIZE:
                stderr = stderr[:MAX_OUTPUT_SIZE] + "\n... [output truncated]"

            response = {
                "template": template,
                "stdout": stdout,
                "returncode": result.returncode,
            }

            if stderr:
                response["stderr"] = stderr

            if result.returncode == 0:
                response["message"] = f"Command '{template}' executed successfully."
            else:
                response["message"] = f"Command '{template}' exited with code {result.returncode}."

            logger.info(f"App command completed: {template} → exit code {result.returncode}")
            return response

        except subprocess.TimeoutExpired:
            logger.warning(f"App command timed out: {template}")
            return {"error": f"Command '{template}' timed out after {COMMAND_TIMEOUT} seconds."}

    def _run_detached(self, command: str, template: str) -> dict:
        """Run a command as a detached background process."""
        try:
            # Start process in new session so it survives parent exit
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid if platform.system() != "Windows" else None,
                start_new_session=True,
            )

            return {
                "template": template,
                "pid": process.pid,
                "message": (
                    f"Command '{template}' started as background process (PID: {process.pid}). "
                    f"Use 'process_check' to verify it's running."
                ),
                "detached": True,
            }

        except Exception as e:
            return {"error": f"Failed to start background process: {str(e)}"}
