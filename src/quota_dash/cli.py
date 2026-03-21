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
from quota_dash.providers.google import GoogleProvider
from quota_dash.providers.groq import GroqProvider
from quota_dash.providers.mistral import MistralProvider
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

    provider_map_cls = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
        "groq": GroqProvider,
        "mistral": MistralProvider,
    }
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
def config() -> None:
    """Manage configuration."""
    pass


@config.command()
@click.option("--output", default=None, type=click.Path(), help="Output path")
def init(output: str | None) -> None:
    """Interactive config wizard."""
    import tomli_w

    output_path = Path(output) if output else Path.home() / ".config" / "quota-dash" / "config.toml"

    if output_path.exists():
        if not click.confirm(f"{output_path} already exists. Overwrite?"):
            click.echo("Aborted.")
            return

    # Provider selection
    all_providers = ["openai", "anthropic", "google", "groq", "mistral"]
    enabled = []
    click.echo("\nSelect providers to enable:")
    for p in all_providers:
        if click.confirm(f"  Enable {p}?", default=(p in ("openai", "anthropic"))):
            enabled.append(p)

    # Provider config
    providers: dict[str, dict] = {}
    env_defaults = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }
    for p in enabled:
        click.echo(f"\n--- {p} ---")
        key_env = click.prompt("  API key env var", default=env_defaults.get(p, ""))
        balance = click.prompt("  Balance (USD, blank to skip)", default="", show_default=False)
        limit = click.prompt("  Limit (USD, blank to skip)", default="", show_default=False)
        prov: dict = {"enabled": True, "api_key_env": key_env, "log_path": "~/"}
        if balance:
            try:
                prov["balance_usd"] = float(balance)
            except ValueError:
                click.echo(f"  Invalid balance value: {balance}, skipping")
        if limit:
            try:
                prov["limit_usd"] = float(limit)
            except ValueError:
                click.echo(f"  Invalid limit value: {limit}, skipping")
        providers[p] = prov

    # Proxy
    click.echo("\n--- Proxy ---")
    proxy_enabled = click.confirm("  Enable proxy?", default=True)
    proxy_port = click.prompt("  Proxy port", default=8300, type=int) if proxy_enabled else 8300
    auto_start = click.confirm("  Auto-start proxy with dashboard?", default=False) if proxy_enabled else False

    # Alerts
    click.echo("\n--- Alerts ---")
    warning = click.prompt("  Warning threshold %", default=50, type=int)
    alert = click.prompt("  Alert threshold %", default=20, type=int)
    critical = click.prompt("  Critical threshold %", default=5, type=int)

    # Build config dict
    config_dict = {
        "general": {"polling_interval": 60, "theme": "auto"},
        "providers": providers,
        "proxy": {"enabled": proxy_enabled, "port": proxy_port, "auto_start": auto_start},
        "alerts": {"warning": warning, "alert": alert, "critical": critical},
    }

    # Write
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        tomli_w.dump(config_dict, f)

    click.echo(f"\nConfig written to {output_path}")


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


@proxy.command()
@click.pass_context
def install(ctx: click.Context) -> None:
    """Install proxy as macOS launchd service."""
    import plistlib

    config_path_str = ctx.obj.get("config_path") if ctx.obj else None
    path = Path(config_path_str) if config_path_str else Path.home() / ".config" / "quota-dash" / "config.toml"
    config = load_config(path if path.exists() else None)

    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.quota-dash.proxy.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    # Find quota-dash executable
    import shutil
    exe = shutil.which("quota-dash") or "quota-dash"

    plist = {
        "Label": "com.quota-dash.proxy",
        "ProgramArguments": [exe, "proxy", "start", "--port", str(config.proxy.port)],
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(config.proxy.log_path),
        "StandardErrorPath": str(config.proxy.log_path),
    }

    with open(plist_path, "wb") as f:
        plistlib.dump(plist, f)

    import subprocess
    subprocess.run(["launchctl", "load", str(plist_path)], check=False)
    click.echo(f"Proxy service installed at {plist_path}")
    click.echo("It will start automatically on login.")


@proxy.command()
def uninstall() -> None:
    """Uninstall proxy launchd service."""
    import subprocess

    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.quota-dash.proxy.plist"
    if not plist_path.exists():
        click.echo("No proxy service installed.")
        return

    subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
    plist_path.unlink()
    click.echo("Proxy service uninstalled.")


def _fmt_tokens(n: int) -> str:
    """Format token count for display."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


@main.command()
@click.option("--config", "config_path", default=None, type=click.Path(), help="Config file path")
def doctor(config_path: str | None) -> None:
    """Check quota-dash configuration and connectivity."""
    import os
    import sqlite3

    from quota_dash.proxy.daemon import proxy_status

    console = Console()
    console.print("\n[bold]quota-dash doctor[/]\n")

    checks = []

    # 1. Config file
    path = Path(config_path) if config_path else Path.home() / ".config" / "quota-dash" / "config.toml"
    if path.exists():
        checks.append(("Config file", "OK", f"{path}"))
        config = load_config(path)
    else:
        checks.append(("Config file", "MISSING", f"{path} not found. Run: quota-dash config init"))
        config = load_config(None)

    # 2. Providers configured
    enabled = [n for n, p in config.providers.items() if p.enabled]
    if enabled:
        checks.append(("Providers", "OK", ", ".join(enabled)))
    else:
        checks.append(("Providers", "WARN", "No providers configured"))

    # 3. API keys in environment
    for name, pconfig in config.providers.items():
        if pconfig.enabled and pconfig.api_key_env:
            val = os.environ.get(pconfig.api_key_env, "")
            if val:
                checks.append((f"  {name} API key", "OK", f"${pconfig.api_key_env} is set"))
            else:
                checks.append((f"  {name} API key", "WARN", f"${pconfig.api_key_env} not set"))

    # 4. Proxy database
    db_path = config.proxy.db_path
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM api_calls").fetchone()[0]
            conn.close()
            checks.append(("Proxy database", "OK", f"{db_path} ({count} records)"))
        except Exception as e:
            checks.append(("Proxy database", "ERROR", f"Cannot read: {e}"))
    else:
        checks.append(("Proxy database", "MISSING", "Run: quota-dash proxy start"))

    # 5. Proxy process
    status = proxy_status()
    if status:
        checks.append(("Proxy process", "OK", f"Running (PID {status['pid']})"))
    else:
        checks.append(("Proxy process", "STOPPED", "Not running. Run: quota-dash proxy start"))

    # 6. Ghostty detection
    term = os.environ.get("TERM_PROGRAM", "unknown")
    if term == "ghostty":
        checks.append(("Terminal", "OK", "Ghostty detected — enhanced features active"))
    else:
        checks.append(("Terminal", "INFO", f"{term} — Ghostty features unavailable"))

    # 7. Alert webhook
    if config.alerts.webhook_url:
        checks.append(("Webhook", "OK", config.alerts.webhook_url[:50] + "..."))
    else:
        checks.append(("Webhook", "INFO", "Not configured"))

    # Display results
    table = Table(show_header=True, header_style="bold", border_style="dim")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    status_styles = {
        "OK": "[green]OK[/]",
        "WARN": "[yellow]WARN[/]",
        "ERROR": "[red]ERROR[/]",
        "MISSING": "[red]MISSING[/]",
        "STOPPED": "[yellow]STOPPED[/]",
        "INFO": "[dim]INFO[/]",
    }

    for check_name, check_status, details in checks:
        styled_status = status_styles.get(check_status, check_status)
        table.add_row(check_name, styled_status, details)

    console.print(table)

    errors = sum(1 for _, s, _ in checks if s in ("ERROR", "MISSING"))
    warns = sum(1 for _, s, _ in checks if s in ("WARN", "STOPPED"))
    if errors:
        console.print(f"\n[red]{errors} error(s) found.[/]")
    elif warns:
        console.print(f"\n[yellow]{warns} warning(s).[/] See details above.")
    else:
        console.print("\n[green]All checks passed![/]")


@main.command()
@click.option("--period", default="24h", help="Time period: 1h, 24h, 7d, 30d")
@click.option("--config", "config_path", default=None, type=click.Path(), help="Config file path")
def stats(period: str, config_path: str | None) -> None:
    """Show usage summary statistics."""
    from rich.panel import Panel

    path = Path(config_path) if config_path else Path.home() / ".config" / "quota-dash" / "config.toml"
    config = load_config(path if path.exists() else None)

    db_path = config.proxy.db_path
    if not db_path.exists():
        Console().print("[yellow]No proxy database found.[/] Start proxy first: [bold]quota-dash proxy start[/]")
        return

    from quota_dash.export import query_calls, build_summary
    calls = asyncio.run(query_calls(db_path, period=period))
    summary = build_summary(calls, period)

    console = Console()
    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("Provider", style="bold")
    table.add_column("Calls", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("In", justify="right", style="dim")
    table.add_column("Out", justify="right", style="dim")

    # Per-provider rows
    for prov, prov_stats in summary["by_provider"].items():
        prov_calls = [c for c in calls if c.get("provider") == prov]
        in_tok = sum(c.get("input_tokens", 0) or 0 for c in prov_calls)
        out_tok = sum(c.get("output_tokens", 0) or 0 for c in prov_calls)
        table.add_row(
            prov,
            str(prov_stats["calls"]),
            _fmt_tokens(prov_stats["tokens"]),
            _fmt_tokens(in_tok),
            _fmt_tokens(out_tok),
        )

    # Total row
    total_in = sum(c.get("input_tokens", 0) or 0 for c in calls)
    total_out = sum(c.get("output_tokens", 0) or 0 for c in calls)
    table.add_section()
    table.add_row(
        "[bold]Total[/]",
        f"[bold]{summary['total_calls']}[/]",
        f"[bold]{_fmt_tokens(summary['total_tokens'])}[/]",
        _fmt_tokens(total_in),
        _fmt_tokens(total_out),
    )

    panel = Panel(table, title=f"[bold]quota-dash stats[/] [dim](last {period})[/]", border_style="cyan")
    console.print(panel)


@main.command()
@click.option("--period", default="24h", help="Time period: 24h, 7d, 30d")
@click.option("--format", "fmt", default="csv", type=click.Choice(["csv", "json"]), help="Output format")
@click.option("--provider", default=None, help="Filter by provider")
@click.option("--output", "output_path", default=None, type=click.Path(), help="Output file (default: stdout)")
@click.pass_context
def export(ctx: click.Context, period: str, fmt: str, provider: str | None, output_path: str | None) -> None:
    """Export usage data from proxy database."""
    from quota_dash.export import query_calls, build_summary, format_csv, format_json

    config_path_str = ctx.obj.get("config_path") if ctx.obj else None
    path = Path(config_path_str) if config_path_str else Path.home() / ".config" / "quota-dash" / "config.toml"
    config = load_config(path if path.exists() else None)

    db_path = config.proxy.db_path
    if not db_path.exists():
        click.echo("No proxy database found. Start the proxy first: quota-dash proxy start")
        return

    calls = asyncio.run(query_calls(db_path, period=period, provider=provider))
    summary = build_summary(calls, period)

    if fmt == "json":
        result = format_json(calls, summary)
    else:
        result = format_csv(calls, summary)

    if output_path:
        Path(output_path).write_text(result)
        click.echo(f"Exported {len(calls)} records to {output_path}")
    else:
        click.echo(result)
