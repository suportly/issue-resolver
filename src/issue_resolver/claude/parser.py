"""Parse Claude Code CLI JSON output per contracts/claude-output.md."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClaudeResult:
    """Parsed result from a Claude Code CLI invocation."""

    outcome: str  # success, timeout, process_error, parse_error, budget_exceeded
    result_text: str
    cost_usd: float
    duration_ms: int
    num_turns: int
    session_id: str
    is_error: bool
    raw_stdout: str


def parse_response(
    stdout: str,
    stderr: str,
    returncode: int,
    timeout_expired: bool,
) -> ClaudeResult:
    """Parse Claude Code CLI output into a structured result.

    Handles all termination conditions per contracts/claude-output.md:
    - Normal completion
    - Max turns reached
    - Budget exceeded
    - Auth/usage error
    - External timeout
    - Malformed JSON
    """
    # 1. Handle external timeout (subprocess.TimeoutExpired)
    if timeout_expired:
        return ClaudeResult(
            outcome="timeout",
            result_text="",
            cost_usd=0.0,
            duration_ms=0,
            num_turns=0,
            session_id="",
            is_error=True,
            raw_stdout=stdout,
        )

    # 2. Handle non-zero exit code (auth/usage error)
    if returncode != 0:
        logger.error("Claude CLI exited with code %d: %s", returncode, stderr.strip())
        return ClaudeResult(
            outcome="process_error",
            result_text="",
            cost_usd=0.0,
            duration_ms=0,
            num_turns=0,
            session_id="",
            is_error=True,
            raw_stdout=stdout,
        )

    # 3. Try to parse JSON
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Claude JSON output: %s", e)
        logger.debug("Raw stdout: %s", stdout[:500])
        return ClaudeResult(
            outcome="parse_error",
            result_text="",
            cost_usd=0.0,
            duration_ms=0,
            num_turns=0,
            session_id="",
            is_error=True,
            raw_stdout=stdout,
        )

    # 4. Normalize cost field (handle both cost_usd and total_cost_usd)
    cost = data.get("cost_usd", data.get("total_cost_usd", 0.0))

    result_text = data.get("result", "")
    is_error = data.get("is_error", False)
    duration_ms = data.get("duration_ms", 0)
    num_turns = data.get("num_turns", 0)
    session_id = data.get("session_id", "")

    # 5. Classify termination — check BOTH is_error and exit code independently
    if is_error:
        # Budget exceeded: is_error=true AND cost approaches budget
        if cost > 0:
            outcome = "budget_exceeded"
        else:
            outcome = "process_error"
    else:
        outcome = "success"

    return ClaudeResult(
        outcome=outcome,
        result_text=result_text,
        cost_usd=cost,
        duration_ms=duration_ms,
        num_turns=num_turns,
        session_id=session_id,
        is_error=is_error,
        raw_stdout=stdout,
    )
