import json

from quota_dash.proxy.parser import detect_provider, extract_usage
from quota_dash.proxy.streaming import StreamingBuffer


def test_detect_google():
    body = {
        "candidates": [{"content": {"parts": [{"text": "hi"}]}}],
        "usageMetadata": {
            "promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15,
        },
    }
    assert detect_provider(body) == "google"


def test_detect_google_no_false_positive_openai():
    body = {"choices": [{}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
    assert detect_provider(body) == "openai"


def test_extract_google_usage():
    body = {
        "modelVersion": "gemini-2.0-flash",
        "candidates": [{}],
        "usageMetadata": {
            "promptTokenCount": 100, "candidatesTokenCount": 50, "totalTokenCount": 150,
        },
    }
    headers = {}
    endpoint = "/v1beta/models/gemini-2.0-flash:generateContent"
    target_url = (
        "https://generativelanguage.googleapis.com"
        "/v1beta/models/gemini-2.0-flash:generateContent"
    )
    record = extract_usage(body, headers, endpoint=endpoint, target_url=target_url)
    assert record.provider == "google"
    assert record.input_tokens == 100
    assert record.output_tokens == 50
    assert record.total_tokens == 150
    assert record.model == "gemini-2.0-flash"


def test_extract_google_no_usage():
    body = {"candidates": [{}]}
    record = extract_usage(body, {}, endpoint="/v1beta/models/test", target_url="https://example.com")
    assert record.provider == "unknown"


def test_streaming_google_usage():
    buf = StreamingBuffer()
    buf.feed_line("data: " + json.dumps({
        "candidates": [{"content": {"parts": [{"text": "Hello"}]}}],
    }))
    buf.feed_line("data: " + json.dumps({
        "candidates": [{"content": {"parts": [{"text": " world"}]}}],
        "usageMetadata": {
            "promptTokenCount": 50, "candidatesTokenCount": 20, "totalTokenCount": 70,
        },
    }))

    record = buf.extract_usage(
        headers={},
        endpoint="/v1beta/models/gemini:generateContent",
        target_url="https://generativelanguage.googleapis.com",
    )
    assert record.provider == "google"
    assert record.input_tokens == 50
    assert record.output_tokens == 20
    assert record.total_tokens == 70
