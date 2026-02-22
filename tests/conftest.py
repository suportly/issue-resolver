"""Shared test fixtures and mock factories."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import sqlite_utils

from issue_resolver.config.schema import AppConfig
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

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_db(tmp_path: Path) -> sqlite_utils.Database:
    """Create a temporary SQLite database with full schema."""
    db_path = str(tmp_path / "test.db")
    return get_database(db_path)


@pytest.fixture
def repository(tmp_db: sqlite_utils.Database) -> Repository:
    """Repository backed by a temporary database."""
    return Repository(tmp_db)


@pytest.fixture
def mock_config() -> AppConfig:
    """AppConfig with test-friendly defaults."""
    return AppConfig(
        dry_run=True,
        auto_pr=False,
        max_issues_per_run=3,
    )


@pytest.fixture
def sample_issue() -> Issue:
    """A sample GitHub issue for testing."""
    return Issue(
        repo_owner="encode",
        repo_name="django-rest-framework",
        number=9501,
        title="Fix regression in serializer validation for nested fields",
        body=(
            "When using nested serializers with `many=True`,"
            " validation error messages are incorrectly formatted."
        ),
        labels=["bug", "good first issue"],
        url="https://github.com/encode/django-rest-framework/issues/9501",
        state="open",
        has_assignees=False,
        has_linked_prs=False,
        language="Python",
        repo_stars=28100,
        created_at=datetime(2026, 2, 19, 10, 30, 0),
    )


@pytest.fixture
def sample_analysis(sample_issue: Issue) -> Analysis:
    """A sample solvability analysis for testing."""
    return Analysis(
        issue_id=sample_issue.id,
        rating=SolvabilityRating.SOLVABLE,
        confidence=0.85,
        complexity="low",
        reasoning="Clear bug with specific error message and test case provided.",
        cost_usd=0.05,
        model="haiku",
        duration_ms=3000,
    )


@pytest.fixture
def sample_attempt(sample_issue: Issue) -> Attempt:
    """A sample resolution attempt for testing."""
    return Attempt(
        issue_id=sample_issue.id,
        status=AttemptStatus.SUCCEEDED,
        outcome=OutcomeCategory.PR_SUBMITTED,
        cost_usd=2.34,
        duration_ms=45000,
        workspace_path="/tmp/issue-resolver-workspaces/abc123",
        pr_url="https://github.com/encode/django-rest-framework/pull/9999",
        pr_number=9999,
        branch_name="fix/issue-9501-serializer-validation",
        num_turns=8,
        model="opus",
        diff_summary="2 files changed, 15 insertions, 3 deletions",
    )


@pytest.fixture
def fixture_dir() -> Path:
    """Path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def sample_issue_json(fixture_dir: Path) -> dict:
    """Load sample issue JSON fixture."""
    with open(fixture_dir / "issues" / "sample_issue.json") as f:
        return json.load(f)


@pytest.fixture
def claude_success_json(fixture_dir: Path) -> dict:
    """Load Claude success response fixture."""
    with open(fixture_dir / "claude_responses" / "success.json") as f:
        return json.load(f)


@pytest.fixture
def claude_analysis_json(fixture_dir: Path) -> dict:
    """Load Claude analysis response fixture."""
    with open(fixture_dir / "claude_responses" / "analysis_success.json") as f:
        return json.load(f)


def make_mock_subprocess(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> MagicMock:
    """Create a mock subprocess.CompletedProcess."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.stderr = stderr
    mock.returncode = returncode
    return mock
