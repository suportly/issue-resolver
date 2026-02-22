"""Subprocess helpers with timeout and retry."""

from __future__ import annotations

import logging
import random
import subprocess
import time

logger = logging.getLogger(__name__)


def run_with_timeout(
    cmd: list[str],
    timeout: int = 120,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with timeout.

    Args:
        cmd: Command and arguments.
        timeout: Timeout in seconds.
        cwd: Working directory.
        env: Environment variables (merged with current env if provided).

    Returns:
        CompletedProcess with stdout and stderr.

    Raises:
        subprocess.TimeoutExpired: If the command exceeds the timeout.
    """
    logger.debug("Running: %s (timeout=%ds, cwd=%s)", " ".join(cmd), timeout, cwd)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
        env=env,
    )


def run_with_retry(
    cmd: list[str],
    max_retries: int = 3,
    backoff_base: float = 1.0,
    timeout: int = 120,
    cwd: str | None = None,
    rate_limit_pattern: str = "rate limit",
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with exponential backoff retry on rate limits.

    Args:
        cmd: Command and arguments.
        max_retries: Maximum number of retry attempts.
        backoff_base: Base delay in seconds for exponential backoff.
        timeout: Per-attempt timeout in seconds.
        cwd: Working directory.
        rate_limit_pattern: Pattern to detect rate limiting in stderr.

    Returns:
        CompletedProcess from the successful attempt.

    Raises:
        subprocess.TimeoutExpired: If the final attempt times out.
        subprocess.CalledProcessError: If all retries exhausted.
    """
    last_result = None

    for attempt in range(max_retries + 1):
        result = run_with_timeout(cmd, timeout=timeout, cwd=cwd)
        last_result = result

        if result.returncode == 0:
            return result

        # Check for rate limit
        if rate_limit_pattern.lower() in (result.stderr or "").lower():
            if attempt < max_retries:
                delay = backoff_base * (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "Rate limited. Retrying in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(delay)
                continue

        # Non-rate-limit error — don't retry
        return result

    # Should not reach here, but return last result for safety
    assert last_result is not None
    return last_result
