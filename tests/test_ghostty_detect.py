from unittest.mock import patch
from quota_dash.ghostty.detect import is_ghostty


def test_is_ghostty_true():
    with patch.dict("os.environ", {"TERM_PROGRAM": "ghostty"}):
        assert is_ghostty() is True


def test_is_ghostty_false_other_terminal():
    with patch.dict("os.environ", {"TERM_PROGRAM": "iTerm2"}):
        assert is_ghostty() is False


def test_is_ghostty_false_no_env():
    with patch.dict("os.environ", {}, clear=True):
        assert is_ghostty() is False
