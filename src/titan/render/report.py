from datetime import datetime, timezone

from titan.backtest.engine import BacktestResult, BarResult


def _compute_max_drawdown(equity: list[float]) -> float:
    if not equity:
        return 0.0
    peak = equity[0]
    max_dd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        dd = peak - v
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _make_svg_path(equity: list[float], width: int, height: int, pad: int) -> str:
    n = len(equity)
    if n < 2:
        return ""
    mn, mx = min(equity), max(equity)
    rng = mx - mn or 1
    pts = [f"{pad + i * (width - 2 * pad) // max(n - 1, 1)},{pad + int((1 - (v - mn) / rng) * (height - 2 * pad))}" for i, v in enumerate(equity)]
    return " ".join(pts)


def _equity_svg(equity: list[float], width: int = 800, height: int = 300) -> str:
    n = len(equity)
    if n < 2:
        return f'<svg width="{width}" height="{height}"><text x="10" y="20">No equity data</text></svg>'

    mn, mx = min(equity), max(equity)
    rng = mx - mn or 1
    pad = 40
    plot_w = width - 2 * pad
    plot_h = height - 2 * pad

    pts = " ".join(
        f"{pad + i * plot_w // max(n - 1, 1)},{pad + int((1 - (v - mn) / rng) * plot_h)}"
        for i, v in enumerate(equity)
    )

    y_ticks = 5
    y_lines = ""
    y_labels = ""
    for i in range(y_ticks + 1):
        y = pad + i * plot_h // y_ticks
        val = mx - i * rng / y_ticks
        y_lines += f'<line x1="{pad}" y1="{y}" x2="{width - pad}" y2="{y}" stroke="#e0e0e0" stroke-width="1"/>\n'
        y_labels += f'<text x="{pad - 5}" y="{y + 4}" text-anchor="end" font-size="12" fill="#666">${val:,.0f}</text>\n'

    x_ticks = 5
    x_lines = ""
    x_labels = ""
    for i in range(x_ticks + 1):
        x = pad + i * plot_w // x_ticks
        x_lines += f'<line x1="{x}" y1="{pad}" x2="{x}" y2="{height - pad}" stroke="#e0e0e0" stroke-width="1"/>\n'
        x_labels += f'<text x="{x}" y="{height - pad + 18}" text-anchor="middle" font-size="12" fill="#666">{i * max(n - 1, 1) // x_ticks}</text>\n'

    return f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
<rect width="{width}" height="{height}" fill="#fafafa"/>
{y_lines}
{x_lines}
{y_labels}
{x_labels}
<polyline points="{pts}" fill="none" stroke="#2196F3" stroke-width="2"/>
<polygon points="{pad},{pad + int((1 - (0 - mn) / rng) * plot_h) if mn <= 0 <= mx else pad + plot_h} {pts} {pad + plot_w},{pad + plot_h}" fill="rgba(33,150,243,0.1)"/>
</svg>'''


def render_qualification_report(result: BacktestResult, title: str = "Qualification Report") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    trades = [b for b in result.bar_results if b.signal is not None and b.accepted]
    total_pnl = float(result.total_pnl)
    final_cash = float(result.final_cash)
    initial_cash = final_cash - total_pnl
    equity = [float(b.cash) for b in result.bar_results]
    max_dd = _compute_max_drawdown(equity)
    max_dd_pct = (max_dd / initial_cash * 100) if initial_cash else 0.0
    total_comm = float(result.total_commission)

    svg = _equity_svg(equity)

    rows_html = ""
    for b in trades:
        style = 'background:#e8f5e9' if b.signal and b.signal.upper() == 'BUY' else ('background:#ffebee' if b.signal and b.signal.upper() == 'SELL' else '')
        rows_html += f'''<tr style="{style}">
<td>{b.timestamp}</td><td>{b.signal}</td><td>{b.fill_qty}</td><td>{b.fill_price}</td>
<td>{b.position_qty}</td><td>{b.cash}</td>
</tr>\n'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 2rem; color: #333; }}
h1 {{ color: #1565C0; }}
table {{ border-collapse: collapse; width: 100%; max-width: 900px; margin: 1rem 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: right; }}
th {{ background: #1565C0; color: #fff; text-align: center; }}
tr:nth-child(even) {{ background: #f9f9f9; }}
.metrics td:first-child {{ text-align: left; font-weight: 600; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p>Generated: {ts}</p>

<h2>Metrics</h2>
<table class="metrics">
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Bars Processed</td><td>{result.bars_processed}</td></tr>
<tr><td>Total Trades</td><td>{result.trades}</td></tr>
<tr><td>Total PnL</td><td>${total_pnl:,.2f}</td></tr>
<tr><td>Final Cash</td><td>${final_cash:,.2f}</td></tr>
<tr><td>Max Drawdown</td><td>${max_dd:,.2f} ({max_dd_pct:.2f}%)</td></tr>
<tr><td>Total Commission</td><td>${total_comm:,.2f}</td></tr>
</table>

<h2>Equity Curve</h2>
{svg}

<h2>Trade Log</h2>
<table>
<tr><th>Timestamp</th><th>Signal</th><th>Fill Qty</th><th>Fill Price</th><th>Position Qty</th><th>Cash</th></tr>
{rows_html}
</table>
</body>
</html>'''


def render_shadow_trend(results_by_label: dict[str, list[BarResult]]) -> str:
    width, height = 800, 300
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#E91E63', '#9C27B0', '#00BCD4']

    all_equity: list[list[float]] = []
    for bars in results_by_label.values():
        eq = [float(b.cash) for b in bars]
        all_equity.append(eq)

    if not all_equity or all(len(eq) < 2 for eq in all_equity):
        return f'<svg width="{width}" height="{height}"><text x="10" y="20">No equity data</text></svg>'

    flat = [v for eq in all_equity for v in eq]
    mn, mx = min(flat), max(flat)
    rng = mx - mn or 1
    pad = 40
    plot_w = width - 2 * pad
    plot_h = height - 2 * pad

    y_ticks = 5
    y_lines = ""
    y_labels = ""
    for i in range(y_ticks + 1):
        y = pad + i * plot_h // y_ticks
        val = mx - i * rng / y_ticks
        y_lines += f'<line x1="{pad}" y1="{y}" x2="{width - pad}" y2="{y}" stroke="#e0e0e0" stroke-width="1"/>\n'
        y_labels += f'<text x="{pad - 5}" y="{y + 4}" text-anchor="end" font-size="12" fill="#666">${val:,.0f}</text>\n'

    x_ticks = 5
    x_lines = ""
    x_labels = ""
    for i in range(x_ticks + 1):
        x = pad + i * plot_w // x_ticks
        x_lines += f'<line x1="{x}" y1="{pad}" x2="{x}" y2="{height - pad}" stroke="#e0e0e0" stroke-width="1"/>\n'
        x_labels += f'<text x="{x}" y="{height - pad + 18}" text-anchor="middle" font-size="12" fill="#666">{i * max(len(next(iter(results_by_label.values()))), 1) // x_ticks}</text>\n'

    polys = ""
    for idx, (label, bars) in enumerate(results_by_label.items()):
        eq = [float(b.cash) for b in bars]
        n = len(eq)
        if n < 2:
            continue
        color = colors[idx % len(colors)]
        pts = " ".join(
            f"{pad + i * plot_w // max(n - 1, 1)},{pad + int((1 - (v - mn) / rng) * plot_h)}"
            for i, v in enumerate(eq)
        )
        polys += f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>\n'

    legend = ""
    for idx, label in enumerate(results_by_label.keys()):
        color = colors[idx % len(colors)]
        legend += f'<span style="display:inline-block;margin-right:1.5rem;"><span style="display:inline-block;width:16px;height:3px;background:{color};vertical-align:middle;margin-right:4px;"></span>{label}</span>\n'

    return f'''<div>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
<rect width="{width}" height="{height}" fill="#fafafa"/>
{y_lines}
{x_lines}
{y_labels}
{x_labels}
{polys}
</svg>
<div style="margin-top:8px;text-align:center;font-size:14px;">
{legend}
</div>
</div>'''
