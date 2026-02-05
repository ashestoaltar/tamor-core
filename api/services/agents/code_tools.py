# api/services/agents/code_tools.py
"""
Filesystem and shell tools for the Code Agent.

Each tool is a function that takes validated arguments and returns a string result.
Tools are sandboxed: writes restricted to working_dir, reads allowed in
working_dir + any paths specified via --allow-read.

Usage:
    from services.agents.code_tools import (
        TOOL_DEFINITIONS,
        PathSandbox,
        build_tool_dispatch,
    )

    sandbox = PathSandbox(
        working_dir="/home/user/project",
        allowed_read_paths=["/home/user/docs"],
    )
    dispatch = build_tool_dispatch(sandbox, "/home/user/project")

    # Execute a tool call
    result = dispatch["read_file"]({"path": "src/main.py"})
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Callable

from services.llm_service import ToolDefinition

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path Security: PathSandbox
# ---------------------------------------------------------------------------

class PathSandbox:
    """
    Path validation with configurable read-only expansion.

    - Writes are always restricted to working_dir
    - Reads are allowed in working_dir + any allowed_read_paths
    - Symlink attacks caught by Path.resolve()
    """

    def __init__(
        self,
        working_dir: str,
        allowed_read_paths: List[str] = None,
    ):
        self.working_dir = Path(working_dir).resolve()
        self.read_paths: List[Path] = [self.working_dir]

        if allowed_read_paths:
            for p in allowed_read_paths:
                resolved = Path(p).resolve()
                if resolved.exists():
                    self.read_paths.append(resolved)
                else:
                    logger.warning(f"--allow-read path does not exist: {p}")

    def validate_read(self, path: str) -> Path:
        """
        Resolve path and ensure it's within an allowed read path.
        Raises ValueError if path escapes all allowed areas.
        """
        # Handle absolute vs relative paths
        if Path(path).is_absolute():
            resolved = Path(path).resolve()
        else:
            resolved = Path(self.working_dir, path).resolve()

        for allowed in self.read_paths:
            try:
                # Check if resolved path is under allowed path
                resolved.relative_to(allowed)
                return resolved
            except ValueError:
                continue

        raise ValueError(
            f"Path '{path}' is outside allowed read paths. "
            f"Use --allow-read to grant access to additional directories."
        )

    def validate_write(self, path: str) -> Path:
        """
        Resolve path and ensure it's within working_dir.
        Writes are never allowed outside the sandbox.
        """
        # Handle absolute vs relative paths
        if Path(path).is_absolute():
            resolved = Path(path).resolve()
        else:
            resolved = Path(self.working_dir, path).resolve()

        try:
            resolved.relative_to(self.working_dir)
            return resolved
        except ValueError:
            raise ValueError(
                f"Path '{path}' resolves outside working directory. "
                f"Writes are restricted to {self.working_dir}"
            )


# ---------------------------------------------------------------------------
# Tool Implementations
# ---------------------------------------------------------------------------

def tool_read_file(
    path: str,
    sandbox: PathSandbox,
    start_line: int = None,
    end_line: int = None,
) -> str:
    """Read a file's contents, optionally a specific line range."""
    try:
        resolved = sandbox.validate_read(path)
    except ValueError as e:
        return f"ERROR: {e}"

    if not resolved.exists():
        return f"ERROR: File not found: {path}"
    if not resolved.is_file():
        return f"ERROR: Not a file: {path}"

    try:
        content = resolved.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=False)

        if start_line is not None:
            start = max(0, start_line - 1)  # Convert to 0-indexed
            end = end_line if end_line else len(lines)
            lines = lines[start:end]
            offset = start_line
        else:
            offset = 1

        # Format with line numbers
        numbered = []
        for i, line in enumerate(lines):
            numbered.append(f"{offset + i:4d} | {line}")

        return "\n".join(numbered)

    except UnicodeDecodeError:
        return f"ERROR: Binary file, cannot read as text: {path}"
    except Exception as e:
        return f"ERROR: Failed to read file: {e}"


def tool_write_file(
    path: str,
    content: str,
    sandbox: PathSandbox,
) -> str:
    """Write content to a file (creates or overwrites). Restricted to working_dir."""
    try:
        resolved = sandbox.validate_write(path)
    except ValueError as e:
        return f"ERROR: {e}"

    try:
        # Create parent directories if needed
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"OK: Wrote {len(content)} bytes to {path}"
    except OSError as e:
        return f"ERROR: {e}"


def tool_patch_file(
    path: str,
    old_str: str,
    new_str: str,
    sandbox: PathSandbox,
) -> str:
    """
    Replace a unique string in a file.
    This is the surgical edit tool — same pattern Claude Code uses.
    old_str must appear exactly once in the file.
    """
    try:
        resolved = sandbox.validate_write(path)
    except ValueError as e:
        return f"ERROR: {e}"

    if not resolved.exists():
        return f"ERROR: File not found: {path}"

    try:
        content = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"ERROR: Binary file, cannot patch: {path}"

    count = content.count(old_str)

    if count == 0:
        # Provide helpful context for debugging
        preview = old_str[:100] + "..." if len(old_str) > 100 else old_str
        return (
            f"ERROR: String not found in {path}\n"
            f"Looking for: {repr(preview)}"
        )
    if count > 1:
        return (
            f"ERROR: String appears {count} times in {path} "
            f"(must be unique). Add more surrounding context to disambiguate."
        )

    new_content = content.replace(old_str, new_str, 1)

    try:
        resolved.write_text(new_content, encoding="utf-8")
    except OSError as e:
        return f"ERROR: Failed to write file: {e}"

    return f"OK: Patched {path} ({len(old_str)} chars → {len(new_str)} chars)"


def tool_list_directory(
    path: str,
    sandbox: PathSandbox,
    max_depth: int = 2,
) -> str:
    """List files and directories, respecting depth and common ignores."""
    try:
        resolved = sandbox.validate_read(path)
    except ValueError as e:
        return f"ERROR: {e}"

    if not resolved.exists():
        return f"ERROR: Directory not found: {path}"
    if not resolved.is_dir():
        return f"ERROR: Not a directory: {path}"

    # Common directories to ignore
    IGNORE = {
        ".git", "node_modules", "__pycache__", ".venv",
        "venv", ".pytest_cache", ".mypy_cache", "dist", "build",
        ".tox", ".eggs", "*.egg-info", ".coverage", "htmlcov",
    }

    lines = []

    def walk(dir_path: Path, depth: int, prefix: str = ""):
        if depth > max_depth:
            return
        try:
            entries = sorted(
                dir_path.iterdir(),
                key=lambda e: (not e.is_dir(), e.name.lower())
            )
        except PermissionError:
            lines.append(f"{prefix}[permission denied]")
            return

        for entry in entries:
            # Skip ignored directories and hidden files
            if entry.name in IGNORE or entry.name.startswith("."):
                continue
            if entry.is_dir():
                lines.append(f"{prefix}{entry.name}/")
                walk(entry, depth + 1, prefix + "  ")
            else:
                lines.append(f"{prefix}{entry.name}")

    walk(resolved, 0)
    return "\n".join(lines) if lines else "(empty directory)"


def tool_run_command(
    command: str,
    working_dir: str,
    timeout: int = 30,
) -> str:
    """Execute a shell command and return stdout + stderr."""
    # Enforce maximum timeout
    timeout = min(timeout, 120)

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output_parts = []
        if result.stdout:
            output_parts.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            output_parts.append(f"STDERR:\n{result.stderr}")
        output_parts.append(f"EXIT CODE: {result.returncode}")

        return "\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return f"ERROR: Command timed out after {timeout}s"
    except Exception as e:
        return f"ERROR: {e}"


def tool_git_status(working_dir: str) -> str:
    """Get git status of the working directory."""
    return tool_run_command("git status --short", working_dir)


def tool_git_diff(working_dir: str, staged: bool = False) -> str:
    """Get git diff (staged or unstaged)."""
    cmd = "git diff --staged" if staged else "git diff"
    return tool_run_command(cmd, working_dir)


def tool_git_commit(message: str, working_dir: str) -> str:
    """Stage all changes and commit."""
    # Escape quotes in commit message
    escaped_message = message.replace('"', '\\"')

    # Stage all changes first
    stage_result = tool_run_command("git add -A", working_dir)
    if "ERROR" in stage_result:
        return stage_result

    # Create commit
    return tool_run_command(f'git commit -m "{escaped_message}"', working_dir)


# ---------------------------------------------------------------------------
# Tool Definitions (JSON Schema for LLM)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: List[ToolDefinition] = [
    ToolDefinition(
        name="read_file",
        description=(
            "Read a file's contents. Returns numbered lines for reference. "
            "Use start_line/end_line for large files."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the project root",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to read (1-indexed, optional)",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to read (inclusive, optional)",
                },
            },
            "required": ["path"],
        },
    ),
    ToolDefinition(
        name="write_file",
        description=(
            "Create or overwrite a file with the given content. "
            "Creates parent directories if needed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the project root",
                },
                "content": {
                    "type": "string",
                    "description": "Full file content to write",
                },
            },
            "required": ["path", "content"],
        },
    ),
    ToolDefinition(
        name="patch_file",
        description=(
            "Replace a unique string in a file with new content. "
            "The old_str must appear exactly once. Include enough "
            "surrounding context to make it unique."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the project root",
                },
                "old_str": {
                    "type": "string",
                    "description": "Exact string to find (must appear once)",
                },
                "new_str": {
                    "type": "string",
                    "description": "Replacement string",
                },
            },
            "required": ["path", "old_str", "new_str"],
        },
    ),
    ToolDefinition(
        name="list_directory",
        description=(
            "List files and directories in a path. "
            "Ignores .git, node_modules, __pycache__, etc."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Directory path relative to project root "
                        "(use '.' for root)"
                    ),
                },
                "max_depth": {
                    "type": "integer",
                    "description": "How deep to recurse (default: 2)",
                },
            },
            "required": ["path"],
        },
    ),
    ToolDefinition(
        name="run_command",
        description=(
            "Execute a shell command in the project directory. "
            "Returns stdout, stderr, and exit code. "
            "Use for running tests, linting, pip install, etc."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 30, max 120)",
                },
            },
            "required": ["command"],
        },
    ),
    ToolDefinition(
        name="git_status",
        description="Show the current git status (modified, staged, untracked files).",
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
    ToolDefinition(
        name="git_diff",
        description="Show the current git diff. Use staged=true for staged changes.",
        parameters={
            "type": "object",
            "properties": {
                "staged": {
                    "type": "boolean",
                    "description": "If true, show staged changes only",
                },
            },
        },
    ),
    ToolDefinition(
        name="git_commit",
        description=(
            "Stage all changes and create a git commit with the given message."
        ),
        parameters={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message",
                },
            },
            "required": ["message"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tool Dispatch Builder
# ---------------------------------------------------------------------------

def build_tool_dispatch(
    sandbox: PathSandbox,
    working_dir: str,
) -> Dict[str, Callable[[Dict[str, Any]], str]]:
    """
    Build the tool dispatch map with a specific sandbox instance.

    Called once per CodeAgent initialization with the configured sandbox.

    Args:
        sandbox: PathSandbox instance for path validation
        working_dir: Working directory for shell commands

    Returns:
        Dictionary mapping tool names to callable functions.
        Each function takes a dict of arguments and returns a string result.
    """
    return {
        "read_file": lambda args: tool_read_file(
            args["path"],
            sandbox,
            args.get("start_line"),
            args.get("end_line"),
        ),
        "write_file": lambda args: tool_write_file(
            args["path"],
            args["content"],
            sandbox,
        ),
        "patch_file": lambda args: tool_patch_file(
            args["path"],
            args["old_str"],
            args["new_str"],
            sandbox,
        ),
        "list_directory": lambda args: tool_list_directory(
            args.get("path", "."),
            sandbox,
            args.get("max_depth", 2),
        ),
        "run_command": lambda args: tool_run_command(
            args["command"],
            working_dir,
            args.get("timeout", 30),
        ),
        "git_status": lambda args: tool_git_status(working_dir),
        "git_diff": lambda args: tool_git_diff(
            working_dir,
            args.get("staged", False),
        ),
        "git_commit": lambda args: tool_git_commit(
            args["message"],
            working_dir,
        ),
    }
