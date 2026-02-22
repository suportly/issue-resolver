"""Claude Code CLI subprocess wrapper."""

from __future__ import annotations

import logging
import subprocess

from issue_resolver.utils.exceptions import PrerequisiteError
from issue_resolver.utils.subprocess_utils import run_with_timeout

logger = logging.getLogger(__name__)


def check_claude_installed() -> None:
    """Verify that Claude Code CLI is installed.

    Raises:
        PrerequisiteError: If claude is not found.
    """
    result = run_with_timeout(["claude", "--version"], timeout=10)
    if result.returncode != 0:
        raise PrerequisiteError(
            "Claude Code CLI is not installed. "
            "Install with: npm install -g @anthropic-ai/claude-code"
        )


def invoke(
    prompt: str,
    output_format: str = "json",
    max_turns: int = 1,
    model: str | None = None,
    permission_mode: str | None = None,
    max_budget_usd: float | None = None,
    timeout: int = 300,
    cwd: str | None = None,
) -> tuple[str, str, int, bool]:
    """Invoke Claude Code CLI and return raw output.

    Args:
        prompt: The prompt text.
        output_format: Output format (json or text).
        max_turns: Maximum conversation turns.
        model: Model to use (e.g., "haiku", "opus").
        permission_mode: Permission mode (e.g., "bypassPermissions").
        max_budget_usd: Maximum budget in USD.
        timeout: Timeout in seconds.
        cwd: Working directory.

    Returns:
        Tuple of (stdout, stderr, returncode, timeout_expired).

    Raises:
        ClaudeError: If there's an unexpected error invoking the CLI.
    """
    cmd = ["claude", "-p", prompt, "--output-format", output_format]

    if max_turns:
        cmd.extend(["--max-turns", str(max_turns)])
    if model:
        cmd.extend(["--model", model])
    if permission_mode:
        cmd.extend(["--permission-mode", permission_mode])
    if max_budget_usd is not None:
        cmd.extend(["--max-budget-usd", f"{max_budget_usd:.2f}"])

    logger.debug(
        "Invoking Claude: model=%s, max_turns=%d, budget=$%.2f, cwd=%s",
        model or "default",
        max_turns,
        max_budget_usd or 0,
        cwd,
    )

    try:
        result = run_with_timeout(cmd, timeout=timeout, cwd=cwd)
        return result.stdout, result.stderr, result.returncode, False
    except subprocess.TimeoutExpired:
        logger.warning("Claude CLI timed out after %ds", timeout)
        return "", f"Timeout after {timeout}s", -1, True
