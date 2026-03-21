from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProviderConfig:
    enabled: bool = True
    api_key_env: str = ""
    log_path: Path = field(default_factory=lambda: Path.home())

    # Manual quota entry (fallback when API unavailable)
    balance_usd: float | None = None
    limit_usd: float | None = None


@dataclass
class ProxyConfig:
    enabled: bool = False
    port: int = 8300
    db_path: Path = field(default_factory=lambda: Path.home() / ".config" / "quota-dash" / "usage.db")
    log_path: Path = field(default_factory=lambda: Path.home() / ".config" / "quota-dash" / "proxy.log")
    targets: dict[str, str] = field(default_factory=lambda: {
        "openai": "https://api.openai.com",
        "anthropic": "https://api.anthropic.com",
    })
    auto_start: bool = False


@dataclass
class AlertConfig:
    warning: int = 50
    alert: int = 20
    critical: int = 5


@dataclass
class AppConfig:
    polling_interval: int = 60
    theme: str = "auto"
    mode: str = "dashboard"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)


def load_config(path: Path | None) -> AppConfig:
    if path is None or not path.exists():
        return AppConfig()

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    general = raw.get("general", {})
    providers_raw = raw.get("providers", {})

    providers: dict[str, ProviderConfig] = {}
    for name, prov in providers_raw.items():
        log_path = Path(prov.get("log_path", "~")).expanduser()
        providers[name] = ProviderConfig(
            enabled=prov.get("enabled", True),
            api_key_env=prov.get("api_key_env", ""),
            log_path=log_path,
            balance_usd=prov.get("balance_usd"),
            limit_usd=prov.get("limit_usd"),
        )

    proxy_raw = raw.get("proxy", {})
    proxy_targets = proxy_raw.get("targets", {})
    proxy = ProxyConfig(
        enabled=proxy_raw.get("enabled", False),
        port=proxy_raw.get("port", 8300),
        db_path=Path(proxy_raw.get("db_path", "~/.config/quota-dash/usage.db")).expanduser(),
        log_path=Path(proxy_raw.get("log_path", "~/.config/quota-dash/proxy.log")).expanduser(),
        targets={**ProxyConfig().targets, **proxy_targets},
        auto_start=proxy_raw.get("auto_start", False),
    )

    alerts_raw = raw.get("alerts", {})
    alerts = AlertConfig(
        warning=alerts_raw.get("warning", 50),
        alert=alerts_raw.get("alert", 20),
        critical=alerts_raw.get("critical", 5),
    )

    return AppConfig(
        polling_interval=general.get("polling_interval", 60),
        theme=general.get("theme", "auto"),
        mode=general.get("mode", "dashboard"),
        providers=providers,
        proxy=proxy,
        alerts=alerts,
    )
