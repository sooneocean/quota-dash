# tests/test_proxy_streaming.py
import json
from quota_dash.proxy.streaming import StreamingBuffer


def test_openai_streaming_usage():
    buf = StreamingBuffer()
    # Simulate OpenAI SSE chunks
    buf.feed_line("data: " + json.dumps({"choices": [{"delta": {"content": "Hello"}}]}))
    buf.feed_line("data: " + json.dumps({
        "choices": [],
        "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
    }))
    buf.feed_line("data: [DONE]")

    record = buf.extract_usage(
        headers={},
        endpoint="/v1/chat/completions",
        target_url="https://api.openai.com/v1/chat/completions",
    )
    assert record is not None
    assert record.provider == "openai"
    assert record.input_tokens == 50
    assert record.output_tokens == 20
    assert record.total_tokens == 70


def test_anthropic_streaming_usage():
    buf = StreamingBuffer()
    # message_start with input_tokens
    buf.feed_line("event: message_start")
    buf.feed_line("data: " + json.dumps({
        "type": "message_start", "message": {"usage": {"input_tokens": 100}},
    }))
    # content delta
    buf.feed_line("event: content_block_delta")
    buf.feed_line("data: " + json.dumps({"type": "content_block_delta"}))
    # message_delta with output_tokens
    buf.feed_line("event: message_delta")
    buf.feed_line("data: " + json.dumps({
        "type": "message_delta", "usage": {"output_tokens": 45},
    }))
    # message_stop
    buf.feed_line("event: message_stop")
    buf.feed_line("data: " + json.dumps({"type": "message_stop"}))

    record = buf.extract_usage(
        headers={"request-id": "r-1"},
        endpoint="/v1/messages",
        target_url="https://api.anthropic.com/v1/messages",
    )
    assert record is not None
    assert record.provider == "anthropic"
    assert record.input_tokens == 100
    assert record.output_tokens == 45
    assert record.total_tokens == 145
    assert record.request_id == "r-1"


def test_streaming_no_usage():
    buf = StreamingBuffer()
    buf.feed_line("data: " + json.dumps({"choices": [{"delta": {"content": "hi"}}]}))
    buf.feed_line("data: [DONE]")

    record = buf.extract_usage(
        headers={},
        endpoint="/v1/chat/completions",
        target_url="https://api.openai.com/v1/chat/completions",
    )
    assert record is not None
    assert record.total_tokens == 0
    assert record.provider == "unknown"


def test_streaming_malformed_lines():
    buf = StreamingBuffer()
    buf.feed_line("not valid sse")
    buf.feed_line("data: {not json}")
    buf.feed_line("data: [DONE]")

    record = buf.extract_usage(
        headers={}, endpoint="/v1/test", target_url="https://example.com"
    )
    assert record is not None
    assert record.total_tokens == 0
