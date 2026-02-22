"""Integration tests for the resolve CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from issue_resolver.cli import app, exit_codes

runner = CliRunner()


class TestResolveCommand:
    def test_help_output(self) -> None:
        result = runner.invoke(app, ["resolve", "--help"])
        assert result.exit_code == 0
        assert "issue-url" in result.output.lower() or "ISSUE_URL" in result.output

    @patch("issue_resolver.cli.resolve.check_gh_installed")
    @patch("issue_resolver.cli.resolve.check_gh_authenticated")
    @patch("issue_resolver.cli.resolve.check_claude_installed")
    @patch("issue_resolver.cli.resolve.run_gh_json")
    @patch("issue_resolver.cli.resolve.analyze_issue")
    def test_dry_run_no_side_effects(
        self,
        mock_analyze: MagicMock,
        mock_gh_json: MagicMock,
        mock_claude_check: MagicMock,
        mock_gh_auth: MagicMock,
        mock_gh_install: MagicMock,
        sample_issue,
        sample_analysis,
    ) -> None:
        """Dry-run mode should analyze but not fork/clone/resolve."""
        mock_gh_json.return_value = {
            "title": "Test issue",
            "body": "Test body",
            "labels": [{"name": "bug"}],
            "state": "OPEN",
            "assignees": [],
            "url": "https://github.com/test/repo/issues/1",
        }
        mock_analyze.return_value = sample_analysis

        result = runner.invoke(
            app,
            ["--dry-run", "resolve", "https://github.com/test/repo/issues/1"],
        )

        assert result.exit_code == exit_codes.OK
        assert "DRY RUN" in result.output

    @patch("issue_resolver.cli.resolve._check_prerequisites")
    def test_invalid_url(self, mock_prereq: MagicMock) -> None:
        result = runner.invoke(app, ["resolve", "not-a-valid-url"])
        assert result.exit_code == exit_codes.GENERAL_ERROR

    @patch("issue_resolver.cli.resolve._check_prerequisites", side_effect=Exception("gh not found"))
    def test_prerequisite_failure(self, mock_prereq: MagicMock) -> None:
        """Missing prerequisites should exit with PREREQUISITE_FAILED."""
        from issue_resolver.utils.exceptions import PrerequisiteError

        mock_prereq.side_effect = PrerequisiteError("gh not installed")
        result = runner.invoke(
            app,
            ["resolve", "https://github.com/test/repo/issues/1"],
        )
        assert result.exit_code == exit_codes.PREREQUISITE_FAILED

    @patch("issue_resolver.cli.resolve.check_gh_installed")
    @patch("issue_resolver.cli.resolve.check_gh_authenticated")
    @patch("issue_resolver.cli.resolve.check_claude_installed")
    @patch("issue_resolver.cli.resolve.run_gh_json")
    @patch("issue_resolver.cli.resolve.analyze_issue")
    def test_analysis_rejected(
        self,
        mock_analyze: MagicMock,
        mock_gh_json: MagicMock,
        mock_claude_check: MagicMock,
        mock_gh_auth: MagicMock,
        mock_gh_install: MagicMock,
    ) -> None:
        """Issues below confidence threshold should exit with ANALYSIS_REJECTED."""
        from issue_resolver.utils.exceptions import AnalysisRejectedError

        mock_gh_json.return_value = {
            "title": "Vague issue",
            "body": "Something is broken",
            "labels": [],
            "state": "OPEN",
            "assignees": [],
            "url": "https://github.com/test/repo/issues/2",
        }
        mock_analyze.side_effect = AnalysisRejectedError("Confidence too low")

        result = runner.invoke(
            app,
            ["resolve", "https://github.com/test/repo/issues/2"],
        )
        assert result.exit_code == exit_codes.ANALYSIS_REJECTED
