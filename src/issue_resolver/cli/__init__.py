"""Root Typer application with global options and sub-command composition."""

from __future__ import annotations

import typer

from issue_resolver import __version__
from issue_resolver.cli.context import state
from issue_resolver.config.loader import load_config
from issue_resolver.utils.logging import setup_logging

app = typer.Typer(
    name="issue-resolver",
    help="AI-Powered GitHub Issue Resolution Tool",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value is True:
        typer.echo(f"issue-resolver {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Zero side effects mode",
        envvar="ISSUE_RESOLVER_DRY_RUN",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable DEBUG-level logging",
        envvar="ISSUE_RESOLVER_VERBOSE",
    ),
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML config file",
        envvar="ISSUE_RESOLVER_CONFIG",
    ),
    auto_pr: bool = typer.Option(
        False,
        "--auto-pr",
        help="Submit PR without confirmation",
        envvar="ISSUE_RESOLVER_AUTO_PR",
    ),
    max_budget: float | None = typer.Option(
        None,
        "--max-budget",
        help="Session budget cap in USD",
        envvar="ISSUE_RESOLVER_MAX_BUDGET",
    ),
    _version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """AI-Powered GitHub Issue Resolution Tool."""
    setup_logging(verbose)

    state.dry_run = dry_run
    state.verbose = verbose
    state.auto_pr = auto_pr
    state.config_path = config
    state.max_budget = max_budget

    cli_overrides: dict = {}
    if dry_run:
        cli_overrides["dry_run"] = True
    if auto_pr:
        cli_overrides["auto_pr"] = True

    state.config = load_config(config_path=config, cli_overrides=cli_overrides)

    if max_budget is not None:
        state.config.claude.total_session_budget_usd = max_budget


# ── Sub-command registration ──
from issue_resolver.cli.config_cmd import config_app  # noqa: E402
from issue_resolver.cli.resolve import resolve_app  # noqa: E402
from issue_resolver.cli.run import run_app  # noqa: E402
from issue_resolver.cli.scan import scan_app  # noqa: E402
from issue_resolver.cli.status import status_app  # noqa: E402

app.add_typer(resolve_app, name="resolve")
app.add_typer(scan_app, name="scan")
app.add_typer(run_app, name="run")
app.add_typer(status_app, name="status")
app.add_typer(config_app, name="config")
