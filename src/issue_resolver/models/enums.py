"""Enumerations for issue resolver domain models."""

from enum import StrEnum


class SolvabilityRating(StrEnum):
    """AI assessment of whether an issue can be resolved."""

    SOLVABLE = "solvable"
    LIKELY_SOLVABLE = "likely_solvable"
    UNLIKELY_SOLVABLE = "unlikely_solvable"
    UNSOLVABLE = "unsolvable"
    NEEDS_CONTEXT = "needs_context"


class AttemptStatus(StrEnum):
    """Current status of a resolution attempt."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class OutcomeCategory(StrEnum):
    """Categorized outcome of a resolution attempt."""

    PR_SUBMITTED = "pr_submitted"
    TESTS_FAILED = "tests_failed"
    EMPTY_DIFF = "empty_diff"
    RESOLUTION_FAILED = "resolution_failed"
    ANALYSIS_FAILED = "analysis_failed"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMEOUT = "timeout"
    PARSE_ERROR = "parse_error"
    STALE_ISSUE = "stale_issue"
    UNTESTED = "untested"
