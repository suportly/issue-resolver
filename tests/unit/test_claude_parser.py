"""Unit tests for Claude Code CLI JSON output parser."""

import json

from issue_resolver.claude.parser import parse_response


class TestParseResponse:
    def test_success(self) -> None:
        stdout = json.dumps(
            {
                "result": "Fix applied successfully",
                "is_error": False,
                "cost_usd": 2.34,
                "duration_ms": 45000,
                "num_turns": 8,
                "session_id": "test-session-1",
            }
        )
        result = parse_response(stdout, "", 0, False)
        assert result.outcome == "success"
        assert result.result_text == "Fix applied successfully"
        assert result.cost_usd == 2.34
        assert result.duration_ms == 45000
        assert result.num_turns == 8
        assert result.session_id == "test-session-1"
        assert result.is_error is False

    def test_error_with_is_error_true(self) -> None:
        stdout = json.dumps(
            {
                "result": "",
                "is_error": True,
                "cost_usd": 0.15,
                "duration_ms": 5000,
                "num_turns": 1,
                "session_id": "test-session-2",
            }
        )
        result = parse_response(stdout, "", 0, False)
        assert result.outcome == "budget_exceeded"
        assert result.is_error is True
        assert result.cost_usd == 0.15

    def test_timeout_handling(self) -> None:
        result = parse_response("", "Timeout", -1, True)
        assert result.outcome == "timeout"
        assert result.is_error is True
        assert result.cost_usd == 0.0

    def test_non_zero_exit_code(self) -> None:
        result = parse_response("", "Auth error", 1, False)
        assert result.outcome == "process_error"
        assert result.is_error is True

    def test_malformed_json(self) -> None:
        result = parse_response("not json at all", "", 0, False)
        assert result.outcome == "parse_error"
        assert result.is_error is True
        assert result.raw_stdout == "not json at all"

    def test_cost_usd_normalization(self) -> None:
        """Parser should accept both cost_usd and total_cost_usd."""
        stdout = json.dumps(
            {
                "result": "done",
                "is_error": False,
                "cost_usd": 1.23,
                "duration_ms": 1000,
                "num_turns": 1,
                "session_id": "s1",
            }
        )
        result = parse_response(stdout, "", 0, False)
        assert result.cost_usd == 1.23

    def test_total_cost_usd_fallback(self) -> None:
        """Parser should use total_cost_usd when cost_usd is absent."""
        stdout = json.dumps(
            {
                "result": "done",
                "is_error": False,
                "total_cost_usd": 4.56,
                "duration_ms": 2000,
                "num_turns": 3,
                "session_id": "s2",
            }
        )
        result = parse_response(stdout, "", 0, False)
        assert result.cost_usd == 4.56

    def test_budget_exceeded_detection(self) -> None:
        """Budget exceeded: is_error=True with cost > 0."""
        stdout = json.dumps(
            {
                "result": "Partial work",
                "is_error": True,
                "cost_usd": 4.95,
                "duration_ms": 120000,
                "num_turns": 25,
                "session_id": "s3",
            }
        )
        result = parse_response(stdout, "", 0, False)
        assert result.outcome == "budget_exceeded"
        assert result.cost_usd == 4.95

    def test_is_error_true_zero_cost(self) -> None:
        """is_error=True with zero cost is a process error, not budget exceeded."""
        stdout = json.dumps(
            {
                "result": "",
                "is_error": True,
                "cost_usd": 0.0,
                "duration_ms": 0,
                "num_turns": 0,
                "session_id": "s4",
            }
        )
        result = parse_response(stdout, "", 0, False)
        assert result.outcome == "process_error"

    def test_empty_stdout_with_zero_exit(self) -> None:
        result = parse_response("", "", 0, False)
        assert result.outcome == "parse_error"
