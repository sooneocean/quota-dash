from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from quota_dash.config import load_config
from quota_dash.providers.anthropic import AnthropicProvider
from quota_dash.providers.base import Provider
from quota_dash.providers.openai import OpenAIProvider


def _json_serializer(obj: object) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")


async def _run_once(
    providers: dict[str, Provider], as_json: bool
) -> None:
    results: dict[str, dict] = {}
    for name, provider in providers.items():
        quota = await provider.get_quota()
        tokens = await provider.get_token_usage()
        context = await provider.get_context_window()
        results[name] = {
            "quota": asdict(quota),
            "tokens": asdict(tokens),
            "context": asdict(context),
        }

    if as_json:
        click.echo(json.dumps(results, default=_json_serializer, indent=2))
    else:
        console = Console()
        table = Table(title="quota-dash")
        table.add_column("Provider")
        table.add_column("Balance")
        table.add_column("Limit")
        table.add_column("Tokens (in/out)")
        table.add_column("Context")
        table.add_column("Source")

        for name, data in results.items():
            q = data["quota"]
            t = data["tokens"]
            c = data["context"]
            bal = f"${q['balance_usd']:.2f}" if q["balance_usd"] is not None else "N/A"
            lim = f"${q['limit_usd']:.2f}" if q["limit_usd"] is not None else "N/A"
            tok = f"{t['input_tokens']}/{t['output_tokens']}"
            ctx = f"{c['percent_used']:.0f}% ({c['model']})"
            table.add_row(name, bal, lim, tok, ctx, q["source"])

        console.print(table)


@click.command("quota-dash")
@click.option("--once", is_flag=True, help="One-shot query, print and exit")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON (with --once)")
@click.option("--provider", default=None, help="Show only this provider")
@click.option("--theme", default=None, help="Force theme: default | ghostty")
@click.option("--config", "config_path", default=None, type=click.Path(), help="Config file path")
def main(
    once: bool,
    as_json: bool,
    provider: str | None,
    theme: str | None,
    config_path: str | None,
) -> None:
    """Multi-provider LLM quota monitoring dashboard."""
    path = Path(config_path) if config_path else Path.home() / ".config" / "quota-dash" / "config.toml"
    config = load_config(path if path.exists() else None)

    provider_map_cls = {"openai": OpenAIProvider, "anthropic": AnthropicProvider}
    providers: dict[str, Provider] = {}
    for name, pconfig in config.providers.items():
        if not pconfig.enabled:
            continue
        if provider and name != provider:
            continue
        if name in provider_map_cls:
            providers[name] = provider_map_cls[name](pconfig)

    if once:
        asyncio.run(_run_once(providers, as_json))
    else:
        from quota_dash.app import QuotaDashApp

        app = QuotaDashApp(config=config, theme_override=theme)
        app.run()
