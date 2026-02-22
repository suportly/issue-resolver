"""GitHub CLI (gh) subprocess wrapper."""

from __future__ import annotations

import json
import logging

from issue_resolver.utils.exceptions import GitHubError, PrerequisiteError
from issue_resolver.utils.subprocess_utils import run_with_retry, run_with_timeout

logger = logging.getLogger(__name__)


def check_gh_installed() -> None:
    """Verify that gh CLI is installed.

    Raises:
        PrerequisiteError: If gh is not found.
    """
    result = run_with_timeout(["gh", "--version"], timeout=10)
    if result.returncode != 0:
        raise PrerequisiteError(
            "GitHub CLI (gh) is not installed. Install from https://cli.github.com"
        )


def check_gh_authenticated() -> None:
    """Verify that gh CLI is authenticated.

    Raises:
        PrerequisiteError: If gh is not authenticated.
    """
    result = run_with_timeout(["gh", "auth", "status"], timeout=10)
    if result.returncode != 0:
        raise PrerequisiteError("GitHub CLI is not authenticated. Run: gh auth login")


def run_gh(
    args: list[str],
    timeout: int = 30,
    cwd: str | None = None,
    retry: bool = False,
) -> str:
    """Run a gh CLI command and return stdout.

    Args:
        args: Arguments to pass to gh (e.g., ["issue", "view", "42"]).
        timeout: Timeout in seconds.
        cwd: Working directory.
        retry: Whether to retry on rate limits.

    Returns:
        Stdout output as a string.

    Raises:
        GitHubError: If the command fails.
    """
    cmd = ["gh"] + args

    if retry:
        result = run_with_retry(cmd, timeout=timeout, cwd=cwd)
    else:
        result = run_with_timeout(cmd, timeout=timeout, cwd=cwd)

    if result.returncode != 0:
        raise GitHubError(f"gh command failed: {result.stderr.strip()}")

    return result.stdout


def run_gh_json(
    args: list[str],
    timeout: int = 30,
    cwd: str | None = None,
    retry: bool = False,
) -> dict | list:
    """Run a gh CLI command and parse JSON output.

    Args:
        args: Arguments to pass to gh.
        timeout: Timeout in seconds.
        cwd: Working directory.
        retry: Whether to retry on rate limits.

    Returns:
        Parsed JSON (dict or list).

    Raises:
        GitHubError: If the command fails or output is not valid JSON.
    """
    stdout = run_gh(args, timeout=timeout, cwd=cwd, retry=retry)
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        raise GitHubError(f"Failed to parse gh JSON output: {e}") from e


def get_rate_limit() -> dict:
    """Query GitHub API rate limit status.

    Returns:
        Dict with rate limit information.
    """
    return run_gh_json(["api", "rate_limit", "--jq", ".resources.search"])
