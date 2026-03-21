import json
import tempfile
from pathlib import Path

from quota_dash.data.log_parser import parse_claude_costs_jsonl, parse_codex_logs


def test_parse_claude_costs_jsonl_with_data():
    entries = [
        {
            "timestamp": "2026-03-20T10:00:00Z", "session_id": "s1",
            "model": "claude-opus-4-6", "input_tokens": 1500,
            "output_tokens": 800, "cost_usd": 0.05,
        },
        {
            "timestamp": "2026-03-20T10:05:00Z", "session_id": "s1",
            "model": "claude-opus-4-6", "input_tokens": 2000,
            "output_tokens": 1200, "cost_usd": 0.07,
        },
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
        path = Path(f.name)

    result = parse_claude_costs_jsonl(path)
    assert result.input_tokens == 3500
    assert result.output_tokens == 2000
    assert result.total_tokens == 5500
    assert len(result.history) == 2
    path.unlink()


def test_parse_claude_costs_jsonl_all_zeros():
    entries = [
        {
            "timestamp": "2026-03-20T10:00:00Z", "session_id": "s1",
            "model": "unknown", "input_tokens": 0, "output_tokens": 0, "cost_usd": 0,
        },
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
        path = Path(f.name)

    result = parse_claude_costs_jsonl(path)
    assert result.total_tokens == 0
    assert result.source == "log"
    path.unlink()


def test_parse_claude_costs_jsonl_missing_file():
    result = parse_claude_costs_jsonl(Path("/nonexistent/costs.jsonl"))
    assert result.total_tokens == 0
    assert result.source == "estimated"


def test_parse_codex_logs_missing_file():
    result = parse_codex_logs(Path("/nonexistent/logs.sqlite"))
    assert result.total_tokens == 0
    assert result.source == "estimated"


def test_parse_claude_costs_permission_error(tmp_path):
    """File with no read permission should return estimated."""
    import os
    path = tmp_path / "no_read.jsonl"
    path.write_text('{"input_tokens": 100}')
    os.chmod(path, 0o000)
    result = parse_claude_costs_jsonl(path)
    assert result.source == "estimated"
    os.chmod(path, 0o644)  # cleanup


def test_parse_claude_costs_jsonl_malformed_line(tmp_path):
    """Lines that are not valid JSON should be silently skipped."""
    path = tmp_path / "costs.jsonl"
    path.write_text('not json\n{"input_tokens": 10, "output_tokens": 5}\n')
    result = parse_claude_costs_jsonl(path)
    assert result.total_tokens == 15
    assert result.source == "log"


def test_parse_claude_costs_jsonl_bad_timestamp(tmp_path):
    """Entries with malformed timestamps should fall back to datetime.now()."""
    import json
    entry = {"timestamp": "INVALID", "input_tokens": 7, "output_tokens": 3}
    path = tmp_path / "costs.jsonl"
    path.write_text(json.dumps(entry) + "\n")
    result = parse_claude_costs_jsonl(path)
    assert result.total_tokens == 10
    assert len(result.history) == 1
