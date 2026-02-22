"""PR creation and submission pipeline stage."""

from __future__ import annotations

import logging

import typer

from issue_resolver.cli.console import console
from issue_resolver.config.schema import AppConfig
from issue_resolver.github.pr import build_pr_body, create_pr
from issue_resolver.github.repo_ops import push_branch
from issue_resolver.models.analysis import Analysis
from issue_resolver.models.attempt import Attempt
from issue_resolver.models.enums import OutcomeCategory
from issue_resolver.models.issue import Issue

logger = logging.getLogger(__name__)


def submit_pr(
    issue: Issue,
    attempt: Attempt,
    analysis: Analysis,
    config: AppConfig,
    auto_pr: bool = False,
    dry_run: bool = False,
) -> str | None:
    """Create and submit a PR for a resolved issue.

    Args:
        issue: The target issue.
        attempt: The resolution attempt.
        analysis: The solvability analysis.
        config: Application configuration.
        auto_pr: If True, submit without confirmation.
        dry_run: If True, show what would be done without acting.

    Returns:
        PR URL if submitted, None otherwise.
    """
    is_untested = attempt.outcome == OutcomeCategory.UNTESTED

    if dry_run:
        console.print(
            f"[dry_run][DRY RUN][/dry_run] Would submit PR for {issue.full_repo}#{issue.number}"
        )
        console.print(f"  Branch: {attempt.branch_name}")
        console.print(f"  Changes: {attempt.diff_summary or 'unknown'}")
        if is_untested:
            console.print("  [warning]Warning: No test suite detected[/warning]")
        return None

    # Build PR content
    title = f"Fix #{issue.number}: {issue.title[:60]}"
    body = build_pr_body(
        issue=issue,
        analysis=analysis,
        diff_summary=attempt.diff_summary,
        test_output=attempt.test_output,
        cost_usd=attempt.cost_usd or 0.0,
        is_untested=is_untested,
    )

    if not auto_pr:
        # Interactive mode — show diff and ask for confirmation
        console.print("\n[info]Resolution Summary:[/info]")
        console.print(f"  Issue: {issue.full_repo}#{issue.number}")
        console.print(f"  Title: {issue.title}")
        console.print(f"  Rating: {analysis.rating.value} ({analysis.confidence:.0%})")
        console.print(f"  Changes: {attempt.diff_summary or 'unknown'}")
        console.print(f"  Cost: [cost]${attempt.cost_usd or 0:.2f}[/cost]")
        if is_untested:
            console.print("  [warning]Note: No test suite detected[/warning]")
        console.print()

        if not typer.confirm("Submit PR?"):
            logger.info("PR submission declined by user")
            return None

    # Push branch and create PR
    assert attempt.workspace_path is not None
    assert attempt.branch_name is not None

    push_branch(attempt.workspace_path, attempt.branch_name)

    # Get the user's fork name for the head branch
    from issue_resolver.github.repo_ops import _get_gh_username

    gh_user = _get_gh_username()
    head_branch = f"{gh_user}:{attempt.branch_name}"

    pr_url = create_pr(
        owner=issue.repo_owner,
        repo=issue.repo_name,
        head_branch=head_branch,
        title=title,
        body=body,
        issue_number=issue.number,
    )

    return pr_url
