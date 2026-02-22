"""Issue discovery and filtering pipeline stage."""

from __future__ import annotations

import logging

from issue_resolver.config.schema import AppConfig
from issue_resolver.db.repository import Repository
from issue_resolver.github.search import build_search_query, parse_search_result, search_issues
from issue_resolver.models.issue import Issue

logger = logging.getLogger(__name__)


def scan_issues(
    config: AppConfig,
    repository: Repository,
    limit: int = 10,
    language: str | None = None,
    labels: list[str] | None = None,
    min_stars: int | None = None,
    max_age: int | None = None,
) -> list[Issue]:
    """Scan GitHub for candidate issues, filtering and deduplicating.

    Args:
        config: Application configuration.
        repository: Database repository for deduplication.
        limit: Maximum issues to return.
        language: Override language filter.
        labels: Override label filter.
        min_stars: Override minimum stars.
        max_age: Override maximum age in days.

    Returns:
        List of new candidate issues (persisted to database).
    """
    search_config = config.search

    query = build_search_query(
        labels=labels or search_config.labels,
        languages=[language] if language else search_config.languages,
        min_stars=min_stars or search_config.min_stars,
        max_age_days=max_age or search_config.max_age_days,
        repos=config.targets.repos or None,
        exclude_assignees=search_config.exclude_assignees,
        exclude_linked_prs=search_config.exclude_linked_prs,
    )

    # Fetch more than needed to account for deduplication filtering
    raw_results = search_issues(query, limit=limit * 3)

    candidates: list[Issue] = []
    for item in raw_results:
        issue = parse_search_result(item)

        # Skip if already in database (FR-010 deduplication)
        if repository.issue_exists(issue.repo_owner, issue.repo_name, issue.number):
            logger.debug("Skipping duplicate: %s#%d", issue.full_repo, issue.number)
            continue

        # Persist and collect
        repository.upsert_issue(issue)
        candidates.append(issue)

        if len(candidates) >= limit:
            break

    logger.info(
        "Scan complete: %d candidates from %d results",
        len(candidates),
        len(raw_results),
    )
    return candidates
