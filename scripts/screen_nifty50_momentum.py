"""Project TITAN — NIFTY 50 Quantitative Factor & Momentum Screener.

Screens all 50 constituent equities of the NIFTY 50 index using zero-cost direct
market data feeds, evaluates cross-sectional momentum, risk-adjusted returns,
volatility, and trend structure, and outputs:
1. Complete Ranked Universe Leaderboard.
2. Top 5 Factor Momentum Picks for Monday Opening Bell.
3. Recommended Portfolio Rebalance Plan for Sleeve D (₹1,00,000 INR Budget).
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("nifty-screener")

# Official NIFTY 50 Universe (NSE India)
NIFTY_50_SYMBOLS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS",
    "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INFY.NS", "INDUSINDBK.NS", "JSWSTEEL.NS", "SHRIRAMFIN.NS", "KOTAKBANK.NS",
    "LT.NS", "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS",
    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS",
    "SUNPHARMA.NS", "TATACONSUM.NS", "TMCV.NS", "TATASTEEL.NS", "TCS.NS",
    "TECHM.NS", "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS", "WIPRO.NS"
]


@dataclass
class StockFactorMetrics:
    symbol: str
    display_name: str
    current_price: float
    return_20d_pct: float
    return_60d_pct: float
    volatility_20d_pct: float
    sharpe_factor: float
    rsi_14: float
    sma_50: float
    trend_above_sma50: bool
    dist_from_high_pct: float
    composite_score: float = 0.0
    rank: int = 0


def compute_rsi(prices: List[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0

    gains = []
    losses = []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    if len(gains) < period:
        return 50.0

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0.0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def fetch_stock_bars(symbol: str) -> Optional[List[float]]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=3mo"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            res = data.get("chart", {}).get("result", [{}])[0]
            closes = res.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            valid_closes = [float(c) for c in closes if c is not None]
            return valid_closes if len(valid_closes) >= 25 else None
    except Exception as e:
        logger.debug("Failed fetching bars for %s: %s", symbol, e)
        return None


def analyze_stock(symbol: str) -> Optional[StockFactorMetrics]:
    bars = fetch_stock_bars(symbol)
    if not bars or len(bars) < 25:
        return None

    current_price = round(bars[-1], 2)
    p_20d_ago = bars[-21] if len(bars) >= 21 else bars[0]
    p_60d_ago = bars[-61] if len(bars) >= 61 else bars[0]

    ret_20d = round(((current_price - p_20d_ago) / p_20d_ago) * 100.0, 2)
    ret_60d = round(((current_price - p_60d_ago) / p_60d_ago) * 100.0, 2)

    # 20-day realized volatility (annualized)
    recent_bars = bars[-21:]
    daily_rets = [(recent_bars[i] - recent_bars[i - 1]) / recent_bars[i - 1] for i in range(1, len(recent_bars))]
    if daily_rets:
        mean_ret = sum(daily_rets) / len(daily_rets)
        var = sum((r - mean_ret) ** 2 for r in daily_rets) / len(daily_rets)
        std = math.sqrt(var)
        vol_ann = round(std * math.sqrt(252) * 100.0, 2)
    else:
        vol_ann = 20.0

    # Risk-adjusted factor (return / volatility)
    sharpe_factor = round(ret_20d / vol_ann, 2) if vol_ann > 0 else 0.0

    # RSI 14
    rsi = compute_rsi(bars, period=14)

    # 50-day SMA
    sma_len = min(50, len(bars))
    sma_50 = round(sum(bars[-sma_len:]) / sma_len, 2)
    above_sma = current_price >= sma_50

    # Distance from 60d high
    high_60d = max(bars[-60:]) if len(bars) >= 60 else max(bars)
    dist_high = round(((current_price - high_60d) / high_60d) * 100.0, 2)

    clean_name = symbol.replace(".NS", "")

    return StockFactorMetrics(
        symbol=symbol,
        display_name=clean_name,
        current_price=current_price,
        return_20d_pct=ret_20d,
        return_60d_pct=ret_60d,
        volatility_20d_pct=vol_ann,
        sharpe_factor=sharpe_factor,
        rsi_14=rsi,
        sma_50=sma_50,
        trend_above_sma50=above_sma,
        dist_from_high_pct=dist_high,
    )


def run_nifty_momentum_screen(top_n: int = 5) -> List[StockFactorMetrics]:
    logger.info("Initiating quantitative factor scan across all %d NIFTY 50 constituents...", len(NIFTY_50_SYMBOLS))

    metrics_list: List[StockFactorMetrics] = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for m in executor.map(analyze_stock, NIFTY_50_SYMBOLS):
            if m is not None:
                metrics_list.append(m)

    logger.info("Successfully ingested and computed factor metrics for %d stocks.", len(metrics_list))

    if not metrics_list:
        return []

    # Cross-sectional percentile ranking
    n = len(metrics_list)
    by_ret20 = sorted(metrics_list, key=lambda x: x.return_20d_pct)
    by_sharpe = sorted(metrics_list, key=lambda x: x.sharpe_factor)
    by_ret60 = sorted(metrics_list, key=lambda x: x.return_60d_pct)
    by_dist = sorted(metrics_list, key=lambda x: x.dist_from_high_pct)

    rank_ret20 = {s.symbol: i / n for i, s in enumerate(by_ret20)}
    rank_sharpe = {s.symbol: i / n for i, s in enumerate(by_sharpe)}
    rank_ret60 = {s.symbol: i / n for i, s in enumerate(by_ret60)}
    rank_dist = {s.symbol: i / n for i, s in enumerate(by_dist)}

    for m in metrics_list:
        # Penalize overbought RSI > 78 or oversold RSI < 35
        rsi_penalty = -0.15 if m.rsi_14 > 78 or m.rsi_14 < 35 else 0.0
        # Trend gate bonus
        trend_bonus = 0.05 if m.trend_above_sma50 else -0.10

        composite = (
            0.40 * rank_ret20[m.symbol]
            + 0.30 * rank_sharpe[m.symbol]
            + 0.20 * rank_ret60[m.symbol]
            + 0.10 * rank_dist[m.symbol]
            + rsi_penalty
            + trend_bonus
        )
        m.composite_score = round(composite * 100.0, 1)

    ranked = sorted(metrics_list, key=lambda x: x.composite_score, reverse=True)
    for i, m in enumerate(ranked, 1):
        m.rank = i

    return ranked


def print_leaderboard(ranked: List[StockFactorMetrics], top_n: int = 5):
    print("\n" + "=" * 90)
    print("🎯 PROJECT TITAN — NIFTY 50 CROSS-SECTIONAL MOMENTUM LEADERBOARD")
    print("=" * 90)
    print(f"{'Rank':<5} {'Symbol':<14} {'Price (₹)':<10} {'20d Ret %':<11} {'60d Ret %':<11} {'20d Vol %':<11} {'Sharpe':<8} {'RSI':<6} {'Score':<6}")
    print("-" * 90)

    for m in ranked[:15]:
        marker = "⭐ [TOP 5]" if m.rank <= top_n else ""
        print(f"{m.rank:<5} {m.display_name:<14} {m.current_price:<10.2f} {m.return_20d_pct:>+8.2f}% {m.return_60d_pct:>+8.2f}% {m.volatility_20d_pct:>8.1f}% {m.sharpe_factor:>7.2f} {m.rsi_14:>5.1f} {m.composite_score:>5.1f}  {marker}")

    print("-" * 90)
    print(f"Total Universe Screened: {len(ranked)} / {len(NIFTY_50_SYMBOLS)} stocks.")


def generate_sleeve_d_allocation_plan(top_picks: List[StockFactorMetrics], total_budget_inr: float = 100_000.0):
    print("\n" + "=" * 90)
    print(f"💼 RECOMMENDED SLEEVE D REBALANCE PLAN (BUDGET: ₹{total_budget_inr:,.2f})")
    print("=" * 90)

    # 5 stocks, 15% each = 75% equity exposure, 25% cash buffer (₹25,000)
    allocation_per_stock = (total_budget_inr * 0.75) / len(top_picks)
    cash_cushion = total_budget_inr * 0.25

    total_allocated = 0.0
    print(f"{'Stock':<14} {'Current Px':<12} {'Target Qty':<12} {'Target Value (₹)':<18} {'Weight %':<10}")
    print("-" * 90)

    for p in top_picks:
        qty = int(allocation_per_stock // p.current_price)
        val = qty * p.current_price
        total_allocated += val
        weight = (val / total_budget_inr) * 100.0
        print(f"{p.display_name:<14} ₹{p.current_price:<10.2f} {qty:<12} ₹{val:<16.2f} {weight:.1f}%")

    actual_cash = total_budget_inr - total_allocated
    print("-" * 90)
    print(f"Total Invested Equity:  ₹{total_allocated:,.2f} ({(total_allocated / total_budget_inr) * 100:.1f}%)")
    print(f"Preserved Cash Cushion: ₹{actual_cash:,.2f} ({(actual_cash / total_budget_inr) * 100:.1f}%)")
    print("=" * 90)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NIFTY 50 Quantitative Momentum Screener")
    parser.add_argument("--top", type=int, default=5, help="Number of top momentum stocks to select")
    parser.add_argument("--budget", type=float, default=100_000.0, help="Sleeve D allocation capital in INR")
    args = parser.parse_args()

    ranked_stocks = run_nifty_momentum_screen(top_n=args.top)
    if ranked_stocks:
        print_leaderboard(ranked_stocks, top_n=args.top)
        generate_sleeve_d_allocation_plan(ranked_stocks[:args.top], total_budget_inr=args.budget)
