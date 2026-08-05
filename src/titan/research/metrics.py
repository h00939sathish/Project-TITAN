"""Research metrics — turnover, exposure, confidence intervals, regime analysis."""

import random
import statistics
from dataclasses import dataclass
from math import sqrt

from titan.backtest.results import BacktestResult


@dataclass
class InstrumentDailyCorrelation:
    instrument_a: str
    instrument_b: str
    pearson_r: float
    observation_count: int


def compute_cagr(equity_curve: list[float], periods_per_year: int = 252) -> float:
    """Compute compound annual growth rate from an equity curve."""
    if len(equity_curve) < 2 or equity_curve[0] <= 0 or equity_curve[-1] <= 0:
        return 0.0

    periods = len(equity_curve) - 1
    growth = equity_curve[-1] / equity_curve[0]
    return round(((growth ** (periods_per_year / periods)) - 1.0) * 100.0, 4)


def compute_turnover(trades: list[dict], initial_capital: float) -> dict:
    """Portfolio turnover: total traded volume / average capital."""
    if not trades:
        return {"total_turnover_pct": 0.0, "annualized_turnover_pct": 0.0,
                "avg_trade_size_pct": 0.0}

    buy_trades = [t for t in trades if t.get("side") == "buy"]
    total_bought = sum(t.get("qty", 0) * t.get("price", 0) for t in buy_trades)
    total_turnover_pct = (total_bought / initial_capital) * 100
    avg_trade_size_pct = (total_bought / max(len(buy_trades), 1)) / initial_capital * 100

    return {
        "total_turnover_pct": round(total_turnover_pct, 2),
        "annualized_turnover_pct": round(total_turnover_pct, 2),
        "avg_trade_size_pct": round(avg_trade_size_pct, 4),
        "total_bought": round(total_bought, 2),
    }


def compute_exposure(bars: list[dict], trades: list[dict],
                     buy_signal_fn=None) -> dict:
    """Compute time in market and longest flat period.

    If buy_signal_fn is provided (a function that takes a bar and returns
    True if in position), it is used to determine position state. Otherwise
    the trades list is used to infer position.
    """
    if not bars:
        return {"time_in_market_pct": 0.0, "bars_in_market": 0,
                "total_bars": 0, "longest_flat_period_bars": 0}

    if buy_signal_fn is not None:
        position_active = False
        position_bars = 0
        flat_bars = 0
        max_flat_streak = 0
        for bar in bars:
            signal = buy_signal_fn(bar)
            if signal == "BUY":
                position_active = True
                flat_bars = 0
            elif signal == "SELL":
                position_active = False
                flat_bars = 0
            if position_active:
                position_bars += 1
                flat_bars = 0
            else:
                flat_bars += 1
                max_flat_streak = max(max_flat_streak, flat_bars)
    else:
        # Infer from trades: buy sets position, sell clears it
        buy_timestamps = {t.get("timestamp", "") for t in trades if t.get("side") == "buy"}
        sell_timestamps = {t.get("timestamp", "") for t in trades if t.get("side") == "sell"}
        position_active = False
        position_bars = 0
        flat_bars = 0
        max_flat_streak = 0
        for bar in bars:
            ts = bar.get("timestamp", "")
            if ts in buy_timestamps:
                position_active = True
                flat_bars = 0
            elif ts in sell_timestamps:
                position_active = False
                flat_bars = 0
            if position_active:
                position_bars += 1
                flat_bars = 0
            else:
                flat_bars += 1
                max_flat_streak = max(max_flat_streak, flat_bars)

    time_in_market = (position_bars / max(len(bars), 1)) * 100
    return {
        "time_in_market_pct": round(time_in_market, 2),
        "bars_in_market": position_bars,
        "total_bars": len(bars),
        "longest_flat_period_bars": max_flat_streak,
    }


def daily_return_bootstrap(equity_curve: list[float],
                           n_simulations: int = 10000) -> dict:
    """Bootstrap daily returns to estimate confidence intervals for
    annualized return and Sharpe ratio."""
    if not equity_curve or len(equity_curve) < 5:
        return {"annual_return_ci": (0, 0), "sharpe_ci": (0, 0),
                "n_days": 0}

    daily_returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        if prev > 0:
            daily_returns.append((equity_curve[i] - prev) / prev)
        else:
            daily_returns.append(0.0)

    if len(daily_returns) < 5:
        return {"annual_return_ci": (0, 0), "sharpe_ci": (0, 0),
                "n_days": len(daily_returns)}

    ann_returns = []
    sharpes = []
    mean_block_length = 5
    p_geom = 1.0 / mean_block_length
    n_samples = len(daily_returns)

    for _ in range(n_simulations):
        sample = []
        while len(sample) < n_samples:
            start_idx = random.randint(0, n_samples - 1)
            block_len = 1
            while random.random() > p_geom and block_len < 20:
                block_len += 1
            for offset in range(block_len):
                sample.append(daily_returns[(start_idx + offset) % n_samples])
                if len(sample) >= n_samples:
                    break

        avg_r = sum(sample) / len(sample)
        var_r = sum((r - avg_r) ** 2 for r in sample) / (len(sample) - 1) if len(sample) > 1 else 0.0
        std_r = sqrt(var_r) if var_r > 0 else 1e-10
        ann_ret = avg_r * 252 * 100
        sharpe = (avg_r / std_r) * sqrt(252) if std_r > 0 else 0.0
        ann_returns.append(ann_ret)
        sharpes.append(sharpe)

    def ci_95(data):
        s = sorted(data)
        n = len(s)
        return (round(s[int(n * 0.025)], 4), round(s[int(n * 0.975)], 4))

    return {
        "annual_return_ci": ci_95(ann_returns),
        "sharpe_ci": ci_95(sharpes),
        "mean_annual_return": round(statistics.mean(ann_returns), 4),
        "mean_sharpe": round(statistics.mean(sharpes), 4),
        "n_days": len(daily_returns),
        "n_simulations": n_simulations,
    }


def exposure_adjusted_benchmark(benchmark_result: BacktestResult,
                                candidate_exposure_pct: float,
                                label: str = "BH") -> dict:
    """Scale a benchmark's return and drawdown by the candidate's time-in-market."""
    exposure = candidate_exposure_pct / 100.0
    adj_return = benchmark_result.total_return_pct * exposure if exposure > 0 else 0.0

    # Compute exposure-adjusted equity curve and recalculate max drawdown
    raw_equity = getattr(benchmark_result, 'equity_curve', [100.0])
    if len(raw_equity) > 1:
        adj_equity = [raw_equity[0]]
        for i in range(1, len(raw_equity)):
            ret = (raw_equity[i] - raw_equity[i - 1]) / raw_equity[i - 1]
            adj_equity.append(adj_equity[-1] * (1.0 + ret * exposure))

        peak = adj_equity[0]
        max_dd = 0.0
        for val in adj_equity:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        adj_dd = max_dd * 100.0
    else:
        adj_dd = benchmark_result.max_drawdown_pct * exposure if exposure > 0 else 0.0

    return {
        "label": f"{label} (exposure-adj)",
        "original_return": benchmark_result.total_return_pct,
        "exposure_pct": candidate_exposure_pct,
        "adjusted_return_pct": round(adj_return, 4),
        "adjusted_max_dd_pct": round(adj_dd, 4),
    }



def identify_regimes(bars: list[dict]) -> list[dict]:
    """Label each bar with a market regime (bull/bear/crash/recovery/unknown)."""
    if len(bars) < 220:
        return [{"regime": "unknown"} for _ in bars]

    closes = [b["close"] for b in bars]
    regimes = []

    sma200 = []
    for i in range(len(closes)):
        if i < 200:
            sma200.append(None)
        else:
            sma200.append(sum(closes[i - 200:i]) / 200)

    running_peak = 0.0
    in_crash = False
    in_recovery = False

    for i in range(len(bars)):
        close = closes[i]
        running_peak = max(running_peak, close)
        dd_pct = (running_peak - close) / running_peak * 100

        if i >= 220 and sma200[i] is not None and sma200[i - 20] is not None:
            sma_slope = (sma200[i] - sma200[i - 20]) / sma200[i - 20]
        else:
            sma_slope = 0.0

        crash = dd_pct > 20
        recovery = not crash and dd_pct > 10

        if crash:
            regime = "crash"
            in_crash = True
            in_recovery = False
        elif recovery:
            regime = "recovery"
            in_crash = False
            in_recovery = True
        elif sma_slope > 0.001:
            regime = "bull"
            in_crash = False
            in_recovery = False
        elif sma_slope < -0.001:
            regime = "bear"
            in_crash = False
            in_recovery = False
        else:
            if in_crash:
                regime = "crash"
            elif in_recovery:
                regime = "recovery"
            elif i > 0:
                regime = regimes[-1]["regime"]
            else:
                regime = "unknown"

        regimes.append({"regime": regime, "close": close, "dd_pct": round(dd_pct, 2)})

    return regimes


def regime_results(bars: list[dict], trades: list[dict],
                   equity_curve: list[float]) -> dict:
    """Compute return, Sharpe, max DD, and trade count per regime.

    Returns dict keyed by regime name with per-regime metrics.
    """
    regimes = identify_regimes(bars)
    if not regimes or len(regimes) != len(bars):
        return {}

    per_regime: dict[str, dict] = {}
    for r in regimes:
        rn = r["regime"]
        if rn not in per_regime:
            per_regime[rn] = {"bars": 0, "trades": 0, "return_pct": 0.0,
                              "sharpe": 0.0, "max_dd_pct": 0.0,
                              "start_equity": None, "peak_equity": 0.0,
                              "daily_returns": [], "in_period": 0}

    # Map each bar to its regime and track equity curve
    for i, bar in enumerate(bars):
        rn = regimes[i]["regime"]
        per_regime[rn]["bars"] += 1
        per_regime[rn]["in_period"] += 1

    # Process equity curve per-regime
    for i in range(min(len(equity_curve) - 1, len(bars))):
        rn = regimes[i]["regime"]
        if per_regime[rn]["start_equity"] is None:
            per_regime[rn]["start_equity"] = equity_curve[i]
            per_regime[rn]["peak_equity"] = equity_curve[i]

        eq = equity_curve[i + 1]
        prev_eq = equity_curve[i]
        if prev_eq > 0:
            daily_r = (eq - prev_eq) / prev_eq
            per_regime[rn]["daily_returns"].append(daily_r)

        # Track drawdown within regime
        per_regime[rn]["peak_equity"] = max(per_regime[rn]["peak_equity"], eq)
        dd = (per_regime[rn]["peak_equity"] - eq) / per_regime[rn]["peak_equity"] * 100
        per_regime[rn]["max_dd_pct"] = max(per_regime[rn]["max_dd_pct"], dd)

        # Return for this regime
        if per_regime[rn]["start_equity"] and per_regime[rn]["start_equity"] > 0:
            ret = (eq - per_regime[rn]["start_equity"]) / per_regime[rn]["start_equity"] * 100
            per_regime[rn]["return_pct"] = ret

        # Sharpe for this regime
        dr = per_regime[rn]["daily_returns"]
        if len(dr) > 1:
            avg_r = sum(dr) / len(dr)
            var_r = sum((r - avg_r) ** 2 for r in dr) / (len(dr) - 1)
            std_r = sqrt(var_r) if var_r > 0 else 1e-10
            per_regime[rn]["sharpe"] = round((avg_r / std_r) * sqrt(252) if std_r > 0 else 0.0, 4)

    # Count trades per regime
    trade_counter = {rn: 0 for rn in per_regime}
    if trades:
        trade_timestamps = {t.get("timestamp", "") for t in trades if t.get("side") in ("buy", "sell")}
        for i, bar in enumerate(bars):
            ts = bar.get("timestamp", "")
            if ts in trade_timestamps:
                rn = regimes[i]["regime"]
                trade_counter[rn] = trade_counter.get(rn, 0) + 1
                per_regime[rn]["trades"] = trade_counter[rn]

    # Clean up output
    result = {}
    for rn, data in per_regime.items():
        result[rn] = {
            "bars": data["bars"],
            "trades": data["trades"],
            "return_pct": round(data["return_pct"], 2),
            "sharpe": data["sharpe"],
            "max_dd_pct": round(data["max_dd_pct"], 2),
        }
    return result


def block_bootstrap(trades: list[dict], n_simulations: int = 1000,
                    block_size: int = 5) -> dict:
    """Block bootstrap of trade PnL sequence."""
    trade_pnls = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) != 0]
    if len(trade_pnls) < block_size:
        return {"mean": 0.0, "median": 0.0, "std": 0.0,
                "p5": 0.0, "p95": 0.0, "method": "simple_resample"}

    blocks = []
    for i in range(0, len(trade_pnls), block_size):
        blocks.append(trade_pnls[i:i + block_size])

    results = []
    for _ in range(n_simulations):
        sample = []
        while len(sample) < len(trade_pnls):
            block = random.choice(blocks)
            sample.extend(block)
        sample = sample[:len(trade_pnls)]
        results.append(sum(sample))

    sorted_r = sorted(results)
    return {
        "mean": round(statistics.mean(results), 2),
        "median": round(statistics.median(results), 2),
        "std": round(statistics.stdev(results), 2) if len(results) > 1 else 0.0,
        "p5": round(sorted_r[int(len(sorted_r) * 0.05)], 2),
        "p95": round(sorted_r[int(len(sorted_r) * 0.95)], 2),
        "method": f"block_bootstrap(block_size={block_size}, n={n_simulations})",
        "n_blocks": len(blocks),
    }


def _daily_return_map(bars: list[dict]) -> dict[str, float]:
    result = {}
    for i in range(1, len(bars)):
        ts = bars[i].get("timestamp", bars[i].get("date", ""))
        prev_close = bars[i - 1]["close"]
        if prev_close > 0:
            result[ts] = (bars[i]["close"] - prev_close) / prev_close
    return result


def compute_pairwise_correlations(
    instrument_data: list[tuple[str, list[dict]]]
) -> list[InstrumentDailyCorrelation]:
    correlations = []
    n = len(instrument_data)
    for i in range(n):
        for j in range(i + 1, n):
            id_a, bars_a = instrument_data[i]
            id_b, bars_b = instrument_data[j]
            ret_a = _daily_return_map(bars_a)
            ret_b = _daily_return_map(bars_b)
            common = sorted(set(ret_a.keys()) & set(ret_b.keys()))
            if len(common) < 2:
                continue
            ra = [ret_a[d] for d in common]
            rb = [ret_b[d] for d in common]
            k = len(ra)
            mean_a = sum(ra) / k
            mean_b = sum(rb) / k
            cov = sum((ra[t] - mean_a) * (rb[t] - mean_b) for t in range(k))
            var_a = sum((r - mean_a) ** 2 for r in ra)
            var_b = sum((r - mean_b) ** 2 for r in rb)
            denom = (var_a * var_b) ** 0.5
            r_value = cov / denom if denom > 0 else 0.0
            correlations.append(InstrumentDailyCorrelation(
                instrument_a=id_a, instrument_b=id_b,
                pearson_r=r_value, observation_count=k,
            ))
    return correlations


def compute_effective_trades(
    total_trades: int,
    n_instruments: int,
    avg_pairwise_corr: float,
) -> float:
    if avg_pairwise_corr < 0.3:
        return float(total_trades)
    discount = 1.0 + avg_pairwise_corr * (n_instruments - 1)
    return total_trades / discount if discount > 0 else float(total_trades)
