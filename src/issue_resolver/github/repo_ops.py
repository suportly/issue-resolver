"""GitHub repository operations: fork, clone, branch, push."""

from __future__ import annotations

import logging

from issue_resolver.github.client import run_gh
from issue_resolver.utils.exceptions import GitHubError
from issue_resolver.utils.subprocess_utils import run_with_timeout

logger = logging.getLogger(__name__)


def fork_repo(owner: str, repo: str) -> str:
    """Fork a repository (or reuse existing fork).

    Args:
        owner: Repository owner.
        repo: Repository name.

    Returns:
        The fork's full name (e.g., "myuser/repo").
    """
    logger.info("Forking %s/%s", owner, repo)
    try:
        output = run_gh(
            ["repo", "fork", f"{owner}/{repo}", "--clone=false"],
            timeout=60,
        )
        logger.debug("Fork output: %s", output.strip())
    except GitHubError as e:
        # "already exists" is not an error — reuse the fork
        if "already exists" in str(e).lower():
            logger.info("Fork already exists, reusing")
        else:
            raise

    # Get the fork name
    gh_user = _get_gh_username()
    return f"{gh_user}/{repo}"


def clone_repo(
    clone_url: str,
    workspace_path: str,
    depth: int = 1,
) -> None:
    """Clone a repository to a workspace directory.

    Args:
        clone_url: Repository URL or owner/repo to clone.
        workspace_path: Target directory.
        depth: Clone depth (1 for shallow).
    """
    logger.info("Cloning %s to %s (depth=%d)", clone_url, workspace_path, depth)
    run_gh(
        ["repo", "clone", clone_url, workspace_path, "--", f"--depth={depth}"],
        timeout=120,
    )


def sync_fork_upstream(workspace_path: str) -> None:
    """Sync a fork with its upstream repository.

    Args:
        workspace_path: Path to the cloned fork.
    """
    logger.info("Syncing fork with upstream")
    result = run_with_timeout(
        ["git", "fetch", "upstream"],
        timeout=60,
        cwd=workspace_path,
    )
    if result.returncode != 0:
        # upstream remote might not exist — add it
        logger.debug("Upstream fetch failed, may need to add remote")


def create_branch(workspace_path: str, branch_name: str) -> None:
    """Create and checkout a new branch.

    Args:
        workspace_path: Path to the repository.
        branch_name: Name of the branch to create.
    """
    logger.info("Creating branch: %s", branch_name)
    result = run_with_timeout(
        ["git", "checkout", "-b", branch_name],
        timeout=10,
        cwd=workspace_path,
    )
    if result.returncode != 0:
        raise GitHubError(f"Failed to create branch: {result.stderr.strip()}")


def push_branch(workspace_path: str, branch_name: str) -> None:
    """Push a branch to the origin remote.

    Args:
        workspace_path: Path to the repository.
        branch_name: Name of the branch to push.
    """
    logger.info("Pushing branch: %s", branch_name)
    result = run_with_timeout(
        ["git", "push", "origin", branch_name],
        timeout=60,
        cwd=workspace_path,
    )
    if result.returncode != 0:
        raise GitHubError(f"Failed to push branch: {result.stderr.strip()}")


def get_diff_summary(workspace_path: str) -> str | None:
    """Get a summary of uncommitted or committed changes.

    Returns:
        Diff stat summary string, or None if no changes.
    """
    result = run_with_timeout(
        ["git", "diff", "--stat", "HEAD~1"],
        timeout=10,
        cwd=workspace_path,
    )
    if result.returncode != 0:
        # Try against working tree
        result = run_with_timeout(
            ["git", "diff", "--stat"],
            timeout=10,
            cwd=workspace_path,
        )
    output = result.stdout.strip()
    return output if output else None


def has_changes(workspace_path: str) -> bool:
    """Check if there are any uncommitted or committed changes since clone."""
    result = run_with_timeout(
        ["git", "diff", "--stat", "HEAD~1"],
        timeout=10,
        cwd=workspace_path,
    )
    if result.returncode == 0 and result.stdout.strip():
        return True

    # Check working tree
    result = run_with_timeout(
        ["git", "status", "--porcelain"],
        timeout=10,
        cwd=workspace_path,
    )
    return bool(result.stdout.strip())


def _get_gh_username() -> str:
    """Get the authenticated GitHub username."""
    output = run_gh(["api", "/user", "--jq", ".login"], timeout=30)
    return output.strip()
