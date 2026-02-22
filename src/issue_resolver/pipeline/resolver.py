"""Resolution pipeline stage: fork, clone, AI fix, tests, commit."""

from __future__ import annotations

import logging
import time

from issue_resolver.claude.invoker import invoke
from issue_resolver.claude.parser import parse_response
from issue_resolver.claude.prompts import build_resolution_prompt
from issue_resolver.config.schema import AppConfig
from issue_resolver.db.repository import Repository
from issue_resolver.github.pr import read_contributing_md, read_pr_template
from issue_resolver.github.repo_ops import (
    clone_repo,
    create_branch,
    fork_repo,
    get_diff_summary,
    has_changes,
)
from issue_resolver.models.analysis import Analysis
from issue_resolver.models.attempt import Attempt
from issue_resolver.models.enums import AttemptStatus, OutcomeCategory
from issue_resolver.models.issue import Issue
from issue_resolver.utils.exceptions import BudgetExceededError, TestsFailedError
from issue_resolver.utils.subprocess_utils import run_with_timeout
from issue_resolver.workspace.manager import create_workspace
from issue_resolver.workspace.project_detector import detect_test_runner

logger = logging.getLogger(__name__)


def resolve_issue(
    issue: Issue,
    analysis: Analysis,
    config: AppConfig,
    repository: Repository,
    dry_run: bool = False,
) -> Attempt:
    """Execute the full resolution flow for an issue.

    Flow: fork → clone → detect test runner → invoke AI agent →
          verify changes → run tests → record attempt.

    Args:
        issue: The issue to resolve.
        analysis: The solvability analysis.
        config: Application configuration.
        repository: Database repository.
        dry_run: If True, skip actual resolution.

    Returns:
        The recorded Attempt with outcome.
    """
    start_time = time.time()
    branch_name = f"fix/issue-{issue.number}"

    attempt = Attempt(
        issue_id=issue.id,
        status=AttemptStatus.IN_PROGRESS,
        branch_name=branch_name,
        model=config.claude.model,
    )
    repository.insert_attempt(attempt)

    if dry_run:
        attempt.status = AttemptStatus.SUCCEEDED
        attempt.outcome = OutcomeCategory.PR_SUBMITTED
        attempt.cost_usd = 0.0
        attempt.duration_ms = 0
        attempt.diff_summary = "[DRY RUN] Would implement fix and run tests"
        repository.update_attempt(attempt)
        return attempt

    try:
        # Step 1: Fork and clone
        fork_name = fork_repo(issue.repo_owner, issue.repo_name)
        workspace_path = create_workspace(
            config.workspace.base_dir, issue.repo_owner, issue.repo_name
        )
        attempt.workspace_path = workspace_path
        repository.update_attempt(attempt)

        clone_repo(fork_name, workspace_path, depth=1)
        create_branch(workspace_path, branch_name)

        # Step 2: Detect test runner and read project guidelines
        test_runner = detect_test_runner(workspace_path)
        contributing_md = read_contributing_md(workspace_path)
        pr_template = read_pr_template(workspace_path)

        test_command = test_runner.command if test_runner else None

        # Step 3: Invoke AI agent for resolution
        prompt = build_resolution_prompt(
            issue=issue,
            contributing_md=contributing_md,
            pr_template=pr_template,
            test_command=test_command,
        )

        stdout, stderr, returncode, timeout_expired = invoke(
            prompt=prompt,
            output_format="json",
            max_turns=30,
            model=config.claude.model,
            permission_mode="bypassPermissions",
            max_budget_usd=config.claude.resolution_max_budget_usd,
            timeout=config.claude.timeout_seconds,
            cwd=workspace_path,
        )

        claude_result = parse_response(stdout, stderr, returncode, timeout_expired)
        attempt.cost_usd = claude_result.cost_usd
        attempt.num_turns = claude_result.num_turns

        # Handle AI agent failures
        if claude_result.outcome == "timeout":
            attempt.status = AttemptStatus.FAILED
            attempt.outcome = OutcomeCategory.TIMEOUT
            attempt.duration_ms = int((time.time() - start_time) * 1000)
            repository.update_attempt(attempt)
            return attempt

        if claude_result.outcome == "budget_exceeded":
            attempt.status = AttemptStatus.FAILED
            attempt.outcome = OutcomeCategory.BUDGET_EXCEEDED
            attempt.duration_ms = int((time.time() - start_time) * 1000)
            repository.update_attempt(attempt)
            raise BudgetExceededError(f"Resolution budget exceeded: ${claude_result.cost_usd:.2f}")

        if claude_result.outcome in ("process_error", "parse_error"):
            attempt.status = AttemptStatus.FAILED
            attempt.outcome = OutcomeCategory(claude_result.outcome)
            attempt.duration_ms = int((time.time() - start_time) * 1000)
            repository.update_attempt(attempt)
            return attempt

        # Step 4: Verify non-empty diff (FR-004)
        if not has_changes(workspace_path):
            attempt.status = AttemptStatus.FAILED
            attempt.outcome = OutcomeCategory.EMPTY_DIFF
            attempt.duration_ms = int((time.time() - start_time) * 1000)
            repository.update_attempt(attempt)
            return attempt

        attempt.diff_summary = get_diff_summary(workspace_path)

        # Step 5: Run project tests (FR-005)
        if test_runner:
            logger.info("Running tests: %s", test_runner.command)
            test_result = run_with_timeout(
                test_runner.command.split(),
                timeout=test_runner.timeout,
                cwd=workspace_path,
            )
            attempt.test_output = (test_result.stdout + test_result.stderr)[:5000]

            if test_result.returncode != 0:
                # pytest exit code 5 = no tests collected (not a failure)
                if test_runner.runner_name == "pytest" and test_result.returncode == 5:
                    logger.info("No tests collected — treating as untested")
                    attempt.status = AttemptStatus.SUCCEEDED
                    attempt.outcome = OutcomeCategory.UNTESTED
                else:
                    attempt.status = AttemptStatus.FAILED
                    attempt.outcome = OutcomeCategory.TESTS_FAILED
                    attempt.duration_ms = int((time.time() - start_time) * 1000)
                    repository.update_attempt(attempt)
                    raise TestsFailedError(f"Tests failed. Output: {attempt.test_output[:500]}")
            else:
                attempt.status = AttemptStatus.SUCCEEDED
                attempt.outcome = OutcomeCategory.PR_SUBMITTED
        else:
            # No test suite detected
            attempt.status = AttemptStatus.SUCCEEDED
            attempt.outcome = OutcomeCategory.UNTESTED

        attempt.duration_ms = int((time.time() - start_time) * 1000)
        repository.update_attempt(attempt)
        return attempt

    except (BudgetExceededError, TestsFailedError):
        raise
    except Exception as e:
        logger.error("Resolution failed: %s", e)
        attempt.status = AttemptStatus.FAILED
        attempt.outcome = OutcomeCategory.RESOLUTION_FAILED
        attempt.duration_ms = int((time.time() - start_time) * 1000)
        repository.update_attempt(attempt)
        return attempt
