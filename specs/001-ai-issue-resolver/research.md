# Research: AI-Powered GitHub Issue Resolution Tool

**Feature**: 001-ai-issue-resolver
**Date**: 2026-02-22
**Purpose**: Resolve all technical unknowns before implementation

---

## Decision 1: CLI Framework — Typer

**Decision**: Use Typer 0.9+ with Rich markup mode

**Rationale**:
- Built on Click, providing mature CLI patterns (parameter types, help generation, shell completion)
- `rich_markup_mode="rich"` enables Rich formatting in help text natively
- `add_typer()` allows composing sub-apps from separate files — each command in its own module
- `@app.callback()` pattern handles global options (--dry-run, --verbose, --config, --auto-pr, --max-budget)
- `envvar=` parameter on `typer.Option` gives config hierarchy for free: CLI > env > default
- `typer.Exit(code=N)` for controlled exits, `typer.confirm()` for interactive gates

**Alternatives considered**:
- **Click directly**: More boilerplate, no type annotations for parameter definition. Typer wraps Click with less ceremony.
- **argparse**: Stdlib but verbose, no subcommand composition pattern, manual help formatting.

**Key patterns**:
- Root `cli/__init__.py` composes sub-apps via `app.add_typer(scan_app, name="scan")`
- `cli/context.py` holds `GlobalState` dataclass populated in root callback
- Each command module imports `state` and accesses global options
- Business logic in `pipeline/`, `github/`, `claude/` — zero Typer imports outside `cli/`
- `CliRunner` from Click for integration testing

---

## Decision 2: Claude Code CLI Integration

**Decision**: Use `claude -p "prompt" --output-format json` via `subprocess.run()`

**Rationale**:
- JSON output provides structured result with cost tracking, turn count, error status
- `--permission-mode bypassPermissions` enables unattended tool execution in isolated workspaces
- `--max-budget-usd` provides server-side budget enforcement (proactive, < 10% variance)
- `--max-turns` limits agent loops; hitting the limit is NOT an error (is_error=false)
- External timeout via `subprocess.run(timeout=N)` handles agent hangs

**JSON output schema**:
```json
{
  "result": "string — final assistant response",
  "is_error": false,
  "cost_usd": 0.0123,
  "duration_ms": 4521,
  "num_turns": 3,
  "session_id": "uuid"
}
```

**Key findings**:
- Cost field is `cost_usd` (not `total_cost_usd`) — parser should handle both defensively
- Budget exceeded: `is_error=true`, exit code 0, partial result may exist
- Max turns hit: `is_error=false`, exit code 0, partial result exists
- Timeout (external): No JSON output, `subprocess.TimeoutExpired` exception
- Auth/usage error: exit code 1, error on stderr
- Must check BOTH exit code AND `is_error` field — they are independent

**Two-tier model strategy**:
- Analysis (solvability): `--max-turns 1 --model haiku` — cheap, fast, read-only
- Resolution (code fix): `--max-turns 30 --model opus --permission-mode bypassPermissions` — full agent

**Alternatives considered**:
- **Anthropic Python SDK directly**: More control but loses Claude Code's built-in tool use (file editing, bash, search). The CLI is the correct abstraction for agent-driven code changes.
- **stream-json output**: Enables real-time progress monitoring but adds parsing complexity. Defer to v1.1.

---

## Decision 3: GitHub CLI (`gh`) Integration

**Decision**: Use `gh` CLI via subprocess for all GitHub operations

**Rationale**:
- `gh` handles authentication, pagination, rate limiting at the transport level
- JSON output via `--json field1,field2` or `gh api` with `--jq`
- Fork, clone, PR creation are single commands
- Exit codes are reliable: 0 = success, 1 = error

**Key commands**:

| Operation | Command |
|-----------|---------|
| Search issues | `gh api search/issues -X GET -f q="is:issue is:open no:assignee -linked:pr label:bug language:python stars:>50" -f per_page=30 --jq '.items'` |
| View issue | `gh issue view {number} --repo {owner}/{repo} --json title,body,labels,comments,state,assignees` |
| Check issue freshness | `gh issue view {number} --repo {owner}/{repo} --json state,assignees` |
| Fork repo | `gh repo fork {owner}/{repo} --clone=false` |
| Check fork exists | `gh repo list --fork --json nameWithOwner --jq '.[].nameWithOwner'` |
| Create PR | `gh pr create --repo {owner}/{repo} --head {user}:{branch} --title "..." --body "..."` |
| Rate limit check | `gh api rate_limit --jq '.resources.search'` |

**Rate limit handling**:
- `gh` returns exit code 1 on 429; stderr contains "rate limit exceeded"
- Detect via exit code + stderr pattern matching
- Apply exponential backoff: 1s, 2s, 4s (max 3 retries, with jitter)

**Alternatives considered**:
- **PyGitHub / ghapi**: Python libraries for GitHub API. Adds a dependency and loses `gh`'s built-in auth management. The spec explicitly uses `gh` as an external tool.
- **requests + GitHub REST API directly**: More code, manual auth handling, pagination, rate limiting. `gh` handles all of this.

---

## Decision 4: Database — SQLite with sqlite-utils

**Decision**: Use `sqlite-utils` 3.36+ with hand-rolled schema migrations

**Rationale**:
- Purpose-built for this exact use case: small local database, Python CLI tool
- `db["issues"].upsert(row, pk="id")` handles idempotent scan insertion (FR-010)
- `alter=True` on insert auto-creates tables and adds new columns — migration primitive for early development
- No ORM overhead; rows are plain dicts that map cleanly to Pydantic models
- Ships a CLI for debugging (`sqlite-utils schema data.db`)
- Zero external dependencies (wraps stdlib `sqlite3`)

**Migration strategy**:
- `schema_version` table with single integer version
- Sequential numbered migrations in a Python list
- Applied at startup: compare current version, run pending migrations
- ~40 lines, no Alembic, fully auditable

**Connection management**:
- WAL mode for concurrent read/write safety
- `PRAGMA foreign_keys=ON` for referential integrity
- `PRAGMA busy_timeout=30000` for lock contention (30s wait)
- Context manager: one connection per command, closed in `finally`

**Database location**: `~/.issue-resolver/data.db` (default, configurable)

**Alternatives considered**:
- **SQLAlchemy + Alembic**: Enterprise-grade, massive surface area. Three tables with ~1000 rows does not justify Session, DeclarativeBase, migration scripts, alembic_versions table. Rejected for complexity.
- **Peewee**: Lighter ORM, but weaker type annotation support and no CLI tooling. `sqlite-utils` is simpler for dict-based workflows.
- **Raw sqlite3**: Zero deps but manual INSERT/SELECT/UPSERT boilerplate accumulates. `sqlite-utils` wraps it cleanly.
- **TinyDB / shelve**: No SQL, limited querying capability, no migration story. Rejected.

---

## Decision 5: Test Runner Detection

**Decision**: Priority-ordered detection waterfall per language with file-based heuristics

**Rationale**:
- Each language has 2-3 signals that reliably indicate the test runner
- File existence checks are fast (< 1ms) and require no execution
- Detect language first (by marker files), then detect runner within that language
- First match wins — no ambiguity

**Detection priority by language**:

| Language | Detection Files | Command | Timeout |
|----------|----------------|---------|---------|
| Python/pytest | `pytest.ini`, `conftest.py`, `[tool.pytest]` in pyproject.toml | `python -m pytest -v --tb=short` | 300s |
| Python/unittest | `test_*.py` files (fallback) | `python -m unittest discover -v` | 300s |
| JavaScript | `package.json` with test script | `npm test` (with `CI=true` env) | 300s |
| Rust | `Cargo.toml` | `cargo test` | 600s |
| Go | `go.mod` + `*_test.go` files | `go test -timeout 120s ./...` | 180s |
| Ruby/RSpec | `spec/`, `.rspec` | `bundle exec rspec` | 300s |
| Java/Maven | `pom.xml` | `./mvnw test -B` | 600s |
| Java/Gradle | `build.gradle*` | `./gradlew test` | 600s |

**"No test suite" detection**: If all language-specific checks fail, conclude no test suite exists. Flag attempt as "untested" and proceed with PR submission (with a note in the PR body).

**Key gotchas addressed**:
- npm's default test script (`echo "Error..." && exit 1`) is a placeholder, not a test suite
- pytest exit code 5 means "no tests collected" — treat as no suite, not failure
- `vitest` defaults to watch mode — always use `vitest run`
- Compiled languages (Rust, Java) need 600s timeout for first compilation
- Use wrapper scripts (`./mvnw`, `./gradlew`, `bundle exec`) over system tools

---

## Decision 6: Configuration Architecture

**Decision**: Pydantic Settings with YAML loader + env var overrides, following CLI > env > config > defaults hierarchy

**Rationale**:
- `pydantic-settings` 2.1+ supports custom settings sources (YAML)
- Typer's `envvar=` parameter on options handles CLI > env precedence
- YAML config provides human-readable, commentable configuration
- Secrets always from env vars: `GITHUB_TOKEN`, `ANTHROPIC_API_KEY`

**Config file discovery** (in order):
1. `--config` CLI flag (explicit path)
2. `ISSUE_RESOLVER_CONFIG` env var
3. `.issue-resolver.yaml` in current directory
4. `~/.config/issue-resolver/config.yaml` (XDG default)
5. No config file — use defaults

**Alternatives considered**:
- **TOML**: Python 3.11 has `tomllib` in stdlib. But YAML is more expressive for nested config and the user's description specifies YAML.
- **JSON**: No comments. Rejected for configuration files.
- **dotenv**: Too flat for nested config structure. Good for secrets only.

---

## Decision 7: Logging Architecture

**Decision**: Python `logging` module with Rich handler + structured context

**Rationale**:
- Rich's `RichHandler` provides beautiful terminal output with timestamps, level colors, tracebacks
- Standard `logging` module allows filtering by level (--verbose maps to DEBUG, default is INFO, --quiet maps to WARNING)
- Structured context via `logging.extra` for machine-readable fields (cost, duration, issue_url)
- stderr for logs, stdout for command output — composable with shell pipes

**Alternatives considered**:
- **structlog**: Excellent for production services, overkill for a CLI tool. Adds a dependency for marginal benefit.
- **loguru**: Nice API but non-standard. Rich handler on stdlib logging achieves the same output.
