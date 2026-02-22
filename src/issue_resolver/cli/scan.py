"""CLI scan command: search GitHub for resolvable issues."""

from __future__ import annotations

import logging

import typer
from rich.table import Table

from issue_resolver.cli import exit_codes
from issue_resolver.cli.console import console, err_console
from issue_resolver.cli.context import state
from issue_resolver.db.engine import get_database
from issue_resolver.db.repository import Repository
from issue_resolver.github.client import check_gh_authenticated, check_gh_installed
from issue_resolver.pipeline.scanner import scan_issues
from issue_resolver.utils.exceptions import PrerequisiteError

logger = logging.getLogger(__name__)

scan_app = typer.Typer(name="scan", help="Search GitHub for resolvable issues")


@scan_app.callback(invoke_without_command=True)
def scan(
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum issues to return"),
    language: str | None = typer.Option(None, "--language", "-l", help="Filter by language"),
    label: str | None = typer.Option(None, "--label", help="Filter by label (comma-separated)"),
    min_stars: int | None = typer.Option(None, "--min-stars", help="Minimum repo stars"),
    max_age: int | None = typer.Option(None, "--max-age", help="Maximum issue age in days"),
) -> None:
    """Scan GitHub for resolvable issues."""
    config = state.config

    # Validate prerequisites
    try:
        check_gh_installed()
        check_gh_authenticated()
    except PrerequisiteError as e:
        err_console.print(f"[error]Error: {e}[/error]")
        raise typer.Exit(code=exit_codes.PREREQUISITE_FAILED)

    db = get_database(config.db_path)
    repository = Repository(db)

    prefix = "[dry_run][DRY RUN][/dry_run] " if state.dry_run else ""
    console.print(f"{prefix}Scanning for issues...")

    try:
        candidates = scan_issues(
            config=config,
            repository=repository,
            limit=limit,
            language=language,
            labels=label.split(",") if label else None,
            min_stars=min_stars,
            max_age=max_age,
        )
    except Exception as e:
        err_console.print(f"[error]Scan failed: {e}[/error]")
        raise typer.Exit(code=exit_codes.GENERAL_ERROR)

    if not candidates:
        console.print("No matching issues found.")
        raise typer.Exit(code=exit_codes.OK)

    # Display results table
    table = Table(title=f"Found {len(candidates)} candidate issues")
    table.add_column("#", style="dim", width=3)
    table.add_column("Repository", style="cyan")
    table.add_column("Issue", style="green")
    table.add_column("Labels", style="yellow")
    table.add_column("Stars", justify="right")
    table.add_column("Age", justify="right")

    from datetime import datetime

    for i, issue in enumerate(candidates, 1):
        age_days = (datetime.utcnow() - issue.created_at).days
        labels_str = ", ".join(issue.labels[:3])
        stars_str = _format_stars(issue.repo_stars) if issue.repo_stars else "-"

        table.add_row(
            str(i),
            issue.full_repo,
            f"#{issue.number}",
            labels_str,
            stars_str,
            f"{age_days}d",
        )

    console.print(table)
    console.print(
        f"\n{len(candidates)} issues saved. Run `issue-resolver resolve <url>` to resolve one."
    )


def _format_stars(stars: int | None) -> str:
    if stars is None:
        return "-"
    if stars >= 1000:
        return f"{stars / 1000:.1f}k"
    return str(stars)
