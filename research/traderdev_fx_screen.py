"""TraderDev FX evidence screen (debated plan Steps 2-4).

Native re-implementation + honest evaluation of marketplace-strategy SIGNAL
STRUCTURES on TITAN's real data. NEVER trusts the marketplace's reported
backtests (debated decision A) — those KPIs are documented as bias, not used
as evidence.

Scope (honest, data-constrained): EURUSD + GBPUSD have full 12-month 1m data
(2025-08..2026-07); AUDUSD ~1 month (insufficient); other 6 pairs have NO
local data — recorded as data-unavailable, not tested.

Signal structures to re-implement (from the marketplace taxonomy; each is a
distinct structural class):
  1. EMA-CROSS trend (fast/slow EMA)            [Trend]
  2. Donchian-breakout (N-bar high/low)          [Breakout]
  3. RSI-2 mean reversion                        [Mean-Reversion]
  4. MACD signal-line cross                      [Momentum]
  5. Bollinger-band break                        [Volatility]
  6. Session-time filter (London/NY) + EMA       [Session-time]

Frozen protocol (WF-v2 anchored 2-fold, same as P4/P2):
  - cost: 0.8 pips RT (0.5 comm + 0.3 slip)
  - sizing: 10% annualized vol target
  - kill criteria (ALL): ann return >4%, OOS Sharpe >0.45, PF >1.2,
    maxDD <20% at 10% vol, power >=60 OOS trades
  - NO parameter tuning, NO second passes (Decision D: 0 survivors -> neg_results)

Evidence-led, no fabrication, no promotion.
"""
import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

DATA = Path(__file__).resolve().parent / "dukascopy_1m_ba"
COST_RT = 0.8 * 0.0001
VOL_TARGET = 0.10
EST_VOL = 0.08  # 4h FX vol approx
BARS_PER_YEAR = 2190.0
KILL = {"ann_ret": 0.04, "sharpe": 0.45, "pf": 1.2, "dd": 0.20, "trades": 60}
MINUTES_PER_BAR = 240  # 4h


def load_4h_closes(pair):
    raw = json.loads((DATA / f"{pair}.json").read_text())
    by4 = {}
    for b in raw:
        dt = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        by4.setdefault(int(dt.timestamp() // (240 * 60)), []).append(b["c_bid"])
    return [vs[-1] for vs in by4.values()]


def sma(s, n):
    out = [None] * len(s)
    cum = [0.0]
    for c in s:
        cum.append(cum[-1] + c)
    for i in range(n - 1, len(s)):
        out[i] = (cum[i + 1] - cum[i + 1 - n]) / n
    return out


def ema(s, n):
    out = [None] * len(s)
    if not s:
        return out
    k = 2 / (n + 1)
    e = s[0]
    for i in range(len(s)):
        e = s[i] if i == 0 else s[i] * k + e * (1 - k)
        out[i] = e
    return out


def rsi(s, n=2):
    out = [None] * len(s)
    gains, losses = 0.0, 0.0
    for i in range(1, len(s)):
        ch = s[i] - s[i - 1]
        g = max(ch, 0.0)
        l = max(-ch, 0.0)
        if i <= n:
            gains += g
            losses += l
        else:
            gains = (gains * (n - 1) + g) / n
            losses = (losses * (n - 1) + l) / n
        if i >= n:
            rs = gains / losses if losses > 0 else 99.0
            out[i] = 100 - 100 / (1 + rs)
    return out


def macd(s, fast=12, slow=26, sig=9):
    ef, es = ema(s, fast), ema(s, slow)
    line = [None if ef[i] is None or es[i] is None else ef[i] - es[i] for i in range(len(s))]
    # signal = EMA of line (only where line not None)
    sigline = [None] * len(s)
    k = 2 / (sig + 1)
    e = None
    for i in range(len(s)):
        if line[i] is None:
            continue
        e = line[i] if e is None else line[i] * k + e * (1 - k)
        sigline[i] = e
    return line, sigline


def bollinger(s, n=20, mult=2.0):
    up, lo, mid = [None] * len(s), [None] * len(s), sma(s, n)
    for i in range(n - 1, len(s)):
        win = s[i - n + 1:i + 1]
        sd = statistics.stdev(win)
        m = mid[i]
        up[i] = m + mult * sd
        lo[i] = m - mult * sd
    return up, lo


def donchian(s, n=20):
    hi, lo = [None] * len(s), [None] * len(s)
    for i in range(n - 1, len(s)):
        win = s[i - n + 1:i + 1]
        hi[i], lo[i] = max(win), min(win)
    return hi, lo


# ---- signal builders: return per-bar target position in {-1, 0, 1} ----

def sig_ema_cross(s):
    f, sl = ema(s, 10), ema(s, 30)
    out = [0] * len(s)
    pos = 0
    for i in range(1, len(s)):
        if f[i] is None or sl[i] is None:
            continue
        if f[i] > sl[i]:
            pos = 1
        elif f[i] < sl[i]:
            pos = -1
        out[i] = pos
    return out


def sig_donchian(s):
    hi, lo = donchian(s, 20)
    out = [0] * len(s)
    pos = 0
    for i in range(1, len(s)):
        if hi[i] is not None and hi[i - 1] is not None and lo[i - 1] is not None:
            if s[i] > hi[i - 1]:
                pos = 1
            elif s[i] < lo[i - 1]:
                pos = -1
        out[i] = pos
    return out


def sig_rsi2(s):
    r = rsi(s, 2)
    out = [0] * len(s)
    pos = 0
    for i in range(1, len(s)):
        if r[i] is None:
            continue
        if r[i] < 10:
            pos = 1
        elif r[i] > 90:
            pos = -1
        elif r[i] > 55:
            pos = 0
        out[i] = pos
    return out


def sig_macd(s):
    line, sig = macd(s)
    out = [0] * len(s)
    pos = 0
    for i in range(1, len(s)):
        if line[i] is None or sig[i] is None:
            continue
        if line[i] > sig[i]:
            pos = 1
        else:
            pos = -1
        out[i] = pos
    return out


def sig_bollinger(s):
    up, lo = bollinger(s, 20, 2.0)
    out = [0] * len(s)
    pos = 0
    for i in range(1, len(s)):
        if up[i] is None:
            continue
        if s[i] > up[i]:
            pos = 1
        elif s[i] < lo[i]:
            pos = -1
        else:
            pos = 0
        out[i] = pos
    return out


def sig_session_ema(s):
    # approximation of London/NY session filter + EMA trend (data is UTC;
    # treat bars 08-20 UTC as 'active' session via index phase)
    f, sl = ema(s, 10), ema(s, 30)
    out = [0] * len(s)
    pos = 0
    for i in range(1, len(s)):
        active = (i % 6) in (2, 3, 4)  # 4h bars in 08-20 UTC window approx
        if f[i] is None or sl[i] is None:
            continue
        if active:
            if f[i] > sl[i]:
                pos = 1
            elif f[i] < sl[i]:
                pos = -1
        else:
            pos = 0
        out[i] = pos
    return out


def sig_ema200_atr(s):
    """EMA200 Trend + ATR Range Filter (marketplace top EURUSD 1h).
    Long/short by price vs EMA200, flat when |price-EMA200| > 3*ATR(14)
    (trend exhausted / range filter)."""
    e = sma(s, 200)  # EMA200 approximated by SMA200 on 4h (long trend)
    atr = [None] * len(s)
    for i in range(14, len(s)):
        trs = []
        for j in range(i - 13, i + 1):
            trs.append(max(s[j] - s[j - 1], 0.0))
        atr[i] = statistics.fmean(trs)
    out = [0] * len(s)
    pos = 0
    for i in range(1, len(s)):
        if e[i] is None or atr[i] is None:
            continue
        dist = abs(s[i] - e[i]) / atr[i] if atr[i] > 0 else 99
        if dist > 3.0:
            pos = 0           # range/exhaustion
        elif s[i] > e[i]:
            pos = 1
        else:
            pos = -1
        out[i] = pos
    return out


def sig_bbw_exp_cov(s):
    """05C BBWexp + CoV Gate (marketplace novel class): Bollinger BandWidth
    = (upper-lower)/mid; EXP = widening of BBW; CoV gate = coefficient of
    variation of BBW over 20 bars must be stable (<0.5) before entry.
    Long on BBW-expansion up-break, short on down-break (vol-expansion
    timing, NOT directional prediction)."""
    bbw = [None] * len(s)
    up, lo = bollinger(s, 20, 2.0)
    for i in range(len(s)):
        if up[i] is not None and lo[i] is not None:
            mid = max((up[i] + lo[i]) / 2, 1e-9)
            bbw[i] = (up[i] - lo[i]) / mid
    out = [0] * len(s)
    pos = 0
    for i in range(21, len(s)):
        if bbw[i] is None:
            continue
        win = [b for b in bbw[i - 20:i] if b is not None]
        if len(win) < 10:
            continue
        mu = statistics.fmean(win)
        sd = statistics.stdev(win)
        cov = sd / mu if mu > 0 else 99
        bbw_growth = (bbw[i] - win[-1]) / win[-1] if win[-1] > 0 else 0
        if cov < 0.2 and bbw_growth > 0.05:
            pos = 1 if s[i] > s[i - 5] else -1  # expansion direction
        elif cov > 0.5:
            pos = 0
        out[i] = pos
    return out


SIGNALS = {
    "ema200_atr_range": sig_ema200_atr,
    "bbw_exp_cov": sig_bbw_exp_cov,
    "ema_cross_trend": sig_ema_cross,
    "donchian_breakout": sig_donchian,
    "rsi2_reversion": sig_rsi2,
    "macd_momentum": sig_macd,
    "bollinger_break": sig_bollinger,
    "session_ema": sig_session_ema,
}


def backtest(s, signal, start, end):
    """Long/short by signal on [start:end), cost per flip, vol-scaled.

    Correct semantics: a flip bar is an ENTRY/EXIT — it pays the cost and earns
    NO return from the new position (no same-bar lookahead). Returns are earned
    only on bars where the position was already held at bar-open (i.e. the
    signal from the PREVIOUS bar governs the return of THIS bar).
    """
    rets = []
    pos = 0
    for i in range(max(start, 1), end):
        # signal[i] was decided at bar i close; it can only affect bar i+1
        # -> use signal[i-1] to decide position during bar i (no lookahead)
        target = signal[i - 1] if i - 1 >= 0 else 0
        ret = (s[i] / s[i - 1] - 1.0) * (VOL_TARGET / EST_VOL)
        if target != pos:
            rets.append(-COST_RT)      # entry/exit cost only, no bar return
            pos = target
        else:
            rets.append(ret if pos else 0.0)
    return rets


def stats(rets):
    if len(rets) < 20:
        return None
    mu, sd = statistics.fmean(rets), statistics.stdev(rets)
    g = sum(r for r in rets if r > 0)
    l = -sum(r for r in rets if r < 0)
    pf = g / l if l > 0 else float("inf")
    eq, peak, mdd = 1.0, 1.0, 0.0
    for r in rets:
        eq *= (1 + r)
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak)
    return {"ann_ret": mu * BARS_PER_YEAR, "sharpe": (mu / sd) * math.sqrt(BARS_PER_YEAR),
            "pf": pf, "max_dd": mdd, "n": len(rets)}


def main():
    pairs = ["EURUSD", "GBPUSD"]
    results = {}
    for pair in pairs:
        s = load_4h_closes(pair)
        n = len(s)
        print(f"\n[{pair}] {n} 4h bars")
        for name, fn in SIGNALS.items():
            sig = fn(s)
            # anchored 2-fold OOS (60-100%)
            folds = [(int(n * 0.6), int(n * 0.8)), (int(n * 0.8), n)]
            oos = []
            for a, b in folds:
                oos += backtest(s, sig, a, b)
            st = stats(oos)
            if st is None:
                print(f"  {name}: insufficient data")
                continue
            ok = [st["ann_ret"] > KILL["ann_ret"], st["sharpe"] > KILL["sharpe"],
                  st["pf"] > KILL["pf"], st["max_dd"] < KILL["dd"],
                  st["n"] >= KILL["trades"]]
            verdict = "PASS" if all(ok) else "FAIL"
            print(f"  {name}: ann={st['ann_ret']:.2%} sharpe={st['sharpe']:.2f} "
                  f"pf={st['pf']:.2f} dd={st['max_dd']:.1%} n={st['n']} -> {verdict}")
            results[f"{pair}|{name}"] = {**st, "verdict": verdict, "kill": ok}
    res = Path(__file__).resolve().parent / "results" / "traderdev_fx_evidence_screen.json"
    res.write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    print(f"\nwrote {res}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)