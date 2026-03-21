from __future__ import annotations

from quota_dash.providers.base import ManualProvider


class MistralProvider(ManualProvider):
    name = "mistral"
    _default_model = "mistral-large"
    _max_context = 131072
