"""CLI run command: full pipeline — scan, analyze, resolve."""

from __future__ import annotations

import logging

import typer

from issue_resolver.claude.invoker import check_claude_installed
from issue_resolver.cli import exit_codes
from issue_resolver.cli.console import console, err_console
from issue_resolver.cli.context import state
from issue_resolver.db.engine import get_database
from issue_resolver.db.repository import Repository
from issue_resolver.github.client import check_gh_authenticated, check_gh_installed
from issue_resolver.pipeline.orchestrator import run_pipeline
from issue_resolver.utils.exceptions import PrerequisiteError

logger = logging.getLogger(__name__)

run_app = typer.Typer(name="run", help="Full pipeline: scan + analyze + resolve")


@run_app.callback(invoke_without_command=True)
def run(
    max_issues: int | None = typer.Option(None, "--max-issues", "-n", help="Max issues to process"),
    budget: float | None = typer.Option(None, "--budget", help="Session budget cap (USD)"),
) -> None:
    """Run the full pipeline: scan, analyze, and resolve issues."""
    config = state.config
    dry_run = state.dry_run
    auto_pr = state.auto_pr

    if budget is not None:
        config.claude.total_session_budget_usd = budget

    # Validate prerequisites
    try:
        check_gh_installed()
        check_gh_authenticated()
        if not dry_run:
            check_claude_installed()
    except PrerequisiteError as e:
        err_console.print(f"[error]Error: {e}[/error]")
        raise typer.Exit(code=exit_codes.PREREQUISITE_FAILED)

    db = get_database(config.db_path)
    repository = Repository(db)

    prefix = "[dry_run][DRY RUN][/dry_run] " if dry_run else ""

    limit = max_issues or config.max_issues_per_run
    budget_usd = config.claude.total_session_budget_usd
    console.print(f"{prefix}Starting pipeline (max {limit} issues, budget ${budget_usd:.2f})")

    def on_progress(index: int, total: int, issue: object, status: str) -> None:
        issue_name = getattr(issue, "full_repo", "?") + "#" + str(getattr(issue, "number", "?"))
        console.print(f"  [{index}/{total}] {issue_name}: {status}...")

    try:
        result = run_pipeline(
            config=config,
            repository=repository,
            max_issues=max_issues,
            auto_pr=auto_pr,
            dry_run=dry_run,
            on_progress=on_progress,
        )
    except Exception as e:
        err_console.print(f"[error]Pipeline failed: {e}[/error]")
        raise typer.Exit(code=exit_codes.GENERAL_ERROR)

    # Print summary
    console.print(f"\n{prefix}Pipeline complete:")
    console.print(f"  Scanned:    {result.issues_scanned}")
    console.print(f"  Analyzed:   {result.issues_analyzed}")
    console.print(f"  Attempted:  {result.issues_attempted}")
    console.print(f"  PRs:        {result.prs_submitted}")
    console.print(f"  Failures:   {result.failures}")
    console.print(f"  Total cost: [cost]${result.total_cost_usd:.2f}[/cost]")

    if result.budget_exhausted:
        console.print("  [warning]Budget exhausted — stopped early[/warning]")
        raise typer.Exit(code=exit_codes.BUDGET_EXCEEDED)
