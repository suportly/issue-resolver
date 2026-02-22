"""Global CLI state shared across commands."""

from __future__ import annotations

from dataclasses import dataclass, field

from issue_resolver.config.schema import AppConfig


@dataclass
class GlobalState:
    """Shared state populated in root @app.callback(), accessed by all commands."""

    dry_run: bool = False
    verbose: bool = False
    auto_pr: bool = False
    config_path: str | None = None
    max_budget: float | None = None
    config: AppConfig = field(default_factory=AppConfig)


# Module-level singleton populated by the root callback
state = GlobalState()
