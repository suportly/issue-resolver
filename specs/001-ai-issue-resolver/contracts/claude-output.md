# Claude Code CLI Output Contract

**Feature**: 001-ai-issue-resolver
**Date**: 2026-02-22
**Source**: [research.md](../research.md) Decision 2

---

## JSON Output Schema

When invoking Claude Code CLI with `--output-format json`, the CLI emits a single JSON object to stdout upon completion.

```json
{
  "result": "string — the final text response from the model",
  "is_error": false,
  "cost_usd": 0.0123,
  "duration_ms": 4521,
  "num_turns": 3,
  "session_id": "uuid-string"
}
```

### Field Reference

| Field | Type | Always Present | Description |
|-------|------|----------------|-------------|
| `result` | string | yes | Final assistant response text. May be empty on error. |
| `is_error` | boolean | yes | `true` if the session ended abnormally (budget exceeded, unrecoverable error). |
| `cost_usd` | number | yes | Total API cost in USD. Note: some versions use `total_cost_usd` — parser handles both. |
| `duration_ms` | number | yes | Wall-clock duration in milliseconds. |
| `num_turns` | number | yes | Number of conversational turns executed. |
| `session_id` | string | yes | UUID identifying the session. |

---

## Invocation Patterns

### Analysis (Read-Only, Cheap)

```python
subprocess.run(
    ["claude", "-p", analysis_prompt,
     "--output-format", "json",
     "--max-turns", "1",
     "--model", "haiku"],
    capture_output=True, text=True, timeout=60
)
```

- **Purpose**: Solvability assessment — classify issue, estimate confidence
- **Budget**: ~$0.05-0.50 per analysis
- **No permissions needed**: Read-only, no tool use

### Resolution (Full Agent, Expensive)

```python
subprocess.run(
    ["claude", "-p", resolution_prompt,
     "--output-format", "json",
     "--max-turns", "30",
     "--model", "opus",
     "--permission-mode", "bypassPermissions",
     "--max-budget-usd", "5.00"],
    capture_output=True, text=True, timeout=300,
    cwd=workspace_path
)
```

- **Purpose**: Implement fix — edit files, run commands, commit changes
- **Budget**: ~$1.00-5.00 per resolution
- **Permissions bypassed**: Required for unattended file editing and shell execution

---

## Termination Conditions

| Condition | `is_error` | Exit Code | `result` | How to Detect |
|-----------|-----------|-----------|----------|---------------|
| Normal completion | `false` | 0 | Full response | Default case |
| Max turns reached | `false` | 0 | Partial (work so far) | `num_turns == max_turns` |
| Budget exceeded | `true` | 0 | Partial or empty | `is_error=true AND cost_usd >= budget * 0.9` |
| Auth/usage error | `true` | 1 | Empty | `returncode != 0` |
| External timeout | N/A | N/A | No JSON | `subprocess.TimeoutExpired` exception |

---

## Parser Contract

The `claude/parser.py` module must:

1. Handle `subprocess.TimeoutExpired` → return `outcome="timeout"`
2. Handle non-zero exit code → return `outcome="process_error"`
3. Handle `json.JSONDecodeError` → return `outcome="parse_error"`, log raw stdout
4. Normalize cost field: accept both `cost_usd` and `total_cost_usd`
5. Check BOTH `is_error` and exit code — they are independent signals
6. Classify termination: budget exceeded vs. max turns vs. agent error vs. success
