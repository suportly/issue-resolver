# Data Model: AI-Powered GitHub Issue Resolution Tool

**Feature**: 001-ai-issue-resolver
**Date**: 2026-02-22
**Source**: [spec.md](spec.md) Key Entities + [research.md](research.md) Decision 4

---

## Entity: Issue

A GitHub issue discovered through scanning. Represents the raw issue metadata as fetched from GitHub.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | yes | Internal unique identifier |
| repo_owner | string | yes | Repository owner (e.g., "encode") |
| repo_name | string | yes | Repository name (e.g., "django-rest-framework") |
| number | integer | yes | GitHub issue number |
| title | string | yes | Issue title |
| body | string | no | Issue body (markdown) |
| labels | list[string] | no | Issue labels (stored as JSON text) |
| url | string (URL) | yes | Full GitHub issue URL |
| state | string | yes | Issue state: "open" or "closed" |
| has_assignees | boolean | yes | Whether the issue has assignees |
| has_linked_prs | boolean | yes | Whether the issue has linked PRs |
| language | string | no | Primary repo language (from GitHub) |
| repo_stars | integer | no | Repository star count at scan time |
| created_at | datetime (ISO 8601) | yes | When the issue was created on GitHub |
| discovered_at | datetime (ISO 8601) | yes | When the tool first discovered this issue |

### Constraints

- **Unique**: `(repo_owner, repo_name, number)` — no duplicate issues
- **Primary key**: `id` (UUID generated on insert)

### Lifecycle

```
discovered → analyzed → attempted (or filtered/skipped)
```

---

## Entity: Analysis

An AI-generated solvability assessment for an issue. Created by the analyzer pipeline stage. Serves as the gate for resolution attempts.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | yes | Internal unique identifier |
| issue_id | string (FK → Issue.id) | yes | Reference to the analyzed issue |
| rating | enum | yes | Solvability rating (see below) |
| confidence | float (0.0-1.0) | yes | AI confidence in the assessment |
| complexity | string | no | Estimated complexity (low, medium, high) |
| reasoning | string | yes | Human-readable explanation of the assessment |
| cost_usd | float | no | Cost of the analysis AI call |
| model | string | no | AI model used for analysis |
| duration_ms | integer | no | Duration of the analysis call |
| created_at | datetime (ISO 8601) | yes | When the analysis was performed |

### Solvability Rating (Enum)

| Value | Meaning | Action |
|-------|---------|--------|
| `solvable` | Clear bug with reproduction steps, specific error, small scope | Proceed to resolution |
| `likely_solvable` | Probable fix possible but some uncertainty | Proceed if confidence >= 70% |
| `unlikely_solvable` | Significant uncertainty — vague description, large scope | Skip (record as filtered) |
| `unsolvable` | Feature request, design discussion, requires maintainer decision | Skip (record as filtered) |

### Constraints

- **Foreign key**: `issue_id` references `issues.id`
- **Check**: `confidence` BETWEEN 0.0 AND 1.0
- **Check**: `rating` IN ('solvable', 'likely_solvable', 'unlikely_solvable', 'unsolvable')
- **Gate rule** (FR-003): Only proceed to resolution if `rating` IN ('solvable', 'likely_solvable') AND `confidence` >= 0.7

---

## Entity: Attempt

A record of a resolution attempt. Created when the resolver pipeline stage begins work on an issue. Updated as the attempt progresses through stages.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID) | yes | Internal unique identifier |
| issue_id | string (FK → Issue.id) | yes | Reference to the target issue |
| status | enum | yes | Current attempt status (see below) |
| outcome | enum | no | Outcome category when completed/failed (see below) |
| cost_usd | float | no | Total cost of the resolution AI call |
| duration_ms | integer | no | Total duration of the attempt |
| workspace_path | string | no | Path to the temporary workspace directory |
| pr_url | string (URL) | no | URL of the submitted PR (if any) |
| pr_number | integer | no | PR number on the target repo (if any) |
| branch_name | string | no | Git branch name used for the fix |
| num_turns | integer | no | Number of AI agent turns used |
| model | string | no | AI model used for resolution |
| test_output | string | no | Truncated test runner output (stdout + stderr) |
| diff_summary | string | no | Summary of changes (files changed, insertions, deletions) |
| created_at | datetime (ISO 8601) | yes | When the attempt started |
| updated_at | datetime (ISO 8601) | yes | Last update timestamp |

### Attempt Status (Enum)

| Value | Meaning |
|-------|---------|
| `pending` | Attempt created, not yet started |
| `in_progress` | Resolution actively running |
| `succeeded` | PR submitted successfully (tests passed) |
| `failed` | Attempt ended with a categorized failure |

### Outcome Category (Enum)

| Value | Meaning | Workspace |
|-------|---------|-----------|
| `pr_submitted` | PR created and submitted | Cleaned up |
| `tests_failed` | AI fix applied but tests failed | Preserved |
| `empty_diff` | AI produced no changes | Cleaned up |
| `resolution_failed` | AI agent errored during resolution | Preserved |
| `analysis_failed` | Solvability analysis itself failed | N/A |
| `budget_exceeded` | Per-resolution budget limit hit | Preserved |
| `timeout` | AI agent exceeded timeout | Preserved |
| `parse_error` | AI returned unparseable/invalid JSON | Preserved |
| `stale_issue` | Issue closed or PR submitted since scan | N/A |
| `untested` | Fix applied, no test suite found, PR submitted | Cleaned up |

### Constraints

- **Foreign key**: `issue_id` references `issues.id`
- **Check**: `status` IN ('pending', 'in_progress', 'succeeded', 'failed')
- **Check**: `outcome` IN (the enum values above) OR NULL (when pending/in_progress)

---

## Entity Relationships

```
Issue (1) ──── (0..N) Analysis
Issue (1) ──── (0..N) Attempt
```

- One issue can have multiple analyses (re-analysis after spec update, different models)
- One issue can have multiple attempts (retry after failure, different budget, different model)
- Analyses and attempts are independent — an attempt doesn't require a specific analysis record, though in practice one analysis gates the attempt

---

## SQLite Schema (Migration 1)

```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS issues (
    id              TEXT PRIMARY KEY,
    repo_owner      TEXT NOT NULL,
    repo_name       TEXT NOT NULL,
    number          INTEGER NOT NULL,
    title           TEXT NOT NULL,
    body            TEXT,
    labels          TEXT,              -- JSON array of strings
    url             TEXT NOT NULL,
    state           TEXT NOT NULL DEFAULT 'open',
    has_assignees   INTEGER NOT NULL DEFAULT 0,
    has_linked_prs  INTEGER NOT NULL DEFAULT 0,
    language        TEXT,
    repo_stars      INTEGER,
    created_at      TEXT NOT NULL,
    discovered_at   TEXT NOT NULL,
    UNIQUE(repo_owner, repo_name, number)
);

CREATE TABLE IF NOT EXISTS analyses (
    id              TEXT PRIMARY KEY,
    issue_id        TEXT NOT NULL REFERENCES issues(id),
    rating          TEXT NOT NULL,
    confidence      REAL NOT NULL,
    complexity      TEXT,
    reasoning       TEXT NOT NULL,
    cost_usd        REAL,
    model           TEXT,
    duration_ms     INTEGER,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    id              TEXT PRIMARY KEY,
    issue_id        TEXT NOT NULL REFERENCES issues(id),
    status          TEXT NOT NULL DEFAULT 'pending',
    outcome         TEXT,
    cost_usd        REAL,
    duration_ms     INTEGER,
    workspace_path  TEXT,
    pr_url          TEXT,
    pr_number       INTEGER,
    branch_name     TEXT,
    num_turns       INTEGER,
    model           TEXT,
    test_output     TEXT,
    diff_summary    TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_issues_repo ON issues(repo_owner, repo_name);
CREATE INDEX IF NOT EXISTS idx_analyses_issue_id ON analyses(issue_id);
CREATE INDEX IF NOT EXISTS idx_attempts_issue_id ON attempts(issue_id);
CREATE INDEX IF NOT EXISTS idx_attempts_status ON attempts(status);
CREATE INDEX IF NOT EXISTS idx_attempts_outcome ON attempts(outcome);
```

---

## Key Queries

### Deduplication (FR-010): Exclude already-attempted issues

```sql
SELECT i.* FROM issues i
WHERE i.repo_owner = ? AND i.repo_name = ? AND i.number = ?
AND NOT EXISTS (
    SELECT 1 FROM attempts a WHERE a.issue_id = i.id
);
```

### Resolution Funnel (FR-023)

```sql
SELECT
    COUNT(*) AS discovered,
    SUM(CASE WHEN EXISTS (SELECT 1 FROM analyses a WHERE a.issue_id = i.id AND a.rating IN ('solvable','likely_solvable') AND a.confidence >= 0.7) THEN 1 ELSE 0 END) AS passed_filter,
    SUM(CASE WHEN EXISTS (SELECT 1 FROM attempts t WHERE t.issue_id = i.id) THEN 1 ELSE 0 END) AS attempted,
    SUM(CASE WHEN EXISTS (SELECT 1 FROM attempts t WHERE t.issue_id = i.id AND t.outcome != 'empty_diff') THEN 1 ELSE 0 END) AS non_empty_diff,
    SUM(CASE WHEN EXISTS (SELECT 1 FROM attempts t WHERE t.issue_id = i.id AND t.outcome IN ('pr_submitted','untested')) THEN 1 ELSE 0 END) AS tests_pass,
    SUM(CASE WHEN EXISTS (SELECT 1 FROM attempts t WHERE t.issue_id = i.id AND t.outcome IN ('pr_submitted','untested') AND t.pr_url IS NOT NULL) THEN 1 ELSE 0 END) AS pr_submitted
FROM issues i;
```

### Per-Language Statistics (FR-022)

```sql
SELECT
    i.language,
    COUNT(t.id) AS attempts,
    SUM(CASE WHEN t.outcome IN ('pr_submitted','untested') THEN 1 ELSE 0 END) AS successes,
    ROUND(AVG(t.cost_usd), 4) AS avg_cost,
    ROUND(AVG(t.duration_ms) / 1000.0, 1) AS avg_duration_s
FROM attempts t
JOIN issues i ON t.issue_id = i.id
WHERE t.status = 'failed' OR t.status = 'succeeded'
GROUP BY i.language;
```

### Solvability Calibration (FR-024)

```sql
SELECT
    CASE
        WHEN a.confidence >= 0.9 THEN '90-100%'
        WHEN a.confidence >= 0.7 THEN '70-89%'
        WHEN a.confidence >= 0.5 THEN '50-69%'
        ELSE '<50%'
    END AS confidence_band,
    COUNT(*) AS total,
    SUM(CASE WHEN t.outcome IN ('pr_submitted','untested') THEN 1 ELSE 0 END) AS actual_successes,
    ROUND(100.0 * SUM(CASE WHEN t.outcome IN ('pr_submitted','untested') THEN 1 ELSE 0 END) / COUNT(*), 1) AS actual_success_rate
FROM analyses a
JOIN attempts t ON t.issue_id = a.issue_id
GROUP BY confidence_band;
```
