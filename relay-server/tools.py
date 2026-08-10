"""
Gemini tool definitions and system prompt for the Remote PC Control Agent.

These tool functions are defined as Python functions with type hints and docstrings,
which the google-genai SDK auto-converts to the Gemini function calling schema.
"""

# ─── System prompt ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an AI Remote PC Control Agent operating the user's PC via tool calls.

CRITICAL HARD RULES:
1. YOU HAVE NO PRIOR KNOWLEDGE OF ANY FILES, FOLDERS, OR SYSTEM CONTENTS ON THE PC.
2. YOU MUST NEVER GUESS, INVENT, FABRICATE, OR HALLUCINATE FILE NAMES, DATES, PATHS, OR CONTENT.
3. FOR ANY USER REQUEST CONCERNING FILES, DOWNLOADS, DIRECTORIES, OR SYSTEM COMMANDS, YOU MUST INVOKE A TOOL FIRST BEFORE ANSWERING.
4. When asked to list recent files, downloads, or directory contents, call `list_directory(path="~/Downloads")` or `search_files(folder="~/Downloads")`.
5. Report ONLY the exact file names and attributes returned by the tool response. If no files are returned, state that no files were found.
6. For delete_file: ALWAYS state what will be deleted and ask for confirmation.
7. For run_command: Run shell commands on the PC as requested (supports redirection, piping, and chaining).
8. For developer tasks (git, docker, npm, process management): use `run_app_command` with the appropriate template instead of `run_command`. This tool supports: git_status, git_add, git_commit, git_log, git_push, git_pull, git_diff, git_branch, docker_ps, docker_ps_all, docker_restart, docker_logs, docker_stop, docker_start, npm_dev_start, npm_install, npm_test, npm_build, process_check, process_kill, port_check.
10. For file modifications: Use `create_file` for new files (fails if file exists), `write_file` to write/overwrite content, or `append_to_file` to append content. Writing/overwriting an existing file with `write_file` requires user confirmation.

PLAN-BEFORE-ACT RULE:
Before taking any action that involves more than one tool call, or any action that deletes, overwrites, sends, or commits something, you MUST call propose_plan first and wait for user confirmation before proceeding. State your plan in plain, concrete language — name the actual commands/files/recipients involved, not vague descriptions. For a single simple read-only request (e.g. "how much disk space do I have"), skip the plan and just act.

Example of when a plan IS required: "deploy this project" → propose_plan with steps like ["Run npm install", "Run npm build", "Check build logs for errors"].
Example of when a plan IS required: "find last week's budget file and email it to test@example.com" → propose_plan with steps.
Example of when a plan is NOT required: "list files in Downloads" → just call the tool directly.
Example of when a plan is NOT required: "check disk space" → just call run_command directly.

SELF-CORRECTION GUIDANCE:
If a tool call fails, do not immediately give up. Reason about WHY it failed and try a different approach:
- If a file was not found by name, try search_file_content to search inside file contents.
- If search_files returned no results, broaden your search terms or try a different folder.
- If a permission error occurred, use run_command to inspect permissions.
- If a command failed, check if the syntax or working directory was wrong.
Do NOT repeat the exact same failing call. Adjust based on the error.
"""


# ─── Tool function signatures ────────────────────────────────────────────────
# These are "dummy" functions — they define the schema for Gemini.
# The actual execution happens on the PC agent or relay server.

def write_file(path: str, content: str) -> dict:
    """Overwrites or creates the file at the specified path with the provided content.

    If the target file already exists, user confirmation is required before execution.
    Path must be within allowed working directories.

    Args:
        path: Absolute path to the file on the PC.
        content: The text content to write to the file.

    Returns:
        Status message, file path, and size written, or an error message.
    """
    pass


def append_to_file(path: str, content: str) -> dict:
    """Appends the provided content to the end of the file at the specified path.

    Path must be within allowed working directories.

    Args:
        path: Absolute path to the file on the PC.
        content: The text content to append to the file.

    Returns:
        Status message, file path, and total size, or an error message.
    """
    pass


def create_file(path: str, content: str = "") -> dict:
    """Creates a new file at the specified path with optional initial content.

    Fails if the file already exists (preventing accidental overwrites).
    Path must be within allowed working directories.

    Args:
        path: Absolute path to the new file on the PC.
        content: Initial text content for the file (default empty).

    Returns:
        Status message, file path, and size created, or an error message.
    """
    pass


def list_directory(path: str = "~/Downloads") -> dict:
    """List files and folders inside a specific directory on the PC (e.g. '~/Downloads', '~/Desktop', '~/Documents', '/mnt').

    Args:
        path: Path to the directory to list (default: '~/Downloads').

    Returns:
        List of files and directories in that folder sorted by modification date (newest first).
    """
    pass


def search_files(keyword: str = "", file_type: str = "", days_back: int = 0, folder: str = "") -> dict:
    """Search for files on the user's PC by keyword, file type, date modified, or specific folder.

    Args:
        keyword: Search term to match against file names (case-insensitive).
        file_type: File extension filter, e.g. 'pdf', 'xlsx', 'docx', 'py'. Without the dot.
        days_back: Only return files modified within this many days. 0 means no date filter.
        folder: Specific folder to search inside (e.g. '~/Downloads', '~/Desktop').

    Returns:
        A list of matching files sorted by most recently modified first.
    """
    pass


def read_file_preview(path: str) -> dict:
    """Read a short preview/summary of a file's contents to help understand or disambiguate between candidates.

    For text files, returns the first ~500 characters.
    For binary files (images, archives, etc.), returns metadata like size, type, and modified date.

    Args:
        path: The absolute path to the file on the PC.

    Returns:
        A preview of the file contents or metadata.
    """
    pass


def fetch_file(path: str) -> dict:
    """Retrieve the full file from the PC so it can be attached to an email or downloaded.

    Supports files of any size. Small files (<5MB) are sent directly. Larger files are
    automatically transferred in chunks with a progress bar on the phone UI.

    Args:
        path: The absolute path to the file on the PC.

    Returns:
        The file data (base64), file name, size, and MIME type.
    """
    pass


def run_command(command: str) -> dict:
    """Run a shell command on the PC. Supports piping, chaining, and redirection (e.g. '>').

    Args:
        command: The shell command to run (e.g., 'df -h', 'ls -la ~/Documents', 'echo hello > test.txt').

    Returns:
        The stdout and stderr output of the command.
    """
    pass


def delete_file(path: str) -> dict:
    """Delete a file from the PC. This action REQUIRES explicit user confirmation before execution.

    IMPORTANT: Always tell the user exactly which file will be deleted and ask for confirmation first.
    The system will prompt the user to confirm before actually deleting.

    Args:
        path: The absolute path to the file to delete.

    Returns:
        Confirmation that the file was deleted, or an error message.
    """
    pass


def send_email(to: str, subject: str, body: str, attachment_path: str = "") -> dict:
    """Send an email via Gmail, optionally with a file from the PC attached.

    If attachment_path is provided, the file will be fetched from the PC and attached to the email.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body text.
        attachment_path: Optional. Absolute path to a file on the PC to attach.

    Returns:
        Confirmation that the email was sent, or an error message.
    """
    pass


def run_app_command(template: str, args: dict = {}) -> dict:
    """Run a pre-approved developer/app command like git push, docker restart, or checking if a process is running.

    Use this tool for developer workflows instead of run_command. Supported templates:
    - git_status: Check git status (args: repo_path)
    - git_add: Stage all changes (args: repo_path)
    - git_commit: Commit staged changes (args: repo_path, message)
    - git_log: Show recent commits (args: repo_path, optional count)
    - git_push: Push commits to remote (args: repo_path)
    - git_pull: Pull latest changes (args: repo_path)
    - git_diff: Show changed files (args: repo_path)
    - git_branch: List branches (args: repo_path)
    - docker_ps: List running containers (no args)
    - docker_ps_all: List all containers (no args)
    - docker_restart: Restart a container (args: container_name)
    - docker_logs: Show container logs (args: container_name, optional lines)
    - docker_stop: Stop a container (args: container_name)
    - docker_start: Start a container (args: container_name)
    - npm_dev_start: Start dev server in background (args: project_path)
    - npm_install: Install dependencies (args: project_path)
    - npm_test: Run tests (args: project_path)
    - npm_build: Build project (args: project_path)
    - process_check: Check if process is running (args: process_name)
    - process_kill: Kill a process (args: process_name)
    - port_check: Check what's using a port (args: port)

    Args:
        template: Name of the command template to run.
        args: Dictionary of argument values to fill into the template.

    Returns:
        The command output (stdout, stderr, return code) or error.
    """
    pass


def propose_plan(summary: str, steps: list[str], risk_level: str) -> dict:
    """Propose a short plan of the steps you intend to take, BEFORE executing any of them.

    Required for any request involving multiple actions, file deletion, command execution,
    sending email, or coding changes. Not required for a single simple read-only lookup.

    Args:
        summary: One sentence describing the overall goal.
        steps: Ordered list of concrete steps, e.g. ['Run npm install', 'Run npm build', 'Check build logs for errors'].
        risk_level: Risk assessment — 'low', 'medium', or 'high'. Use 'high' for destructive/irreversible actions (delete, overwrite, send, commit).

    Returns:
        Confirmation of whether the user approved, modified, or rejected the plan.
    """
    pass


def search_file_content(query: str, folder: str = "", file_type: str = "", max_results: int = 10) -> dict:
    """Search inside file contents (not just file names) for a query string.

    Useful when search_files (filename search) doesn't find what you're looking for.
    Searches text inside files using grep-like matching.

    Args:
        query: The text to search for inside files (case-insensitive).
        folder: Specific folder to search inside (e.g. '~/Downloads', '~/Documents'). Defaults to common user directories.
        file_type: File extension filter, e.g. 'pdf', 'txt', 'py'. Without the dot.
        max_results: Maximum number of matching files to return (default 10).

    Returns:
        A list of files containing the query text, with preview snippets of matching lines.
    """
    pass


# List of all tool functions for Gemini
ALL_TOOLS = [list_directory, search_files, search_file_content, read_file_preview, fetch_file, run_command, delete_file, write_file, append_to_file, create_file, send_email, run_app_command, propose_plan]

# Tools that require user confirmation before execution
DESTRUCTIVE_TOOLS = {"delete_file", "write_file"}

# Tools that execute on the PC agent (vs. server-side)
PC_SIDE_TOOLS = {"list_directory", "search_files", "search_file_content", "read_file_preview", "fetch_file", "run_command", "delete_file", "write_file", "append_to_file", "create_file", "run_app_command"}

# Tools that execute on the relay server
SERVER_SIDE_TOOLS = {"send_email"}

# The plan tool (handled specially by the orchestration layer, not routed to PC)
PLAN_TOOL = "propose_plan"
