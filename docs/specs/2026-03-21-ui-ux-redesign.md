# quota-dash v0.3: UI/UX Redesign — Design Spec

> Replace text-render widgets with Textual native components. Overview+Detail layout, responsive, proxy-powered history.

## Overview

Full widget layer rewrite. Replace the 4 existing text-render widgets with a new architecture: an `OverviewTable` (Textual `DataTable`) showing all providers at a glance, and a `DetailPanel` with 5 sub-widgets using Textual native components (`ProgressBar`, `Sparkline`, `DataTable`, `Static`). Two-stage responsive layout for wide (≥120 cols) and narrow (<120 cols) terminals.

## Goals

1. See all providers at once in a summary table (no more one-at-a-time sidebar)
2. Rich detail panel with quota, tokens, context, rate limits, and API call history
3. Use Textual built-in widgets — not custom text rendering
4. Responsive: 2x2 grid on wide terminals, single column on narrow
5. SQLite-powered history table and sparkline data

## Non-Goals

- Custom chart library (plotext, etc.)
- Multiple Textual Screens
- Drag-and-drop or mouse-heavy interactions

## Layout

### Wide (≥120 columns)

```
┌─ Header ────────────────────────────────────────────┐
├─ OverviewTable (DataTable, 6 cols, full width) ─────┤
│ Provider │ Balance │ Tokens │ Ctx │ Rate │ Source    │
│ ▸ OpenAI │ $47.32  │ 20.5K  │ 62% │ 9K   │ proxy   │
│   Anthro │ $200    │ 63.9K  │ 35% │ 50K  │ proxy   │
│   Total  │ $247.32 │ 84.4K  │     │      │         │
├─ DetailPanel ───────────────────────────────────────┤
│ ┌─ QuotaCard ───┐┌─ TokenCard ──────────────────┐  │
│ │ ProgressBar   ││ Sparkline + stats            │  │
│ └───────────────┘└──────────────────────────────┘  │
│ ┌─ ContextCard ─┐┌─ RateLimitCard ──────────────┐  │
│ │ ProgressBar   ││ Static text                  │  │
│ └───────────────┘└──────────────────────────────┘  │
├─ HistoryTable (DataTable, 4 cols, full width) ──────┤
│ Time │ Model │ Tokens │ Endpoint                    │
├─ Footer ────────────────────────────────────────────┤
```

### Narrow (<120 columns)

- OverviewTable hides Rate Limit and Source columns
- DetailPanel switches to single column (all cards stacked)
- Everything else same structure

## New File Structure

```
src/quota_dash/widgets/
├── __init__.py
├── overview_table.py     # OverviewTable — DataTable with 6 cols + Total row
├── detail_panel.py       # DetailPanel — container for 5 sub-widgets
├── quota_card.py         # QuotaCard — ProgressBar + label
├── token_card.py         # TokenCard — Sparkline + stats
├── context_card.py       # ContextCard — ProgressBar + label
├── ratelimit_card.py     # RateLimitCard — Static text
└── history_table.py      # HistoryTable — DataTable of recent API calls
```

### Deleted Files

- `widgets/provider_list.py` — replaced by `overview_table.py`
- `widgets/quota_panel.py` — replaced by `quota_card.py`
- `widgets/token_panel.py` — replaced by `token_card.py`
- `widgets/context_gauge.py` — replaced by `context_card.py`

## Widget Specifications

### OverviewTable

- Textual `DataTable` with `cursor_type="row"`
- 6 columns: Provider | Balance | Tokens Today | Context % | Rate Limit | Source
- Last row = Total (bold): sums Balance and Tokens only
- Row highlight triggers `DetailPanel` update via `on_data_table_row_highlighted`
- Data source: `DataStore` all providers

### QuotaCard

- Container with Textual `ProgressBar` — set `total = limit_usd`, `progress = balance_usd` (percentage is auto-computed as `progress/total`, read-only). Set `show_eta=False`.
- `Static` label above: `$47.32 / $100.00 [manual]`
- Source tag and stale indicator
- Shows "not configured" when `source == "unavailable"`

### TokenCard

- Textual `Sparkline` widget showing 24h token history
- Data from `query_token_history()` — list of (timestamp, total_tokens) tuples
- `Static` below: `In: 12,400 | Out: 8,100 | Total: 20,500`
- Source tag: `[proxy]` / `[log]` / `[estimated]`

### ContextCard

- Textual `ProgressBar` — set `total = max_tokens`, `progress = used_tokens`. `show_eta=False`.
- `Static` label: `62% (80K / 128K) — gpt-4`
- Bottom note: `last call snapshot` or `approximation — CLI logs lack per-turn data`

### RateLimitCard

- `Static` widget with 3 lines:
  - `Tokens: 9,000 remaining`
  - `Requests: 99 remaining`
  - `Reset: 2m 30s`
- Shows `no data` when proxy hasn't captured rate limit headers

**Model change required**: Add `ratelimit_reset: str | None = None` to `ProxyData` in `models.py`, and update `query_provider_data()` in `proxy/db.py` to return it from the `ratelimit_reset` column.

### HistoryTable

- Textual `DataTable` with 4 columns: Time | Model | Tokens | Endpoint
- Data from `query_recent_calls()` — latest 20 rows from SQLite for selected provider
- Shows `Start proxy to see API call history` when no data
- Auto-scrolls to most recent entry

## New DB Queries

Added to `proxy/db.py`:

```python
async def query_recent_calls(db_path: Path, provider: str, limit: int = 20) -> list[dict]:
    """Today's API call records for HistoryTable."""

async def query_token_history(db_path: Path, provider: str, limit: int = 50) -> list[tuple[datetime, int]]:
    """Recent (timestamp, total_tokens) pairs for Sparkline."""
```

**DataStore vs direct DB**: `DataStore` continues to hold the provider-level summary data (`QuotaInfo`, `TokenUsage`, `ContextInfo`, `ProxyData`). The new DB queries (`query_recent_calls`, `query_token_history`) are called **directly by the DetailPanel sub-widgets** during refresh — they bypass `DataStore` because they are view-specific queries (history rows, sparkline time-series) not provider-level state.

**TokenCard data source**: The `Sparkline` uses `query_token_history()` from SQLite when proxy data is available (db_path exists). Falls back to `TokenUsage.history` from the model when no proxy DB.

**OverviewTable "Tokens Today" aggregation**: Add `total_tokens_today() -> int` method to `DataStore` that sums `ProxyData.tokens_today` across all providers (or falls back to `TokenUsage.total_tokens`).

## Data Flow

```
poll interval / manual refresh
    │
    ▼
providers[*].get_quota/tokens/context()
    │
    ▼
DataStore (update all providers)
    │
    ├──▶ OverviewTable.refresh_data(all_providers)
    │
    └──▶ DetailPanel (selected provider only)
            ├── QuotaCard.update(QuotaInfo)
            ├── TokenCard.update(TokenUsage, token_history)
            ├── ContextCard.update(ContextInfo)
            ├── RateLimitCard.update(ProxyData)
            └── HistoryTable.update(recent_calls)
```

### Refresh Triggers

- **Polling** (existing `set_interval`) → updates all widgets
- **`r` key** → force refresh all
- **OverviewTable row change** → updates DetailPanel only (cached data, no API call)

### OverviewTable Row Selection

- Textual's `on_data_table_row_highlighted` event
- Reads cached data from `DataStore` for that provider
- Pushes to all DetailPanel sub-widgets
- Does NOT trigger a new API poll

## Responsive CSS

```css
/* Wide: 2x2 grid for detail cards */
#detail-grid {
    layout: grid;
    grid-size: 2 2;
}

/* Narrow: single column */
@media (width < 120) {
    #detail-grid {
        grid-size: 1;
    }
}
```

**OverviewTable column hiding** (narrow screen): Textual's `DataTable` does not support per-column CSS classes. Column hiding is implemented **programmatically**: `OverviewTable` watches `app.size` via `on_resize`, and rebuilds the table with 4 columns (dropping Rate Limit and Source) when `width < 120`.

## Theme Updates

Both `default.tcss` and `ghostty.tcss` are updated:
- Remove old widget selectors (`ProviderList`, `QuotaPanel`, `TokenPanel`, `ContextGauge`)
- Add new selectors: `OverviewTable`, `DetailPanel`, `#detail-grid`, `QuotaCard`, `TokenCard`, `ContextCard`, `RateLimitCard`, `HistoryTable`
- Ghostty theme gets richer `ProgressBar` colors. Static CSS sets base colors via `bar--bar` and `bar--complete`. Dynamic green→yellow→red gradient is implemented programmatically in `QuotaCard`/`ContextCard` via a `watch_percentage` callback that updates `styles.color` based on the current value (green <50%, yellow 50-80%, red >80%)

## App Changes

`app.py` changes:
- `compose()` yields new widget tree: `Header → OverviewTable → DetailPanel(detail-grid(QuotaCard, TokenCard, ContextCard, RateLimitCard), HistoryTable) → Footer`
- **`_refresh_all()` must iterate ALL providers** (not just the selected one as before): loop through `self._providers`, call `get_quota/get_token_usage/get_context_window` for each, update `DataStore` for each. Then push all-provider summary to `OverviewTable`, and push selected provider's detail to `DetailPanel`.
- New `on_data_table_row_highlighted` handler for provider switching — reads cached data from `DataStore`, pushes to `DetailPanel` (no API call)
- Remove old imports, add new widget imports
- `_init_providers` unchanged

## Keyboard Controls

Same as before, adapted to new widgets:

| Key | Action |
|-----|--------|
| `↑↓` | Move row in OverviewTable (switches provider) |
| `r` | Force refresh all data |
| `Tab` | Cycle focus: OverviewTable → DetailPanel → HistoryTable |
| `q` | Quit |
| `?` | Help overlay |

## Error States

- No providers configured → OverviewTable shows empty state message
- Proxy not running → HistoryTable shows "Start proxy to see API call history"
- API call failed → QuotaCard shows stale indicator, last known data
- No token history → TokenCard Sparkline is empty, shows "no history"

## Testing Strategy

- Widget unit tests: each new widget mounts in a test app, receives data, renders without error
- OverviewTable tests: row highlighting triggers correct event
- Responsive tests: verify grid changes at width breakpoint
- Integration: full app with mock config, verify all widgets present and data flows
- Delete old widget tests, write new ones

## Migration Path

This is a breaking change to the widget layer. No migration needed — v0.1/v0.2 widgets are internal, not public API. Old widget files are deleted, old tests are rewritten.
