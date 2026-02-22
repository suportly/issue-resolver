"""Exception hierarchy for issue resolver."""


class IssueResolverError(Exception):
    """Base exception for all issue resolver errors."""


class PrerequisiteError(IssueResolverError):
    """Required external tool is missing or not authenticated."""


class BudgetExceededError(IssueResolverError):
    """Budget limit has been reached."""


class AnalysisRejectedError(IssueResolverError):
    """Issue did not pass solvability analysis threshold."""


class TestsFailedError(IssueResolverError):
    """Project tests failed after applying the fix."""


class RateLimitError(IssueResolverError):
    """External service rate limit encountered."""


class ClaudeError(IssueResolverError):
    """Error invoking the Claude Code CLI."""


class GitHubError(IssueResolverError):
    """Error interacting with GitHub via gh CLI."""


class ConfigError(IssueResolverError):
    """Configuration loading or validation error."""


class WorkspaceError(IssueResolverError):
    """Workspace creation, cleanup, or access error."""
