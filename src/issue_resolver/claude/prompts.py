"""Prompt templates for Claude Code CLI analysis and resolution."""

from __future__ import annotations

from issue_resolver.models.issue import Issue


def build_analysis_prompt(issue: Issue) -> str:
    """Build a solvability analysis prompt for an issue.

    The prompt instructs Claude to return a JSON object with:
    rating, confidence, complexity, reasoning.
    """
    labels_str = ", ".join(issue.labels) if issue.labels else "none"

    return f"""Analyze this GitHub issue for solvability. You are evaluating whether \
an automated AI coding agent can successfully fix this issue.

## Issue Details

**Repository**: {issue.full_repo}
**Issue #{issue.number}**: {issue.title}
**Labels**: {labels_str}
**Language**: {issue.language or "unknown"}

**Description**:
{issue.body or "(no description)"}

## Instructions

Respond with ONLY a JSON object (no markdown, no code blocks) with these fields:

- "rating": One of "solvable", "likely_solvable", "unlikely_solvable", "unsolvable"
  - "solvable": Clear bug with reproduction steps, specific error, small scope
  - "likely_solvable": Probable fix but some uncertainty
  - "unlikely_solvable": Vague, large scope, significant uncertainty
  - "unsolvable": Feature request, design discussion, requires maintainer decision
- "confidence": Float between 0.0 and 1.0
- "complexity": One of "low", "medium", "high"
- "reasoning": 1-3 sentences explaining your assessment

Factors that increase solvability:
- Specific error messages or stack traces
- Clear reproduction steps
- Small, well-defined scope
- Maintainer comments pointing to the fix location
- Existing test cases that fail

Factors that decrease solvability:
- Vague "doesn't work" descriptions
- Feature requests or design discussions
- Requires understanding of complex architecture
- No reproduction steps
- Multiple interconnected issues"""


def build_resolution_prompt(
    issue: Issue,
    contributing_md: str | None = None,
    pr_template: str | None = None,
    test_command: str | None = None,
) -> str:
    """Build a resolution prompt for the AI coding agent.

    This prompt is used with the full agent (opus, 30 turns, bypassPermissions).
    """
    labels_str = ", ".join(issue.labels) if issue.labels else "none"

    sections = [
        f"""You are fixing a GitHub issue. Your goal is to implement a correct fix, \
ensure tests pass, and commit the changes.

## Issue Details

**Repository**: {issue.full_repo}
**Issue #{issue.number}**: {issue.title}
**Labels**: {labels_str}

**Description**:
{issue.body or "(no description)"}

## Instructions

1. Understand the issue thoroughly — read relevant source files, tests, and related code
2. Implement a minimal, focused fix that addresses the issue
3. Follow the project's coding style and conventions"""
    ]

    if contributing_md:
        sections.append(
            f"""
## Contributing Guidelines

{contributing_md[:3000]}"""
        )

    if test_command:
        sections.append(
            f"""
## Testing

Run the project's tests to verify your fix:
```
{test_command}
```

- Your fix MUST NOT break existing tests
- Add new test cases if appropriate
- If tests fail, investigate and fix your implementation"""
        )
    else:
        sections.append(
            """
## Testing

No test runner was detected for this project. \
Verify your changes manually by reviewing the code carefully."""
        )

    sections.append(
        """
## Commit

After implementing and testing the fix:
1. Stage your changes with `git add`
2. Commit with a descriptive message: `git commit -m "Fix: <concise description>"`
3. Do NOT push — the tool will handle pushing and PR creation

## Quality

- Keep changes minimal and focused on the issue
- Do not refactor unrelated code
- Add comments only where the logic isn't self-evident
- Follow existing code patterns in the repository"""
    )

    if pr_template:
        sections.append(
            f"""
## PR Template Reference

Use this as guidance for what information to include in your commit message:
{pr_template[:2000]}"""
        )

    return "\n".join(sections)
