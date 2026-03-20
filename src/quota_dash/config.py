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
class AppConfig:
    polling_interval: int = 60
    theme: str = "auto"
    mode: str = "dashboard"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)


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

    polling_interval = general.get("polling_interval", 60)
    if not isinstance(polling_interval, (int, float)) or polling_interval < 1:
        polling_interval = 60

    return AppConfig(
        polling_interval=int(polling_interval),
        theme=general.get("theme", "auto"),
        mode=general.get("mode", "dashboard"),
        providers=providers,
    )
