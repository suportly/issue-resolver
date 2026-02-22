# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered GitHub Issue Resolution Tool — a CLI tool that automates the full lifecycle of resolving GitHub issues: scan for resolvable issues, analyze solvability with AI, fork/clone the repository, implement a fix using an AI coding agent, run the project's tests, and submit a pull request.

## Project Structure

```
issue-resolver/
├── .claude/                    # Claude Code agent configuration
│   ├── agents/                 # Specialized agent definitions
│   │   ├── engineering/        # CLI architecture, AI integration, GitHub, DevOps
│   │   ├── testing/            # Integration testing, test analysis, workflow
│   │   ├── product/            # Sprint planning, feedback analysis
│   │   ├── project-management/ # Project shipping
│   │   └── operations/         # Analytics, cost optimization
│   ├── commands/               # Speckit workflow commands
│   └── settings.local.json     # Local agent permissions
├── .specify/                   # Spec-Driven Development framework
│   ├── scripts/bash/           # Automation scripts
│   └── templates/              # Document templates
├── specs/                      # Feature specifications
│   └── 001-ai-issue-resolver/  # Current feature spec
│       ├── spec.md             # Feature specification (24 FRs)
│       └── checklists/         # Validation checklists
└── src/                        # Source code (Python)
```

## Technology Stack

- **Language**: Python 3.11+
- **CLI Framework**: Click/Typer (TBD)
- **Terminal UI**: Rich (formatted output, tables, progress bars)
- **Configuration**: YAML with environment variable overrides
- **Database**: SQLite (local persistence for issues, analyses, attempts)
- **External Tools**: GitHub CLI (`gh`), AI coding agent CLI, `git`
- **Testing**: pytest, pytest-cov, unittest.mock
- **Linting**: ruff (lint + format)
- **Type Checking**: mypy or pyright

## Common Development Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run the tool
issue-resolver resolve <github-issue-url>
issue-resolver scan --language python --label bug
issue-resolver status
issue-resolver config --init

# Testing
pytest                          # Run all tests
pytest --cov                    # Run with coverage
pytest tests/unit/              # Unit tests only
pytest tests/integration/       # Integration tests only
pytest -x                       # Stop on first failure

# Linting
ruff check .                    # Lint
ruff format .                   # Format
mypy src/                       # Type check
```

## Architecture Overview

### Core Commands
- **resolve**: Accept a GitHub issue URL → analyze → fork → implement fix → run tests → submit PR
- **scan**: Search GitHub for resolvable issues matching filters → ranked list with solvability scores
- **analyze**: Run solvability analysis on a specific issue without attempting resolution
- **status**: Display statistics (attempts, success rate, costs, breakdown by repo)
- **config**: Manage configuration (init, validate, show)

### Key Data Flow
```
Issue URL → Prerequisite Check → Solvability Analysis → Fork/Clone →
AI Resolution → Test Execution → Diff Validation → PR Submission
```

### Key Entities
- **Issue**: GitHub issue metadata (repo, number, title, body, labels, URL)
- **Analysis**: Solvability assessment (rating, confidence 0-1, complexity, reasoning, cost)
- **Attempt**: Resolution record (status, cost, duration, workspace path, PR URL)

### Critical Design Constraints
- **Budget Enforcement**: Three levels — per-analysis, per-resolution, per-session (FR-006, FR-007)
- **Dry-Run Safety**: `--dry-run` must produce ZERO side effects (FR-008, SC-007)
- **Rate Limiting**: Exponential backoff, max 3 retries for GitHub API (FR-012, FR-014)
- **Workspace Management**: Clean up on success, preserve on failure (FR-018)
- **Issue Deduplication**: Skip already-attempted issues using database (FR-021)
- **PR Quality**: Reference original issue, follow contributing guidelines (FR-011, FR-019)

## Development Workflow

### Feature Development (Spec-Driven)
1. `/speckit.specify` — Define requirements
2. `/speckit.clarify` — Resolve ambiguities
3. `/speckit.checklist` — Validate specification
4. `/speckit.plan` — Create implementation plan
5. `/speckit.tasks` — Generate implementation tasks
6. `/speckit.implement` — Execute implementation

### Branch Convention
- Main branch: `main`
- Feature branches: `NNN-feature-name` (e.g., `001-ai-issue-resolver`)

## Success Criteria (from spec)

- SC-001: Single-command resolution (URL → PR)
- SC-002: 70%+ scan relevancy
- SC-003: 80%+ unsolvable detection accuracy
- SC-004: 30%+ PR test pass rate
- SC-005: Budget adherence within 10%
- SC-006: < 10 min per resolution
- SC-007: Zero side effects in dry-run
- SC-008: Failed attempt context preservation
- SC-009: Cost tracking within 5% accuracy
- SC-010: Batch processing of 5+ issues

## Active Technologies
- Python 3.11+ + Typer 0.9+ (CLI), Rich 13+ (terminal UI), Pydantic 2.5+ (models/config), pydantic-settings 2.1+ (YAML + env), PyYAML 6+ (config parsing), sqlite-utils 3.36+ (database) (001-ai-issue-resolver)
- SQLite (local file, WAL mode) — 3 tables: issues, analyses, attempts (001-ai-issue-resolver)

## Recent Changes
- 001-ai-issue-resolver: Added Python 3.11+ + Typer 0.9+ (CLI), Rich 13+ (terminal UI), Pydantic 2.5+ (models/config), pydantic-settings 2.1+ (YAML + env), PyYAML 6+ (config parsing), sqlite-utils 3.36+ (database)
