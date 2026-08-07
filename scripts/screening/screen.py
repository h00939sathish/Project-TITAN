"""Track 3 — cheap wide signal screening (debated plan).

Screens 15 simple, academically-backed signal concepts on real 4h FX data with
a shared, cost-aware, position-aware backtest engine (no lookahead:
signal-at-close -> fill-at-next-open; real bid/ask spread; slippage +
commission; forced to flat at end).

Kill criterion (debated plan): a concept must yield >= 200 pips/year net of
costs on >= 2 of the screened pairs, else dropped immediately with no further
work. Breadth over depth — default params only.

Usage: python screen.py  -> writes scripts/screening/results.json + prints.
"""
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "research"))
import run_traderdev_families as m

SLIPPAGE_BPS = 0.5
COMMISSION_BPS = 0.2
QTY = 10_000
PIP = 0.0001
BARS_PER_YEAR = 2190.0
KILL_PIPS_PER_YEAR = 200.0
MIN_PAIRS = 2
PAIRS = ("EURUSD", "GBPUSD")


def backtest(bars, side_fn):
    cash = 0.0
    pos = 0
    entry = 0.0
    n_trades = 0
    peak = 100000.0
    maxdd = 0.0
    n = len(bars)
    for i in range(n - 1):
        if pos == 0:
            s = side_fn(i)
            if s in ("BUY", "SELL"):
                nb = bars[i + 1]
                fill = nb["o_ask"] if s == "BUY" else nb["o_bid"]
                fill = fill + (SLIPPAGE_BPS / 10000) * fill if s == "BUY" else fill - (SLIPPAGE_BPS / 10000) * fill
                cash -= (COMMISSION_BPS / 10000) * fill * QTY
                entry = fill
                pos = 1 if s == "BUY" else -1
        if pos != 0:
            c = bars[i + 1]["c_bid"] if pos > 0 else bars[i + 1]["c_ask"]
            eq = 100000.0 + (cash + (c - entry) * QTY * pos)
            peak = max(peak, eq)
            if peak > 0:
                maxdd = max(maxdd, (peak - eq) / peak)
    if pos != 0:
        last = bars[n - 1]
        fill = last["c_bid"] if pos > 0 else last["c_ask"]
        cash += (fill - entry) * QTY * pos
        cash -= (COMMISSION_BPS / 10000) * fill * QTY
        n_trades += 1
    pips = cash / (QTY * PIP)
    frac = max(n / BARS_PER_YEAR, 1.0)
    return {"trades": n_trades, "net_pips": round(pips, 1),
            "pips_per_year": round(pips / frac, 1),
            "max_dd_pct": round(maxdd * 100, 2), "bars": n}


# ---------------- indicator primitives ----------------
def _ema(vals, p):
    k = 2.0 / (p + 1)
    out = [None] * len(vals)
    e = None
    for i, v in enumerate(vals):
        e = v if e is None else v * k + e * (1 - k)
        out[i] = e
    return out


def _sma(vals, p):
    out = [None] * len(vals)
    acc = 0.0
    for i, v in enumerate(vals):
        acc += v
        if i >= p:
            acc -= vals[i - p]
        if i >= p - 1:
            out[i] = acc / p
    return out


def _std(vals, p):
    out = [None] * len(vals)
    for i in range(len(vals)):
        if i >= p - 1:
            win = vals[i - p + 1:i + 1]
            mu = sum(win) / p
            out[i] = (sum((x - mu) ** 2 for x in win) / p) ** 0.5
    return out


def _atr(bars, p):
    tr = [0.0] * len(bars)
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["h_bid"], bars[i]["l_bid"], bars[i - 1]["c_bid"]
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
    return _sma(tr, p)


def _rsi(vals, p):
    out = [None] * len(vals)
    g = [0.0] * len(vals)
    l = [0.0] * len(vals)
    for i in range(1, len(vals)):
        d = vals[i] - vals[i - 1]
        g[i] = max(d, 0.0)
        l[i] = max(-d, 0.0)
    for i in range(p, len(vals)):
        ag = sum(g[i - p + 1:i + 1]) / p
        al = sum(l[i - p + 1:i + 1]) / p
        out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out


def _highest(vals, p, i):
    return max(vals[max(0, i - p + 1):i + 1])


def _lowest(vals, p, i):
    return min(vals[max(0, i - p + 1):i + 1])


# ---------------- concept library ----------------
def make_concepts(bars):
    """dict name -> side_fn(i). No lookahead: side_fn reads bars[..i] only."""
    c = [x["c_bid"] for x in bars]
    h = [x["h_bid"] for x in bars]
    l = [x["l_bid"] for x in bars]
    n = len(bars)
    fns = {}

    sma10, sma30, sma50 = _sma(c, 10), _sma(c, 30), _sma(c, 50)
    ema12, ema26 = _ema(c, 12), _ema(c, 26)
    macd = [None] * n
    for i in range(n):
        if ema12[i] is not None and ema26[i] is not None:
            macd[i] = ema12[i] - ema26[i]
    macd_sig = _ema([x or 0.0 for x in macd], 9)
    bol_mid, bol_sd = _sma(c, 20), _std(c, 20)
    rsi14 = _rsi(c, 14)
    atr20 = _atr(bars, 20)
    stok = [None] * n
    for i in range(13, n):
        ll = _lowest(l, 14, i)
        hh = _highest(h, 14, i)
        stok[i] = 100.0 * (c[i] - ll) / (hh - ll) if hh > ll else 50.0
    willr = [None] * n
    for i in range(13, n):
        hh = _highest(h, 14, i)
        ll = _lowest(l, 14, i)
        willr[i] = -100.0 * (hh - c[i]) / (hh - ll) if hh > ll else 0.0

    def cross_up(a, b, i):
        return (a[i] is not None and b[i] is not None and a[i - 1] is not None
                and b[i - 1] is not None and a[i] > b[i] and a[i - 1] <= b[i - 1])

    def cross_dn(a, b, i):
        return (a[i] is not None and b[i] is not None and a[i - 1] is not None
                and b[i - 1] is not None and a[i] < b[i] and a[i - 1] >= b[i - 1])

    # 1. SMA crossover (10/30) — momentum
    def sma_cross(i):
        if cross_up(sma10, sma30, i):
            return "BUY"
        if cross_dn(sma10, sma30, i):
            return "SELL"
        return None
    fns["sma_cross"] = sma_cross

    # 2. Bollinger mean reversion (20, 2σ)
    def bb_rev(i):
        if bol_mid[i] is None or bol_sd[i] is None:
            return None
        if c[i] <= bol_mid[i] - 2 * bol_sd[i]:
            return "BUY"
        if c[i] >= bol_mid[i] + 2 * bol_sd[i]:
            return "SELL"
        return None
    fns["bb_reversion"] = bb_rev

    # 3. RSI extremes (14)
    def rsi_ext(i):
        if rsi14[i] is None:
            return None
        if rsi14[i] < 30:
            return "BUY"
        if rsi14[i] > 70:
            return "SELL"
        return None
    fns["rsi_extremes"] = rsi_ext

    # 4. MACD histogram crossover
    def macd_div(i):
        hist = macd[i] - macd_sig[i] if macd[i] is not None and macd_sig[i] is not None else None
        phist = macd[i - 1] - macd_sig[i - 1] if i and macd[i - 1] is not None and macd_sig[i - 1] is not None else None
        if hist is not None and phist is not None and hist > 0 and phist <= 0:
            return "BUY"
        if hist is not None and phist is not None and hist < 0 and phist >= 0:
            return "SELL"
        return None
    fns["macd_histogram"] = macd_div

    # 5. Donchian breakout (20)
    def donchian(i):
        if i < 21:
            return None
        hh = _highest(h, 20, i - 1)
        ll = _lowest(l, 20, i - 1)
        if c[i] > hh:
            return "BUY"
        if c[i] < ll:
            return "SELL"
        return None
    fns["donchian_breakout"] = donchian

    # 6. ATR volatility expansion (20)
    def atr_exp(i):
        if atr20[i] is None or i < 41:
            return None
        prev = sum(x or 0.0 for x in atr20[i - 20:i]) / 20
        if prev > 0 and atr20[i] > 1.5 * prev:
            return "BUY" if c[i] > c[i - 1] else "SELL"
        return None
    fns["atr_expansion"] = atr_exp

    # 7. VWAP pullback (daily vwap proxy)
    vwap = m.vwap_daily(bars)
    def vwap_pull(i):
        if vwap[i] is None:
            return None
        if c[i] < vwap[i] * 0.998:
            return "BUY"
        if c[i] > vwap[i] * 1.002:
            return "SELL"
        return None
    fns["vwap_pullback"] = vwap_pull

    # 8. Keltner squeeze breakout (20, 2×ATR)
    def keltner(i):
        if bol_mid[i] is None or atr20[i] is None:
            return None
        up = bol_mid[i] + 2 * atr20[i]
        dn = bol_mid[i] - 2 * atr20[i]
        if c[i] > up:
            return "BUY"
        if c[i] < dn:
            return "SELL"
        return None
    fns["keltner_squeeze"] = keltner

    # 9. Stochastic crossover (14,3)
    def stoch_cross(i):
        if stok[i] is None or stok[i - 1] is None:
            return None
        if stok[i] < 20 and stok[i] > stok[i - 1] and stok[i - 1] <= stok[i - 2] if i >= 2 else False:
            return "BUY"
        if stok[i] > 80 and stok[i] < stok[i - 1] and stok[i - 1] >= stok[i - 2] if i >= 2 else False:
            return "SELL"
        return None
    fns["stoch_cross"] = stoch_cross

    # 10. Ichimoku bounce: price above cloud = long bias, below = short
    tenkan = [None] * n
    kijun = [None] * n
    for i in range(8, n):
        tenkan[i] = (_highest(h, 9, i) + _lowest(l, 9, i)) / 2
    for i in range(25, n):
        kijun[i] = (_highest(h, 26, i) + _lowest(l, 26, i)) / 2
    span_a = [None] * n
    for i in range(25, n):
        span_a[i] = (tenkan[i] + kijun[i]) / 2 if tenkan[i] is not None and kijun[i] is not None else None

    def ichimoku(i):
        if span_a[i] is None or i < 26:
            return None
        if c[i] > span_a[i]:
            return "BUY"
        if c[i] < span_a[i]:
            return "SELL"
        return None
    fns["ichimoku_bounce"] = ichimoku

    # 11. Parabolic SAR reversal (simplified: 0.02/0.2 via high/low)
    def psar(i):
        if i < 3:
            return None
        if c[i] > max(h[i - 1], h[i - 2]) and c[i - 1] <= max(h[i - 2], h[i - 3]):
            return "BUY"
        if c[i] < min(l[i - 1], l[i - 2]) and c[i - 1] >= min(l[i - 2], l[i - 3]):
            return "SELL"
        return None
    fns["psar_reversal"] = psar

    # 12. Price channel breakout (20)
    def price_channel(i):
        return donchian(i)
    fns["price_channel"] = price_channel

    # 13. Williams %R extremes (14)
    def williams_r(i):
        if willr[i] is None:
            return None
        if willr[i] < -80:
            return "BUY"
        if willr[i] > -20:
            return "SELL"
        return None
    fns["williams_r"] = williams_r

    # 14. ROC momentum (20)
    def roc_mom(i):
        if i < 21 or c[i - 20] == 0:
            return None
        r = c[i] / c[i - 20] - 1.0
        if r > 0.02:
            return "BUY"
        if r < -0.02:
            return "SELL"
        return None
    fns["roc_momentum"] = roc_mom

    # 15. Inside bar breakout
    def inside_bar(i):
        if i < 2:
            return None
        if h[i - 1] <= h[i - 2] and l[i - 1] >= l[i - 2]:
            # inside bar at i-1; break on bar i
            if c[i] > h[i - 1]:
                return "BUY"
            if c[i] < l[i - 1]:
                return "SELL"
        return None
    fns["inside_bar"] = inside_bar

    return fns


CONCEPT_NAMES = [
    "sma_cross", "bb_reversion", "rsi_extremes", "macd_histogram",
    "donchian_breakout", "atr_expansion", "vwap_pullback", "keltner_squeeze",
    "stoch_cross", "ichimoku_bounce", "psar_reversal", "price_channel",
    "williams_r", "roc_momentum", "inside_bar",
]


def main():
    out = {}
    for pair in PAIRS:
        raw = json.loads((m.DATA / f"{pair}.json").read_text(encoding="utf-8"))
        bars = m.load(raw, 240)
        fns = make_concepts(bars)
        for name in CONCEPT_NAMES:
            r = backtest(bars, fns[name])
            out.setdefault(name, {})[pair] = r

    # kill criterion
    rows = []
    for name, pair_res in out.items():
        qualifying = [p for p in PAIRS if pair_res[p]["pips_per_year"] >= KILL_PIPS_PER_YEAR]
        ok = len(qualifying) >= MIN_PAIRS
        rows.append({"concept": name, "survives": ok, "pairs": qualifying,
                     "per_pair": pair_res})
        print(f"{'SURVIVE' if ok else 'killed ':7} {name:18} "
              f"{ {p: pair_res[p]['pips_per_year'] for p in PAIRS} }")

    res = Path(__file__).resolve().parent / "results.json"
    res.write_text(json.dumps({"kill_pips_per_year": KILL_PIPS_PER_YEAR,
                               "min_pairs": MIN_PAIRS, "rows": rows}, indent=2),
                   encoding="utf-8")
    n_surv = sum(1 for r in rows if r["survives"])
    print(f"\n{len(rows)} concepts, {n_surv} survive the kill criterion")
    print(f"wrote {res}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)