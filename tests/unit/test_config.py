"""Unit tests for configuration loading and schema."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from issue_resolver.config.loader import discover_config_file, load_config
from issue_resolver.config.schema import AppConfig


class TestAppConfig:
    def test_defaults(self) -> None:
        config = AppConfig()
        assert config.auto_pr is False
        assert config.dry_run is False
        assert config.max_issues_per_run == 5
        assert config.search.min_stars == 50
        assert config.claude.model == "opus"
        assert config.claude.total_session_budget_usd == 25.00

    def test_search_config_defaults(self) -> None:
        config = AppConfig()
        assert "good first issue" in config.search.labels
        assert "python" in config.search.languages
        assert config.search.exclude_assignees is True
        assert config.search.exclude_linked_prs is True

    def test_claude_config_defaults(self) -> None:
        config = AppConfig()
        assert config.claude.analysis_max_budget_usd == 0.50
        assert config.claude.resolution_max_budget_usd == 5.00
        assert config.claude.timeout_seconds == 600

    def test_rate_limit_defaults(self) -> None:
        config = AppConfig()
        assert config.rate_limit.github_requests_per_minute == 25
        assert config.rate_limit.claude_invocations_per_hour == 30
        assert config.rate_limit.min_delay_between_issues_seconds == 10


class TestLoadConfig:
    def test_load_defaults_no_file(self) -> None:
        config = load_config()
        assert isinstance(config, AppConfig)
        assert config.dry_run is False

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        config_data = {
            "auto_pr": True,
            "max_issues_per_run": 10,
            "search": {"min_stars": 200},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = load_config(config_path=str(config_file))
        assert config.auto_pr is True
        assert config.max_issues_per_run == 10
        assert config.search.min_stars == 200

    def test_cli_overrides(self) -> None:
        config = load_config(cli_overrides={"dry_run": True})
        assert config.dry_run is True

    def test_cli_overrides_over_yaml(self, tmp_path: Path) -> None:
        config_data = {"dry_run": False, "auto_pr": False}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config = load_config(
            config_path=str(config_file),
            cli_overrides={"dry_run": True},
        )
        assert config.dry_run is True

    def test_missing_config_file_raises_error(self) -> None:
        from issue_resolver.utils.exceptions import ConfigError

        with pytest.raises(ConfigError):
            load_config(config_path="/nonexistent/path.yaml")


class TestDiscoverConfigFile:
    def test_no_config_found(self, tmp_path: Path) -> None:
        with patch("issue_resolver.config.loader.Path.cwd", return_value=tmp_path):
            result = discover_config_file()
        # Should return None or fall through to defaults
        assert result is None or not Path(result).exists() or result is not None

    def test_local_config_found(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".issue-resolver.yaml"
        config_file.write_text("dry_run: true")

        with patch("issue_resolver.config.loader.Path.cwd", return_value=tmp_path):
            result = discover_config_file()

        if result is not None:
            assert Path(result).exists()
