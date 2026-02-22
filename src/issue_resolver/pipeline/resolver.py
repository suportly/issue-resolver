"""Resolution pipeline stage: fork, clone, AI fix, tests, commit."""

from __future__ import annotations

import logging
import re
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
from issue_resolver.workspace.project_detector import (
    DetectedTestRunner,
    detect_install_command,
    detect_test_runner,
)

logger = logging.getLogger(__name__)


def _run_tests(
    test_runner: DetectedTestRunner,
    workspace_path: str,
) -> tuple[int, str, set[str]]:
    """Run tests and extract failed test names.

    Returns:
        Tuple of (return_code, raw_output, set_of_failed_test_ids).
    """
    result = run_with_timeout(
        test_runner.command.split(),
        timeout=test_runner.timeout,
        cwd=workspace_path,
    )
    raw_output = (result.stdout + result.stderr)[:5000]
    failed_tests = _extract_failed_tests(raw_output, test_runner.runner_name)
    return result.returncode, raw_output, failed_tests


def _extract_failed_tests(output: str, runner_name: str) -> set[str]:
    """Extract failed test identifiers from test runner output."""
    failed = set()

    if runner_name in ("pytest", "unittest"):
        # Match pytest FAILED lines: "FAILED tests/foo.py::test_bar - Error"
        for match in re.finditer(r"FAILED\s+(\S+)", output):
            test_id = match.group(1).rstrip(" -")
            failed.add(test_id)

    elif runner_name == "npm":
        # Match "FAIL src/foo.test.js" or "● test name"
        for match in re.finditer(r"FAIL\s+(\S+)", output):
            failed.add(match.group(1))

    elif runner_name == "cargo":
        # Match "test result: FAILED" and "failures:" section
        for match in re.finditer(
            r"----\s+(\S+)\s+stdout\s+----", output,
        ):
            failed.add(match.group(1))

    elif runner_name == "go":
        # Match "--- FAIL: TestName"
        for match in re.finditer(r"---\s+FAIL:\s+(\S+)", output):
            failed.add(match.group(1))

    elif runner_name in ("rspec", "maven", "gradle"):
        # Generic: count failures from summary line
        for match in re.finditer(r"(\d+)\s+failures?", output):
            if int(match.group(1)) > 0:
                failed.add(f"_unknown_failure_{match.group(0)}")

    return failed


def resolve_issue(
    issue: Issue,
    analysis: Analysis,
    config: AppConfig,
    repository: Repository,
    dry_run: bool = False,
) -> Attempt:
    """Execute the full resolution flow for an issue.

    Flow: fork → clone → install deps → baseline tests → invoke AI agent →
          verify changes → run tests → compare with baseline → record attempt.

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

        # Step 2: Install dependencies
        installer = detect_install_command(workspace_path)
        if installer:
            logger.info("Installing dependencies: %s", installer.command)
            install_result = run_with_timeout(
                ["bash", "-c", installer.command],
                timeout=installer.timeout,
                cwd=workspace_path,
            )
            if install_result.returncode != 0:
                logger.warning(
                    "Dependency install had issues (continuing): %s",
                    install_result.stderr[:200]
                    if install_result.stderr
                    else "unknown",
                )

        # Step 3: Detect test runner and read project guidelines
        test_runner = detect_test_runner(workspace_path)
        contributing_md = read_contributing_md(workspace_path)
        pr_template = read_pr_template(workspace_path)

        test_command = test_runner.command if test_runner else None

        # Step 4: Run baseline tests (before any changes)
        baseline_failures: set[str] = set()
        baseline_returncode = 0
        if test_runner:
            logger.info("Running baseline tests: %s", test_runner.command)
            baseline_returncode, _, baseline_failures = _run_tests(
                test_runner, workspace_path,
            )
            if baseline_failures:
                logger.info(
                    "Baseline: %d pre-existing test failure(s)",
                    len(baseline_failures),
                )
            elif baseline_returncode != 0:
                # Tests fail but we can't parse which ones — record the code
                logger.info(
                    "Baseline tests exit code: %d", baseline_returncode,
                )

        # Step 5: Invoke AI agent for resolution
        install_command = installer.command if installer else None
        prompt = build_resolution_prompt(
            issue=issue,
            contributing_md=contributing_md,
            pr_template=pr_template,
            test_command=test_command,
            install_command=install_command,
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

        claude_result = parse_response(
            stdout, stderr, returncode, timeout_expired,
        )
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
            raise BudgetExceededError(
                f"Resolution budget exceeded: ${claude_result.cost_usd:.2f}"
            )

        if claude_result.outcome in ("process_error", "parse_error"):
            attempt.status = AttemptStatus.FAILED
            attempt.outcome = OutcomeCategory(claude_result.outcome)
            attempt.duration_ms = int((time.time() - start_time) * 1000)
            repository.update_attempt(attempt)
            return attempt

        # Step 6: Verify non-empty diff (FR-004)
        if not has_changes(workspace_path):
            attempt.status = AttemptStatus.FAILED
            attempt.outcome = OutcomeCategory.EMPTY_DIFF
            attempt.duration_ms = int((time.time() - start_time) * 1000)
            repository.update_attempt(attempt)
            return attempt

        attempt.diff_summary = get_diff_summary(workspace_path)

        # Step 7: Run project tests and compare with baseline (FR-005)
        if test_runner:
            logger.info("Running post-fix tests: %s", test_runner.command)
            post_returncode, post_output, post_failures = _run_tests(
                test_runner, workspace_path,
            )
            attempt.test_output = post_output

            if post_returncode == 0:
                # All tests pass
                attempt.status = AttemptStatus.SUCCEEDED
                attempt.outcome = OutcomeCategory.PR_SUBMITTED
            elif (
                test_runner.runner_name == "pytest"
                and post_returncode == 5
            ):
                # pytest exit code 5 = no tests collected
                logger.info("No tests collected — treating as untested")
                attempt.status = AttemptStatus.SUCCEEDED
                attempt.outcome = OutcomeCategory.UNTESTED
            else:
                # Tests failed — check if these are new regressions
                new_failures = post_failures - baseline_failures
                if new_failures:
                    logger.error(
                        "New test regressions: %s", new_failures,
                    )
                    attempt.status = AttemptStatus.FAILED
                    attempt.outcome = OutcomeCategory.TESTS_FAILED
                    attempt.duration_ms = int(
                        (time.time() - start_time) * 1000
                    )
                    repository.update_attempt(attempt)
                    raise TestsFailedError(
                        f"New test regressions ({len(new_failures)}): "
                        f"{', '.join(sorted(new_failures)[:5])}"
                    )

                if not post_failures and baseline_returncode != 0:
                    # Can't parse failures but baseline also failed
                    # with same or worse exit code — treat as OK
                    logger.info(
                        "Tests exit code %d matches baseline %d "
                        "— no new regressions detected",
                        post_returncode,
                        baseline_returncode,
                    )
                    attempt.status = AttemptStatus.SUCCEEDED
                    attempt.outcome = OutcomeCategory.PR_SUBMITTED
                elif post_failures and post_failures <= baseline_failures:
                    # All failures are pre-existing
                    logger.info(
                        "All %d failure(s) are pre-existing — "
                        "no new regressions",
                        len(post_failures),
                    )
                    attempt.status = AttemptStatus.SUCCEEDED
                    attempt.outcome = OutcomeCategory.PR_SUBMITTED
                else:
                    # Fallback: can't determine, treat as failure
                    attempt.status = AttemptStatus.FAILED
                    attempt.outcome = OutcomeCategory.TESTS_FAILED
                    attempt.duration_ms = int(
                        (time.time() - start_time) * 1000
                    )
                    repository.update_attempt(attempt)
                    raise TestsFailedError(
                        f"Tests failed. Output: {post_output[:500]}"
                    )
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
