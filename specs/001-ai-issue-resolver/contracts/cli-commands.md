# CLI Command Contracts

**Feature**: 001-ai-issue-resolver
**Date**: 2026-02-22
**Source**: [spec.md](../spec.md) CLI Commands + [research.md](../research.md) Decision 1

---

## Global Options

All commands accept these global options, processed in the root `@app.callback()`:

| Flag | Type | Default | Env Var | Description |
|------|------|---------|---------|-------------|
| `--dry-run` | bool | `false` | `ISSUE_RESOLVER_DRY_RUN` | Zero side effects mode (FR-016) |
| `--verbose` / `-v` | bool | `false` | `ISSUE_RESOLVER_VERBOSE` | Enable DEBUG-level logging |
| `--config` / `-c` | path | auto-discover | `ISSUE_RESOLVER_CONFIG` | Path to YAML config file |
| `--auto-pr` | bool | `false` | `ISSUE_RESOLVER_AUTO_PR` | Submit PR without confirmation (FR-017) |
| `--max-budget` | float | from config | `ISSUE_RESOLVER_MAX_BUDGET` | Session budget cap in USD (FR-011) |
| `--version` | bool | — | — | Show version and exit (eager) |

**Precedence**: CLI flag > env var > config file > default

---

## Exit Codes

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | `OK` | Success (including dry-run completion) |
| 1 | `GENERAL_ERROR` | Unhandled error |
| 2 | `PREREQUISITE_FAILED` | Missing gh, git, or claude CLI |
| 3 | `BUDGET_EXCEEDED` | Session budget exhausted |
| 4 | `ANALYSIS_REJECTED` | Issue below confidence threshold |
| 5 | `TESTS_FAILED` | AI fix applied but tests failed |

---

## Command: `resolve`

Resolve a specific GitHub issue end-to-end.

### Signature

```
issue-resolver resolve <issue-url> [OPTIONS]
```

### Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `issue-url` | string (URL) | yes | GitHub issue URL (e.g., `https://github.com/org/repo/issues/42`) |

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--budget` | float | from config | Per-resolution budget override (USD) |

### Execution Flow

1. Validate prerequisites (gh, git, claude installed and authenticated)
2. Parse issue URL → extract owner, repo, issue number
3. Fetch issue details via `gh issue view`
4. Verify issue freshness (still open, no assignees, no linked PRs)
5. Run solvability analysis (cheap model, 1 turn)
6. If confidence < 70% → report reasoning, exit with code 4
7. Fork repo (or reuse existing fork, sync upstream)
8. Clone to temporary workspace (shallow, `--depth=1`)
9. Detect test runner + read CONTRIBUTING.md + PR template
10. Invoke AI agent for resolution (full model, up to 30 turns)
11. Verify non-empty diff
12. Run project tests
13. If tests fail → report, preserve workspace, exit with code 5
14. If `--auto-pr` → create PR via `gh pr create`
15. Else → display diff + analysis + cost, prompt for confirmation
16. Record attempt in database

### Output (stdout)

**Interactive mode** (default):
```
Analyzing issue: encode/django-rest-framework#9501
  Rating: solvable (confidence: 0.85)
  Complexity: low
  Reasoning: Clear bug with specific error message and test case provided.

Resolving...
  Workspace: /tmp/issue-resolver-workspaces/abc123
  Changes: 2 files changed, 15 insertions, 3 deletions
  Tests: 42 passed, 0 failed
  Cost: $1.23 (3 turns)

Submit PR? [y/N]:
```

**Auto-PR mode**:
```
...same as above...
  PR: https://github.com/encode/django-rest-framework/pull/9999
```

**Dry-run mode**:
```
[DRY RUN] Analyzing issue: encode/django-rest-framework#9501
  Rating: solvable (confidence: 0.85)
  ...
[DRY RUN] Would fork, clone, resolve, and submit PR. No changes made.
```

### Error Output (stderr)

```
Error: GitHub CLI (gh) is not installed. Install from https://cli.github.com
Error: Issue #9501 is no longer open (closed 2h ago). Skipping.
Error: Budget exceeded ($5.12 spent of $5.00 limit). Workspace preserved at /tmp/...
```

---

## Command: `scan`

Search GitHub for resolvable issues.

### Signature

```
issue-resolver scan [OPTIONS]
```

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--limit` / `-n` | int | 10 | Maximum issues to return |
| `--language` / `-l` | string | from config | Filter by programming language |
| `--label` | string (multi) | from config | Filter by issue label (repeatable) |
| `--min-stars` | int | from config | Minimum repository star count |
| `--max-age` | int | from config | Maximum issue age in days |

### Execution Flow

1. Validate prerequisites (gh authenticated)
2. Build GitHub search query from filters
3. Execute search via `gh api search/issues`
4. Filter out: issues with assignees, linked PRs, already in database
5. Persist new issues to database
6. Display ranked list

### Output (stdout)

```
Found 7 candidate issues:

 #  Repository                          Issue   Labels           Stars   Age
 1  encode/django-rest-framework        #9501   bug              28.1k   3d
 2  pallets/flask                       #5432   help-wanted      67.8k   12d
 3  psf/requests                        #6789   good-first-issue 52.3k   45d
 ...

7 issues saved. Run `issue-resolver resolve <url>` to resolve one.
```

### Exit Codes

- 0: Issues found and displayed
- 0: No issues found (with message "No matching issues found")
- 1: Error (auth failure, network error)
- 2: Prerequisite missing

---

## Command: `run`

Execute the full pipeline: scan + analyze + resolve.

### Signature

```
issue-resolver run [OPTIONS]
```

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--max-issues` | int | from config | Maximum issues to attempt |
| `--budget` | float | from config | Per-resolution budget override |

### Execution Flow

1. Validate prerequisites
2. Scan for issues (using config filters)
3. For each issue (up to max-issues):
   a. Analyze solvability
   b. If passes threshold → attempt resolution
   c. If fails → record and continue
   d. Check session budget before each issue
4. Report summary

### Output (stdout)

```
Pipeline run: 5 issues maximum, $25.00 session budget

Scanning... found 12 candidates.

[1/5] encode/django-rest-framework#9501
  Analysis: solvable (0.85) — $0.12
  Resolution: PR submitted — $2.34
  PR: https://github.com/encode/django-rest-framework/pull/9999

[2/5] pallets/flask#5432
  Analysis: likely_solvable (0.72) — $0.08
  Resolution: tests_failed — $3.45
  Workspace preserved: /tmp/issue-resolver-workspaces/def456

[3/5] psf/requests#6789
  Analysis: unsolvable (0.91) — $0.05
  Skipped: Feature request, requires design discussion.

Session budget remaining: $18.96

Summary: 3 analyzed, 2 attempted, 1 PR submitted, 1 tests failed, 1 skipped
Total cost: $6.04
```

---

## Command: `status`

Display resolution history and statistics.

### Signature

```
issue-resolver status [OPTIONS]
```

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--summary` | bool | `false` | Show aggregated statistics |

### Output (stdout, `--summary`)

```
Issue Resolver Statistics

Overview:
  Total issues discovered:  142
  Total analyses:           89
  Total resolution attempts: 34
  PRs submitted:            12 (35.3%)
  Total cost:               $87.45
  Avg cost per attempt:     $2.57

Resolution Funnel:
  Discovered         142  (100%)
  Passed filter       89  (62.7%)  ▏ -37.3% unsolvable/low confidence
  Attempted           34  (24.0%)  ▏ -38.7% budget/skip
  Non-empty diff      28  (19.7%)  ▏ -4.2% empty diff
  Tests pass          15  (10.6%)  ▏ -9.2% test failures
  PR submitted        12  (8.5%)   ▏ -2.1% manual review declined

By Language:
  Language     Attempts  Success  Avg Cost  Avg Time
  Python       18        44.4%    $2.12     4.2m
  JavaScript   9         22.2%    $3.01     6.1m
  Go           4         50.0%    $1.89     3.5m
  Rust         3         33.3%    $3.45     7.8m
```

---

## Command: `config`

Manage tool configuration.

### Signature

```
issue-resolver config [OPTIONS]
```

### Options

| Flag | Type | Description |
|------|------|-------------|
| `--init` | bool | Generate example config file in current directory |
| `--show` | bool | Display current effective configuration (secrets redacted) |

### Output (`--show`)

```
Current Configuration (merged from: ~/.config/issue-resolver/config.yaml + env vars)

  auto_pr: false
  dry_run: false
  max_issues_per_run: 5

  search:
    labels: [bug, help-wanted, good-first-issue]
    languages: [python]
    min_stars: 50
    max_age_days: 365

  claude:
    model: opus
    analysis_max_budget_usd: 0.50
    resolution_max_budget_usd: 5.00
    total_session_budget_usd: 25.00

  workspace:
    base_dir: /tmp/issue-resolver-workspaces

  Secrets:
    GITHUB_TOKEN: ****set****
    ANTHROPIC_API_KEY: ****set****
```
