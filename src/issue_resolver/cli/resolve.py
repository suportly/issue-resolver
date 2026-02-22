"""CLI resolve command: resolve a specific GitHub issue."""

from __future__ import annotations

import logging
import re
from datetime import UTC

import typer

from issue_resolver.claude.invoker import check_claude_installed
from issue_resolver.cli import exit_codes
from issue_resolver.cli.console import console, err_console
from issue_resolver.cli.context import state
from issue_resolver.db.engine import get_database
from issue_resolver.db.repository import Repository
from issue_resolver.github.client import check_gh_authenticated, check_gh_installed, run_gh_json
from issue_resolver.models.enums import AttemptStatus
from issue_resolver.models.issue import Issue
from issue_resolver.pipeline.analyzer import analyze_issue
from issue_resolver.pipeline.resolver import resolve_issue
from issue_resolver.pipeline.submitter import submit_pr
from issue_resolver.utils.exceptions import (
    AnalysisRejectedError,
    BudgetExceededError,
    ClaudeError,
    PrerequisiteError,
    TestsFailedError,
)
from issue_resolver.utils.logging import log_cost

logger = logging.getLogger(__name__)

resolve_app = typer.Typer(name="resolve", help="Resolve a specific GitHub issue")


@resolve_app.callback(invoke_without_command=True)
def resolve(
    issue_url: str = typer.Argument(help="GitHub issue URL"),
    budget: float | None = typer.Option(None, "--budget", help="Per-resolution budget (USD)"),
) -> None:
    """Resolve a specific GitHub issue end-to-end."""
    config = state.config
    dry_run = state.dry_run
    auto_pr = state.auto_pr

    if budget is not None:
        config.claude.resolution_max_budget_usd = budget

    # Step 1: Validate prerequisites (FR-007)
    try:
        _check_prerequisites(dry_run)
    except PrerequisiteError as e:
        err_console.print(f"[error]Error: {e}[/error]")
        raise typer.Exit(code=exit_codes.PREREQUISITE_FAILED)

    # Step 2: Parse issue URL
    owner, repo, number = _parse_issue_url(issue_url)
    if not owner:
        err_console.print(f"[error]Error: Invalid issue URL: {issue_url}[/error]")
        raise typer.Exit(code=exit_codes.GENERAL_ERROR)

    db = get_database(config.db_path)
    repository = Repository(db)

    prefix = "[dry_run][DRY RUN][/dry_run] " if dry_run else ""
    console.print(f"{prefix}Analyzing issue: {owner}/{repo}#{number}")

    # Step 3: Fetch issue details and verify freshness (FR-021)
    try:
        issue = _fetch_issue(owner, repo, number, repository, dry_run)
    except Exception as e:
        err_console.print(f"[error]Error fetching issue: {e}[/error]")
        raise typer.Exit(code=exit_codes.GENERAL_ERROR)

    # Step 4: Solvability analysis
    try:
        analysis = analyze_issue(issue, config, repository, dry_run)
        console.print(f"  Rating: {analysis.rating.value} (confidence: {analysis.confidence:.0%})")
        console.print(f"  Complexity: {analysis.complexity or 'unknown'}")
        console.print(f"  Reasoning: {analysis.reasoning}")
        if analysis.cost_usd:
            log_cost("Analysis", analysis.cost_usd, analysis.duration_ms)
    except AnalysisRejectedError as e:
        console.print(f"  [warning]{e}[/warning]")
        raise typer.Exit(code=exit_codes.ANALYSIS_REJECTED)
    except ClaudeError as e:
        err_console.print(f"[error]Analysis failed: {e}[/error]")
        raise typer.Exit(code=exit_codes.GENERAL_ERROR)

    if dry_run:
        console.print(f"\n{prefix}Would fork, clone, resolve, and submit PR. No changes made.")
        raise typer.Exit(code=exit_codes.OK)

    # Step 5: Resolution
    console.print("\nResolving...")
    try:
        attempt = resolve_issue(issue, analysis, config, repository, dry_run)
    except BudgetExceededError as e:
        err_console.print(f"[error]{e}[/error]")
        raise typer.Exit(code=exit_codes.BUDGET_EXCEEDED)
    except TestsFailedError as e:
        err_console.print(f"[error]{e}[/error]")
        raise typer.Exit(code=exit_codes.TESTS_FAILED)

    if attempt.status != AttemptStatus.SUCCEEDED:
        err_console.print(f"[error]Resolution outcome: {attempt.outcome.value}[/error]")
        if attempt.workspace_path:
            console.print(f"  Workspace: {attempt.workspace_path}")
        if attempt.cost_usd:
            console.print(f"  Cost: [cost]${attempt.cost_usd:.2f}[/cost]")
        raise typer.Exit(code=exit_codes.GENERAL_ERROR)

    console.print(f"  Workspace: {attempt.workspace_path}")
    console.print(f"  Changes: {attempt.diff_summary or 'unknown'}")
    if attempt.test_output:
        lines = attempt.test_output.strip().split("\n")
        last_line = lines[-1] if lines else ""
        console.print(f"  Tests: {last_line}")
    console.print(f"  Cost: [cost]${attempt.cost_usd or 0:.2f}[/cost]")

    # Step 6: Submit PR
    pr_url = submit_pr(
        issue=issue,
        attempt=attempt,
        analysis=analysis,
        config=config,
        auto_pr=auto_pr,
        dry_run=dry_run,
    )

    if pr_url:
        attempt.pr_url = pr_url
        # Extract PR number from URL
        pr_match = re.search(r"/pull/(\d+)", pr_url)
        if pr_match:
            attempt.pr_number = int(pr_match.group(1))
        repository.update_attempt(attempt)
        console.print(f"\n[success]PR: {pr_url}[/success]")


def _check_prerequisites(dry_run: bool) -> None:
    """Validate all external tools are installed and authenticated."""
    check_gh_installed()
    if not dry_run:
        check_gh_authenticated()
        check_claude_installed()


def _parse_issue_url(url: str) -> tuple[str | None, str | None, int | None]:
    """Parse a GitHub issue URL into (owner, repo, number)."""
    pattern = r"github\.com/([^/]+)/([^/]+)/issues/(\d+)"
    match = re.search(pattern, url)
    if not match:
        return None, None, None
    return match.group(1), match.group(2), int(match.group(3))


def _fetch_issue(
    owner: str,
    repo: str,
    number: int,
    repository: Repository,
    dry_run: bool,
) -> Issue:
    """Fetch issue details from GitHub and persist to database."""
    from datetime import datetime

    if dry_run:
        # In dry-run, still fetch issue metadata (read-only)
        pass

    data = run_gh_json(
        [
            "issue",
            "view",
            str(number),
            "--repo",
            f"{owner}/{repo}",
            "--json",
            "title,body,labels,state,assignees,url",
        ],
        timeout=30,
        retry=True,
    )

    labels = [label.get("name", "") for label in data.get("labels", [])]
    has_assignees = len(data.get("assignees", [])) > 0

    # Check freshness (FR-021)
    if data.get("state", "").upper() != "OPEN":
        raise ValueError(
            f"Issue #{number} is no longer open (state: {data.get('state')}). Skipping."
        )

    if has_assignees and not dry_run:
        raise ValueError(f"Issue #{number} has assignees. Skipping to respect existing work.")

    issue = Issue(
        repo_owner=owner,
        repo_name=repo,
        number=number,
        title=data.get("title", ""),
        body=data.get("body"),
        labels=labels,
        url=data.get("url", f"https://github.com/{owner}/{repo}/issues/{number}"),
        state="open",
        has_assignees=has_assignees,
        has_linked_prs=False,
        language=None,
        created_at=datetime.now(UTC),
    )

    repository.upsert_issue(issue)
    return issue
