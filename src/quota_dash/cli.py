from __future__ import annotations

import asyncio
import json
import os
import shutil
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

EXAMPLE_CONFIG = Path(__file__).parent.parent.parent / "config.example.toml"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "quota-dash"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"


def _format_tokens(t: dict) -> str:
    """Format token counts, preferring in/out split when available."""
    inp, out, total = t["input_tokens"], t["output_tokens"], t["total_tokens"]
    if inp > 0 or out > 0:
        return f"{_human_k(inp)}/{_human_k(out)}"
    if total > 0:
        return _human_k(total)
    return "0"


def _human_k(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


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
        table.add_column("Tokens")
        table.add_column("Context")
        table.add_column("Source")

        for name, data in results.items():
            q = data["quota"]
            t = data["tokens"]
            c = data["context"]
            bal = f"${q['balance_usd']:.2f}" if q["balance_usd"] is not None else "N/A"
            lim = f"${q['limit_usd']:.2f}" if q["limit_usd"] is not None else "N/A"
            tok = _format_tokens(t)
            ctx = f"{c['percent_used']:.0f}% ({c['model']})"
            table.add_row(name, bal, lim, tok, ctx, q["source"])

        console.print(table)


async def _run_check(providers: dict[str, Provider]) -> None:
    """Test connectivity for each provider and print results."""
    console = Console()
    from quota_dash.data.api_client import check_openai_connection

    for name, provider in providers.items():
        console.print(f"\n[bold]{name}[/bold]")

        if name == "openai":
            api_key = os.environ.get(provider._config.api_key_env, "")
            ok, msg = await check_openai_connection(api_key)
            status = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
            console.print(f"  API connection: {status} — {msg}")

            state_db = provider._config.log_path / "state_5.sqlite"
            if state_db.exists():
                console.print(f"  Codex state DB: [green]found[/green] — {state_db}")
            else:
                console.print(f"  Codex state DB: [yellow]not found[/yellow] — {state_db}")

        elif name == "anthropic":
            costs_path = provider._config.log_path / "metrics" / "costs.jsonl"
            if costs_path.exists():
                console.print(f"  costs.jsonl:    [green]found[/green] — {costs_path}")
            else:
                console.print(f"  costs.jsonl:    [yellow]not found[/yellow] — {costs_path}")

            if provider._config.balance_usd is not None:
                console.print(f"  Manual quota:   [green]configured[/green] — ${provider._config.balance_usd:.2f}")
            else:
                console.print("  Manual quota:   [yellow]not set[/yellow] (Anthropic has no usage API)")

    console.print()


def _run_init() -> None:
    """Copy example config to default location."""
    console = Console()

    if DEFAULT_CONFIG_PATH.exists():
        console.print(f"[yellow]Config already exists:[/yellow] {DEFAULT_CONFIG_PATH}")
        console.print("Delete it first if you want to reinitialize.")
        return

    # Find the example config (works both installed and editable)
    example = EXAMPLE_CONFIG
    if not example.exists():
        # Fallback: look relative to package
        example = Path(__file__).parent / "config.example.toml"
    if not example.exists():
        console.print("[red]Could not find config.example.toml[/red]")
        return

    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(example, DEFAULT_CONFIG_PATH)
    console.print(f"[green]Config created:[/green] {DEFAULT_CONFIG_PATH}")
    console.print("Edit it to configure your providers.")


@click.command("quota-dash")
@click.option("--once", is_flag=True, help="One-shot query, print and exit")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON (with --once)")
@click.option("--provider", default=None, help="Show only this provider")
@click.option("--theme", default=None, help="Force theme: default | ghostty")
@click.option("--config", "config_path", default=None, type=click.Path(), help="Config file path")
@click.option("--init", "do_init", is_flag=True, help="Create default config file")
@click.option("--check", "do_check", is_flag=True, help="Test provider connectivity")
def main(
    once: bool,
    as_json: bool,
    provider: str | None,
    theme: str | None,
    config_path: str | None,
    do_init: bool,
    do_check: bool,
) -> None:
    """Multi-provider LLM quota monitoring dashboard."""
    if do_init:
        _run_init()
        return

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
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

    if not providers and not do_init:
        click.echo("No providers configured. Run 'quota-dash --init' to create a config file.")
        if not do_check and not once:
            return

    if do_check:
        asyncio.run(_run_check(providers))
    elif once:
        asyncio.run(_run_once(providers, as_json))
    else:
        from quota_dash.app import QuotaDashApp

        app = QuotaDashApp(config=config, theme_override=theme, provider_filter=provider)
        app.run()
