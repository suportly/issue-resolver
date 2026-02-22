"""Pipeline orchestrator: scan, analyze, resolve in one unattended run."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from issue_resolver.config.schema import AppConfig
from issue_resolver.db.repository import Repository
from issue_resolver.pipeline.analyzer import analyze_issue
from issue_resolver.pipeline.resolver import resolve_issue
from issue_resolver.pipeline.scanner import scan_issues
from issue_resolver.pipeline.submitter import submit_pr
from issue_resolver.utils.exceptions import (
    AnalysisRejectedError,
    BudgetExceededError,
    ClaudeError,
    TestsFailedError,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Summary of a pipeline run."""

    issues_scanned: int = 0
    issues_analyzed: int = 0
    issues_attempted: int = 0
    prs_submitted: int = 0
    failures: int = 0
    total_cost_usd: float = 0.0
    budget_exhausted: bool = False
    results: list[dict] = field(default_factory=list)


def run_pipeline(
    config: AppConfig,
    repository: Repository,
    max_issues: int | None = None,
    auto_pr: bool = False,
    dry_run: bool = False,
    on_progress: object | None = None,
) -> PipelineResult:
    """Run the full scan → analyze → resolve pipeline.

    Args:
        config: Application configuration.
        repository: Database repository.
        max_issues: Override max issues per run.
        auto_pr: Submit PRs without confirmation.
        dry_run: Skip side effects.
        on_progress: Optional callback(index, total, issue, status) for progress reporting.

    Returns:
        PipelineResult with session summary.
    """
    limit = max_issues or config.max_issues_per_run
    session_budget = config.claude.total_session_budget_usd
    rate_delay = config.rate_limit.min_delay_between_issues_seconds

    summary = PipelineResult()

    # Step 1: Scan for candidates
    logger.info("Scanning for up to %d candidate issues", limit)
    candidates = scan_issues(config=config, repository=repository, limit=limit)
    summary.issues_scanned = len(candidates)

    if not candidates:
        logger.info("No candidate issues found")
        return summary

    # Step 2: Iterate through candidates with budget tracking
    for i, issue in enumerate(candidates):
        # Budget gate: check remaining session budget
        remaining = session_budget - summary.total_cost_usd
        if remaining <= 0:
            logger.warning("Session budget exhausted ($%.2f spent)", summary.total_cost_usd)
            summary.budget_exhausted = True
            break

        if on_progress:
            on_progress(i + 1, len(candidates), issue, "analyzing")  # type: ignore[operator]

        result_entry: dict = {
            "issue": f"{issue.full_repo}#{issue.number}",
            "status": "pending",
        }

        # Step 2a: Analyze
        try:
            analysis = analyze_issue(issue, config, repository, dry_run)
            summary.issues_analyzed += 1
            summary.total_cost_usd += analysis.cost_usd or 0.0
            result_entry["analysis"] = analysis.rating.value
        except AnalysisRejectedError as e:
            logger.info("Issue rejected: %s", e)
            result_entry["status"] = "rejected"
            summary.results.append(result_entry)
            _delay(rate_delay)
            continue
        except ClaudeError as e:
            logger.warning("Analysis failed for %s#%d: %s", issue.full_repo, issue.number, e)
            result_entry["status"] = "analysis_failed"
            summary.failures += 1
            summary.results.append(result_entry)
            _delay(rate_delay)
            continue

        if on_progress:
            on_progress(i + 1, len(candidates), issue, "resolving")  # type: ignore[operator]

        # Step 2b: Resolve
        try:
            attempt = resolve_issue(issue, analysis, config, repository, dry_run)
            summary.issues_attempted += 1
            summary.total_cost_usd += attempt.cost_usd or 0.0
            result_entry["outcome"] = attempt.outcome.value if attempt.outcome else "unknown"
        except BudgetExceededError as e:
            logger.warning("Budget exceeded: %s", e)
            result_entry["status"] = "budget_exceeded"
            summary.budget_exhausted = True
            summary.failures += 1
            summary.results.append(result_entry)
            break
        except TestsFailedError as e:
            logger.warning("Tests failed for %s#%d: %s", issue.full_repo, issue.number, e)
            result_entry["status"] = "tests_failed"
            summary.failures += 1
            summary.results.append(result_entry)
            _delay(rate_delay)
            continue
        except Exception as e:
            logger.error("Resolution failed for %s#%d: %s", issue.full_repo, issue.number, e)
            result_entry["status"] = "resolution_failed"
            summary.failures += 1
            summary.results.append(result_entry)
            _delay(rate_delay)
            continue

        # Step 2c: Submit PR if resolution succeeded
        if attempt.outcome and attempt.outcome.value in ("pr_submitted", "untested"):
            try:
                pr_url = submit_pr(
                    issue=issue,
                    attempt=attempt,
                    analysis=analysis,
                    config=config,
                    auto_pr=auto_pr,
                    dry_run=dry_run,
                )
                if pr_url:
                    summary.prs_submitted += 1
                    result_entry["pr_url"] = pr_url
                result_entry["status"] = "success"
            except Exception as e:
                logger.error("PR submission failed for %s#%d: %s", issue.full_repo, issue.number, e)
                result_entry["status"] = "pr_failed"
                summary.failures += 1
        else:
            result_entry["status"] = "failed"
            summary.failures += 1

        summary.results.append(result_entry)
        _delay(rate_delay)

    return summary


def _delay(seconds: int) -> None:
    """Rate-limiting delay between issues."""
    if seconds > 0:
        time.sleep(seconds)
