# Quickstart: AI-Powered GitHub Issue Resolution Tool

**Feature**: 001-ai-issue-resolver
**Date**: 2026-02-22

---

## Prerequisites

The following tools must be installed and in your PATH:

| Tool | Purpose | Install |
|------|---------|---------|
| **Python 3.11+** | Runtime | `pyenv install 3.11` or system package manager |
| **git** | Repository operations | System package manager |
| **gh** (GitHub CLI) | GitHub API + auth | `brew install gh` / `apt install gh` / [cli.github.com](https://cli.github.com) |
| **claude** (Claude Code CLI) | AI agent for analysis + resolution | `npm install -g @anthropic-ai/claude-code` |

### Authentication

```bash
# GitHub CLI — authenticate with your GitHub account
gh auth login

# Claude Code CLI — set API key
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Installation

```bash
# Clone the repo
git clone https://github.com/your-user/issue-resolver.git
cd issue-resolver

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Verify installation
issue-resolver --version
issue-resolver --help
```

---

## Quick Usage

### 1. Resolve a specific issue (core workflow)

```bash
# Dry run first — no side effects
issue-resolver --dry-run resolve https://github.com/encode/django-rest-framework/issues/9501

# Full resolution with manual PR review
issue-resolver resolve https://github.com/encode/django-rest-framework/issues/9501

# Full resolution with automatic PR
issue-resolver --auto-pr resolve https://github.com/encode/django-rest-framework/issues/9501
```

### 2. Scan for issues

```bash
# Find Python bug issues in popular repos
issue-resolver scan --language python --label bug --min-stars 100 --limit 5
```

### 3. Run the pipeline

```bash
# Scan + analyze + resolve up to 3 issues (dry run)
issue-resolver --dry-run run --max-issues 3

# Full pipeline with auto-PR
issue-resolver --auto-pr run --max-issues 5 --max-budget 25.00
```

### 4. Check status

```bash
issue-resolver status --summary
```

### 5. Configuration

```bash
# Generate example config
issue-resolver config --init

# View effective configuration
issue-resolver config --show
```

---

## Configuration

Create `~/.config/issue-resolver/config.yaml`:

```yaml
auto_pr: false
dry_run: false
max_issues_per_run: 5

search:
  labels: ["good first issue", "bug", "help wanted"]
  languages: ["python"]
  min_stars: 50
  max_age_days: 365
  exclude_assignees: true
  exclude_linked_prs: true

targets:
  repos: []                    # Empty = broad search
  exclude_repos: []

claude:
  model: "opus"
  analysis_max_budget_usd: 0.50
  resolution_max_budget_usd: 5.00
  total_session_budget_usd: 25.00
  timeout_seconds: 300

workspace:
  base_dir: "/tmp/issue-resolver-workspaces"
  cleanup_on_success: true
  cleanup_on_failure: false

rate_limit:
  github_requests_per_minute: 25
  claude_invocations_per_hour: 30
  min_delay_between_issues_seconds: 10
```

Environment variables for secrets:
```bash
export GITHUB_TOKEN="ghp_..."          # Or use `gh auth login`
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Development

```bash
# Run tests
pytest
pytest --cov                    # With coverage
pytest tests/unit/              # Unit tests only
pytest tests/integration/       # Integration tests only

# Lint and format
ruff check .
ruff format .

# Type check
mypy src/
```

---

## Verification Checklist

After setup, verify each command works:

1. `issue-resolver scan --limit 1 --dry-run` — finds and lists 1 issue
2. `issue-resolver resolve <url> --dry-run` — analyzes and shows plan, no PR
3. `issue-resolver resolve <url> --auto-pr` — full cycle with real PR
4. `issue-resolver status --summary` — shows statistics
5. `pytest tests/ -v` — all tests pass
