from __future__ import annotations

from quota_dash.providers.base import ManualProvider


class GroqProvider(ManualProvider):
    name = "groq"
    _default_model = "llama-3.3-70b"
    _max_context = 131072
