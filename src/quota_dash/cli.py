from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from importlib.metadata import version as pkg_version
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


@click.group(invoke_without_command=True)
@click.version_option(version=pkg_version("quota-dash"), prog_name="quota-dash")
@click.option("--once", is_flag=True, help="One-shot query, print and exit")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON (with --once)")
@click.option("--provider", default=None, help="Show only this provider")
@click.option("--theme", default=None, help="Force theme: default | ghostty")
@click.option("--config", "config_path", default=None, type=click.Path(), help="Config file path")
@click.option("--with-proxy", is_flag=True, help="Auto-start proxy with dashboard")
@click.option("--proxy-port", default=None, type=int, help="Proxy port (with --with-proxy)")
@click.pass_context
def main(
    ctx: click.Context,
    once: bool,
    as_json: bool,
    provider: str | None,
    theme: str | None,
    config_path: str | None,
    with_proxy: bool,
    proxy_port: int | None,
) -> None:
    """Multi-provider LLM quota monitoring dashboard."""
    if ctx.invoked_subcommand is not None:
        ctx.ensure_object(dict)
        ctx.obj["config_path"] = config_path
        return

    path = Path(config_path) if config_path else Path.home() / ".config" / "quota-dash" / "config.toml"
    config = load_config(path if path.exists() else None)

    provider_map_cls = {"openai": OpenAIProvider, "anthropic": AnthropicProvider}
    providers: dict[str, Provider] = {}
    db_path = config.proxy.db_path
    for name, pconfig in config.providers.items():
        if not pconfig.enabled:
            continue
        if provider and name != provider:
            continue
        if name in provider_map_cls:
            providers[name] = provider_map_cls[name](pconfig, db_path=db_path)

    if once:
        asyncio.run(_run_once(providers, as_json))
    else:
        if with_proxy:
            import subprocess
            import time
            port = proxy_port or config.proxy.port
            subprocess.Popen(
                ["quota-dash", "proxy", "start", "--port", str(port)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            time.sleep(1)  # wait for proxy to initialize DB

        from quota_dash.app import QuotaDashApp

        app = QuotaDashApp(config=config, theme_override=theme)
        app.run()


@main.group()
@click.pass_context
def proxy(ctx: click.Context) -> None:
    """Manage the local API proxy."""
    pass


@proxy.command()
@click.option("--port", default=8300, help="Proxy port")
@click.option("--target", default=None, help="Only forward to this provider")
@click.pass_context
def start(ctx: click.Context, port: int, target: str | None) -> None:
    """Start the proxy daemon."""
    from quota_dash.proxy.daemon import start_proxy
    config_path = ctx.obj.get("config_path") if ctx.obj else None
    path = Path(config_path) if config_path else Path.home() / ".config" / "quota-dash" / "config.toml"
    config = load_config(path if path.exists() else None)

    start_proxy(
        port=port,
        db_path=config.proxy.db_path,
        log_path=config.proxy.log_path,
        config_targets=config.proxy.targets,
        target_filter=target,
    )


@proxy.command()
def stop() -> None:
    """Stop the proxy daemon."""
    from quota_dash.proxy.daemon import stop_proxy
    stop_proxy()


@proxy.command()
def status() -> None:
    """Show proxy status."""
    from quota_dash.proxy.daemon import proxy_status
    info = proxy_status()
    if info:
        click.echo(f"Proxy running (PID {info['pid']})")
    else:
        click.echo("No proxy running.")
