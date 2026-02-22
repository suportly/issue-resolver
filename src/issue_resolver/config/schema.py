"""Pydantic settings schema for issue resolver configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class SearchConfig(BaseModel):
    """GitHub issue search filter configuration."""

    labels: list[str] = Field(default=["good first issue", "bug", "help wanted"])
    languages: list[str] = Field(default=["python"])
    min_stars: int = 50
    max_age_days: int = 365
    exclude_assignees: bool = True
    exclude_linked_prs: bool = True


class TargetsConfig(BaseModel):
    """Target repository configuration."""

    repos: list[str] = Field(default_factory=list)
    exclude_repos: list[str] = Field(default_factory=list)


class ClaudeConfig(BaseModel):
    """AI agent configuration."""

    model: str = "opus"
    analysis_max_budget_usd: float = 0.50
    resolution_max_budget_usd: float = 5.00
    total_session_budget_usd: float = 25.00
    timeout_seconds: int = 600


class WorkspaceConfig(BaseModel):
    """Workspace management configuration."""

    base_dir: str = "/tmp/issue-resolver-workspaces"
    cleanup_on_success: bool = True
    cleanup_on_failure: bool = False


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    github_requests_per_minute: int = 25
    claude_invocations_per_hour: int = 30
    min_delay_between_issues_seconds: int = 10


class AppConfig(BaseSettings):
    """Root application configuration.

    Hierarchy: CLI flags > env vars > config file > defaults.
    """

    auto_pr: bool = False
    dry_run: bool = False
    max_issues_per_run: int = 5

    search: SearchConfig = Field(default_factory=SearchConfig)
    targets: TargetsConfig = Field(default_factory=TargetsConfig)
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)

    db_path: str = str(Path.home() / ".issue-resolver" / "data.db")

    model_config = {"env_prefix": "ISSUE_RESOLVER_"}
