from quota_dash.i18n import t, set_language


def test_default_english():
    set_language("en")
    assert t("quota") == "Quota"
    assert t("loading") == "loading..."


def test_zh_tw():
    set_language("zh-TW")
    assert t("quota") == "額度"
    assert t("loading") == "載入中..."
    set_language("en")  # reset


def test_fallback_to_english():
    set_language("zh-TW")
    assert t("nonexistent_key") == "nonexistent_key"
    set_language("en")


def test_format_args():
    set_language("en")
    result = t("exported_records", count=5, path="out.csv")
    assert "5" in result and "out.csv" in result


def test_invalid_language_keeps_current():
    set_language("en")
    set_language("invalid")
    assert t("quota") == "Quota"  # still English
