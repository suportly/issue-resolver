"""GitHub issue search via gh API."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from issue_resolver.github.client import run_gh_json
from issue_resolver.models.issue import Issue

logger = logging.getLogger(__name__)


def build_search_query(
    labels: list[str] | None = None,
    languages: list[str] | None = None,
    min_stars: int | None = None,
    max_age_days: int | None = None,
    repos: list[str] | None = None,
    exclude_assignees: bool = True,
    exclude_linked_prs: bool = True,
) -> str:
    """Build a GitHub search query string from filter parameters.

    Args:
        labels: Issue labels to require.
        languages: Programming languages to filter by.
        min_stars: Minimum repository star count.
        max_age_days: Maximum issue age in days.
        repos: Specific repos to search (empty for broad search).
        exclude_assignees: Exclude issues with assignees.
        exclude_linked_prs: Exclude issues with linked PRs.

    Returns:
        GitHub search query string.
    """
    parts = ["is:issue", "is:open"]

    if exclude_assignees:
        parts.append("no:assignee")
    if exclude_linked_prs:
        parts.append("-linked:pr")

    if labels:
        for label in labels:
            parts.append(f'label:"{label}"')

    if languages:
        for lang in languages:
            parts.append(f"language:{lang}")

    if min_stars:
        parts.append(f"stars:>{min_stars}")

    if max_age_days:
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        parts.append(f"created:>{cutoff.strftime('%Y-%m-%d')}")

    if repos:
        repo_parts = " ".join(f"repo:{r}" for r in repos)
        parts.append(repo_parts)

    return " ".join(parts)


def search_issues(
    query: str,
    limit: int = 30,
) -> list[dict]:
    """Execute a GitHub issue search.

    Args:
        query: GitHub search query string.
        limit: Maximum results to return.

    Returns:
        List of raw issue dicts from GitHub API.
    """
    logger.info("Searching GitHub: %s (limit=%d)", query, limit)

    result = run_gh_json(
        [
            "api",
            "search/issues",
            "-X",
            "GET",
            "-f",
            f"q={query}",
            "-f",
            f"per_page={min(limit, 100)}",
            "--jq",
            ".items",
        ],
        timeout=30,
        retry=True,
    )

    if not isinstance(result, list):
        logger.warning("Unexpected search result type: %s", type(result))
        return []

    logger.info("Search returned %d results", len(result))
    return result[:limit]


def parse_search_result(item: dict) -> Issue:
    """Parse a single search result item into an Issue model.

    Args:
        item: Raw dict from GitHub search API response.

    Returns:
        Issue model instance.
    """
    # Extract repo info from the URL
    url = item.get("html_url", item.get("url", ""))
    repo_url = item.get("repository_url", "")

    # Parse owner/repo from repository_url: https://api.github.com/repos/owner/repo
    parts = repo_url.rstrip("/").split("/")
    repo_owner = parts[-2] if len(parts) >= 2 else ""
    repo_name = parts[-1] if len(parts) >= 1 else ""

    labels = [label.get("name", "") for label in item.get("labels", [])]
    assignees = item.get("assignees", [])

    created_str = item.get("created_at", "")
    try:
        created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        created_at = datetime.now(UTC)

    return Issue(
        repo_owner=repo_owner,
        repo_name=repo_name,
        number=item.get("number", 0),
        title=item.get("title", ""),
        body=item.get("body"),
        labels=labels,
        url=url,
        state="open",
        has_assignees=len(assignees) > 0,
        has_linked_prs=False,
        language=None,
        created_at=created_at,
    )
