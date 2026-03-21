from __future__ import annotations

import os


def is_ghostty() -> bool:
    return os.environ.get("TERM_PROGRAM") == "ghostty"
