# src/quota_dash/i18n.py
from __future__ import annotations

_LANG = "en"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "providers": "PROVIDERS",
        "quick_stats": "QUICK STATS",
        "total": "Total",
        "quota": "Quota",
        "tokens_session": "Tokens (session)",
        "context_window": "Context Window",
        "rate_limits": "Rate Limits",
        "history": "History",
        "loading": "loading...",
        "not_configured": "not configured",
        "no_data": "no data",
        "no_history": "Start proxy to see API call history",
        "stale": "stale",
        "last_call_snapshot": "last call snapshot",
        "all_checks_passed": "All checks passed!",
        "errors_found": "error(s) found.",
        "warnings_found": "warning(s). See details above.",
        "config_written": "Config written to",
        "no_proxy_db": "No proxy database found. Start the proxy first: quota-dash proxy start",
        "proxy_not_running": "No proxy running.",
        "proxy_running": "Proxy running",
        "exported_records": "Exported {count} records to {path}",
    },
    "zh-TW": {
        "providers": "供應商",
        "quick_stats": "快速統計",
        "total": "合計",
        "quota": "額度",
        "tokens_session": "Token 用量（本次）",
        "context_window": "上下文視窗",
        "rate_limits": "速率限制",
        "history": "歷史記錄",
        "loading": "載入中...",
        "not_configured": "未設定",
        "no_data": "無資料",
        "no_history": "啟動 proxy 以查看 API 呼叫歷史",
        "stale": "過期",
        "last_call_snapshot": "最後呼叫快照",
        "all_checks_passed": "所有檢查通過！",
        "errors_found": "個錯誤。",
        "warnings_found": "個警告。請查看上方詳情。",
        "config_written": "設定已寫入",
        "no_proxy_db": "找不到 proxy 資料庫。請先啟動 proxy：quota-dash proxy start",
        "proxy_not_running": "Proxy 未執行。",
        "proxy_running": "Proxy 執行中",
        "exported_records": "已匯出 {count} 筆記錄至 {path}",
    },
}


def set_language(lang: str) -> None:
    global _LANG
    if lang in TRANSLATIONS:
        _LANG = lang


def t(key: str, **kwargs: str | int) -> str:
    """Translate a key. Falls back to English."""
    text = TRANSLATIONS.get(_LANG, TRANSLATIONS["en"]).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text
