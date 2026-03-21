# tests/test_proxy_parser.py
from quota_dash.proxy.parser import detect_provider, extract_usage
from quota_dash.proxy.db import ApiCallRecord


def test_detect_openai():
    body = {"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
    assert detect_provider(body) == "openai"


def test_detect_anthropic():
    body = {"type": "message", "usage": {"input_tokens": 10, "output_tokens": 5}}
    assert detect_provider(body) == "anthropic"


def test_detect_unknown():
    body = {"foo": "bar"}
    assert detect_provider(body) == "unknown"


def test_extract_openai_usage():
    body = {"model": "gpt-4", "choices": [{}], "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}
    headers = {"x-request-id": "req-abc", "x-ratelimit-remaining-tokens": "9000", "x-ratelimit-remaining-requests": "99"}
    record = extract_usage(body, headers, endpoint="/v1/chat/completions", target_url="https://api.openai.com/v1/chat/completions")
    assert record.provider == "openai"
    assert record.input_tokens == 100
    assert record.output_tokens == 50
    assert record.total_tokens == 150
    assert record.model == "gpt-4"
    assert record.request_id == "req-abc"
    assert record.ratelimit_remaining_tokens == 9000


def test_extract_anthropic_usage():
    body = {"type": "message", "model": "claude-opus-4-6", "usage": {"input_tokens": 200, "output_tokens": 80}}
    headers = {"request-id": "req-xyz", "anthropic-ratelimit-tokens-remaining": "50000"}
    record = extract_usage(body, headers, endpoint="/v1/messages", target_url="https://api.anthropic.com/v1/messages")
    assert record.provider == "anthropic"
    assert record.input_tokens == 200
    assert record.output_tokens == 80
    assert record.total_tokens == 280
    assert record.ratelimit_remaining_tokens == 50000


def test_extract_unknown_provider():
    body = {"random": "data"}
    headers = {"x-ratelimit-remaining-tokens": "5000"}
    record = extract_usage(body, headers, endpoint="/v1/foo", target_url="https://example.com")
    assert record.provider == "unknown"
    assert record.input_tokens == 0


def test_extract_malformed_body():
    record = extract_usage({}, {}, endpoint="/v1/test", target_url="https://example.com")
    assert record.provider == "unknown"
    assert record.total_tokens == 0
