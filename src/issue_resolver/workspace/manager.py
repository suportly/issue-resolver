"""Temporary workspace lifecycle management."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from issue_resolver.utils.exceptions import WorkspaceError

logger = logging.getLogger(__name__)


def create_workspace(base_dir: str, repo_owner: str, repo_name: str) -> str:
    """Create a temporary workspace directory for cloning a repository.

    Args:
        base_dir: Base directory for all workspaces.
        repo_owner: Repository owner.
        repo_name: Repository name.

    Returns:
        Path to the created workspace directory.

    Raises:
        WorkspaceError: If workspace creation fails.
    """
    workspace_id = uuid.uuid4().hex[:12]
    workspace_name = f"{repo_owner}-{repo_name}-{workspace_id}"
    workspace_path = Path(base_dir) / workspace_name

    try:
        workspace_path.mkdir(parents=True, exist_ok=True)
        logger.info("Created workspace: %s", workspace_path)
        return str(workspace_path)
    except OSError as e:
        raise WorkspaceError(f"Failed to create workspace: {e}") from e


def cleanup_workspace(workspace_path: str, force: bool = False) -> None:
    """Remove a workspace directory.

    Args:
        workspace_path: Path to the workspace to clean up.
        force: If True, remove even if it doesn't look like a workspace.
    """
    path = Path(workspace_path)
    if not path.exists():
        return

    if not force and not path.is_dir():
        logger.warning("Not a directory, skipping cleanup: %s", workspace_path)
        return

    try:
        shutil.rmtree(path)
        logger.info("Cleaned up workspace: %s", workspace_path)
    except OSError as e:
        logger.warning("Failed to clean up workspace %s: %s", workspace_path, e)


def list_workspaces(base_dir: str) -> list[str]:
    """List all workspace directories.

    Args:
        base_dir: Base directory containing workspaces.

    Returns:
        List of workspace directory paths.
    """
    base = Path(base_dir)
    if not base.exists():
        return []
    return sorted(str(p) for p in base.iterdir() if p.is_dir())
