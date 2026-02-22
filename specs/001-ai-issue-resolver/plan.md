# Implementation Plan: AI-Powered GitHub Issue Resolution Tool

**Branch**: `001-ai-issue-resolver` | **Date**: 2026-02-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-ai-issue-resolver/spec.md`

## Summary

Build a Python CLI tool that automates the full lifecycle of resolving GitHub issues: scan for resolvable issues, analyze solvability with an AI agent, fork/clone the repository, implement a fix, run project tests, and submit a pull request. The tool uses Typer for CLI structure, SQLite (via sqlite-utils) for local state persistence, Rich for terminal output, and orchestrates external tools (GitHub CLI `gh`, Claude Code CLI `claude`, `git`) via subprocess. Configuration is YAML-based with env var overrides. Budget enforcement, rate limiting, and dry-run safety are core constraints.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Typer 0.9+ (CLI), Rich 13+ (terminal UI), Pydantic 2.5+ (models/config), pydantic-settings 2.1+ (YAML + env), PyYAML 6+ (config parsing), sqlite-utils 3.36+ (database)
**Storage**: SQLite (local file, WAL mode) — 3 tables: issues, analyses, attempts
**Testing**: pytest + pytest-cov + unittest.mock
**Target Platform**: Linux/macOS (developer workstation or CI environment)
**Project Type**: CLI tool
**Performance Goals**: < 10 minutes per single issue resolution (SC-006); < 1s for scan/status commands on ~1000 rows
**Constraints**: Budget adherence within 10% (SC-005); zero side effects in dry-run (SC-007); network access to GitHub + AI agent API required
**Scale/Scope**: Single user, ~1000 database rows, 5 CLI commands, 7 implementation phases

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

No constitution file exists for this project. Gate passes by default — no constraints to enforce.

**Post-Phase 1 re-check**: Design adheres to the spec's principles: budget safety, dry-run safety, community respect, and cost optimization. No constitution violations detected.

## Project Structure

### Documentation (this feature)

```text
specs/001-ai-issue-resolver/
├── plan.md              # This file
├── research.md          # Phase 0 output — technology decisions
├── data-model.md        # Phase 1 output — entity schemas
├── quickstart.md        # Phase 1 output — setup and run guide
├── contracts/           # Phase 1 output — CLI command contracts
│   ├── cli-commands.md  # Command signatures, flags, exit codes
│   └── claude-output.md # AI agent JSON output schema
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
pyproject.toml
config.example.yaml
.github/workflows/scheduled-run.yml

src/issue_resolver/
├── __init__.py
├── __main__.py                    # python -m issue_resolver entry point
├── cli/
│   ├── __init__.py                # Root Typer app + add_typer composition
│   ├── context.py                 # GlobalState dataclass for shared CLI state
│   ├── console.py                 # Rich Console with custom theme
│   ├── exit_codes.py              # Exit code constants
│   ├── scan.py                    # scan command
│   ├── resolve.py                 # resolve command
│   ├── run.py                     # run (pipeline) command
│   ├── status.py                  # status command
│   └── config_cmd.py              # config command (config_cmd to avoid shadowing)
├── config/
│   ├── schema.py                  # Pydantic settings models (YAML + env)
│   └── loader.py                  # Config file discovery and loading
├── models/
│   ├── enums.py                   # Solvability, AttemptStatus, OutcomeCategory
│   ├── issue.py                   # GitHubIssue model
│   ├── analysis.py                # IssueAnalysis model
│   └── attempt.py                 # ResolutionAttempt model
├── db/
│   ├── engine.py                  # SQLite setup, migrations, PRAGMA config
│   └── repository.py              # CRUD operations (issues, analyses, attempts)
├── github/
│   ├── client.py                  # gh CLI subprocess wrapper
│   ├── search.py                  # Issue search via gh api search/issues
│   ├── repo_ops.py                # Fork, clone, branch, push operations
│   └── pr.py                      # PR creation with templates
├── claude/
│   ├── invoker.py                 # Claude Code CLI subprocess wrapper
│   ├── prompts.py                 # Prompt templates (analysis + resolution)
│   └── parser.py                  # JSON output parsing + schema validation
├── pipeline/
│   ├── scanner.py                 # Issue discovery + filtering
│   ├── analyzer.py                # Solvability analysis via Claude
│   ├── resolver.py                # Fork → clone → AI fix → tests → commit
│   ├── submitter.py               # PR creation and submission
│   └── orchestrator.py            # Pipeline coordinator (budget, state, rate limits)
├── workspace/
│   ├── manager.py                 # Temp directory lifecycle management
│   └── project_detector.py        # Test runner + language detection
└── utils/
    ├── logging.py                 # Structured logging with Rich handler
    ├── exceptions.py              # Exception hierarchy
    └── subprocess_utils.py        # Subprocess helpers with timeout + retry

tests/
├── conftest.py                    # Shared fixtures, mock factories
├── unit/
│   ├── test_models.py
│   ├── test_config.py
│   ├── test_db.py
│   ├── test_claude_parser.py
│   ├── test_github_search.py
│   ├── test_project_detector.py
│   └── test_pipeline.py
├── integration/
│   ├── test_cli_scan.py
│   ├── test_cli_resolve.py
│   ├── test_cli_run.py
│   ├── test_cli_status.py
│   └── test_cli_config.py
└── fixtures/
    ├── issues/                    # Sample GitHub issue JSON responses
    ├── claude_responses/          # Sample Claude CLI JSON outputs
    └── configs/                   # Sample YAML config files
```

**Structure Decision**: Single Python project with `src/` layout. The `src/issue_resolver/` package uses Typer sub-apps composed in `cli/__init__.py`. Business logic lives in `pipeline/`, `github/`, `claude/`, `workspace/` — zero Typer imports outside `cli/`. Database is a single SQLite file in `~/.issue-resolver/data.db` (XDG-compliant default).

## Complexity Tracking

No constitution violations to justify — design is straightforward single-project CLI with no unnecessary abstractions.
