# Tasks: AI-Powered GitHub Issue Resolution Tool

**Input**: Design documents from `/specs/001-ai-issue-resolver/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — the spec verification checklist requires `pytest tests/ -v — all tests pass` and the plan defines explicit test file structure.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/issue_resolver/` source, `tests/` at repository root
- Entry point: `src/issue_resolver/__main__.py`
- CLI entrypoint in pyproject.toml: `issue-resolver = "issue_resolver.cli:app"`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization — directory structure, dependencies, dev tooling

- [x] T001 Create full project directory structure with all `__init__.py` files per plan.md starting with src/issue_resolver/__init__.py (subdirectories: cli/, config/, models/, db/, github/, claude/, pipeline/, workspace/, utils/; tests/ with unit/, integration/, fixtures/issues/, fixtures/claude_responses/, fixtures/configs/)
- [x] T002 Create pyproject.toml with project metadata, dependencies (typer>=0.9, rich>=13.0, pydantic>=2.5, pydantic-settings>=2.1, pyyaml>=6.0, sqlite-utils>=3.36), dev dependencies (pytest, pytest-cov, ruff, mypy), entry point `issue-resolver`, and tool configuration for ruff/mypy/pytest in pyproject.toml
- [x] T003 [P] Create config.example.yaml with all configuration options, defaults, and comments per quickstart.md configuration section in config.example.yaml

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented — models, config, database, utils, CLI skeleton, GitHub client base

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Models & Enums

- [x] T004 [P] Create enums module with SolvabilityRating (solvable, likely_solvable, unlikely_solvable, unsolvable), AttemptStatus (pending, in_progress, succeeded, failed), and OutcomeCategory (pr_submitted, tests_failed, empty_diff, resolution_failed, analysis_failed, budget_exceeded, timeout, parse_error, stale_issue, untested) as string enums in src/issue_resolver/models/enums.py
- [x] T005 [P] Create Issue Pydantic model with fields per data-model.md (id, repo_owner, repo_name, number, title, body, labels, url, state, has_assignees, has_linked_prs, language, repo_stars, created_at, discovered_at) and unique constraint on (repo_owner, repo_name, number) in src/issue_resolver/models/issue.py
- [x] T006 [P] Create Analysis Pydantic model with fields per data-model.md (id, issue_id, rating, confidence, complexity, reasoning, cost_usd, model, duration_ms, created_at) with confidence validation (0.0-1.0) in src/issue_resolver/models/analysis.py
- [x] T007 [P] Create Attempt Pydantic model with fields per data-model.md (id, issue_id, status, outcome, cost_usd, duration_ms, workspace_path, pr_url, pr_number, branch_name, num_turns, model, test_output, diff_summary, created_at, updated_at) in src/issue_resolver/models/attempt.py

### Utils

- [x] T008 [P] Create exception hierarchy with base IssueResolverError plus: PrerequisiteError, BudgetExceededError, AnalysisRejectedError, TestsFailedError, RateLimitError, ClaudeError, GitHubError, ConfigError, WorkspaceError in src/issue_resolver/utils/exceptions.py
- [x] T009 [P] Create structured logging module with Rich handler, configurable verbosity (DEBUG for --verbose, INFO default), stderr output, and setup_logging(verbose: bool) function in src/issue_resolver/utils/logging.py
- [x] T010 [P] Create subprocess helpers with run_with_timeout(cmd, timeout, cwd) returning CompletedProcess, and run_with_retry(cmd, max_retries=3, backoff_base=1.0) with exponential backoff + jitter for rate limit handling in src/issue_resolver/utils/subprocess_utils.py

### Configuration

- [x] T011 Create Pydantic settings schema with nested models: SearchConfig (labels, languages, min_stars, max_age_days, exclude_assignees, exclude_linked_prs), TargetsConfig (repos, exclude_repos), ClaudeConfig (model, analysis_max_budget_usd, resolution_max_budget_usd, total_session_budget_usd, timeout_seconds), WorkspaceConfig (base_dir, cleanup_on_success, cleanup_on_failure), RateLimitConfig (github_requests_per_minute, claude_invocations_per_hour, min_delay_between_issues_seconds), and root AppConfig in src/issue_resolver/config/schema.py
- [x] T012 Create config loader with file discovery chain (--config flag → ISSUE_RESOLVER_CONFIG env → .issue-resolver.yaml in cwd → ~/.config/issue-resolver/config.yaml → defaults), YAML parsing, and merge with env var overrides in src/issue_resolver/config/loader.py

### Database

- [x] T013 Create SQLite engine with WAL mode, foreign_keys=ON, busy_timeout=30000, schema_version table, and migration system (sequential numbered migrations applied at startup) with full schema from data-model.md (issues, analyses, attempts tables + indexes) in src/issue_resolver/db/engine.py
- [x] T014 Create repository module with CRUD operations: upsert_issue, get_issue_by_repo, insert_analysis, insert_attempt, update_attempt, get_unattempted_issues, issue_exists (deduplication), and database path default (~/.issue-resolver/data.db) in src/issue_resolver/db/repository.py

### CLI Skeleton

- [x] T015 [P] Create exit code constants: OK=0, GENERAL_ERROR=1, PREREQUISITE_FAILED=2, BUDGET_EXCEEDED=3, ANALYSIS_REJECTED=4, TESTS_FAILED=5 per contracts/cli-commands.md in src/issue_resolver/cli/exit_codes.py
- [x] T016 [P] Create Rich console with custom theme for consistent terminal output in src/issue_resolver/cli/console.py
- [x] T017 Create GlobalState dataclass with fields (dry_run, verbose, auto_pr, config_path, max_budget, config: AppConfig) and populate in root @app.callback() in src/issue_resolver/cli/context.py
- [x] T018 Create root Typer app with rich_markup_mode="rich", global options (--dry-run, --verbose, --config, --auto-pr, --max-budget, --version) in @app.callback(), and add_typer() composition stubs for all commands in src/issue_resolver/cli/__init__.py
- [x] T019 Create __main__.py entry point with `from issue_resolver.cli import app; app()` in src/issue_resolver/__main__.py

### GitHub Client Base

- [x] T020 Create GitHub CLI wrapper with run_gh(args, capture=True) method, authentication check (gh auth status), rate limit query (gh api rate_limit), and error handling for exit code 1 + stderr pattern matching for rate limits in src/issue_resolver/github/client.py

### Test Infrastructure

- [x] T021 [P] Create test fixtures: sample GitHub issue JSON responses in tests/fixtures/issues/sample_issue.json, sample Claude CLI JSON outputs (success, error, budget_exceeded, timeout) in tests/fixtures/claude_responses/, and sample YAML configs (default, custom, minimal) in tests/fixtures/configs/
- [x] T022 Create conftest.py with shared fixtures: tmp_db (temp SQLite database), mock_config (AppConfig with test defaults), sample_issue (Issue model instance), sample_analysis (Analysis instance), sample_attempt (Attempt instance), and mock subprocess factories in tests/conftest.py

**Checkpoint**: Foundation ready — all models, config, database, utils, CLI skeleton, and test infrastructure in place. User story implementation can now begin.

---

## Phase 3: User Story 1 — Resolve a Specific Known Issue (Priority: P1) 🎯 MVP

**Goal**: A developer provides a GitHub issue URL and the tool resolves it end-to-end: analyze solvability, fork, implement fix via AI agent, run tests, and submit PR. Single command, single issue, single PR.

**Independent Test**: `issue-resolver resolve <url> --dry-run` performs analysis and shows plan without side effects. With `--auto-pr`, full cycle produces a real PR. Integration tests mock all subprocess calls.

### Implementation for User Story 1

#### Claude Integration

- [x] T023 [P] [US1] Create Claude Code CLI subprocess wrapper with invoke(prompt, output_format="json", max_turns, model, permission_mode, max_budget_usd, timeout, cwd) method, handling subprocess.TimeoutExpired, non-zero exit codes, and returning raw stdout/stderr in src/issue_resolver/claude/invoker.py
- [x] T024 [P] [US1] Create prompt templates: build_analysis_prompt(issue) for solvability assessment (returns JSON with rating, confidence, complexity, reasoning), and build_resolution_prompt(issue, contributing_md, pr_template, test_command) for code fix implementation in src/issue_resolver/claude/prompts.py
- [x] T025 [US1] Create Claude JSON output parser per contracts/claude-output.md: parse_response(stdout, stderr, returncode, timeout_expired) returning ClaudeResult dataclass with outcome (success, timeout, process_error, parse_error, budget_exceeded), normalize cost_usd/total_cost_usd, check both is_error and exit code independently in src/issue_resolver/claude/parser.py

#### Workspace Management

- [x] T026 [P] [US1] Create workspace manager with create_workspace(repo_owner, repo_name) returning temp directory path under configured base_dir, cleanup_workspace(path, force=False), and list_workspaces() in src/issue_resolver/workspace/manager.py
- [x] T027 [P] [US1] Create project detector with detect_language(workspace_path) and detect_test_runner(workspace_path) returning (command, timeout) tuple, implementing priority-ordered detection waterfall per research.md Decision 5 (Python/pytest, Python/unittest, JavaScript/npm, Rust/cargo, Go, Ruby/RSpec, Java/Maven, Java/Gradle) in src/issue_resolver/workspace/project_detector.py

#### GitHub Operations

- [x] T028 [P] [US1] Create GitHub repo operations: fork_repo(owner, repo), check_fork_exists(owner, repo), clone_repo(fork_url, workspace_path, depth=1), sync_fork_upstream(workspace_path), create_branch(workspace_path, branch_name), push_branch(workspace_path, branch_name) in src/issue_resolver/github/repo_ops.py
- [x] T029 [P] [US1] Create PR module: create_pr(owner, repo, head_branch, title, body, issue_number), build_pr_body(issue, analysis, diff_summary, test_output, cost, is_untested), read_pr_template(workspace_path), read_contributing_md(workspace_path) in src/issue_resolver/github/pr.py

#### Pipeline Stages

- [x] T030 [US1] Create analyzer pipeline stage: analyze_issue(issue, config, dry_run) invoking Claude with analysis prompt (haiku, 1 turn), parsing response into Analysis model, applying confidence threshold gate (>=0.7), persisting result to database in src/issue_resolver/pipeline/analyzer.py
- [x] T031 [US1] Create resolver pipeline stage: resolve_issue(issue, analysis, config, dry_run) orchestrating full flow — fork repo, clone to workspace, detect test runner, read contributing guidelines, invoke Claude agent (opus, 30 turns, bypassPermissions), verify non-empty diff, run project tests, commit changes. Returns Attempt with outcome in src/issue_resolver/pipeline/resolver.py
- [x] T032 [US1] Create submitter pipeline stage: submit_pr(issue, attempt, config, auto_pr, dry_run) creating PR via gh if auto_pr, or displaying diff + analysis + cost and prompting user for confirmation in interactive mode. PR references issue with "refs #N" in src/issue_resolver/pipeline/submitter.py

#### CLI Command

- [x] T033 [US1] Create resolve CLI command: `issue-resolver resolve <issue-url> [--budget FLOAT]` per contracts/cli-commands.md — validate prerequisites (FR-007), parse issue URL, fetch issue via gh, verify freshness (FR-021), run analyzer, run resolver, run submitter. Handle all exit codes (0, 1, 2, 3, 4, 5). Support --dry-run, --auto-pr, --verbose output formatting in src/issue_resolver/cli/resolve.py
- [x] T034 [US1] Register resolve command in root Typer app via add_typer() in src/issue_resolver/cli/__init__.py

#### Tests for User Story 1

- [x] T035 [P] [US1] Write unit tests for Claude parser: test success parsing, error parsing, timeout handling, budget exceeded detection, cost_usd vs total_cost_usd normalization, malformed JSON handling in tests/unit/test_claude_parser.py
- [x] T036 [P] [US1] Write unit tests for project detector: test all language/runner detection paths (pytest, unittest, npm, cargo, go, rspec, maven, gradle), test "no test suite" fallback, test language detection in tests/unit/test_project_detector.py
- [x] T037 [US1] Write integration tests for resolve command: test dry-run mode (no side effects), test auto-pr mode, test analysis rejection (confidence < 70%), test tests_failed outcome, test budget exceeded, test prerequisite validation. All subprocess calls mocked in tests/integration/test_cli_resolve.py

**Checkpoint**: User Story 1 complete — `issue-resolver resolve <url>` works end-to-end. This is the MVP. Validate with: `issue-resolver resolve <url> --dry-run` and `pytest tests/ -v`

---

## Phase 4: User Story 2 — Scan and Discover Resolvable Issues (Priority: P2)

**Goal**: Developer searches GitHub for open-source issues the tool can solve, with configurable filters and idempotent deduplication.

**Independent Test**: `issue-resolver scan --limit 1` returns a filtered list. Integration tests mock GitHub API responses.

### Implementation for User Story 2

- [x] T038 [P] [US2] Create GitHub search module: search_issues(query_params) building GitHub search query from filters (labels, language, min_stars, max_age, no assignees, no linked PRs), executing via `gh api search/issues`, parsing response, and handling pagination in src/issue_resolver/github/search.py
- [x] T039 [US2] Create scanner pipeline stage: scan_issues(config, limit, dry_run) querying GitHub, filtering out issues already in database (FR-010 deduplication), persisting new issues, returning ranked candidate list in src/issue_resolver/pipeline/scanner.py
- [x] T040 [US2] Create scan CLI command: `issue-resolver scan [--limit N] [--language STR] [--label STR] [--min-stars INT] [--max-age INT]` per contracts/cli-commands.md — execute scanner, display formatted table (repository, issue number, labels, stars, age), report count saved in src/issue_resolver/cli/scan.py
- [x] T041 [US2] Register scan command in root Typer app via add_typer() in src/issue_resolver/cli/__init__.py

#### Tests for User Story 2

- [x] T042 [P] [US2] Write unit tests for GitHub search: test query building from various filter combinations, test response parsing, test empty results handling in tests/unit/test_github_search.py
- [x] T043 [US2] Write integration tests for scan command: test with mocked GitHub API, test deduplication (re-scan excludes existing), test --limit enforcement, test empty results message, test formatted table output in tests/integration/test_cli_scan.py

**Checkpoint**: User Stories 1 AND 2 work independently. Scan discovers issues, resolve fixes them.

---

## Phase 5: User Story 3 — Automated Pipeline: Scan + Analyze + Resolve (Priority: P3)

**Goal**: Full unattended pipeline — scan, analyze, resolve the most promising issues within a session budget. Suitable for cron/CI scheduling.

**Independent Test**: `issue-resolver run --max-issues 1 --dry-run` executes full pipeline flow without side effects.

**Dependencies**: Requires US1 (resolve) and US2 (scan) to be complete.

### Implementation for User Story 3

- [x] T044 [US3] Create pipeline orchestrator: run_pipeline(config, max_issues, auto_pr, dry_run) coordinating full flow — scan for candidates, iterate with budget tracking (three-tier: per-analysis, per-resolution, per-session), rate limiting (GitHub requests/min, Claude invocations/hour, min delay between issues), graceful failure handling per issue (log + continue), session summary reporting in src/issue_resolver/pipeline/orchestrator.py
- [x] T045 [US3] Create run CLI command: `issue-resolver run [--max-issues INT] [--budget FLOAT]` per contracts/cli-commands.md — execute orchestrator, display per-issue progress ([1/N] format), show session budget remaining, print final summary (analyzed, attempted, PRs submitted, failures, total cost) in src/issue_resolver/cli/run.py
- [x] T046 [US3] Register run command in root Typer app via add_typer() in src/issue_resolver/cli/__init__.py

#### Tests for User Story 3

- [x] T047 [P] [US3] Write unit tests for orchestrator: test budget enforcement (session budget stops processing), test per-issue failure isolation (one failure doesn't stop pipeline), test rate limiting delays, test max-issues limit in tests/unit/test_pipeline.py
- [x] T048 [US3] Write integration tests for run command: test dry-run pipeline, test budget exceeded mid-run, test mixed outcomes (1 success + 1 failure), test summary output format in tests/integration/test_cli_run.py

**Checkpoint**: Full pipeline works end-to-end. `issue-resolver run --max-issues 3 --dry-run` scans, analyzes, and reports plan for 3 issues.

---

## Phase 6: User Story 4 — View History, Statistics, and Resolution Funnel (Priority: P4)

**Goal**: Display resolution effectiveness — success rates by language, cost tracking, solvability calibration, and full resolution funnel.

**Independent Test**: Populate database with known records, run `issue-resolver status --summary`, verify output matches expected statistics.

### Implementation for User Story 4

- [x] T049 [US4] Add reporting queries to repository module: get_resolution_funnel() (discovered → filtered → attempted → non_empty_diff → tests_pass → pr_submitted), get_per_language_stats() (attempts, success rate, avg cost, avg duration per language), get_solvability_calibration() (confidence bands vs actual outcomes), get_summary_stats() (totals, rates, costs) per data-model.md Key Queries in src/issue_resolver/db/repository.py
- [x] T050 [US4] Create status CLI command: `issue-resolver status [--summary]` per contracts/cli-commands.md — display overview stats, resolution funnel with drop-off rates, per-language breakdown table, solvability calibration bands. Handle empty database gracefully in src/issue_resolver/cli/status.py
- [x] T051 [US4] Register status command in root Typer app via add_typer() in src/issue_resolver/cli/__init__.py

#### Tests for User Story 4

- [x] T052 [US4] Write integration tests for status command: test with populated database (verify correct stats), test with empty database (no history message), test funnel accuracy, test per-language segmentation in tests/integration/test_cli_status.py

**Checkpoint**: `issue-resolver status --summary` shows accurate funnel, per-language stats, and calibration data.

---

## Phase 7: User Story 5 — Configuration Management (Priority: P5)

**Goal**: Users can generate, view, and customize configuration. CLI flags > env vars > config file > defaults hierarchy works correctly.

**Independent Test**: Run `issue-resolver config --init` to generate config, modify values, verify `config --show` reflects changes.

### Implementation for User Story 5

- [x] T053 [US5] Create config CLI command: `issue-resolver config [--init] [--show]` per contracts/cli-commands.md — `--init` generates config.example.yaml in current directory with all options and comments, `--show` displays effective merged configuration with secrets redacted (GITHUB_TOKEN, ANTHROPIC_API_KEY shown as "****set****") in src/issue_resolver/cli/config_cmd.py
- [x] T054 [US5] Register config command in root Typer app via add_typer() in src/issue_resolver/cli/__init__.py

#### Tests for User Story 5

- [x] T055 [P] [US5] Write unit tests for config: test config loading from YAML, test env var override, test CLI flag precedence, test default values, test missing config file uses defaults in tests/unit/test_config.py
- [x] T056 [US5] Write integration tests for config command: test --init generates valid YAML, test --show displays merged config, test secrets redaction in tests/integration/test_cli_config.py

**Checkpoint**: Full configuration management works. All 5 user stories are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Remaining tests, CI, and validation across all stories

- [x] T057 [P] Write unit tests for Pydantic models: test all model creation, validation, serialization, enum constraints, confidence range check in tests/unit/test_models.py
- [x] T058 [P] Write unit tests for database: test engine initialization, migration application, CRUD operations, upsert idempotency, foreign key constraints in tests/unit/test_db.py
- [x] T059 [P] Create CI workflow with scheduled run trigger, Python 3.11 setup, dependency install, ruff check, mypy, pytest with coverage, in .github/workflows/scheduled-run.yml
- [x] T060 Run full quickstart.md validation and verify end-to-end setup per specs/001-ai-issue-resolver/quickstart.md: `issue-resolver --version`, `issue-resolver --help`, `pytest tests/ -v` all pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 Resolve (Phase 3)**: Depends on Foundational — No dependencies on other stories
- **US2 Scan (Phase 4)**: Depends on Foundational — No dependencies on other stories
- **US3 Pipeline (Phase 5)**: Depends on Foundational + US1 + US2 (orchestrator composes scanner + analyzer + resolver + submitter)
- **US4 Status (Phase 6)**: Depends on Foundational — No dependencies on other stories (reads from DB populated by US1-US3)
- **US5 Config (Phase 7)**: Depends on Foundational — No dependencies on other stories
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Foundational only — **can start immediately after Phase 2** 🎯 MVP
- **US2 (P2)**: Foundational only — can start after Phase 2, parallel with US1
- **US3 (P3)**: Foundational + US1 + US2 — must wait for both resolve and scan
- **US4 (P4)**: Foundational only — can start after Phase 2, parallel with US1/US2
- **US5 (P5)**: Foundational only — can start after Phase 2, parallel with US1/US2

### Within Each User Story

- Models/utils before services
- Claude invoker + prompts before parser
- GitHub operations before pipeline stages
- Pipeline stages before CLI commands
- CLI command before integration tests
- Unit tests [P] can run parallel with implementation

### Parallel Opportunities

- All Setup tasks T002-T003 can run in parallel
- All Foundational models T004-T007 can run in parallel
- All Foundational utils T008-T010 can run in parallel
- T015-T016 (exit codes, console) can run parallel with models/utils
- T021-T022 (fixtures, conftest) can run parallel with other foundational tasks
- Within US1: T023-T024 (invoker, prompts) parallel; T026-T027 (workspace) parallel; T028-T029 (github ops) parallel
- US1, US2, US4, US5 can all start in parallel after Phase 2
- Unit tests within each story marked [P] can run parallel

---

## Parallel Example: User Story 1

```bash
# Launch Claude integration modules together:
Task: "Create Claude invoker in src/issue_resolver/claude/invoker.py"        # T023
Task: "Create Claude prompts in src/issue_resolver/claude/prompts.py"        # T024

# Launch workspace modules together:
Task: "Create workspace manager in src/issue_resolver/workspace/manager.py"  # T026
Task: "Create project detector in src/issue_resolver/workspace/project_detector.py"  # T027

# Launch GitHub operations together:
Task: "Create GitHub repo operations in src/issue_resolver/github/repo_ops.py"  # T028
Task: "Create GitHub PR module in src/issue_resolver/github/pr.py"             # T029

# Launch unit tests together (after their targets exist):
Task: "Write unit tests for Claude parser in tests/unit/test_claude_parser.py"    # T035
Task: "Write unit tests for project detector in tests/unit/test_project_detector.py"  # T036
```

## Parallel Example: After Phase 2

```bash
# All independent user stories can start simultaneously:
Task: US1 "Create Claude invoker..."      # T023 (Phase 3)
Task: US2 "Create GitHub search module..."  # T038 (Phase 4)
Task: US4 "Add reporting queries..."       # T049 (Phase 6)
Task: US5 "Create config CLI command..."   # T053 (Phase 7)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T022) — CRITICAL, blocks all stories
3. Complete Phase 3: User Story 1 (T023-T037)
4. **STOP and VALIDATE**: `issue-resolver resolve <url> --dry-run` + `pytest tests/ -v`
5. The tool already delivers value — one command resolves one issue

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 Resolve → Test → **MVP!** (single issue resolution)
3. Add US2 Scan → Test → Discovery enabled
4. Add US3 Pipeline → Test → Unattended batch processing
5. Add US4 Status → Test → Operational visibility
6. Add US5 Config → Test → Full customization
7. Polish → CI, remaining tests → Production ready

### Parallel Team Strategy

With multiple developers after Phase 2 completes:

- **Developer A**: US1 Resolve (T023-T037) — critical path
- **Developer B**: US2 Scan (T038-T043) — feeds pipeline
- **Developer C**: US4 Status + US5 Config (T049-T056) — independent
- **After A+B complete**: US3 Pipeline (T044-T048) — composes US1+US2

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- US3 (Pipeline) is the only story with cross-story dependencies (requires US1 + US2)
