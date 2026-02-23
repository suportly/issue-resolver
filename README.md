# Issue Resolver

AI-powered CLI tool that automates the full lifecycle of resolving GitHub issues: scan for resolvable issues, analyze solvability with AI, fork the repository, implement a fix using an AI coding agent, run tests, and submit a pull request.

## How It Works

```
Issue URL → Prerequisite Check → Solvability Analysis → Fork/Clone →
AI Resolution → Test Execution → Diff Validation → PR Submission
```

1. **Analyze** — AI evaluates whether the issue is solvable (bug report vs. feature request vs. design discussion)
2. **Fork & Clone** — Creates a fork and clones the repository into a temporary workspace
3. **Implement** — AI coding agent reads the issue, understands the codebase, and generates a fix
4. **Test** — Detects and runs the project's test suite to validate the fix
5. **Submit** — Creates a pull request referencing the original issue, following the project's contributing guidelines

## Usage

### Resolve a specific issue

```bash
# Analyze, implement, and submit a PR (interactive review)
issue-resolver resolve https://github.com/owner/repo/issues/42

# Automatically create PR without confirmation
issue-resolver --auto-pr resolve https://github.com/owner/repo/issues/42

# Dry-run: analyze and plan without modifying anything
issue-resolver --dry-run resolve https://github.com/owner/repo/issues/42

# Set a session budget cap (USD)
issue-resolver --max-budget 5.00 resolve https://github.com/owner/repo/issues/42
```

### Scan for resolvable issues

```bash
# Find Python bug issues in popular repos
issue-resolver scan --language python --label bug --min-stars 100

# Limit results
issue-resolver scan --language rust --limit 10
```

### Run the full pipeline

```bash
# Scan, analyze, and resolve up to 5 issues automatically
issue-resolver --auto-pr run --max-issues 5

# Dry-run the pipeline
issue-resolver --dry-run run --max-issues 3
```

### View statistics

```bash
# Show resolution history and success rates
issue-resolver status

# Summary only
issue-resolver status --summary
```

### Configuration

```bash
# Generate example config file
issue-resolver config --init

# Show current configuration
issue-resolver config --show
```

### Global options

```bash
issue-resolver --help            # Show all commands
issue-resolver --version         # Show version
issue-resolver --verbose ...     # Enable DEBUG-level logging
issue-resolver --dry-run ...     # Zero side effects mode
issue-resolver --auto-pr ...     # Submit PR without confirmation
issue-resolver --max-budget N .. # Session budget cap in USD
issue-resolver --config FILE ... # Custom YAML config path
```

## Prerequisites

The following tools must be installed and authenticated:

| Tool | Purpose | Install |
|------|---------|---------|
| **Python 3.11+** | Runtime | [python.org](https://www.python.org/downloads/) |
| **git** | Repository operations | `apt install git` / `brew install git` |
| **GitHub CLI (`gh`)** | GitHub API interactions | [cli.github.com](https://cli.github.com/) |
| **Claude Code** | AI code generation | [claude.ai/code](https://claude.ai/code) |

```bash
# Verify prerequisites
gh auth status          # Must be authenticated
git --version           # Must be installed
claude --version        # Must be installed
```

## Installation

```bash
git clone https://github.com/suportly/issue-resolver.git
cd issue-resolver
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Configuration follows a hierarchy: **CLI flags > environment variables > config file > defaults**.

```bash
# Generate a config file with documentation
issue-resolver config --init
```

Example `~/.config/issue-resolver/config.yaml`:

```yaml
# Behavior
auto_pr: false
dry_run: false
max_issues_per_run: 5

# GitHub issue search filters
search:
  labels: ["good first issue", "bug", "help wanted"]
  languages: ["python"]
  min_stars: 50
  max_age_days: 365
  exclude_assignees: true
  exclude_linked_prs: true

# Target repositories (empty = broad GitHub search)
targets:
  repos: []
  exclude_repos: []

# AI agent configuration
claude:
  model: "opus"
  analysis_max_budget_usd: 0.50
  resolution_max_budget_usd: 5.00
  total_session_budget_usd: 25.00
  timeout_seconds: 300

# Workspace management
workspace:
  base_dir: "/tmp/issue-resolver-workspaces"
  cleanup_on_success: true
  cleanup_on_failure: false

# Rate limiting
rate_limit:
  github_requests_per_minute: 25
  claude_invocations_per_hour: 30
  min_delay_between_issues_seconds: 10
```

Secrets are always loaded from environment variables, never stored in config files:

```bash
export GITHUB_TOKEN="ghp_..."           # or use `gh auth login`
export ANTHROPIC_API_KEY="sk-ant-..."
```

Environment variable overrides for CLI options:

| Variable | Description |
|----------|-------------|
| `ISSUE_RESOLVER_DRY_RUN` | Enable dry-run mode |
| `ISSUE_RESOLVER_AUTO_PR` | Enable auto-PR submission |
| `ISSUE_RESOLVER_MAX_BUDGET` | Session budget cap (USD) |
| `ISSUE_RESOLVER_CONFIG` | Path to YAML config file |
| `ISSUE_RESOLVER_VERBOSE` | Enable DEBUG logging |

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| CLI Framework | Typer 0.12+ |
| Terminal UI | Rich 13+ |
| Data Models | Pydantic 2.5+ |
| Configuration | pydantic-settings 2.1+ / PyYAML 6+ |
| Database | SQLite (WAL mode) via sqlite-utils 3.36+ |
| Testing | pytest / pytest-cov |
| Linting | ruff |
| Type Checking | mypy |

## Development

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest                          # All tests
pytest --cov                    # With coverage
pytest tests/unit/              # Unit tests only
pytest tests/integration/       # Integration tests only

# Code quality
ruff check .                    # Lint
ruff format .                   # Format
mypy src/                       # Type check
```

## Project Structure

```
src/issue_resolver/
├── cli/                # Typer commands (resolve, scan, run, status, config)
├── claude/             # AI agent integration (invoker, parser, prompts)
├── config/             # Configuration loading and schema
├── db/                 # SQLite engine and repository
├── github/             # GitHub CLI wrapper (search, PRs, repo ops)
├── models/             # Pydantic data models (Issue, Analysis, Attempt)
├── pipeline/           # Processing pipeline (analyzer, resolver, scanner, submitter)
├── utils/              # Logging, exceptions, subprocess helpers
└── workspace/          # Workspace lifecycle and project type detection
```

## Architecture

### Data Model

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Issue    │────>│ Analysis │────>│ Attempt  │
│          │     │          │     │          │
│ repo     │     │ rating   │     │ status   │
│ number   │     │ confidence│    │ cost     │
│ title    │     │ complexity│    │ duration │
│ labels   │     │ reasoning│     │ workspace│
│ url      │     │ cost     │     │ pr_url   │
└──────────┘     └──────────┘     └──────────┘
```

### Key Design Decisions

- **Budget enforcement at 3 levels** — per-analysis, per-resolution, and per-session to prevent runaway costs
- **Dry-run with zero side effects** — no forks, branches, or PRs created
- **Exponential backoff** — max 3 retries on GitHub rate limits
- **Workspace preservation on failure** — debug failed attempts without losing context
- **Issue deduplication** — SQLite database tracks all attempts to prevent duplicate work
- **Baseline test comparison** — runs tests before and after the fix to avoid blocking on pre-existing failures

## License

MIT
