"""Unit tests for GitHub issue search query builder and parser."""

from __future__ import annotations

from unittest.mock import patch

from issue_resolver.github.search import (
    build_search_query,
    parse_search_result,
    search_issues,
)


class TestBuildSearchQuery:
    def test_defaults(self) -> None:
        query = build_search_query()
        assert "is:issue" in query
        assert "is:open" in query
        assert "no:assignee" in query
        assert "-linked:pr" in query

    def test_labels(self) -> None:
        query = build_search_query(labels=["bug", "good first issue"])
        assert 'label:"bug"' in query
        assert 'label:"good first issue"' in query

    def test_languages(self) -> None:
        query = build_search_query(languages=["python", "rust"])
        assert "language:python" in query
        assert "language:rust" in query

    def test_min_stars(self) -> None:
        query = build_search_query(min_stars=100)
        assert "stars:>100" in query

    def test_max_age_days(self) -> None:
        query = build_search_query(max_age_days=30)
        assert "created:>" in query

    def test_repos(self) -> None:
        query = build_search_query(repos=["owner/repo1", "owner/repo2"])
        assert "repo:owner/repo1" in query
        assert "repo:owner/repo2" in query

    def test_exclude_assignees_false(self) -> None:
        query = build_search_query(exclude_assignees=False)
        assert "no:assignee" not in query

    def test_exclude_linked_prs_false(self) -> None:
        query = build_search_query(exclude_linked_prs=False)
        assert "-linked:pr" not in query

    def test_all_filters_combined(self) -> None:
        query = build_search_query(
            labels=["bug"],
            languages=["python"],
            min_stars=50,
            max_age_days=90,
            repos=["test/repo"],
        )
        assert "is:issue" in query
        assert "is:open" in query
        assert 'label:"bug"' in query
        assert "language:python" in query
        assert "stars:>50" in query
        assert "created:>" in query
        assert "repo:test/repo" in query

    def test_no_stars_filter_when_none(self) -> None:
        query = build_search_query(min_stars=None)
        assert "stars:" not in query

    def test_no_age_filter_when_none(self) -> None:
        query = build_search_query(max_age_days=None)
        assert "created:>" not in query


class TestParseSearchResult:
    def test_full_item(self) -> None:
        item = {
            "html_url": "https://github.com/owner/repo/issues/42",
            "repository_url": "https://api.github.com/repos/owner/repo",
            "number": 42,
            "title": "Test issue",
            "body": "Test body",
            "labels": [{"name": "bug"}, {"name": "help wanted"}],
            "assignees": [],
            "created_at": "2026-01-15T10:00:00Z",
        }
        issue = parse_search_result(item)
        assert issue.repo_owner == "owner"
        assert issue.repo_name == "repo"
        assert issue.number == 42
        assert issue.title == "Test issue"
        assert issue.body == "Test body"
        assert issue.labels == ["bug", "help wanted"]
        assert issue.state == "open"
        assert issue.has_assignees is False

    def test_with_assignees(self) -> None:
        item = {
            "html_url": "https://github.com/o/r/issues/1",
            "repository_url": "https://api.github.com/repos/o/r",
            "number": 1,
            "title": "Assigned",
            "labels": [],
            "assignees": [{"login": "user1"}],
            "created_at": "2026-01-01T00:00:00Z",
        }
        issue = parse_search_result(item)
        assert issue.has_assignees is True

    def test_missing_optional_fields(self) -> None:
        item = {
            "repository_url": "https://api.github.com/repos/o/r",
            "number": 1,
            "title": "Minimal",
            "labels": [],
            "assignees": [],
            "created_at": "2026-01-01T00:00:00Z",
        }
        issue = parse_search_result(item)
        assert issue.body is None
        assert issue.repo_owner == "o"
        assert issue.repo_name == "r"

    def test_malformed_created_at(self) -> None:
        item = {
            "repository_url": "https://api.github.com/repos/o/r",
            "number": 1,
            "title": "Bad date",
            "labels": [],
            "assignees": [],
            "created_at": "not-a-date",
        }
        issue = parse_search_result(item)
        # Should fall back to utcnow without raising
        assert issue.created_at is not None


class TestSearchIssues:
    @patch("issue_resolver.github.search.run_gh_json")
    def test_returns_list(self, mock_gh: object) -> None:
        mock_gh.return_value = [  # type: ignore[attr-defined]
            {"number": 1, "title": "Issue 1"},
            {"number": 2, "title": "Issue 2"},
        ]
        results = search_issues("is:issue", limit=10)
        assert len(results) == 2

    @patch("issue_resolver.github.search.run_gh_json")
    def test_respects_limit(self, mock_gh: object) -> None:
        mock_gh.return_value = [{"number": i} for i in range(50)]  # type: ignore[attr-defined]
        results = search_issues("is:issue", limit=5)
        assert len(results) == 5

    @patch("issue_resolver.github.search.run_gh_json")
    def test_non_list_result(self, mock_gh: object) -> None:
        mock_gh.return_value = {"error": "rate limited"}  # type: ignore[attr-defined]
        results = search_issues("is:issue")
        assert results == []

    @patch("issue_resolver.github.search.run_gh_json")
    def test_empty_results(self, mock_gh: object) -> None:
        mock_gh.return_value = []  # type: ignore[attr-defined]
        results = search_issues("is:issue")
        assert results == []
