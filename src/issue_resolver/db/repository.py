"""CRUD operations for issues, analyses, and attempts."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import sqlite_utils

from issue_resolver.models.analysis import Analysis
from issue_resolver.models.attempt import Attempt
from issue_resolver.models.issue import Issue

logger = logging.getLogger(__name__)


class Repository:
    """Database repository for issue resolver entities."""

    def __init__(self, db: sqlite_utils.Database) -> None:
        self.db = db

    # ── Issues ──

    def upsert_issue(self, issue: Issue) -> None:
        """Insert or update an issue (idempotent by repo_owner/repo_name/number)."""
        row = issue.model_dump()
        row["labels"] = json.dumps(row["labels"])
        row["created_at"] = row["created_at"].isoformat()
        row["discovered_at"] = row["discovered_at"].isoformat()
        row["has_assignees"] = int(row["has_assignees"])
        row["has_linked_prs"] = int(row["has_linked_prs"])
        self.db["issues"].insert(row, replace=True)

    def get_issue_by_repo(self, repo_owner: str, repo_name: str, number: int) -> Issue | None:
        """Get an issue by its unique repo + number combination."""
        rows = list(
            self.db["issues"].rows_where(
                "repo_owner = ? AND repo_name = ? AND number = ?",
                [repo_owner, repo_name, number],
            )
        )
        if not rows:
            return None
        return _row_to_issue(rows[0])

    def issue_exists(self, repo_owner: str, repo_name: str, number: int) -> bool:
        """Check if an issue already exists in the database."""
        return self.get_issue_by_repo(repo_owner, repo_name, number) is not None

    def get_unattempted_issues(self, limit: int = 10) -> list[Issue]:
        """Get issues that have not been attempted yet."""
        sql = """
            SELECT i.* FROM issues i
            WHERE NOT EXISTS (
                SELECT 1 FROM attempts a WHERE a.issue_id = i.id
            )
            ORDER BY i.discovered_at DESC
            LIMIT ?
        """
        rows = list(self.db.execute(sql, [limit]).fetchall())
        columns = [desc[0] for desc in self.db.execute(sql, [limit]).description]
        return [_row_to_issue(dict(zip(columns, row))) for row in rows]

    # ── Analyses ──

    def insert_analysis(self, analysis: Analysis) -> None:
        """Insert an analysis record."""
        row = analysis.model_dump()
        row["created_at"] = row["created_at"].isoformat()
        row["rating"] = str(row["rating"])
        self.db["analyses"].insert(row)

    def get_latest_analysis(self, issue_id: str) -> Analysis | None:
        """Get the most recent analysis for an issue."""
        rows = list(
            self.db["analyses"].rows_where(
                "issue_id = ? ORDER BY created_at DESC LIMIT 1",
                [issue_id],
            )
        )
        if not rows:
            return None
        return _row_to_analysis(rows[0])

    # ── Attempts ──

    def insert_attempt(self, attempt: Attempt) -> None:
        """Insert an attempt record."""
        row = attempt.model_dump()
        row["created_at"] = row["created_at"].isoformat()
        row["updated_at"] = row["updated_at"].isoformat()
        row["status"] = str(row["status"])
        if row["outcome"]:
            row["outcome"] = str(row["outcome"])
        self.db["attempts"].insert(row)

    def update_attempt(self, attempt: Attempt) -> None:
        """Update an existing attempt record."""
        attempt.updated_at = datetime.now(UTC)
        row = attempt.model_dump()
        row["created_at"] = row["created_at"].isoformat()
        row["updated_at"] = row["updated_at"].isoformat()
        row["status"] = str(row["status"])
        if row["outcome"]:
            row["outcome"] = str(row["outcome"])
        self.db["attempts"].update(attempt.id, row)

    def get_attempts_for_issue(self, issue_id: str) -> list[Attempt]:
        """Get all attempts for an issue."""
        rows = list(
            self.db["attempts"].rows_where(
                "issue_id = ? ORDER BY created_at DESC",
                [issue_id],
            )
        )
        return [_row_to_attempt(row) for row in rows]

    def has_attempt(self, issue_id: str) -> bool:
        """Check if any attempt exists for an issue."""
        rows = list(
            self.db["attempts"].rows_where(
                "issue_id = ? LIMIT 1",
                [issue_id],
            )
        )
        return len(rows) > 0

    # ── Statistics (basic — extended in US4) ──

    def count_attempts_by_status(self) -> dict[str, int]:
        """Count attempts grouped by status."""
        sql = "SELECT status, COUNT(*) as cnt FROM attempts GROUP BY status"
        return {row[0]: row[1] for row in self.db.execute(sql).fetchall()}

    def get_total_cost(self) -> float:
        """Get total cost across all attempts."""
        sql = "SELECT COALESCE(SUM(cost_usd), 0) FROM attempts"
        return self.db.execute(sql).fetchone()[0]

    # ── Reporting (US4) ──

    def get_summary_stats(self) -> dict:
        """Get overall summary statistics."""
        issues_count = self.db.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
        analyses_count = self.db.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        attempts_count = self.db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        total_cost = self.get_total_cost()

        succeeded = self.db.execute(
            "SELECT COUNT(*) FROM attempts WHERE status = 'succeeded'"
        ).fetchone()[0]
        failed = self.db.execute(
            "SELECT COUNT(*) FROM attempts WHERE status = 'failed'"
        ).fetchone()[0]

        prs = self.db.execute(
            "SELECT COUNT(*) FROM attempts WHERE outcome = 'pr_submitted'"
        ).fetchone()[0]

        success_rate = (succeeded / attempts_count * 100) if attempts_count > 0 else 0.0
        avg_cost = (total_cost / attempts_count) if attempts_count > 0 else 0.0

        return {
            "issues_discovered": issues_count,
            "analyses_run": analyses_count,
            "attempts_total": attempts_count,
            "attempts_succeeded": succeeded,
            "attempts_failed": failed,
            "prs_submitted": prs,
            "success_rate": success_rate,
            "total_cost_usd": total_cost,
            "avg_cost_usd": avg_cost,
        }

    def get_resolution_funnel(self) -> dict:
        """Get the resolution funnel with drop-off counts."""
        discovered = self.db.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
        analyzed = self.db.execute("SELECT COUNT(DISTINCT issue_id) FROM analyses").fetchone()[0]
        attempted = self.db.execute("SELECT COUNT(DISTINCT issue_id) FROM attempts").fetchone()[0]
        non_empty_diff = self.db.execute(
            "SELECT COUNT(*) FROM attempts WHERE outcome != 'empty_diff' AND outcome IS NOT NULL"
        ).fetchone()[0]
        tests_pass = self.db.execute(
            "SELECT COUNT(*) FROM attempts WHERE outcome IN ('pr_submitted', 'untested')"
        ).fetchone()[0]
        pr_submitted = self.db.execute(
            "SELECT COUNT(*) FROM attempts WHERE outcome = 'pr_submitted'"
        ).fetchone()[0]

        return {
            "discovered": discovered,
            "analyzed": analyzed,
            "attempted": attempted,
            "non_empty_diff": non_empty_diff,
            "tests_pass": tests_pass,
            "pr_submitted": pr_submitted,
        }

    def get_per_language_stats(self) -> list[dict]:
        """Get statistics broken down by programming language."""
        sql = """
            SELECT
                COALESCE(i.language, 'unknown') as language,
                COUNT(a.id) as attempts,
                SUM(CASE WHEN a.status = 'succeeded' THEN 1 ELSE 0 END) as successes,
                COALESCE(SUM(a.cost_usd), 0) as total_cost,
                COALESCE(AVG(a.duration_ms), 0) as avg_duration_ms
            FROM attempts a
            JOIN issues i ON a.issue_id = i.id
            GROUP BY COALESCE(i.language, 'unknown')
            ORDER BY attempts DESC
        """
        rows = self.db.execute(sql).fetchall()
        cols = ["language", "attempts", "successes", "total_cost", "avg_duration_ms"]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            d["success_rate"] = (d["successes"] / d["attempts"] * 100) if d["attempts"] > 0 else 0.0
            results.append(d)
        return results


def _row_to_issue(row: dict) -> Issue:
    """Convert a database row to an Issue model."""
    labels = row.get("labels")
    if isinstance(labels, str):
        labels = json.loads(labels)
    return Issue(
        id=row["id"],
        repo_owner=row["repo_owner"],
        repo_name=row["repo_name"],
        number=row["number"],
        title=row["title"],
        body=row.get("body"),
        labels=labels or [],
        url=row["url"],
        state=row.get("state", "open"),
        has_assignees=bool(row.get("has_assignees", 0)),
        has_linked_prs=bool(row.get("has_linked_prs", 0)),
        language=row.get("language"),
        repo_stars=row.get("repo_stars"),
        created_at=datetime.fromisoformat(row["created_at"]),
        discovered_at=datetime.fromisoformat(row["discovered_at"]),
    )


def _row_to_analysis(row: dict) -> Analysis:
    """Convert a database row to an Analysis model."""
    return Analysis(
        id=row["id"],
        issue_id=row["issue_id"],
        rating=row["rating"],
        confidence=row["confidence"],
        complexity=row.get("complexity"),
        reasoning=row["reasoning"],
        cost_usd=row.get("cost_usd"),
        model=row.get("model"),
        duration_ms=row.get("duration_ms"),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_attempt(row: dict) -> Attempt:
    """Convert a database row to an Attempt model."""
    return Attempt(
        id=row["id"],
        issue_id=row["issue_id"],
        status=row["status"],
        outcome=row.get("outcome"),
        cost_usd=row.get("cost_usd"),
        duration_ms=row.get("duration_ms"),
        workspace_path=row.get("workspace_path"),
        pr_url=row.get("pr_url"),
        pr_number=row.get("pr_number"),
        branch_name=row.get("branch_name"),
        num_turns=row.get("num_turns"),
        model=row.get("model"),
        test_output=row.get("test_output"),
        diff_summary=row.get("diff_summary"),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
