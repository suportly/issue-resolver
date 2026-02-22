"""Integration tests for the scan CLI command."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from issue_resolver.cli import app, exit_codes
from issue_resolver.models.issue import Issue

runner = CliRunner()


class TestScanCommand:
    def test_help_output(self) -> None:
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "limit" in result.output.lower()
        assert "language" in result.output.lower()

    @patch("issue_resolver.cli.scan.check_gh_installed")
    @patch("issue_resolver.cli.scan.check_gh_authenticated")
    @patch("issue_resolver.cli.scan.scan_issues")
    @patch("issue_resolver.cli.scan.get_database")
    def test_scan_with_results(
        self,
        mock_db: MagicMock,
        mock_scan: MagicMock,
        mock_gh_auth: MagicMock,
        mock_gh_install: MagicMock,
    ) -> None:
        mock_db.return_value = MagicMock()
        mock_scan.return_value = [
            Issue(
                repo_owner="test",
                repo_name="repo",
                number=1,
                title="Test issue",
                labels=["bug"],
                url="https://github.com/test/repo/issues/1",
                state="open",
                has_assignees=False,
                has_linked_prs=False,
                repo_stars=500,
                created_at=datetime(2026, 2, 1, tzinfo=UTC),
            ),
        ]

        result = runner.invoke(app, ["scan", "--limit", "5"])
        assert result.exit_code == exit_codes.OK
        assert "test/repo" in result.output
        assert "#1" in result.output

    @patch("issue_resolver.cli.scan.check_gh_installed")
    @patch("issue_resolver.cli.scan.check_gh_authenticated")
    @patch("issue_resolver.cli.scan.scan_issues")
    @patch("issue_resolver.cli.scan.get_database")
    def test_scan_no_results(
        self,
        mock_db: MagicMock,
        mock_scan: MagicMock,
        mock_gh_auth: MagicMock,
        mock_gh_install: MagicMock,
    ) -> None:
        mock_db.return_value = MagicMock()
        mock_scan.return_value = []

        result = runner.invoke(app, ["scan"])
        assert result.exit_code == exit_codes.OK
        assert "No matching issues" in result.output

    @patch("issue_resolver.cli.scan.check_gh_installed")
    def test_prerequisite_failure(self, mock_gh_install: MagicMock) -> None:
        from issue_resolver.utils.exceptions import PrerequisiteError

        mock_gh_install.side_effect = PrerequisiteError("gh not installed")

        result = runner.invoke(app, ["scan"])
        assert result.exit_code == exit_codes.PREREQUISITE_FAILED

    @patch("issue_resolver.cli.scan.check_gh_installed")
    @patch("issue_resolver.cli.scan.check_gh_authenticated")
    @patch("issue_resolver.cli.scan.scan_issues")
    @patch("issue_resolver.cli.scan.get_database")
    def test_dry_run_prefix(
        self,
        mock_db: MagicMock,
        mock_scan: MagicMock,
        mock_gh_auth: MagicMock,
        mock_gh_install: MagicMock,
    ) -> None:
        mock_db.return_value = MagicMock()
        mock_scan.return_value = []

        result = runner.invoke(app, ["--dry-run", "scan"])
        assert result.exit_code == exit_codes.OK
        assert "DRY RUN" in result.output
