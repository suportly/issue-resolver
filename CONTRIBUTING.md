# Contributing to Issue Resolver

Thank you for considering contributing to Issue Resolver! This document provides guidelines and information to make the contribution process smooth.

## Getting Started

### Prerequisites

- Python 3.11+
- git
- GitHub CLI (`gh`) authenticated via `gh auth login`

### Setup

```bash
git clone https://github.com/suportly/issue-resolver.git
cd issue-resolver
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Verify your setup

```bash
pytest                # All tests should pass
ruff check .          # No lint errors
mypy src/             # No type errors
```

## Development Workflow

### 1. Create a branch

```bash
git checkout -b your-branch-name
```

Use a descriptive branch name: `fix/timeout-on-gh-api`, `feat/analyze-command`, `docs/update-readme`.

### 2. Make your changes

- Write code in `src/issue_resolver/`
- Add or update tests in `tests/`
- Follow existing patterns in the codebase

### 3. Run checks before committing

```bash
# Format
ruff format .

# Lint
ruff check .

# Type check
mypy src/

# Tests
pytest
```

### 4. Commit and push

Write clear, concise commit messages:

```
fix: handle gh api timeout on username lookup
feat: add standalone analyze command
docs: update config example with rate limiting
```

### 5. Open a Pull Request

- Provide a clear description of what changed and why
- Reference any related issues (e.g., "Fixes #42")
- Ensure all CI checks pass

## Project Structure

```
src/issue_resolver/
├── cli/                # Typer commands (resolve, scan, run, status, config)
├── claude/             # AI agent integration (invoker, parser, prompts)
├── config/             # Configuration loading and Pydantic schema
├── db/                 # SQLite engine and repository
├── github/             # GitHub CLI wrapper (search, PRs, repo ops)
├── models/             # Pydantic data models (Issue, Analysis, Attempt)
├── pipeline/           # Processing pipeline (analyzer, resolver, scanner, submitter)
├── utils/              # Logging, exceptions, subprocess helpers
└── workspace/          # Workspace lifecycle and project type detection
```

## Code Style

### General

- **Python 3.11+** — use modern syntax (`match`, `type X = ...`, `str | None`)
- **ruff** for linting and formatting (configured in `pyproject.toml`)
- **mypy** for static type checking — all functions must have type annotations
- Line length: **100 characters**

### Conventions

- Use Pydantic `BaseModel` for data structures
- Use Typer for CLI commands
- Use Rich for terminal output (via `issue_resolver.cli.console`)
- Use `run_gh()` / `run_gh_json()` from `issue_resolver.github.client` for GitHub CLI calls
- Use `run_with_timeout()` / `run_with_retry()` from `issue_resolver.utils.subprocess_utils` for subprocess calls
- Custom exceptions live in `issue_resolver.utils.exceptions`

### Naming

- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private functions: `_prefixed_with_underscore`

## Testing

### Structure

```
tests/
├── conftest.py            # Shared fixtures
├── fixtures/              # Test data (JSON, YAML)
├── unit/                  # Fast, isolated tests
│   ├── test_claude_parser.py
│   ├── test_config.py
│   ├── test_db.py
│   ├── test_github_search.py
│   ├── test_models.py
│   ├── test_pipeline.py
│   └── test_project_detector.py
└── integration/           # CLI-level tests
    ├── test_cli_config.py
    ├── test_cli_resolve.py
    ├── test_cli_run.py
    ├── test_cli_scan.py
    └── test_cli_status.py
```

### Guidelines

- **Unit tests** mock external dependencies (GitHub API, AI agent, filesystem)
- **Integration tests** test CLI commands end-to-end with mocked subprocess calls
- Use fixtures from `tests/fixtures/` for consistent test data
- Every bug fix should include a regression test
- Every new command or option should include tests for happy path and error cases

### Running tests

```bash
pytest                          # All tests
pytest --cov                    # With coverage report
pytest tests/unit/              # Unit tests only
pytest tests/integration/       # Integration tests only
pytest -x                       # Stop on first failure
pytest -k "test_resolve"        # Run matching tests
```

## Reporting Issues

- Use GitHub Issues to report bugs or suggest features
- Include steps to reproduce for bug reports
- Include the output of `issue-resolver --version`

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
