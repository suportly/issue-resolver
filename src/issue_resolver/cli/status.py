"""CLI status command: view history and statistics."""

from __future__ import annotations

import logging

import typer
from rich.table import Table

from issue_resolver.cli import exit_codes
from issue_resolver.cli.console import console
from issue_resolver.cli.context import state
from issue_resolver.db.engine import get_database
from issue_resolver.db.repository import Repository

logger = logging.getLogger(__name__)

status_app = typer.Typer(name="status", help="View resolution history and statistics")


@status_app.callback(invoke_without_command=True)
def status(
    summary: bool = typer.Option(False, "--summary", "-s", help="Show summary statistics"),
) -> None:
    """Display resolution history and statistics."""
    config = state.config
    db = get_database(config.db_path)
    repository = Repository(db)

    stats = repository.get_summary_stats()

    if stats["issues_discovered"] == 0:
        console.print(
            "No history yet. Run `issue-resolver scan` or `issue-resolver resolve` first."
        )
        raise typer.Exit(code=exit_codes.OK)

    # Overview
    console.print("[bold]Issue Resolver Status[/bold]\n")

    console.print(f"  Issues discovered:  {stats['issues_discovered']}")
    console.print(f"  Analyses run:       {stats['analyses_run']}")
    console.print(f"  Resolution attempts:{stats['attempts_total']}")
    console.print(f"  PRs submitted:      {stats['prs_submitted']}")
    console.print(f"  Success rate:       {stats['success_rate']:.0f}%")
    console.print(f"  Total cost:         [cost]${stats['total_cost_usd']:.2f}[/cost]")
    console.print(f"  Average cost:       [cost]${stats['avg_cost_usd']:.2f}[/cost]")

    if not summary:
        raise typer.Exit(code=exit_codes.OK)

    # Resolution funnel
    funnel = repository.get_resolution_funnel()
    console.print("\n[bold]Resolution Funnel[/bold]")
    stages = [
        ("Discovered", funnel["discovered"]),
        ("Analyzed", funnel["analyzed"]),
        ("Attempted", funnel["attempted"]),
        ("Non-empty diff", funnel["non_empty_diff"]),
        ("Tests pass", funnel["tests_pass"]),
        ("PR submitted", funnel["pr_submitted"]),
    ]
    prev = None
    for name, count in stages:
        drop = ""
        if prev is not None and prev > 0:
            rate = count / prev * 100
            drop = f" ({rate:.0f}%)"
        console.print(f"  {name:16s} {count:4d}{drop}")
        prev = count

    # Per-language breakdown
    lang_stats = repository.get_per_language_stats()
    if lang_stats:
        console.print("\n[bold]Per-Language Breakdown[/bold]")
        table = Table()
        table.add_column("Language", style="cyan")
        table.add_column("Attempts", justify="right")
        table.add_column("Successes", justify="right")
        table.add_column("Rate", justify="right")
        table.add_column("Cost", justify="right", style="yellow")

        for row in lang_stats:
            table.add_row(
                row["language"],
                str(row["attempts"]),
                str(row["successes"]),
                f"{row['success_rate']:.0f}%",
                f"${row['total_cost']:.2f}",
            )
        console.print(table)
