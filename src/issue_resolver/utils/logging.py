"""Structured logging with Rich handler."""

import logging

from rich.console import Console
from rich.logging import RichHandler


def setup_logging(verbose: bool = False) -> None:
    """Configure logging with Rich handler on stderr.

    Args:
        verbose: If True, set level to DEBUG. Otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                show_path=verbose,
                console=Console(stderr=True),
            )
        ],
        force=True,
    )

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)


# Module-level logger for quick access
logger = get_logger("issue_resolver")


def log_cost(operation: str, cost_usd: float, duration_ms: int | None = None) -> None:
    """Log an operation with cost tracking."""
    msg = f"{operation}: ${cost_usd:.4f}"
    if duration_ms is not None:
        msg += f" ({duration_ms / 1000:.1f}s)"
    logger.info(msg, extra={"cost_usd": cost_usd, "duration_ms": duration_ms})
