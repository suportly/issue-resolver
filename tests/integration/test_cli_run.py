"""Integration tests for the run CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from issue_resolver.cli import app, exit_codes
from issue_resolver.pipeline.orchestrator import PipelineResult

runner = CliRunner()


class TestRunCommand:
    def test_help_output(self) -> None:
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        # Strip ANSI codes before checking (Rich adds escape sequences)
        import re

        clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output).lower()
        assert "max-issues" in clean

    @patch("issue_resolver.cli.run.check_gh_installed")
    @patch("issue_resolver.cli.run.check_gh_authenticated")
    @patch("issue_resolver.cli.run.check_claude_installed")
    @patch("issue_resolver.cli.run.get_database")
    @patch("issue_resolver.cli.run.run_pipeline")
    def test_dry_run_pipeline(
        self,
        mock_pipeline: MagicMock,
        mock_db: MagicMock,
        mock_claude: MagicMock,
        mock_gh_auth: MagicMock,
        mock_gh_install: MagicMock,
    ) -> None:
        mock_db.return_value = MagicMock()
        mock_pipeline.return_value = PipelineResult(
            issues_scanned=3,
            issues_analyzed=2,
            issues_attempted=1,
            prs_submitted=1,
            failures=0,
            total_cost_usd=0.0,
        )

        result = runner.invoke(app, ["--dry-run", "run", "--max-issues", "3"])
        assert result.exit_code == exit_codes.OK
        assert "Pipeline complete" in result.output
        assert "Scanned" in result.output

    @patch("issue_resolver.cli.run.check_gh_installed")
    @patch("issue_resolver.cli.run.check_gh_authenticated")
    @patch("issue_resolver.cli.run.check_claude_installed")
    @patch("issue_resolver.cli.run.get_database")
    @patch("issue_resolver.cli.run.run_pipeline")
    def test_budget_exceeded_exit_code(
        self,
        mock_pipeline: MagicMock,
        mock_db: MagicMock,
        mock_claude: MagicMock,
        mock_gh_auth: MagicMock,
        mock_gh_install: MagicMock,
    ) -> None:
        mock_db.return_value = MagicMock()
        mock_pipeline.return_value = PipelineResult(
            issues_scanned=5,
            issues_analyzed=3,
            issues_attempted=2,
            prs_submitted=1,
            failures=1,
            total_cost_usd=25.0,
            budget_exhausted=True,
        )

        result = runner.invoke(app, ["run"])
        assert result.exit_code == exit_codes.BUDGET_EXCEEDED
        assert "Budget exhausted" in result.output

    @patch("issue_resolver.cli.run.check_gh_installed")
    def test_prerequisite_failure(self, mock_gh: MagicMock) -> None:
        from issue_resolver.utils.exceptions import PrerequisiteError

        mock_gh.side_effect = PrerequisiteError("gh not installed")

        result = runner.invoke(app, ["run"])
        assert result.exit_code == exit_codes.PREREQUISITE_FAILED

    @patch("issue_resolver.cli.run.check_gh_installed")
    @patch("issue_resolver.cli.run.check_gh_authenticated")
    @patch("issue_resolver.cli.run.check_claude_installed")
    @patch("issue_resolver.cli.run.get_database")
    @patch("issue_resolver.cli.run.run_pipeline")
    def test_summary_output(
        self,
        mock_pipeline: MagicMock,
        mock_db: MagicMock,
        mock_claude: MagicMock,
        mock_gh_auth: MagicMock,
        mock_gh_install: MagicMock,
    ) -> None:
        mock_db.return_value = MagicMock()
        mock_pipeline.return_value = PipelineResult(
            issues_scanned=10,
            issues_analyzed=7,
            issues_attempted=5,
            prs_submitted=3,
            failures=2,
            total_cost_usd=12.50,
        )

        result = runner.invoke(app, ["--dry-run", "run"])
        assert result.exit_code == exit_codes.OK
        assert "10" in result.output  # scanned
        assert "7" in result.output  # analyzed
        assert "5" in result.output  # attempted
        assert "3" in result.output  # PRs
