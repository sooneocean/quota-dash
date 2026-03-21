# UI/UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace text-render widgets with Textual native components in an Overview+Detail layout with responsive breakpoints and proxy-powered history.

**Architecture:** `OverviewTable` (DataTable, all providers at a glance) sits above a `DetailPanel` container with 5 sub-widgets (QuotaCard, TokenCard, ContextCard, RateLimitCard, HistoryTable) using Textual's ProgressBar, Sparkline, DataTable, and Static. CSS grid switches from 2x2 to single column at width<120.

**Tech Stack:** Textual (existing), aiosqlite (existing for proxy DB queries)

**Spec:** `docs/specs/2026-03-21-ui-ux-redesign.md`

---

## File Structure

```
src/quota_dash/
├── models.py             # +ratelimit_reset field on ProxyData
├── data/store.py         # +update_proxy, +get_proxy, +total_tokens_today
├── proxy/db.py           # +query_recent_calls, +query_token_history
├── widgets/
│   ├── __init__.py       # updated exports
│   ├── overview_table.py # NEW — DataTable with 6 cols + Total row
│   ├── detail_panel.py   # NEW — container for 5 sub-widgets
│   ├── quota_card.py     # NEW — ProgressBar + label
│   ├── token_card.py     # NEW — Sparkline + stats
│   ├── context_card.py   # NEW — ProgressBar + label
│   ├── ratelimit_card.py # NEW — Static text
│   └── history_table.py  # NEW — DataTable of recent API calls
│   (DELETE: provider_list.py, quota_panel.py, token_panel.py, context_gauge.py)
├── app.py                # new compose(), all-provider refresh, row selection handler
├── themes/
│   ├── default.tcss      # updated selectors
│   └── ghostty.tcss      # updated selectors
tests/
├── test_models.py        # +ratelimit_reset test
├── test_store.py         # +proxy data tests
├── test_proxy_db.py      # +query_recent_calls, +query_token_history tests
├── test_widgets.py       # REWRITTEN — all new widget tests
├── test_app.py           # UPDATED — new widget names
```

---

### Task 1: Model & DataStore Updates

**Files:**
- Modify: `src/quota_dash/models.py`
- Modify: `src/quota_dash/data/store.py`
- Modify: `tests/test_models.py`
- Modify: `tests/test_store.py`

- [ ] **Step 1: Write failing test for ratelimit_reset on ProxyData**

```python
# Append to tests/test_models.py
def test_proxy_data_with_ratelimit_reset():
    pd = ProxyData(
        input_tokens=100, output_tokens=50, total_tokens=150,
        ratelimit_remaining_tokens=9000, ratelimit_remaining_requests=99,
        model="gpt-4", last_call=datetime(2026, 3, 21, 10, 0),
        calls_today=5, tokens_today=1500, ratelimit_reset="2m 30s",
    )
    assert pd.ratelimit_reset == "2m 30s"
```

- [ ] **Step 2: Run test, confirm failure**

Run: `cd quota-dash && pytest tests/test_models.py::test_proxy_data_with_ratelimit_reset -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'ratelimit_reset'`

- [ ] **Step 3: Add ratelimit_reset to ProxyData**

In `src/quota_dash/models.py`, add field to `ProxyData`:
```python
    ratelimit_reset: str | None = None
```

- [ ] **Step 4: Write failing test for DataStore proxy + tokens_today**

```python
# Append to tests/test_store.py
from quota_dash.models import ProxyData

def test_store_update_and_get_proxy():
    store = DataStore()
    pd = ProxyData(
        input_tokens=100, output_tokens=50, total_tokens=150,
        ratelimit_remaining_tokens=9000, ratelimit_remaining_requests=99,
        model="gpt-4", last_call=datetime.now(),
        calls_today=5, tokens_today=1500,
    )
    store.update_proxy("openai", pd)
    assert store.get_proxy("openai") == pd
    assert store.get_proxy("missing") is None

def test_store_total_tokens_today():
    store = DataStore()
    store.update_proxy("openai", ProxyData(
        input_tokens=0, output_tokens=0, total_tokens=0,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        model=None, last_call=datetime.now(),
        calls_today=5, tokens_today=1500,
    ))
    store.update_proxy("anthropic", ProxyData(
        input_tokens=0, output_tokens=0, total_tokens=0,
        ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
        model=None, last_call=datetime.now(),
        calls_today=3, tokens_today=2000,
    ))
    assert store.total_tokens_today() == 3500

def test_store_total_tokens_today_no_proxy():
    store = DataStore()
    store.update_tokens("openai", TokenUsage(
        input_tokens=500, output_tokens=200, total_tokens=700,
        history=[], session_id=None, source="estimated",
    ))
    assert store.total_tokens_today() == 700
```

- [ ] **Step 5: Run test, confirm failure**

Run: `cd quota-dash && pytest tests/test_store.py::test_store_update_and_get_proxy -v`
Expected: FAIL — `AttributeError: 'DataStore' object has no attribute 'update_proxy'`

- [ ] **Step 6: Implement DataStore changes**

In `src/quota_dash/data/store.py`, add `ProxyData` import and:
```python
from quota_dash.models import QuotaInfo, TokenUsage, ContextInfo, ProxyData

class DataStore:
    def __init__(self) -> None:
        # ... existing fields ...
        self._proxy: dict[str, ProxyData] = {}

    def update_proxy(self, provider: str, proxy: ProxyData) -> None:
        self._proxy[provider] = proxy
        self._revision += 1

    def get_proxy(self, provider: str) -> ProxyData | None:
        return self._proxy.get(provider)

    def total_tokens_today(self) -> int:
        # Per-provider: prefer proxy data, fall back to token usage
        total = 0
        all_providers = set(self._proxy) | set(self._tokens)
        for name in all_providers:
            if name in self._proxy:
                total += self._proxy[name].tokens_today
            elif name in self._tokens:
                total += self._tokens[name].total_tokens
        return total
```

- [ ] **Step 7: Run all tests**

Run: `cd quota-dash && pytest tests/test_models.py tests/test_store.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
cd quota-dash && git add src/quota_dash/models.py src/quota_dash/data/store.py tests/test_models.py tests/test_store.py && git commit -m "feat: add ratelimit_reset to ProxyData, proxy data + tokens_today to DataStore"
```

---

### Task 2: New DB Queries

**Files:**
- Modify: `src/quota_dash/proxy/db.py`
- Modify: `tests/test_proxy_db.py`

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/test_proxy_db.py
from quota_dash.proxy.db import query_recent_calls, query_token_history

@pytest.mark.asyncio
async def test_query_recent_calls(db_path):
    await init_db(db_path)
    for i in range(3):
        await write_api_call(db_path, ApiCallRecord(
            provider="openai", model="gpt-4",
            endpoint="/v1/chat/completions",
            input_tokens=100 * (i + 1), output_tokens=50,
            total_tokens=150 * (i + 1),
            ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
            ratelimit_reset=None, request_id=f"r-{i}", target_url="https://api.openai.com",
        ))

    calls = await query_recent_calls(db_path, "openai", limit=2)
    assert len(calls) == 2
    assert "model" in calls[0]
    assert "total_tokens" in calls[0]


@pytest.mark.asyncio
async def test_query_token_history(db_path):
    await init_db(db_path)
    for i in range(5):
        await write_api_call(db_path, ApiCallRecord(
            provider="openai", model="gpt-4",
            endpoint="/v1/chat/completions",
            input_tokens=100, output_tokens=50,
            total_tokens=150,
            ratelimit_remaining_tokens=None, ratelimit_remaining_requests=None,
            ratelimit_reset=None, request_id=None, target_url="https://api.openai.com",
        ))

    history = await query_token_history(db_path, "openai", limit=3)
    assert len(history) == 3
    assert isinstance(history[0], tuple)
    assert len(history[0]) == 2  # (datetime, int)


@pytest.mark.asyncio
async def test_query_recent_calls_empty(db_path):
    await init_db(db_path)
    calls = await query_recent_calls(db_path, "openai")
    assert calls == []


@pytest.mark.asyncio
async def test_query_provider_data_includes_ratelimit_reset(db_path):
    await init_db(db_path)
    await write_api_call(db_path, ApiCallRecord(
        provider="openai", model="gpt-4", endpoint="/v1/chat/completions",
        input_tokens=100, output_tokens=50, total_tokens=150,
        ratelimit_remaining_tokens=9000, ratelimit_remaining_requests=99,
        ratelimit_reset="2m 30s", request_id=None, target_url="https://api.openai.com",
    ))
    data = await query_provider_data(db_path, "openai")
    assert data is not None
    assert data.ratelimit_reset == "2m 30s"
```

- [ ] **Step 2: Run test, confirm failure**

Run: `cd quota-dash && pytest tests/test_proxy_db.py::test_query_recent_calls -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement new queries**

Append to `src/quota_dash/proxy/db.py`:
```python
async def query_recent_calls(db_path: Path, provider: str, limit: int = 20) -> list[dict]:
    if not _HAS_AIOSQLITE:
        return []
    try:
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT timestamp, model, total_tokens, endpoint
                   FROM api_calls WHERE provider = ?
                   AND date(timestamp) = date('now')
                   ORDER BY timestamp DESC LIMIT ?""",
                (provider, limit),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("Failed to query recent calls")
        return []


async def query_token_history(db_path: Path, provider: str, limit: int = 50) -> list[tuple[datetime, int]]:
    if not _HAS_AIOSQLITE:
        return []
    try:
        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                """SELECT timestamp, total_tokens
                   FROM api_calls WHERE provider = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (provider, limit),
            )
            rows = await cursor.fetchall()
            return [(datetime.fromisoformat(ts), tok) for ts, tok in reversed(rows)]
    except Exception:
        logger.exception("Failed to query token history")
        return []
```

Also update `query_provider_data` to include `ratelimit_reset` in its SELECT and return:
```python
# In query_provider_data, add ratelimit_reset to the SELECT:
"""SELECT input_tokens, output_tokens, total_tokens,
          ratelimit_remaining_tokens, ratelimit_remaining_requests,
          ratelimit_reset, model, timestamp
   FROM api_calls WHERE provider = ?
   ORDER BY timestamp DESC, id DESC LIMIT 1"""

# In the ProxyData constructor:
ratelimit_reset=row["ratelimit_reset"],
```

- [ ] **Step 4: Run tests**

Run: `cd quota-dash && pytest tests/test_proxy_db.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add src/quota_dash/proxy/db.py tests/test_proxy_db.py && git commit -m "feat: add query_recent_calls and query_token_history DB functions"
```

---

### Task 3: QuotaCard Widget

**Files:**
- Create: `src/quota_dash/widgets/quota_card.py`
- Create: `tests/test_widgets_new.py` (new test file for all new widgets)

- [ ] **Step 1: Write failing test**

```python
# tests/test_widgets_new.py
from datetime import datetime
import pytest
from textual.app import App, ComposeResult
from quota_dash.models import QuotaInfo
from quota_dash.widgets.quota_card import QuotaCard


class QuotaCardTestApp(App):
    def compose(self) -> ComposeResult:
        yield QuotaCard()


@pytest.mark.asyncio
async def test_quota_card_mount():
    app = QuotaCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(QuotaCard)
        assert card is not None


@pytest.mark.asyncio
async def test_quota_card_update():
    app = QuotaCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(QuotaCard)
        card.update_data(QuotaInfo(
            provider="openai", balance_usd=47.32, limit_usd=100.0,
            usage_today_usd=3.20, last_updated=datetime.now(),
            source="manual", stale=False,
        ))
        await pilot.pause()


@pytest.mark.asyncio
async def test_quota_card_unavailable():
    app = QuotaCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(QuotaCard)
        card.update_data(QuotaInfo(
            provider="openai", balance_usd=None, limit_usd=None,
            usage_today_usd=None, last_updated=datetime.now(),
            source="unavailable", stale=False,
        ))
        await pilot.pause()
```

- [ ] **Step 2: Run test, confirm failure**

Run: `cd quota-dash && pytest tests/test_widgets_new.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement QuotaCard**

```python
# src/quota_dash/widgets/quota_card.py
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Label, ProgressBar

from quota_dash.models import QuotaInfo


class QuotaCard(Widget):
    DEFAULT_CSS = """
    QuotaCard {
        height: auto;
        min-height: 5;
        padding: 1;
        border: solid $primary-muted;
    }
    QuotaCard .title { text-style: bold; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Quota", classes="title")
        yield Label("loading...", id="quota-label")
        yield ProgressBar(total=100, show_eta=False, id="quota-bar")

    def update_data(self, data: QuotaInfo) -> None:
        label = self.query_one("#quota-label", Label)
        bar = self.query_one("#quota-bar", ProgressBar)

        if data.source == "unavailable":
            label.update(f"({data.provider}) not configured")
            bar.update(total=100, progress=0)
            return

        bal = f"${data.balance_usd:.2f}" if data.balance_usd is not None else "N/A"
        lim = f"${data.limit_usd:.2f}" if data.limit_usd is not None else "N/A"
        source_tag = f" [{data.source}]"
        stale_tag = " ⚠ stale" if data.stale else ""
        label.update(f"{bal} / {lim}{source_tag}{stale_tag}")

        if data.limit_usd and data.balance_usd is not None:
            bar.update(total=data.limit_usd, progress=data.balance_usd)
        else:
            bar.update(total=100, progress=0)
```

- [ ] **Step 4: Run test, confirm pass**

Run: `cd quota-dash && pytest tests/test_widgets_new.py -v`
Expected: All 3 PASS

- [ ] **Step 5: Commit**

```bash
cd quota-dash && git add src/quota_dash/widgets/quota_card.py tests/test_widgets_new.py && git commit -m "feat: QuotaCard widget with ProgressBar"
```

---

### Task 4: TokenCard, ContextCard, RateLimitCard Widgets

**Files:**
- Create: `src/quota_dash/widgets/token_card.py`
- Create: `src/quota_dash/widgets/context_card.py`
- Create: `src/quota_dash/widgets/ratelimit_card.py`
- Modify: `tests/test_widgets_new.py`

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/test_widgets_new.py
from quota_dash.models import TokenUsage, ContextInfo, ProxyData
from quota_dash.widgets.token_card import TokenCard
from quota_dash.widgets.context_card import ContextCard
from quota_dash.widgets.ratelimit_card import RateLimitCard


class TokenCardTestApp(App):
    def compose(self) -> ComposeResult:
        yield TokenCard()

class ContextCardTestApp(App):
    def compose(self) -> ComposeResult:
        yield ContextCard()

class RateLimitCardTestApp(App):
    def compose(self) -> ComposeResult:
        yield RateLimitCard()


@pytest.mark.asyncio
async def test_token_card_mount_and_update():
    app = TokenCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(TokenCard)
        card.update_data(
            TokenUsage(input_tokens=12400, output_tokens=8100, total_tokens=20500,
                       history=[(datetime.now(), 500), (datetime.now(), 800)],
                       session_id=None, source="proxy"),
            sparkline_data=[500, 800, 300, 600],
        )
        await pilot.pause()


@pytest.mark.asyncio
async def test_context_card_mount_and_update():
    app = ContextCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(ContextCard)
        card.update_data(ContextInfo(
            used_tokens=62000, max_tokens=128000,
            percent_used=48.4, model="gpt-4", note="last call snapshot",
        ))
        await pilot.pause()


@pytest.mark.asyncio
async def test_ratelimit_card_mount_and_update():
    app = RateLimitCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(RateLimitCard)
        card.update_data(ProxyData(
            input_tokens=0, output_tokens=0, total_tokens=0,
            ratelimit_remaining_tokens=9000, ratelimit_remaining_requests=99,
            model=None, last_call=datetime.now(),
            calls_today=0, tokens_today=0, ratelimit_reset="2m 30s",
        ))
        await pilot.pause()


@pytest.mark.asyncio
async def test_ratelimit_card_no_data():
    app = RateLimitCardTestApp()
    async with app.run_test() as pilot:
        card = app.query_one(RateLimitCard)
        card.update_data(None)
        await pilot.pause()
```

- [ ] **Step 2: Run test, confirm failure**

Run: `cd quota-dash && pytest tests/test_widgets_new.py::test_token_card_mount_and_update -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement TokenCard**

```python
# src/quota_dash/widgets/token_card.py
from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Sparkline

from quota_dash.models import TokenUsage


class TokenCard(Widget):
    DEFAULT_CSS = """
    TokenCard {
        height: auto;
        min-height: 6;
        padding: 1;
        border: solid $primary-muted;
    }
    TokenCard .title { text-style: bold; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Tokens (session)", classes="title")
        yield Sparkline([], id="token-spark")
        yield Label("loading...", id="token-stats")

    def update_data(self, usage: TokenUsage, sparkline_data: list[float] | None = None) -> None:
        spark = self.query_one("#token-spark", Sparkline)
        label = self.query_one("#token-stats", Label)

        data = sparkline_data or [t for _, t in usage.history] or []
        spark.data = data

        def fmt(n: int) -> str:
            return f"{n / 1000:.1f}K" if n >= 1000 else str(n)

        label.update(
            f"In: {fmt(usage.input_tokens)} | Out: {fmt(usage.output_tokens)} "
            f"| Total: {fmt(usage.total_tokens)} [{usage.source}]"
        )
```

- [ ] **Step 4: Implement ContextCard**

```python
# src/quota_dash/widgets/context_card.py
from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, ProgressBar

from quota_dash.models import ContextInfo


class ContextCard(Widget):
    DEFAULT_CSS = """
    ContextCard {
        height: auto;
        min-height: 5;
        padding: 1;
        border: solid $primary-muted;
    }
    ContextCard .title { text-style: bold; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Context Window", classes="title")
        yield ProgressBar(total=100, show_eta=False, id="ctx-bar")
        yield Label("loading...", id="ctx-label")
        yield Label("", id="ctx-note")

    def update_data(self, data: ContextInfo) -> None:
        bar = self.query_one("#ctx-bar", ProgressBar)
        label = self.query_one("#ctx-label", Label)
        note = self.query_one("#ctx-note", Label)

        bar.update(total=data.max_tokens or 1, progress=data.used_tokens)

        def fmt(n: int) -> str:
            return f"{n // 1000}K" if n >= 1000 else str(n)

        label.update(f"{data.percent_used:.0f}% ({fmt(data.used_tokens)} / {fmt(data.max_tokens)}) — {data.model}")
        note.update(data.note if data.note else "")
```

- [ ] **Step 5: Implement RateLimitCard**

```python
# src/quota_dash/widgets/ratelimit_card.py
from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label

from quota_dash.models import ProxyData


class RateLimitCard(Widget):
    DEFAULT_CSS = """
    RateLimitCard {
        height: auto;
        min-height: 5;
        padding: 1;
        border: solid $primary-muted;
    }
    RateLimitCard .title { text-style: bold; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Rate Limits", classes="title")
        yield Label("no data", id="rl-content")

    def update_data(self, data: ProxyData | None) -> None:
        label = self.query_one("#rl-content", Label)
        if data is None or (data.ratelimit_remaining_tokens is None and data.ratelimit_remaining_requests is None):
            label.update("no data")
            return

        lines = []
        if data.ratelimit_remaining_tokens is not None:
            lines.append(f"Tokens: {data.ratelimit_remaining_tokens:,} remaining")
        if data.ratelimit_remaining_requests is not None:
            lines.append(f"Requests: {data.ratelimit_remaining_requests} remaining")
        if data.ratelimit_reset:
            lines.append(f"Reset: {data.ratelimit_reset}")
        label.update("\n".join(lines) if lines else "no data")
```

- [ ] **Step 6: Run tests**

Run: `cd quota-dash && pytest tests/test_widgets_new.py -v`
Expected: All 8 PASS (3 from Task 3 + 5 new)

- [ ] **Step 7: Commit**

```bash
cd quota-dash && git add src/quota_dash/widgets/token_card.py src/quota_dash/widgets/context_card.py src/quota_dash/widgets/ratelimit_card.py tests/test_widgets_new.py && git commit -m "feat: TokenCard, ContextCard, RateLimitCard widgets"
```

---

### Task 5: OverviewTable & HistoryTable Widgets

**Files:**
- Create: `src/quota_dash/widgets/overview_table.py`
- Create: `src/quota_dash/widgets/history_table.py`
- Create: `src/quota_dash/widgets/detail_panel.py`
- Modify: `tests/test_widgets_new.py`

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/test_widgets_new.py
from quota_dash.widgets.overview_table import OverviewTable
from quota_dash.widgets.history_table import HistoryTable
from quota_dash.widgets.detail_panel import DetailPanel


class OverviewTestApp(App):
    def compose(self) -> ComposeResult:
        yield OverviewTable()

class HistoryTestApp(App):
    def compose(self) -> ComposeResult:
        yield HistoryTable()


@pytest.mark.asyncio
async def test_overview_table_mount():
    app = OverviewTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(OverviewTable)
        assert table is not None


@pytest.mark.asyncio
async def test_overview_table_refresh():
    app = OverviewTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(OverviewTable)
        table.refresh_data(
            providers=["openai", "anthropic"],
            quotas={"openai": QuotaInfo(provider="openai", balance_usd=47.32, limit_usd=100.0, usage_today_usd=3.20, last_updated=datetime.now(), source="manual", stale=False)},
            tokens_today={"openai": 20500, "anthropic": 63900},
            context_pcts={"openai": 62.0, "anthropic": 35.0},
            rate_limits={"openai": 9000},
            sources={"openai": "proxy", "anthropic": "proxy"},
            total_balance=247.32,
            total_tokens=84400,
        )
        await pilot.pause()


@pytest.mark.asyncio
async def test_history_table_mount():
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(HistoryTable)
        assert table is not None


@pytest.mark.asyncio
async def test_history_table_update():
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(HistoryTable)
        table.update_data([
            {"timestamp": "2026-03-21T14:32:00", "model": "gpt-4", "total_tokens": 150, "endpoint": "/v1/chat/completions"},
            {"timestamp": "2026-03-21T14:28:00", "model": "gpt-4", "total_tokens": 420, "endpoint": "/v1/chat/completions"},
        ])
        await pilot.pause()


@pytest.mark.asyncio
async def test_history_table_empty():
    app = HistoryTestApp()
    async with app.run_test() as pilot:
        table = app.query_one(HistoryTable)
        table.update_data([])
        await pilot.pause()
```

- [ ] **Step 2: Run test, confirm failure**

Run: `cd quota-dash && pytest tests/test_widgets_new.py::test_overview_table_mount -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement OverviewTable**

```python
# src/quota_dash/widgets/overview_table.py
from __future__ import annotations

from textual.widget import Widget
from textual.widgets import DataTable
from textual.app import ComposeResult

from quota_dash.models import QuotaInfo


class OverviewTable(Widget):
    DEFAULT_CSS = """
    OverviewTable {
        height: auto;
        max-height: 12;
    }
    """

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="row", id="overview-dt")

    def __init__(self) -> None:
        super().__init__()
        self._last_data: dict | None = None
        self._is_wide: bool = True

    def on_mount(self) -> None:
        dt = self.query_one("#overview-dt", DataTable)
        self._is_wide = self.app.size.width >= 120
        self._setup_columns(dt, wide=self._is_wide)

    def on_resize(self) -> None:
        new_wide = self.app.size.width >= 120
        if new_wide != self._is_wide:
            self._is_wide = new_wide
            dt = self.query_one("#overview-dt", DataTable)
            self._setup_columns(dt, wide=new_wide)
            if self._last_data:
                self.refresh_data(**self._last_data)

    def _setup_columns(self, dt: DataTable, wide: bool) -> None:
        dt.clear(columns=True)
        dt.add_column("Provider", key="provider")
        dt.add_column("Balance", key="balance")
        dt.add_column("Tokens", key="tokens")
        dt.add_column("Ctx", key="ctx")
        if wide:
            dt.add_column("Rate", key="rate")
            dt.add_column("Source", key="source")

    def refresh_data(
        self,
        providers: list[str],
        quotas: dict[str, QuotaInfo],
        tokens_today: dict[str, int],
        context_pcts: dict[str, float],
        rate_limits: dict[str, int | None],
        sources: dict[str, str],
        total_balance: float,
        total_tokens: int,
    ) -> None:
        self._last_data = {
            "providers": providers, "quotas": quotas, "tokens_today": tokens_today,
            "context_pcts": context_pcts, "rate_limits": rate_limits,
            "sources": sources, "total_balance": total_balance, "total_tokens": total_tokens,
        }
        dt = self.query_one("#overview-dt", DataTable)
        dt.clear()

        def fmt_usd(v: float | None) -> str:
            return f"${v:.2f}" if v is not None else "N/A"

        def fmt_tok(v: int) -> str:
            return f"{v / 1000:.1f}K" if v >= 1000 else str(v)

        wide = self.app.size.width >= 120 if self.app else True

        for name in providers:
            q = quotas.get(name)
            bal = fmt_usd(q.balance_usd) if q else "N/A"
            tok = fmt_tok(tokens_today.get(name, 0))
            ctx = f"{context_pcts.get(name, 0):.0f}%"
            row = [name, bal, tok, ctx]
            if wide:
                rl = rate_limits.get(name)
                row.append(f"{rl // 1000}K" if rl and rl >= 1000 else str(rl or "—"))
                row.append(sources.get(name, "—"))
            dt.add_row(*row, key=name)

        # Total row
        total_row = ["Total", fmt_usd(total_balance), fmt_tok(total_tokens), ""]
        if wide:
            total_row.extend(["", ""])
        dt.add_row(*total_row, key="__total__")
```

- [ ] **Step 4: Implement HistoryTable**

```python
# src/quota_dash/widgets/history_table.py
from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Label


class HistoryTable(Widget):
    DEFAULT_CSS = """
    HistoryTable {
        height: auto;
        max-height: 10;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("History (today)", classes="title")
        yield DataTable(id="history-dt")

    def on_mount(self) -> None:
        dt = self.query_one("#history-dt", DataTable)
        dt.add_column("Time", key="time")
        dt.add_column("Model", key="model")
        dt.add_column("Tokens", key="tokens")
        dt.add_column("Endpoint", key="endpoint")

    def update_data(self, calls: list[dict]) -> None:
        dt = self.query_one("#history-dt", DataTable)
        dt.clear()

        if not calls:
            dt.add_row("—", "Start proxy to see API call history", "", "")
            return

        for call in calls:
            ts = call.get("timestamp", "")
            if "T" in ts:
                ts = ts.split("T")[1][:5]  # HH:MM
            dt.add_row(
                ts,
                call.get("model", "—"),
                str(call.get("total_tokens", 0)),
                call.get("endpoint", "—"),
            )
```

- [ ] **Step 5: Implement DetailPanel**

```python
# src/quota_dash/widgets/detail_panel.py
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid
from textual.widget import Widget

from quota_dash.widgets.quota_card import QuotaCard
from quota_dash.widgets.token_card import TokenCard
from quota_dash.widgets.context_card import ContextCard
from quota_dash.widgets.ratelimit_card import RateLimitCard


class DetailPanel(Widget):
    DEFAULT_CSS = """
    DetailPanel {
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with Grid(id="detail-grid"):
            yield QuotaCard()
            yield TokenCard()
            yield ContextCard()
            yield RateLimitCard()
```

- [ ] **Step 6: Run tests**

Run: `cd quota-dash && pytest tests/test_widgets_new.py -v`
Expected: All 13 PASS

- [ ] **Step 7: Commit**

```bash
cd quota-dash && git add src/quota_dash/widgets/overview_table.py src/quota_dash/widgets/history_table.py src/quota_dash/widgets/detail_panel.py tests/test_widgets_new.py && git commit -m "feat: OverviewTable, HistoryTable, DetailPanel widgets"
```

---

### Task 6: Updated Themes

**Files:**
- Modify: `src/quota_dash/themes/default.tcss`
- Modify: `src/quota_dash/themes/ghostty.tcss`

- [ ] **Step 1: Rewrite default.tcss**

```css
/* src/quota_dash/themes/default.tcss */
Screen {
    layout: vertical;
    background: $surface;
}

OverviewTable {
    height: auto;
    max-height: 12;
    margin-bottom: 1;
}

DetailPanel {
    height: auto;
}

#detail-grid {
    layout: grid;
    grid-size: 2 2;
    grid-gutter: 1;
}

@media (width < 120) {
    #detail-grid {
        grid-size: 1;
    }
}

HistoryTable {
    height: auto;
    max-height: 10;
    margin-top: 1;
}

Footer {
    dock: bottom;
}
```

- [ ] **Step 2: Rewrite ghostty.tcss**

```css
/* src/quota_dash/themes/ghostty.tcss */
Screen {
    layout: vertical;
    background: #1a1b26;
}

OverviewTable {
    height: auto;
    max-height: 12;
    margin-bottom: 1;
    background: #16161e;
    color: #a9b1d6;
}

DetailPanel {
    height: auto;
}

#detail-grid {
    layout: grid;
    grid-size: 2 2;
    grid-gutter: 1;
}

@media (width < 120) {
    #detail-grid {
        grid-size: 1;
    }
}

QuotaCard, TokenCard, ContextCard, RateLimitCard {
    border: solid #3b4261;
    color: #c0caf5;
}

HistoryTable {
    height: auto;
    max-height: 10;
    margin-top: 1;
    background: #16161e;
    color: #a9b1d6;
}

Footer {
    dock: bottom;
    background: #16161e;
    color: #565f89;
}
```

- [ ] **Step 3: Commit**

```bash
cd quota-dash && git add src/quota_dash/themes/ && git commit -m "feat: updated CSS themes for new widget architecture"
```

---

### Task 7: App Rewrite & Old Widget Cleanup

**Files:**
- Modify: `src/quota_dash/app.py`
- Modify: `src/quota_dash/widgets/__init__.py`
- Delete: `src/quota_dash/widgets/provider_list.py`
- Delete: `src/quota_dash/widgets/quota_panel.py`
- Delete: `src/quota_dash/widgets/token_panel.py`
- Delete: `src/quota_dash/widgets/context_gauge.py`
- Delete: `tests/test_widgets.py` (old)
- Modify: `tests/test_app.py`

- [ ] **Step 1: Delete old widget files**

```bash
cd quota-dash && rm src/quota_dash/widgets/provider_list.py src/quota_dash/widgets/quota_panel.py src/quota_dash/widgets/token_panel.py src/quota_dash/widgets/context_gauge.py
```

- [ ] **Step 2: Update widgets/__init__.py**

```python
# src/quota_dash/widgets/__init__.py
from quota_dash.widgets.overview_table import OverviewTable
from quota_dash.widgets.detail_panel import DetailPanel
from quota_dash.widgets.quota_card import QuotaCard
from quota_dash.widgets.token_card import TokenCard
from quota_dash.widgets.context_card import ContextCard
from quota_dash.widgets.ratelimit_card import RateLimitCard
from quota_dash.widgets.history_table import HistoryTable
```

- [ ] **Step 3: Rewrite app.py**

```python
# src/quota_dash/app.py
from __future__ import annotations

import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header
from textual.widgets import DataTable

from quota_dash.config import AppConfig
from quota_dash.data.store import DataStore
from quota_dash.providers.anthropic import AnthropicProvider
from quota_dash.providers.base import Provider
from quota_dash.providers.openai import OpenAIProvider
from quota_dash.widgets.overview_table import OverviewTable
from quota_dash.widgets.detail_panel import DetailPanel
from quota_dash.widgets.quota_card import QuotaCard
from quota_dash.widgets.token_card import TokenCard
from quota_dash.widgets.context_card import ContextCard
from quota_dash.widgets.ratelimit_card import RateLimitCard
from quota_dash.widgets.history_table import HistoryTable


class QuotaDashApp(App):
    TITLE = "quota-dash"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("tab", "focus_next", "Next Panel", show=False),
        Binding("question_mark", "toggle_help", "Help"),
    ]

    def __init__(
        self,
        config: AppConfig | None = None,
        theme_override: str | None = None,
    ) -> None:
        self._config = config or AppConfig()
        self._theme_override = theme_override
        self._store = DataStore()
        self._providers: dict[str, Provider] = {}
        self._selected_provider: str | None = None

        css_path = self._resolve_theme()
        css_path_arg = [str(css_path)] if css_path else None
        super().__init__(css_path=css_path_arg)

    def _resolve_theme(self) -> Path | None:
        theme = self._theme_override or self._config.theme
        themes_dir = Path(__file__).parent / "themes"
        if theme == "auto":
            term = os.environ.get("TERM_PROGRAM", "")
            theme = "ghostty" if term == "ghostty" else "default"
        theme_file = themes_dir / f"{theme}.tcss"
        return theme_file if theme_file.exists() else None

    def compose(self) -> ComposeResult:
        yield Header()
        yield OverviewTable()
        yield DetailPanel()
        yield HistoryTable()
        yield Footer()

    async def on_mount(self) -> None:
        self._init_providers()
        await self._refresh_all()
        self.set_interval(self._config.polling_interval, self._poll)

    def _init_providers(self) -> None:
        provider_map = {"openai": OpenAIProvider, "anthropic": AnthropicProvider}
        db_path = self._config.proxy.db_path
        for name, pconfig in self._config.providers.items():
            if pconfig.enabled and name in provider_map:
                self._providers[name] = provider_map[name](pconfig, db_path=db_path)

    def _poll(self) -> None:
        self.run_worker(self._refresh_all())

    async def _refresh_all(self) -> None:
        # Refresh ALL providers
        provider_names = list(self._providers.keys())
        tokens_today: dict[str, int] = {}
        context_pcts: dict[str, float] = {}
        rate_limits: dict[str, int | None] = {}
        sources: dict[str, str] = {}

        for name, provider in self._providers.items():
            quota = await provider.get_quota()
            tokens = await provider.get_token_usage()
            context = await provider.get_context_window()

            self._store.update_quota(name, quota)
            self._store.update_tokens(name, tokens)
            self._store.update_context(name, context)

            # Get proxy data if available
            proxy_data = await provider.get_proxy_data()
            if proxy_data:
                self._store.update_proxy(name, proxy_data)
                tokens_today[name] = proxy_data.tokens_today
                rate_limits[name] = proxy_data.ratelimit_remaining_tokens
                sources[name] = "proxy"
            else:
                tokens_today[name] = tokens.total_tokens
                rate_limits[name] = None
                sources[name] = tokens.source

            context_pcts[name] = context.percent_used

        # Update OverviewTable
        quotas = {n: self._store.get_quota(n) for n in provider_names if self._store.get_quota(n)}
        self.query_one(OverviewTable).refresh_data(
            providers=provider_names,
            quotas=quotas,
            tokens_today=tokens_today,
            context_pcts=context_pcts,
            rate_limits=rate_limits,
            sources=sources,
            total_balance=self._store.total_balance(),
            total_tokens=self._store.total_tokens_today(),
        )

        # Update DetailPanel for selected provider
        if not self._selected_provider and provider_names:
            self._selected_provider = provider_names[0]

        if self._selected_provider:
            await self._update_detail(self._selected_provider)

    async def _update_detail(self, provider_name: str) -> None:
        quota = self._store.get_quota(provider_name)
        tokens = self._store.get_tokens(provider_name)
        context = self._store.get_context(provider_name)
        proxy = self._store.get_proxy(provider_name)

        panel = self.query_one(DetailPanel)
        if quota:
            panel.query_one(QuotaCard).update_data(quota)
        if tokens:
            # Try to get sparkline data from proxy DB
            sparkline_data = None
            db_path = self._config.proxy.db_path
            if db_path and db_path.exists():
                from quota_dash.proxy.db import query_token_history
                history = await query_token_history(db_path, provider_name)
                if history:
                    sparkline_data = [tok for _, tok in history]
            panel.query_one(TokenCard).update_data(tokens, sparkline_data=sparkline_data)
        if context:
            panel.query_one(ContextCard).update_data(context)

        panel.query_one(RateLimitCard).update_data(proxy)

        # Update HistoryTable
        history_table = self.query_one(HistoryTable)
        db_path = self._config.proxy.db_path
        if db_path and db_path.exists():
            from quota_dash.proxy.db import query_recent_calls
            calls = await query_recent_calls(db_path, provider_name)
            history_table.update_data(calls)
        else:
            history_table.update_data([])

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value != "__total__":
            self._selected_provider = str(event.row_key.value)
            self.run_worker(self._update_detail(self._selected_provider))

    async def action_refresh(self) -> None:
        await self._refresh_all()

    def action_toggle_help(self) -> None:
        self.notify(
            "[b]Keybindings[/b]\n"
            "↑↓  Switch provider\n"
            "r   Refresh\n"
            "Tab Focus next panel\n"
            "q   Quit\n"
            "?   This help",
            title="Help",
            timeout=8,
        )
```

- [ ] **Step 4: Rewrite test_app.py**

```python
# tests/test_app.py
import pytest
from pathlib import Path
from quota_dash.app import QuotaDashApp
from quota_dash.config import AppConfig, ProviderConfig
from quota_dash.widgets.overview_table import OverviewTable
from quota_dash.widgets.detail_panel import DetailPanel
from quota_dash.widgets.history_table import HistoryTable


@pytest.mark.asyncio
async def test_app_launches():
    app = QuotaDashApp()
    async with app.run_test() as pilot:
        assert app.title == "quota-dash"


@pytest.mark.asyncio
async def test_app_quit_binding():
    app = QuotaDashApp()
    async with app.run_test() as pilot:
        await pilot.press("q")


@pytest.mark.asyncio
async def test_app_refresh_binding():
    app = QuotaDashApp()
    async with app.run_test() as pilot:
        await pilot.press("r")


@pytest.mark.asyncio
async def test_app_has_new_widgets():
    app = QuotaDashApp()
    async with app.run_test() as pilot:
        assert app.query_one(OverviewTable) is not None
        assert app.query_one(DetailPanel) is not None
        assert app.query_one(HistoryTable) is not None


@pytest.mark.asyncio
async def test_app_with_manual_config():
    config = AppConfig(
        polling_interval=60,
        theme="default",
        providers={
            "openai": ProviderConfig(
                enabled=True, api_key_env="NONEXISTENT",
                log_path=Path("/tmp/nonexistent"),
                balance_usd=50.0, limit_usd=100.0,
            ),
        },
    )
    app = QuotaDashApp(config=config)
    async with app.run_test() as pilot:
        assert app.title == "quota-dash"
        await pilot.press("r")
        await pilot.pause()
```

- [ ] **Step 5: Delete old test_widgets.py**

```bash
cd quota-dash && rm tests/test_widgets.py
```

- [ ] **Step 6: Rename test_widgets_new.py to test_widgets.py**

```bash
cd quota-dash && mv tests/test_widgets_new.py tests/test_widgets.py
```

- [ ] **Step 7: Run full test suite**

Run: `cd quota-dash && pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
cd quota-dash && git add -u && git add src/quota_dash/widgets/ src/quota_dash/app.py tests/ && git commit -m "feat: complete UI/UX redesign — Overview+Detail layout with native Textual widgets"
```

---

### Task 8: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Reinstall and verify**

```bash
cd quota-dash && pip install -e ".[dev]" && quota-dash --help
```

- [ ] **Step 2: Run full test suite**

```bash
cd quota-dash && pytest tests/ -v --tb=short
```
Expected: All tests PASS

- [ ] **Step 3: Verify one-shot mode still works**

```bash
cd quota-dash && quota-dash --once
```
Expected: Rich table output, exit 0

- [ ] **Step 4: Commit if any changes needed**
