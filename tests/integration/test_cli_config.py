"""Integration tests for the config CLI command."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from issue_resolver.cli import app, exit_codes

runner = CliRunner()


class TestConfigCommand:
    def test_help_output(self) -> None:
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output.lower()
        assert "show" in result.output.lower()

    def test_show_config(self) -> None:
        result = runner.invoke(app, ["config", "--show"])
        assert result.exit_code == exit_codes.OK
        assert "Effective Configuration" in result.output
        assert "search" in result.output
        assert "claude" in result.output

    def test_show_redacts_secrets(self) -> None:
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_secret123"}):
            result = runner.invoke(app, ["config", "--show"])
        assert result.exit_code == exit_codes.OK
        assert "ghp_secret123" not in result.output
        assert "GITHUB_TOKEN" in result.output

    def test_init_creates_file(self, tmp_path: Path) -> None:
        with patch("issue_resolver.cli.config_cmd.Path.cwd", return_value=tmp_path):
            result = runner.invoke(app, ["config", "--init"])
        assert result.exit_code == exit_codes.OK
        assert "created" in result.output.lower()
        assert (tmp_path / ".issue-resolver.yaml").exists()

    def test_init_refuses_overwrite(self, tmp_path: Path) -> None:
        (tmp_path / ".issue-resolver.yaml").write_text("dry_run: true")
        with patch("issue_resolver.cli.config_cmd.Path.cwd", return_value=tmp_path):
            result = runner.invoke(app, ["config", "--init"])
        assert result.exit_code == exit_codes.GENERAL_ERROR

    def test_default_no_flags(self) -> None:
        result = runner.invoke(app, ["config"])
        assert result.exit_code == exit_codes.OK
        assert "init" in result.output.lower()
