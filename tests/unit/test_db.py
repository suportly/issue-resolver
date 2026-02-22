"""Unit tests for database engine and repository."""

from __future__ import annotations

from pathlib import Path

import sqlite_utils

from issue_resolver.db.engine import get_database
from issue_resolver.db.repository import Repository
from issue_resolver.models.analysis import Analysis
from issue_resolver.models.attempt import Attempt
from issue_resolver.models.enums import (
    AttemptStatus,
    OutcomeCategory,
    SolvabilityRating,
)
from issue_resolver.models.issue import Issue


class TestEngine:
    def test_creates_database(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = get_database(db_path)
        assert isinstance(db, sqlite_utils.Database)

    def test_creates_tables(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = get_database(db_path)
        assert "issues" in db.table_names()
        assert "analyses" in db.table_names()
        assert "attempts" in db.table_names()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "nested" / "dir" / "test.db")
        get_database(db_path)
        assert Path(db_path).exists()

    def test_idempotent_initialization(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db1 = get_database(db_path)
        db1.conn.close()
        db2 = get_database(db_path)
        assert "issues" in db2.table_names()


class TestRepository:
    def test_upsert_issue(self, repository: Repository, sample_issue: Issue) -> None:
        repository.upsert_issue(sample_issue)
        result = repository.get_issue_by_repo(
            sample_issue.repo_owner, sample_issue.repo_name, sample_issue.number
        )
        assert result is not None
        assert result.title == sample_issue.title

    def test_upsert_issue_idempotent(self, repository: Repository, sample_issue: Issue) -> None:
        repository.upsert_issue(sample_issue)
        repository.upsert_issue(sample_issue)  # Should not raise
        assert repository.issue_exists(
            sample_issue.repo_owner, sample_issue.repo_name, sample_issue.number
        )

    def test_issue_exists(self, repository: Repository, sample_issue: Issue) -> None:
        assert not repository.issue_exists("owner", "repo", 999)
        repository.upsert_issue(sample_issue)
        assert repository.issue_exists(
            sample_issue.repo_owner, sample_issue.repo_name, sample_issue.number
        )

    def test_insert_analysis(
        self, repository: Repository, sample_issue: Issue, sample_analysis: Analysis
    ) -> None:
        repository.upsert_issue(sample_issue)
        repository.insert_analysis(sample_analysis)
        result = repository.get_latest_analysis(sample_issue.id)
        assert result is not None
        assert result.confidence == sample_analysis.confidence

    def test_insert_attempt(
        self, repository: Repository, sample_issue: Issue, sample_attempt: Attempt
    ) -> None:
        repository.upsert_issue(sample_issue)
        repository.insert_attempt(sample_attempt)
        attempts = repository.get_attempts_for_issue(sample_issue.id)
        assert len(attempts) == 1
        assert attempts[0].cost_usd == sample_attempt.cost_usd

    def test_update_attempt(self, repository: Repository, sample_issue: Issue) -> None:
        repository.upsert_issue(sample_issue)
        attempt = Attempt(issue_id=sample_issue.id, status=AttemptStatus.PENDING)
        repository.insert_attempt(attempt)

        attempt.status = AttemptStatus.SUCCEEDED
        attempt.cost_usd = 3.00
        repository.update_attempt(attempt)

        attempts = repository.get_attempts_for_issue(sample_issue.id)
        assert attempts[0].status == AttemptStatus.SUCCEEDED
        assert attempts[0].cost_usd == 3.00

    def test_has_attempt(self, repository: Repository, sample_issue: Issue) -> None:
        repository.upsert_issue(sample_issue)
        assert not repository.has_attempt(sample_issue.id)

        attempt = Attempt(issue_id=sample_issue.id)
        repository.insert_attempt(attempt)
        assert repository.has_attempt(sample_issue.id)

    def test_count_attempts_by_status(self, repository: Repository, sample_issue: Issue) -> None:
        repository.upsert_issue(sample_issue)
        for status in [AttemptStatus.SUCCEEDED, AttemptStatus.SUCCEEDED, AttemptStatus.FAILED]:
            attempt = Attempt(issue_id=sample_issue.id, status=status)
            repository.insert_attempt(attempt)

        counts = repository.count_attempts_by_status()
        assert counts.get("succeeded") == 2
        assert counts.get("failed") == 1

    def test_get_total_cost(self, repository: Repository, sample_issue: Issue) -> None:
        repository.upsert_issue(sample_issue)
        for cost in [1.50, 2.50]:
            attempt = Attempt(issue_id=sample_issue.id, cost_usd=cost)
            repository.insert_attempt(attempt)

        assert repository.get_total_cost() == 4.00

    def test_get_summary_stats(self, repository: Repository, sample_issue: Issue) -> None:
        repository.upsert_issue(sample_issue)
        repository.insert_attempt(
            Attempt(
                issue_id=sample_issue.id,
                status=AttemptStatus.SUCCEEDED,
                outcome=OutcomeCategory.PR_SUBMITTED,
                cost_usd=2.0,
            )
        )

        stats = repository.get_summary_stats()
        assert stats["issues_discovered"] == 1
        assert stats["attempts_total"] == 1
        assert stats["prs_submitted"] == 1

    def test_get_summary_stats_empty_db(self, repository: Repository) -> None:
        stats = repository.get_summary_stats()
        assert stats["issues_discovered"] == 0
        assert stats["success_rate"] == 0.0

    def test_get_resolution_funnel(self, repository: Repository, sample_issue: Issue) -> None:
        repository.upsert_issue(sample_issue)
        repository.insert_analysis(
            Analysis(
                issue_id=sample_issue.id,
                rating=SolvabilityRating.SOLVABLE,
                confidence=0.9,
                reasoning="test",
            )
        )
        repository.insert_attempt(
            Attempt(
                issue_id=sample_issue.id,
                status=AttemptStatus.SUCCEEDED,
                outcome=OutcomeCategory.PR_SUBMITTED,
                cost_usd=1.0,
            )
        )

        funnel = repository.get_resolution_funnel()
        assert funnel["discovered"] == 1
        assert funnel["analyzed"] == 1
        assert funnel["attempted"] == 1
        assert funnel["pr_submitted"] == 1

    def test_get_unattempted_issues(self, repository: Repository, sample_issue: Issue) -> None:
        repository.upsert_issue(sample_issue)
        unattempted = repository.get_unattempted_issues()
        assert len(unattempted) == 1

        repository.insert_attempt(Attempt(issue_id=sample_issue.id))
        unattempted = repository.get_unattempted_issues()
        assert len(unattempted) == 0
