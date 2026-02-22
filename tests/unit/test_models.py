"""Unit tests for Pydantic models."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from issue_resolver.models.analysis import Analysis
from issue_resolver.models.attempt import Attempt
from issue_resolver.models.enums import (
    AttemptStatus,
    OutcomeCategory,
    SolvabilityRating,
)
from issue_resolver.models.issue import Issue


class TestIssueModel:
    def test_create_minimal(self) -> None:
        issue = Issue(
            repo_owner="owner",
            repo_name="repo",
            number=1,
            title="Bug",
            url="https://github.com/owner/repo/issues/1",
            created_at=datetime(2026, 1, 1),
        )
        assert issue.repo_owner == "owner"
        assert issue.number == 1
        assert issue.state == "open"
        assert issue.has_assignees is False
        assert issue.labels == []

    def test_full_repo_property(self) -> None:
        issue = Issue(
            repo_owner="org",
            repo_name="project",
            number=42,
            title="Test",
            url="https://github.com/org/project/issues/42",
            created_at=datetime(2026, 1, 1),
        )
        assert issue.full_repo == "org/project"

    def test_id_auto_generated(self) -> None:
        issue = Issue(
            repo_owner="o",
            repo_name="r",
            number=1,
            title="T",
            url="url",
            created_at=datetime(2026, 1, 1),
        )
        assert issue.id is not None
        assert len(issue.id) > 0

    def test_optional_fields_default(self) -> None:
        issue = Issue(
            repo_owner="o",
            repo_name="r",
            number=1,
            title="T",
            url="url",
            created_at=datetime(2026, 1, 1),
        )
        assert issue.body is None
        assert issue.language is None
        assert issue.repo_stars is None


class TestAnalysisModel:
    def test_create(self) -> None:
        analysis = Analysis(
            issue_id="test-id",
            rating=SolvabilityRating.SOLVABLE,
            confidence=0.85,
            reasoning="Clear bug",
        )
        assert analysis.rating == SolvabilityRating.SOLVABLE
        assert analysis.confidence == 0.85

    def test_confidence_validation_too_high(self) -> None:
        with pytest.raises(ValidationError):
            Analysis(
                issue_id="test-id",
                rating=SolvabilityRating.SOLVABLE,
                confidence=1.5,
                reasoning="Invalid",
            )

    def test_confidence_validation_negative(self) -> None:
        with pytest.raises(ValidationError):
            Analysis(
                issue_id="test-id",
                rating=SolvabilityRating.SOLVABLE,
                confidence=-0.1,
                reasoning="Invalid",
            )

    def test_confidence_boundary_values(self) -> None:
        a0 = Analysis(
            issue_id="id",
            rating=SolvabilityRating.UNSOLVABLE,
            confidence=0.0,
            reasoning="r",
        )
        assert a0.confidence == 0.0
        a1 = Analysis(
            issue_id="id",
            rating=SolvabilityRating.SOLVABLE,
            confidence=1.0,
            reasoning="r",
        )
        assert a1.confidence == 1.0

    def test_passes_threshold_solvable_high_confidence(self) -> None:
        analysis = Analysis(
            issue_id="id",
            rating=SolvabilityRating.SOLVABLE,
            confidence=0.9,
            reasoning="r",
        )
        assert analysis.passes_threshold is True

    def test_passes_threshold_likely_solvable(self) -> None:
        analysis = Analysis(
            issue_id="id",
            rating=SolvabilityRating.LIKELY_SOLVABLE,
            confidence=0.75,
            reasoning="r",
        )
        assert analysis.passes_threshold is True

    def test_fails_threshold_low_confidence(self) -> None:
        analysis = Analysis(
            issue_id="id",
            rating=SolvabilityRating.SOLVABLE,
            confidence=0.5,
            reasoning="r",
        )
        assert analysis.passes_threshold is False

    def test_fails_threshold_unsolvable(self) -> None:
        analysis = Analysis(
            issue_id="id",
            rating=SolvabilityRating.UNSOLVABLE,
            confidence=0.9,
            reasoning="r",
        )
        assert analysis.passes_threshold is False

    def test_fails_threshold_needs_context(self) -> None:
        analysis = Analysis(
            issue_id="id",
            rating=SolvabilityRating.NEEDS_CONTEXT,
            confidence=0.9,
            reasoning="r",
        )
        assert analysis.passes_threshold is False


class TestAttemptModel:
    def test_create_minimal(self) -> None:
        attempt = Attempt(issue_id="test-id")
        assert attempt.status == AttemptStatus.PENDING
        assert attempt.outcome is None
        assert attempt.cost_usd is None

    def test_with_outcome(self) -> None:
        attempt = Attempt(
            issue_id="test-id",
            status=AttemptStatus.SUCCEEDED,
            outcome=OutcomeCategory.PR_SUBMITTED,
            cost_usd=2.50,
            duration_ms=30000,
        )
        assert attempt.status == AttemptStatus.SUCCEEDED
        assert attempt.outcome == OutcomeCategory.PR_SUBMITTED

    def test_timestamps_auto_generated(self) -> None:
        attempt = Attempt(issue_id="test-id")
        assert attempt.created_at is not None
        assert attempt.updated_at is not None


class TestEnums:
    def test_solvability_values(self) -> None:
        assert SolvabilityRating.SOLVABLE.value == "solvable"
        assert SolvabilityRating.LIKELY_SOLVABLE.value == "likely_solvable"
        assert SolvabilityRating.UNSOLVABLE.value == "unsolvable"
        assert SolvabilityRating.NEEDS_CONTEXT.value == "needs_context"

    def test_attempt_status_values(self) -> None:
        assert AttemptStatus.PENDING.value == "pending"
        assert AttemptStatus.IN_PROGRESS.value == "in_progress"
        assert AttemptStatus.SUCCEEDED.value == "succeeded"
        assert AttemptStatus.FAILED.value == "failed"

    def test_outcome_category_values(self) -> None:
        assert OutcomeCategory.PR_SUBMITTED.value == "pr_submitted"
        assert OutcomeCategory.TESTS_FAILED.value == "tests_failed"
        assert OutcomeCategory.EMPTY_DIFF.value == "empty_diff"
        assert OutcomeCategory.BUDGET_EXCEEDED.value == "budget_exceeded"
