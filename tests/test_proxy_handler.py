# tests/test_proxy_handler.py
from quota_dash.proxy.handler import resolve_target, DEFAULT_ROUTES, build_routes


def test_resolve_openai_chat():
    url = resolve_target("/v1/chat/completions", DEFAULT_ROUTES)
    assert url == "https://api.openai.com/v1/chat/completions"


def test_resolve_openai_embeddings():
    url = resolve_target("/v1/embeddings", DEFAULT_ROUTES)
    assert url == "https://api.openai.com/v1/embeddings"


def test_resolve_anthropic_messages():
    url = resolve_target("/v1/messages", DEFAULT_ROUTES)
    assert url == "https://api.anthropic.com/v1/messages"


def test_resolve_unknown_path():
    url = resolve_target("/v2/something", DEFAULT_ROUTES)
    assert url is None


def test_resolve_with_custom_targets():
    routes = {**DEFAULT_ROUTES, "/v1/custom": "https://custom.api.com"}
    url = resolve_target("/v1/custom/endpoint", routes)
    assert url == "https://custom.api.com/v1/custom/endpoint"


def test_build_routes_merges_config():
    config_targets = {"openai": "https://custom-openai.com", "anthropic": "https://custom-anthropic.com"}
    routes = build_routes(config_targets)
    assert routes["/v1/chat/completions"] == "https://custom-openai.com"
    assert routes["/v1/messages"] == "https://custom-anthropic.com"


def test_build_routes_defaults():
    routes = build_routes(None)
    assert routes == DEFAULT_ROUTES
