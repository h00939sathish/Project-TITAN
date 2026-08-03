# Reproduction & Adversarial Review Checklist

> **Date:** 2026-07-13
> **Subject experiment:** ma-crossover-baseline-001 (MA(5,20) on SPY, 2020-01-02 to 2020-03-05)

---

## 1. Is the strategy just overfitting to the train period?

**Check:** Out-of-sample performance vs in-sample.

| Sample | Sharpe | Return |
|---|---|---|
| Full (all 46 bars) | -2.54 | -0.15% |
| Walk-forward window 1 (bars 0-29) | 2.03 | (OOS) |
| Walk-forward window 2 (bars 10-39) | 2.03 | (OOS) |

With only 46 bars of data (2 trades), we cannot meaningfully assess overfitting. Need >3 years of daily data (>750 bars, >50 trades) for a credible assessment.

**Verdict:** ⚠️ Inconclusive — insufficient data.

---

## 2. Does it work on other instruments?

**Check:** Run on QQQ, IWM.

No other instrument data is currently available in the test fixtures. The strategy framework is instrument-agnostic, so parameter binding to other instruments is straightforward.

**Verdict:** ❌ Not tested. Documented gap. Recommend adding QQQ and IWM to the sample data.

---

## 3. Does parameter sensitivity kill it?

**Check:** Perturbation grid (±1 on fast and slow periods).

| Variant | Return | Sharpe | Max DD |
|---|---|---|---|
| Baseline (5,20) | -0.15% | -2.54 | 0.17% |
| (4,20) | -0.15% | -2.49 | 0.17% |
| (6,20) | -0.15% | -2.54 | 0.17% |
| (5,19) | -0.15% | -2.54 | 0.17% |
| (5,21) | -0.13% | -2.17 | 0.17% |

All variants produce near-identical results (expected — on this short window all entries/exits happen at the same times). Need more data to see divergence.

**Verdict:** ⚠️ Inconclusive — insufficient data to assess parameter sensitivity.

---

## 4. Would it survive trading costs at scale?

**Check:** Fee stress test (0.5x, 1x, 2x, 5x slippage).

| Multiplier | Return | Sharpe |
|---|---|---|
| 0.5x | -0.15% | -2.54 |
| 1x | -0.15% | -2.54 |
| 2x | -0.15% | -2.54 |
| 5x | -0.15% | -2.55 |

Negligible sensitivity to trading costs — the strategy trades so infrequently (2 trades) that fees are a tiny fraction of PnL.

**Verdict:** ✅ Survives. But low trade count means this test is weak.

---

## 5. Is there a simpler explanation?

**Check:** Buy-and-hold comparison.

| Metric | MA(5,20) | Buy-and-hold |
|---|---|---|
| Return | -0.15% | -4.95% |
| Max DD | 0.17% | 4.95% |

The strategy lost less than buy-and-hold during the COVID crash onset. However, both lost money. The most parsimonious explanation is that the strategy happened to be lightly invested during the drawdown (coincidence on 46 bars). A trend strategy that enters at the highs and barely trades cannot claim skill from 2 trades.

**Verdict:** ⚠️ Plausible simpler explanation exists (chance + insufficient data).

---

## 6. Is the data clean?

**Check:** Point-in-time data tests.

Three of six point-in-time tests pass (look-ahead, stale data, vendor corrections). Three are documented gaps (survivorship bias, missing sessions, corporate actions). No data-quality bugs were found in the positive tests.

**Verdict:** ✅ Data pipeline has known, documented gaps but no observed defects in current scope.

---

## 7. Are results driven by a few outlier days?

**Check:** Tail loss, distribution of returns.

- Tail loss (5th percentile daily return): -0.02%
- Volatility (annualized): 0.33%
- Only 2 trades, both small losers — zero winning trades

On 46 bars with 2 trades, there are no outlier-driven results. The losses are small and consistent.

**Verdict:** ✅ Not outlier-driven (insufficient trading activity for outliers).

---

## Overall Verdict

| # | Question | Verdict |
|---|---|---|
| 1 | Overfitting? | ⚠️ Inconclusive |
| 2 | Other instruments? | ❌ Not tested |
| 3 | Parameter sensitivity? | ⚠️ Inconclusive |
| 4 | Costs at scale? | ✅ Survives |
| 5 | Simpler explanation? | ⚠️ Possible |
| 6 | Data clean? | ✅ Known gaps, no defects |
| 7 | Outlier-driven? | ✅ No |

**Overall:** The baseline experiment cannot be validated or invalidated on 46 bars with 2 trades. The pipeline produces deterministic, reproducible results. The adversarial review reveals that the primary threat to research validity is **insufficient data, not flawed methodology.**

**Recommendation:** The validation pipeline is ready for real data (3+ years of daily bars). Do not accept or reject the hypothesis yet — retain as "inconclusive" until run on adequate data.
