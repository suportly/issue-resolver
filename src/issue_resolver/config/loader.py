"""Configuration file discovery and loading."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

from issue_resolver.config.schema import AppConfig
from issue_resolver.utils.exceptions import ConfigError

logger = logging.getLogger(__name__)

CONFIG_FILE_NAMES = [
    ".issue-resolver.yaml",
    ".issue-resolver.yml",
]

XDG_CONFIG_PATH = Path.home() / ".config" / "issue-resolver" / "config.yaml"


def discover_config_file(explicit_path: str | None = None) -> Path | None:
    """Discover configuration file using the priority chain.

    Priority: explicit path > ISSUE_RESOLVER_CONFIG env > cwd > XDG default.
    """
    # 1. Explicit path from CLI flag
    if explicit_path:
        path = Path(explicit_path)
        if path.is_file():
            return path
        raise ConfigError(f"Config file not found: {explicit_path}")

    # 2. Environment variable
    env_path = os.environ.get("ISSUE_RESOLVER_CONFIG")
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return path
        raise ConfigError(f"Config file from ISSUE_RESOLVER_CONFIG not found: {env_path}")

    # 3. Current directory
    for name in CONFIG_FILE_NAMES:
        path = Path.cwd() / name
        if path.is_file():
            return path

    # 4. XDG default
    if XDG_CONFIG_PATH.is_file():
        return XDG_CONFIG_PATH

    # 5. No config file
    return None


def load_config(
    config_path: str | None = None,
    cli_overrides: dict | None = None,
) -> AppConfig:
    """Load configuration from file, env vars, and CLI overrides.

    Args:
        config_path: Explicit path to config file.
        cli_overrides: Dict of CLI flag overrides (non-None values only).

    Returns:
        Merged AppConfig instance.
    """
    file_path = discover_config_file(config_path)
    file_data: dict = {}

    if file_path:
        logger.debug("Loading config from: %s", file_path)
        with open(file_path) as f:
            file_data = yaml.safe_load(f) or {}

    # Build config: file data as base, env vars auto-loaded by pydantic-settings
    config = AppConfig(**file_data)

    # Apply CLI overrides (highest priority)
    if cli_overrides:
        overrides = {k: v for k, v in cli_overrides.items() if v is not None}
        if overrides:
            config = config.model_copy(update=overrides)

    return config
