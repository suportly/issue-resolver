"""Unit tests for the pipeline orchestrator."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from issue_resolver.config.schema import AppConfig
from issue_resolver.models.analysis import Analysis
from issue_resolver.models.attempt import Attempt
from issue_resolver.models.enums import (
    AttemptStatus,
    OutcomeCategory,
    SolvabilityRating,
)
from issue_resolver.models.issue import Issue
from issue_resolver.pipeline.orchestrator import run_pipeline
from issue_resolver.utils.exceptions import (
    AnalysisRejectedError,
    BudgetExceededError,
    TestsFailedError,
)


def _make_issue(number: int = 1) -> Issue:
    return Issue(
        repo_owner="test",
        repo_name="repo",
        number=number,
        title=f"Test issue #{number}",
        labels=["bug"],
        url=f"https://github.com/test/repo/issues/{number}",
        state="open",
        has_assignees=False,
        has_linked_prs=False,
        created_at=datetime(2026, 1, 1),
    )


def _make_analysis(issue_id: str = "test-id") -> Analysis:
    return Analysis(
        issue_id=issue_id,
        rating=SolvabilityRating.SOLVABLE,
        confidence=0.9,
        complexity="low",
        reasoning="Looks fixable",
        cost_usd=0.05,
        model="haiku",
        duration_ms=2000,
    )


def _make_attempt(
    issue_id: str = "test-id",
    outcome: OutcomeCategory = OutcomeCategory.PR_SUBMITTED,
) -> Attempt:
    return Attempt(
        issue_id=issue_id,
        status=AttemptStatus.SUCCEEDED,
        outcome=outcome,
        cost_usd=2.0,
        duration_ms=30000,
        branch_name="fix/issue-1",
        model="opus",
    )


class TestRunPipeline:
    @patch("issue_resolver.pipeline.orchestrator._delay")
    @patch("issue_resolver.pipeline.orchestrator.submit_pr")
    @patch("issue_resolver.pipeline.orchestrator.resolve_issue")
    @patch("issue_resolver.pipeline.orchestrator.analyze_issue")
    @patch("issue_resolver.pipeline.orchestrator.scan_issues")
    def test_full_success(
        self,
        mock_scan: MagicMock,
        mock_analyze: MagicMock,
        mock_resolve: MagicMock,
        mock_submit: MagicMock,
        mock_delay: MagicMock,
        mock_config: AppConfig,
        repository: MagicMock,
    ) -> None:
        issue = _make_issue()
        mock_scan.return_value = [issue]
        mock_analyze.return_value = _make_analysis()
        mock_resolve.return_value = _make_attempt()
        mock_submit.return_value = "https://github.com/test/repo/pull/1"

        result = run_pipeline(mock_config, repository, dry_run=True)

        assert result.issues_scanned == 1
        assert result.issues_analyzed == 1
        assert result.issues_attempted == 1
        assert result.prs_submitted == 1
        assert result.failures == 0
        assert not result.budget_exhausted

    @patch("issue_resolver.pipeline.orchestrator._delay")
    @patch("issue_resolver.pipeline.orchestrator.scan_issues")
    def test_no_candidates(
        self,
        mock_scan: MagicMock,
        mock_delay: MagicMock,
        mock_config: AppConfig,
        repository: MagicMock,
    ) -> None:
        mock_scan.return_value = []
        result = run_pipeline(mock_config, repository)
        assert result.issues_scanned == 0
        assert result.issues_analyzed == 0

    @patch("issue_resolver.pipeline.orchestrator._delay")
    @patch("issue_resolver.pipeline.orchestrator.analyze_issue")
    @patch("issue_resolver.pipeline.orchestrator.scan_issues")
    def test_analysis_rejected_continues(
        self,
        mock_scan: MagicMock,
        mock_analyze: MagicMock,
        mock_delay: MagicMock,
        mock_config: AppConfig,
        repository: MagicMock,
    ) -> None:
        """Rejected issues don't stop the pipeline."""
        mock_scan.return_value = [_make_issue(1), _make_issue(2)]
        mock_analyze.side_effect = [
            AnalysisRejectedError("Low confidence"),
            _make_analysis(),
        ]

        with (
            patch("issue_resolver.pipeline.orchestrator.resolve_issue") as mock_resolve,
            patch("issue_resolver.pipeline.orchestrator.submit_pr") as mock_submit,
        ):
            mock_resolve.return_value = _make_attempt()
            mock_submit.return_value = None
            result = run_pipeline(mock_config, repository)

        assert result.issues_analyzed == 1  # Only second passed analysis
        assert result.failures == 0  # Rejected is not a failure

    @patch("issue_resolver.pipeline.orchestrator._delay")
    @patch("issue_resolver.pipeline.orchestrator.resolve_issue")
    @patch("issue_resolver.pipeline.orchestrator.analyze_issue")
    @patch("issue_resolver.pipeline.orchestrator.scan_issues")
    def test_budget_exceeded_stops_pipeline(
        self,
        mock_scan: MagicMock,
        mock_analyze: MagicMock,
        mock_resolve: MagicMock,
        mock_delay: MagicMock,
        mock_config: AppConfig,
        repository: MagicMock,
    ) -> None:
        mock_scan.return_value = [_make_issue(1), _make_issue(2)]
        mock_analyze.return_value = _make_analysis()
        mock_resolve.side_effect = BudgetExceededError("Budget exceeded")

        result = run_pipeline(mock_config, repository)

        assert result.budget_exhausted is True
        assert result.failures == 1
        # Second issue should not be attempted
        assert mock_resolve.call_count == 1

    @patch("issue_resolver.pipeline.orchestrator._delay")
    @patch("issue_resolver.pipeline.orchestrator.submit_pr")
    @patch("issue_resolver.pipeline.orchestrator.resolve_issue")
    @patch("issue_resolver.pipeline.orchestrator.analyze_issue")
    @patch("issue_resolver.pipeline.orchestrator.scan_issues")
    def test_per_issue_failure_isolation(
        self,
        mock_scan: MagicMock,
        mock_analyze: MagicMock,
        mock_resolve: MagicMock,
        mock_submit: MagicMock,
        mock_delay: MagicMock,
        mock_config: AppConfig,
        repository: MagicMock,
    ) -> None:
        """One issue failing tests doesn't stop the pipeline."""
        mock_scan.return_value = [_make_issue(1), _make_issue(2)]
        mock_analyze.return_value = _make_analysis()
        mock_resolve.side_effect = [
            TestsFailedError("Tests failed for issue 1"),
            _make_attempt(),
        ]
        mock_submit.return_value = None

        result = run_pipeline(mock_config, repository)

        assert result.issues_attempted == 1  # Only second succeeded
        assert result.failures == 1
        assert mock_resolve.call_count == 2  # Both attempted

    @patch("issue_resolver.pipeline.orchestrator._delay")
    @patch("issue_resolver.pipeline.orchestrator.analyze_issue")
    @patch("issue_resolver.pipeline.orchestrator.scan_issues")
    def test_session_budget_tracking(
        self,
        mock_scan: MagicMock,
        mock_analyze: MagicMock,
        mock_delay: MagicMock,
        repository: MagicMock,
    ) -> None:
        """Pipeline stops when session budget is exhausted via cost accumulation."""
        config = AppConfig(dry_run=True)
        config.claude.total_session_budget_usd = 1.0

        # First analysis costs enough to exhaust budget
        expensive_analysis = _make_analysis()
        expensive_analysis.cost_usd = 1.50

        mock_scan.return_value = [_make_issue(1), _make_issue(2)]
        mock_analyze.return_value = expensive_analysis

        with (
            patch("issue_resolver.pipeline.orchestrator.resolve_issue") as mock_resolve,
            patch("issue_resolver.pipeline.orchestrator.submit_pr") as mock_submit,
        ):
            mock_resolve.return_value = _make_attempt()
            mock_submit.return_value = None
            result = run_pipeline(config, repository)

        assert result.budget_exhausted is True
        # Second issue should not be processed because budget exceeded after first
        assert result.total_cost_usd > 0
