from __future__ import annotations

DEFAULT_ROUTES: dict[str, str] = {
    "/v1/messages": "https://api.anthropic.com",
    "/v1/chat/completions": "https://api.openai.com",
    "/v1/completions": "https://api.openai.com",
    "/v1/embeddings": "https://api.openai.com",
}

# Maps path prefix -> which config target key it belongs to
_PATH_TO_PROVIDER: dict[str, str] = {
    "/v1/messages": "anthropic",
    "/v1/chat/completions": "openai",
    "/v1/completions": "openai",
    "/v1/embeddings": "openai",
}


def resolve_target(path: str, routes: dict[str, str]) -> str | None:
    for prefix, base_url in routes.items():
        if path.startswith(prefix):
            return base_url + path
    return None


def build_routes(config_targets: dict[str, str] | None) -> dict[str, str]:
    """Merge config targets into default routes."""
    if not config_targets:
        return dict(DEFAULT_ROUTES)

    routes: dict[str, str] = {}
    for path_prefix, provider_name in _PATH_TO_PROVIDER.items():
        base = config_targets.get(provider_name, DEFAULT_ROUTES[path_prefix])
        routes[path_prefix] = base
    return routes


def provider_for_path(path: str) -> str | None:
    """Return provider name for a given path, or None."""
    for prefix, provider in _PATH_TO_PROVIDER.items():
        if path.startswith(prefix):
            return provider
    return None
