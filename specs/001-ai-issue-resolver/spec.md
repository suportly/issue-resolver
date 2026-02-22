# Feature Specification: AI-Powered GitHub Issue Resolution Tool

**Feature Branch**: `001-ai-issue-resolver`
**Created**: 2026-02-22
**Status**: Draft
**Input**: User description: "CLI tool that automates the full cycle: scan GitHub for resolvable issues, analyze with AI, fork, implement the fix, run tests, and submit a PR. Born from the real experience of resolving DRF issue #9501."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resolve a Specific Known Issue (Priority: P1)

A developer has found a GitHub issue they want to fix. They provide the issue URL and the tool handles the entire resolution lifecycle: analyze solvability, fork the repository, implement the fix using an AI coding agent, run the project's tests, and either submit a PR automatically or present changes for review. This is the foundational vertical slice — one command, one issue, one PR.

**Why this priority**: This is the core value proposition and the critical path. Every other feature depends on this working end-to-end. It directly replicates the real-world workflow that inspired the tool (DRF #9501). If only this story ships, the tool already delivers value. The Project Shipper principle applies: ship this as an independently usable tool before building anything else.

**Independent Test**: Can be fully tested by running the tool against a real GitHub issue URL and verifying it produces a valid pull request with passing tests. Alternatively, testable in dry-run mode against any public issue to verify analysis and planning without side effects. Integration tests mock external boundaries (GitHub API, AI agent CLI, git) at the subprocess level, not deep inside the application.

**Acceptance Scenarios**:

1. **Given** a valid GitHub issue URL, **When** the user runs the resolve command, **Then** the system validates prerequisites (external tools installed and authenticated), verifies the issue is still open and unassigned, analyzes solvability, forks the repo (or reuses existing fork synced with upstream), implements a fix, runs the project's tests, and presents the result (diff + analysis + cost) to the user.
2. **Given** a valid GitHub issue URL and the `--auto-pr` flag, **When** the user runs the resolve command and tests pass, **Then** the system creates a pull request that references the original issue ("refs #N"), follows the project's PR template and CONTRIBUTING.md guidelines, includes a meaningful description of the change, and notes any limitations.
3. **Given** a valid GitHub issue URL and the `--dry-run` flag, **When** the user runs the resolve command, **Then** the system performs analysis and shows the solvability assessment (rating, confidence, reasoning) and plan but creates no forks, pushes no branches, and opens no PRs — zero external side effects, verifiable by auditing all subprocess calls.
4. **Given** an issue the AI determines is not solvable (feature request, design discussion, requires maintainer decisions, ambiguous reproduction, no clear error or test case), **When** the analysis completes, **Then** the system reports the solvability rating, confidence score, and specific reasoning, records the analysis result in the database, and does not attempt resolution.
5. **Given** the AI implements a fix but the project's tests fail, **When** the resolution completes, **Then** the system reports the test failures with output, preserves the workspace for manual inspection (logging the full workspace path), records the attempt as "tests_failed", and does not submit a PR.
6. **Given** the per-resolution budget is exceeded during the AI fix attempt, **When** the budget limit is approached, **Then** the system stops the AI agent before exceeding the limit (< 10% variance), preserves the workspace, records the partial attempt with actual cost data, and reports what happened.
7. **Given** the required external tools (AI agent CLI, GitHub CLI, git) are not installed or authenticated, **When** the user runs any command, **Then** the system validates all prerequisites before any work begins and fails with clear, actionable error messages listing exactly what's missing and how to fix it.

---

### User Story 2 - Scan and Discover Resolvable Issues (Priority: P2)

A developer wants to find open-source issues the tool can solve. They run a scan command with filters (language, labels, repository popularity, issue age) and receive a ranked list of candidate issues. The scan persists results for deduplication across runs and respects GitHub API rate limits.

**Why this priority**: Discovery feeds the resolution pipeline and enables batch processing (P3). Without scanning, the user must manually find issue URLs. This makes the tool proactive rather than reactive. Each command does one thing well — scan discovers, resolve fixes — and they compose into pipelines.

**Independent Test**: Can be tested by running the scan command with mocked GitHub API responses and verifying it returns a filtered, deduplicated list persisted in the database, with correct exclusion of previously attempted issues.

**Acceptance Scenarios**:

1. **Given** search criteria (language, labels, minimum stars, maximum age), **When** the user runs the scan command, **Then** the system queries GitHub and returns a list of candidate issues matching the criteria, excluding issues that have assignees, linked PRs, or have been previously attempted (any status in database).
2. **Given** previous scan results in the database, **When** the user runs a new scan, **Then** the system performs idempotent deduplication — no issue appears twice, and previously attempted issues are excluded regardless of outcome.
3. **Given** a limit parameter, **When** the user runs scan with `--limit N`, **Then** the system returns at most N issues, ranked by solvability potential (clear bug reports with reproduction steps and specific error messages ranked highest).
4. **Given** GitHub rate limits are approached during scanning, **When** the API returns a 429 status, **Then** the system applies exponential backoff with jitter (max 3 retries) and logs each retry with wait duration.
5. **Given** no matching issues found for the criteria, **When** the scan completes, **Then** the system reports that no suitable issues were found with the active filter settings displayed.
6. **Given** specific target repositories configured, **When** the user runs a scan, **Then** the system searches only within those repositories. Given no targets configured, the system performs a broad GitHub search.

---

### User Story 3 - Automated Pipeline: Scan + Analyze + Resolve (Priority: P3)

A developer wants to run the full pipeline unattended — scanning for issues, analyzing solvability, and resolving the most promising ones within a session budget. This can run on a schedule (cron/CI) for continuous open-source contribution. The orchestrator manages state, budget, and rate limits across all issues.

**Why this priority**: This is the "hands-off" mode that maximizes value for power users but depends on P1 and P2 being solid first. It introduces session-level budget management and multi-issue orchestration — the system must be smart about where it spends money (cheap analysis to filter, expensive resolution only on promising issues).

**Independent Test**: Can be tested by running the pipeline command with `--max-issues 1 --dry-run` and verifying the full flow executes from scan through analysis without external side effects. Budget enforcement tested with mock AI agent returning configurable costs.

**Acceptance Scenarios**:

1. **Given** a configured pipeline with `--max-issues 5`, **When** the user runs the pipeline, **Then** the system scans, analyzes solvability for candidates (using a cheaper/faster model), and attempts resolution (using a more capable model) on issues that meet the confidence threshold (>= 70%), processing up to the limit.
2. **Given** a session budget limit, **When** the cumulative cost across all issues exceeds the budget, **Then** the system stops processing new issues immediately, reports all work completed with per-issue cost breakdowns, and exits with a clear budget-exceeded status.
3. **Given** a pipeline run with multiple issues, **When** one issue fails (analysis error, resolution error, test failure, empty diff, timeout), **Then** the system logs the failure with category and detailed reason, preserves the workspace if applicable, records it in the database, and continues to the next issue.
4. **Given** configurable rate limits for both GitHub API calls and AI agent invocations, **When** the pipeline runs, **Then** the system respects the configured minimum delay between issues and per-hour invocation limits, preventing abuse of external services.

---

### User Story 4 - View History, Statistics, and Resolution Funnel (Priority: P4)

A developer wants to understand the tool's effectiveness — success rates segmented by language and issue type, costs incurred, solvability prediction accuracy (calibration), and the full resolution funnel (scan → analyze → resolve → test → PR). This enables data-driven decisions about which issues to target and how to tune configuration.

**Why this priority**: Operational visibility is essential for trust, cost management, and improving the tool over time. The Analytics Reporter and Feedback Synthesizer agents provide the analytical framework. However, this is a reporting layer — the underlying data collection happens in P1-P3.

**Independent Test**: Can be tested by populating the database with known resolution records and verifying the status command outputs accurate, correctly segmented statistics matching the input data.

**Acceptance Scenarios**:

1. **Given** previous resolution attempts in the database, **When** the user runs the status command with `--summary`, **Then** the system displays: total attempts, success rate, total cost, average cost per issue, and breakdown by outcome category (pr_submitted, tests_failed, analysis_rejected, budget_exceeded, empty_diff, timeout).
2. **Given** resolution data across multiple languages, **When** the user views statistics, **Then** results are segmented by language showing per-language success rate and average cost — because "30% overall success" is misleading if Python bugs succeed at 60% and JavaScript refactors succeed at 5%.
3. **Given** solvability analyses and actual resolution outcomes, **When** the user views statistics, **Then** the system shows solvability prediction calibration — comparing predicted confidence bands (90-100%, 70-89%, 50-69%, <50%) to actual success rates.
4. **Given** the full pipeline history, **When** the user views statistics, **Then** the system shows the resolution funnel: issues discovered → passed solvability filter → resolution attempted → non-empty diff → tests pass → PR submitted, with drop-off counts at each stage.
5. **Given** no previous attempts, **When** the user runs the status command, **Then** the system reports that no history is available yet.

---

### User Story 5 - Configuration Management (Priority: P5)

A developer wants to customize the tool's behavior — search filters, budget limits (per-analysis, per-resolution, per-session), rate limits, target repositories, workspace settings, and autonomy level (auto-PR vs. manual review). Configuration follows a clear hierarchy: CLI flags > environment variables > config file > sensible defaults.

**Why this priority**: Sensible defaults should allow the tool to work out of the box with zero configuration. Custom configuration enhances the experience but is not required for initial usage. Secrets (tokens, API keys) always come from environment variables, never from config files.

**Independent Test**: Can be tested by modifying config values and verifying the tool respects them, by running with conflicting CLI flags and config to verify hierarchy, and by running with no config file to verify defaults.

**Acceptance Scenarios**:

1. **Given** a config file with custom search labels, language filters, and budget limits, **When** the user runs any command, **Then** the system uses those settings.
2. **Given** no config file exists, **When** the user runs any command, **Then** the system uses sensible defaults for all settings and operates correctly.
3. **Given** the user runs `config --init`, **When** the command completes, **Then** a well-documented example configuration file is generated with all available options, their defaults, and comments explaining each setting.
4. **Given** the user runs `config --show`, **When** the command completes, **Then** the system displays the current effective configuration (merged from all sources) with secrets redacted.
5. **Given** a CLI flag that conflicts with a config file value, **When** the user runs a command, **Then** the CLI flag takes precedence (CLI > env > config > defaults).
6. **Given** environment variables for secrets, **When** the tool runs, **Then** it uses environment variables for sensitive values and never persists secrets to the config file or database.

---

### Edge Cases

- **Issue closed since scan**: Before attempting resolution, the system verifies the issue is still open and no PR has been submitted since scanning. If stale, skip and log reason.
- **No test suite in target repo**: The system still attempts the fix but warns that test validation was skipped, and flags the attempt record as "untested."
- **Fork already exists**: The system reuses the existing fork, syncs with upstream (`fetch upstream && rebase upstream/main`), rather than failing or creating a duplicate.
- **Empty diff (AI produces no changes)**: The system reports no fix was generated, marks the attempt as "empty_diff", and does not attempt PR submission.
- **Malformed AI output**: If the AI agent returns unparseable or schema-invalid JSON, the system logs the raw output for debugging, marks the attempt as "parse_error", and does not crash.
- **Budget exceeded mid-resolution**: The system stops the AI agent before exceeding the limit (budget enforcement triggers proactively, not reactively — variance < 10%), preserves the workspace, and records actual cost.
- **GitHub rate limit (429)**: Exponential backoff with jitter, max 3 retries. If all retries exhausted, mark the operation as failed and move to next issue in pipeline mode.
- **AI agent timeout**: If the AI agent exceeds the configured timeout, the system kills the subprocess, marks the attempt as "timeout", logs the duration, and preserves the workspace.
- **Workspace disk space exhaustion**: The system detects clone/write failures, reports the error clearly, and does not leave partial state that could confuse subsequent runs.
- **Pre-existing test failures in target repo**: Ideally the system establishes a baseline test run before applying the fix to distinguish "tests broken by our fix" from "tests already broken." If baseline is not feasible, report test output with a caveat.
- **Concurrent runs against same issue**: The database deduplication check prevents multiple resolution attempts against the same issue. If already in-progress or attempted, the system skips it.
- **Contributing guidelines mention requirements the tool cannot verify**: If CONTRIBUTING.md mentions CI checks, code style, or other requirements beyond test execution, the system includes a note in the PR description acknowledging those requirements.

## Requirements *(mandatory)*

### Functional Requirements

**Core Resolution (P1)**

- **FR-001**: System MUST accept a GitHub issue URL and execute the full resolution lifecycle: validate prerequisites, verify issue freshness, analyze solvability, fork repository (or reuse existing fork), implement fix via AI agent, run project tests, and optionally submit a PR.
- **FR-002**: System MUST analyze issues for solvability before attempting resolution, producing a structured assessment with: solvability rating, confidence score (0.0-1.0), complexity estimate, and human-readable reasoning. Analysis uses a cheaper/faster AI model to minimize cost.
- **FR-003**: System MUST only attempt resolution on issues assessed as solvable or likely solvable with confidence >= 70%. Issues below this threshold are recorded as "filtered" with reasoning.
- **FR-004**: System MUST verify that the AI agent produced actual changes (non-empty diff) before proceeding to test execution or PR submission.
- **FR-005**: System MUST detect the target project's test runner (supporting common runners across languages) and execute tests after implementing a fix, reporting pass/fail status with output.
- **FR-006**: System MUST read and incorporate the target project's CONTRIBUTING.md and PR template when submitting pull requests. If not found, fall back to a sensible default template.
- **FR-007**: System MUST validate that required external tools (AI agent CLI, GitHub CLI, git) are installed and properly authenticated before executing any operation, failing with actionable error messages listing what's missing and how to fix it.

**Discovery & Scanning (P2)**

- **FR-008**: System MUST search GitHub for issues matching configurable criteria: labels, programming language, repository stars, issue age, absence of assignees, and absence of linked PRs.
- **FR-009**: System MUST support targeting specific repositories or performing broad searches across GitHub.
- **FR-010**: System MUST perform idempotent deduplication — issues already in the database (regardless of attempt status) are excluded from new scan results.

**Pipeline & Orchestration (P3)**

- **FR-011**: System MUST enforce configurable budget limits at three tiers: per-analysis, per-resolution, and per-session (total across all issues in one run). Budget enforcement must trigger proactively (before the limit is exceeded), with variance < 10%.
- **FR-012**: System MUST stop the pipeline gracefully when the session budget is exceeded, reporting all work completed with per-issue cost breakdowns.
- **FR-013**: System MUST handle failures gracefully per category: analysis failures skip to next issue; resolution failures preserve workspace; test failures preserve workspace for inspection; all failures are recorded with category and detail in the database.
- **FR-014**: System MUST apply rate limiting for both GitHub API calls and AI agent invocations, with configurable limits (requests per minute for GitHub, invocations per hour for AI, minimum delay between issues).
- **FR-015**: System MUST apply exponential backoff with jitter (max 3 retries) when encountering GitHub rate limits (HTTP 429), logging each retry with wait duration.

**Modes & Safety**

- **FR-016**: System MUST support `--dry-run` mode that produces zero external side effects — no forks created, no branches pushed, no PRs opened, no GitHub state mutations. Analysis and planning only.
- **FR-017**: System MUST support both interactive mode (user reviews diff, analysis, and cost before PR submission) and automatic mode (`--auto-pr` creates PR without confirmation).

**State & Persistence**

- **FR-018**: System MUST persist all discovered issues, analysis results, and resolution attempts to a local database to prevent duplicate work and enable reporting.
- **FR-019**: System MUST record per-attempt data: issue reference, status, outcome category (pr_submitted, tests_failed, empty_diff, resolution_failed, analysis_failed, budget_exceeded, timeout, parse_error), cost incurred, duration, workspace path, and PR URL (if submitted).

**Workspace Management**

- **FR-020**: System MUST manage temporary workspaces for cloned repositories, cleaning up successful workspaces by default and preserving failed ones for debugging, with workspace paths logged for every attempt.
- **FR-021**: System MUST verify issue freshness before resolution — checking that the issue is still open, unassigned, and has no linked PRs since scanning. If stale, skip with logged reason.

**Reporting & Statistics (P4)**

- **FR-022**: System MUST provide a status command showing: total attempts, success rate, total cost, average cost per issue, outcome breakdown by category, and per-language segmentation.
- **FR-023**: System MUST track and display the resolution funnel: issues discovered → passed solvability filter → resolution attempted → non-empty diff → tests pass → PR submitted, with counts and drop-off rates at each stage.
- **FR-024**: System MUST track solvability prediction calibration — comparing predicted confidence bands to actual resolution outcomes — enabling users to assess and improve analysis quality over time.

**Configuration (P5)**

- **FR-025**: System MUST load configuration following the hierarchy: CLI flags > environment variables > config file > sensible defaults. Secrets (tokens, API keys) MUST only come from environment variables, never persisted to config files or database.
- **FR-026**: System MUST generate a documented example configuration file on demand and display the current effective configuration (with secrets redacted) on request.

**Observability**

- **FR-027**: System MUST provide structured, human-readable logging with configurable verbosity levels. Every significant action (prerequisite check, scan, analysis, fork, resolution, test run, PR submission) is logged with relevant context including costs and durations.
- **FR-028**: System MUST create pull requests that reference the original issue ("refs #N"), follow the target project's PR template, describe the change and approach clearly, and note any limitations or untested aspects.

### Key Entities

- **Issue**: A GitHub issue discovered through scanning. Key attributes: repository (owner/name), issue number, title, body, labels, creation date, URL, assignee status, linked PR status. Lifecycle: discovered → analyzed → attempted (or filtered/skipped).
- **Analysis**: An AI-generated solvability assessment for an issue. Key attributes: solvability rating (solvable, likely_solvable, unlikely_solvable, unsolvable), confidence score (0.0-1.0), complexity estimate, reasoning text, cost incurred, model used. Serves as the gate for resolution attempts — only issues passing the confidence threshold proceed.
- **Attempt**: A record of a resolution attempt. Key attributes: associated issue, status (pending, in_progress, succeeded, failed), outcome category (pr_submitted, tests_failed, empty_diff, resolution_failed, analysis_failed, budget_exceeded, timeout, parse_error), cost incurred, duration, workspace path, PR URL (if submitted), AI agent session metadata (turns used, model). Each attempt is a permanent record for funnel analytics and cost tracking.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can resolve a known GitHub issue end-to-end (from URL to submitted PR) with a single command, requiring no manual coding intervention.
- **SC-002**: The scanning feature returns relevant, actionable issues — at least 70% of returned issues are genuinely open, unassigned, and match the configured criteria.
- **SC-003**: The solvability analysis correctly filters out unsolvable issues (feature requests, design discussions, vague reports without reproduction steps) at least 80% of the time, preventing wasted resolution budget.
- **SC-004**: For issues the tool attempts to resolve, at least 30% result in a PR where the project's tests pass. This is the north star metric — tracked over time and segmented by language and issue type.
- **SC-005**: Total cost per resolved issue stays within the user-configured budget, with no overruns exceeding 10% of the per-resolution limit. Session budget enforcement is accurate to within 10% variance.
- **SC-006**: The tool completes a single issue resolution (from analysis through PR submission) within 10 minutes for typical issues (simple bug fixes in well-structured projects).
- **SC-007**: Dry-run mode produces zero side effects — no forks, no branches, no PRs, no GitHub state mutations. Verifiable by testing that no mutating subprocess calls are made.
- **SC-008**: Failed attempts preserve enough context (workspace with code changes, logs, analysis results, cost data, workspace path) for the user to understand what went wrong and potentially complete the fix manually.
- **SC-009**: The status command provides accurate, segmented statistics — cost tracking matches actual AI agent usage within 5% variance, funnel metrics match database records exactly, and per-language breakdowns are correct.
- **SC-010**: The tool can process a batch of 5 issues in a single pipeline run without human intervention (in `--auto-pr` mode), respecting rate limits and session budget.
- **SC-011**: Solvability prediction calibration is trackable — predicted confidence bands (90-100%, 70-89%, etc.) correlate with actual success rates, enabling users to assess and tune analysis quality.
- **SC-012**: The tool is installable and functional with a single setup step (package install + environment variables), with clear prerequisite validation and actionable error messages on first run.

## Assumptions

- Users have the required external tools installed and authenticated: GitHub CLI (`gh`) with a valid token, AI coding agent CLI with a valid API key, and `git`. The tool validates these prerequisites before any operation.
- Target repositories are public GitHub repositories. Private repository support is out of scope for the initial version.
- The AI coding agent CLI supports JSON structured output with cost tracking fields (result, total_cost_usd, duration_ms, num_turns, is_error).
- GitHub's search API provides sufficient filtering capability (labels, language, stars, assignee status, linked PRs) for the discovery use case.
- Shallow clones (`--depth=1`) are sufficient for the AI agent to understand and fix most issues. The AI agent receives minimal but sufficient context: issue description, relevant source files, test structure, and contributing guidelines.
- The tool runs on a developer's local machine or in a CI environment with network access to GitHub and the AI agent API.
- Budget tracking relies on cost information reported by the AI agent CLI and is treated as authoritative.
- Open-source maintainers are receptive to well-crafted, tested, AI-assisted PRs that follow their contributing guidelines. The tool prioritizes PR quality over PR quantity — community respect is a design principle.
- The analysis model (cheaper, faster) and resolution model (more capable, expensive) are different tiers, optimizing cost by spending less on classification and more on actual code generation.
- Solo developer (Alair) + Claude Code AI pair is the development team. Sprint planning is feature-driven, not time-boxed.
