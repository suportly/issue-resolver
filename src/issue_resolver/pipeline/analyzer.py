"""Solvability analysis pipeline stage."""

from __future__ import annotations

import json
import logging
import re

from issue_resolver.claude.invoker import invoke
from issue_resolver.claude.parser import parse_response
from issue_resolver.claude.prompts import build_analysis_prompt
from issue_resolver.config.schema import AppConfig
from issue_resolver.db.repository import Repository
from issue_resolver.models.analysis import Analysis
from issue_resolver.models.enums import SolvabilityRating
from issue_resolver.models.issue import Issue
from issue_resolver.utils.exceptions import AnalysisRejectedError, ClaudeError

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from text that may contain surrounding prose.

    Tries in order:
    1. Direct parse of the full text
    2. Extract from markdown code block (```json ... ``` or ``` ... ```)
    3. Find the first { ... } substring and parse it
    """
    # 1. Direct parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Extract from markdown code block
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block:
        try:
            data = json.loads(code_block.group(1).strip())
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. Find first { ... } substring (greedy from first { to last })
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            data = json.loads(brace_match.group(0))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def analyze_issue(
    issue: Issue,
    config: AppConfig,
    repository: Repository,
    dry_run: bool = False,
) -> Analysis:
    """Analyze an issue for solvability using the cheap/fast model.

    Args:
        issue: The issue to analyze.
        config: Application configuration.
        repository: Database repository.
        dry_run: If True, skip the actual Claude invocation and return a mock result.

    Returns:
        Analysis result.

    Raises:
        AnalysisRejectedError: If the issue doesn't meet the confidence threshold.
        ClaudeError: If the analysis invocation fails.
    """
    logger.info("Analyzing issue: %s#%d", issue.full_repo, issue.number)

    if dry_run:
        analysis = Analysis(
            issue_id=issue.id,
            rating=SolvabilityRating.LIKELY_SOLVABLE,
            confidence=0.75,
            complexity="medium",
            reasoning=(
                "[DRY RUN] Analysis skipped — would invoke AI agent for solvability assessment."
            ),
            cost_usd=0.0,
            model="haiku",
            duration_ms=0,
        )
        repository.insert_analysis(analysis)
        return analysis

    prompt = build_analysis_prompt(issue)

    stdout, stderr, returncode, timeout_expired = invoke(
        prompt=prompt,
        output_format="json",
        max_turns=1,
        model="haiku",
        timeout=config.claude.timeout_seconds,
        cwd="/tmp",
    )

    claude_result = parse_response(stdout, stderr, returncode, timeout_expired)

    if claude_result.outcome != "success":
        analysis = Analysis(
            issue_id=issue.id,
            rating=SolvabilityRating.UNSOLVABLE,
            confidence=0.0,
            reasoning=f"Analysis failed: {claude_result.outcome}",
            cost_usd=claude_result.cost_usd,
            model="haiku",
            duration_ms=claude_result.duration_ms,
        )
        repository.insert_analysis(analysis)
        raise ClaudeError(f"Analysis failed with outcome: {claude_result.outcome}")

    # Parse the structured analysis from Claude's response
    analysis_data = _extract_json(claude_result.result_text)
    if analysis_data is None:
        analysis = Analysis(
            issue_id=issue.id,
            rating=SolvabilityRating.UNSOLVABLE,
            confidence=0.0,
            reasoning=f"Failed to parse analysis JSON: {claude_result.result_text[:200]}",
            cost_usd=claude_result.cost_usd,
            model="haiku",
            duration_ms=claude_result.duration_ms,
        )
        repository.insert_analysis(analysis)
        raise ClaudeError("Analysis returned invalid JSON")

    analysis = Analysis(
        issue_id=issue.id,
        rating=SolvabilityRating(analysis_data.get("rating", "unsolvable")),
        confidence=float(analysis_data.get("confidence", 0.0)),
        complexity=analysis_data.get("complexity"),
        reasoning=analysis_data.get("reasoning", "No reasoning provided"),
        cost_usd=claude_result.cost_usd,
        model="haiku",
        duration_ms=claude_result.duration_ms,
    )

    repository.insert_analysis(analysis)

    logger.info(
        "Analysis: %s (confidence: %.0f%%, complexity: %s)",
        analysis.rating.value,
        analysis.confidence * 100,
        analysis.complexity or "unknown",
    )

    # Gate check (FR-003)
    if not analysis.passes_threshold:
        raise AnalysisRejectedError(
            f"Issue below confidence threshold: {analysis.rating.value} "
            f"({analysis.confidence:.0%}). Reasoning: {analysis.reasoning}"
        )

    return analysis
