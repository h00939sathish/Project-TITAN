# Visualization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Render strategy qualification reports and trend charts as standalone HTML from backtest results.

**Architecture:** One new `render.py` module that takes a `BacktestResult` (or list of them) and produces a self-contained HTML file. No charting library — inline SVG or simple HTML tables + CSS bars. No server, no dashboard framework.

**Tech Stack:** Python 3.12+, HTML + inline CSS + simple SVG for sparklines.

## Global Constraints

- No new dependencies — pure Python, inline HTML, CSS, and hand-drawn SVG.
- Output is a standalone .html file (no network needed to view).
- Must work with existing BacktestResult and BarResult dataclasses.
- MVP scope: equity curve sparkline, trade markers, key metrics table.

---

### Task 1: Qualification report renderer

**File:** `src/titan/render/report.py`

Function `render_qualification_report(result: BacktestResult, title: str = "Qualification Report") -> str` that returns an HTML string containing:
- Title and timestamp
- Summary metrics table (total PnL, max drawdown, trade count, win rate, Sharpe-like ratio)
- Equity curve as inline SVG sparkline (simple polyline)
- Trade log table (timestamp, signal, fill price, fill qty, position, PnL per trade)
- Color coding: green for profit, red for loss

The function should be importable and the output should be saveable to a file.

### Task 2: Shadow trend renderer

**File:** `src/titan/render/report.py` (same file)

Function `render_shadow_trend(results: list[BacktestResult], labels: list[str]) -> str` that overlays multiple equity curves on one SVG for comparison.

### Task 3: CLI entry point

**File:** `scripts/visualize.py`

CLI that runs a backtest and renders the report:
```
python scripts/visualize.py --fixture tests/data/fixtures/eurusd_2026.csv --output report.html
```

### Task 4: Verify

Run: `python scripts/visualize.py; python -c "from pathlib import Path; assert Path('report.html').exists(); print('report created')"`
