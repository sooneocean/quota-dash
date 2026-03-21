from __future__ import annotations

from quota_dash.providers.base import ManualProvider


class GoogleProvider(ManualProvider):
    name = "google"
    _default_model = "gemini-2.0-flash"
    _max_context = 1048576
