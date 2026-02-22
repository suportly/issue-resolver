"""CLI config command: view and generate configuration."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import typer
import yaml

from issue_resolver.cli import exit_codes
from issue_resolver.cli.console import console, err_console
from issue_resolver.cli.context import state

logger = logging.getLogger(__name__)

config_app = typer.Typer(name="config", help="View and manage configuration")

# Path to the example config bundled with the package
_EXAMPLE_CONFIG = Path(__file__).parent.parent.parent.parent / "config.example.yaml"


@config_app.callback(invoke_without_command=True)
def config(
    init: bool = typer.Option(False, "--init", help="Generate config file in current directory"),
    show: bool = typer.Option(False, "--show", help="Display effective configuration"),
) -> None:
    """View or generate issue-resolver configuration."""
    if init:
        _init_config()
        return

    if show:
        _show_config()
        return

    # Default: show help
    console.print("Use --init to generate a config file or --show to view effective config.")
    console.print("Run `issue-resolver config --help` for details.")


def _init_config() -> None:
    """Generate a config file in the current directory."""
    target = Path.cwd() / ".issue-resolver.yaml"

    if target.exists():
        err_console.print(f"[warning]Config file already exists: {target}[/warning]")
        raise typer.Exit(code=exit_codes.GENERAL_ERROR)

    if _EXAMPLE_CONFIG.exists():
        shutil.copy2(_EXAMPLE_CONFIG, target)
    else:
        # Generate from current defaults
        cfg = state.config
        data = cfg.model_dump()
        with open(target, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    console.print(f"[success]Config file created: {target}[/success]")
    console.print("Edit this file to customize your settings.")


def _show_config() -> None:
    """Display the effective merged configuration."""
    cfg = state.config
    data = cfg.model_dump()

    # Redact secrets from environment
    import os

    secrets = {
        "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN"),
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY"),
    }

    console.print("[bold]Effective Configuration[/bold]\n")

    config_yaml = yaml.dump(data, default_flow_style=False, sort_keys=False)
    console.print(config_yaml)

    # Show secret status
    console.print("[bold]Secrets[/bold]")
    for name, value in secrets.items():
        status = "[success]****set****[/success]" if value else "[warning]not set[/warning]"
        console.print(f"  {name}: {status}")

    if state.config_path:
        console.print(f"\nLoaded from: {state.config_path}")
