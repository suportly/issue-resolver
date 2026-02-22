"""Integration tests for the status CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from issue_resolver.cli import app, exit_codes

runner = CliRunner()


class TestStatusCommand:
    def test_help_output(self) -> None:
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0
        assert "summary" in result.output.lower()

    @patch("issue_resolver.cli.status.get_database")
    @patch("issue_resolver.cli.status.Repository")
    def test_empty_database(
        self,
        mock_repo_cls: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        mock_db.return_value = MagicMock()
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_summary_stats.return_value = {
            "issues_discovered": 0,
            "analyses_run": 0,
            "attempts_total": 0,
            "attempts_succeeded": 0,
            "attempts_failed": 0,
            "prs_submitted": 0,
            "success_rate": 0.0,
            "total_cost_usd": 0.0,
            "avg_cost_usd": 0.0,
        }

        result = runner.invoke(app, ["status"])
        assert result.exit_code == exit_codes.OK
        assert "No history" in result.output

    @patch("issue_resolver.cli.status.get_database")
    @patch("issue_resolver.cli.status.Repository")
    def test_with_data(
        self,
        mock_repo_cls: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        mock_db.return_value = MagicMock()
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_summary_stats.return_value = {
            "issues_discovered": 25,
            "analyses_run": 20,
            "attempts_total": 10,
            "attempts_succeeded": 7,
            "attempts_failed": 3,
            "prs_submitted": 5,
            "success_rate": 70.0,
            "total_cost_usd": 15.50,
            "avg_cost_usd": 1.55,
        }

        result = runner.invoke(app, ["status"])
        assert result.exit_code == exit_codes.OK
        assert "25" in result.output
        assert "70%" in result.output

    @patch("issue_resolver.cli.status.get_database")
    @patch("issue_resolver.cli.status.Repository")
    def test_summary_with_funnel(
        self,
        mock_repo_cls: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        mock_db.return_value = MagicMock()
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo
        mock_repo.get_summary_stats.return_value = {
            "issues_discovered": 50,
            "analyses_run": 40,
            "attempts_total": 20,
            "attempts_succeeded": 15,
            "attempts_failed": 5,
            "prs_submitted": 10,
            "success_rate": 75.0,
            "total_cost_usd": 30.0,
            "avg_cost_usd": 1.5,
        }
        mock_repo.get_resolution_funnel.return_value = {
            "discovered": 50,
            "analyzed": 40,
            "attempted": 20,
            "non_empty_diff": 18,
            "tests_pass": 15,
            "pr_submitted": 10,
        }
        mock_repo.get_per_language_stats.return_value = [
            {
                "language": "python",
                "attempts": 15,
                "successes": 12,
                "success_rate": 80.0,
                "total_cost": 20.0,
                "avg_duration_ms": 30000,
            },
            {
                "language": "javascript",
                "attempts": 5,
                "successes": 3,
                "success_rate": 60.0,
                "total_cost": 10.0,
                "avg_duration_ms": 25000,
            },
        ]

        result = runner.invoke(app, ["status", "--summary"])
        assert result.exit_code == exit_codes.OK
        assert "Resolution Funnel" in result.output
        assert "Discovered" in result.output
        assert "python" in result.output
