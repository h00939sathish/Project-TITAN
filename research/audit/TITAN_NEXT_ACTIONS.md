# TITAN NEXT ACTIONS

**Date:** 2026-09-29. *The smallest set of changes producing the largest verified improvement.*

**This is not a 100-task roadmap. It is 8 items, 6 of which are deletions or one-line gates.**

## The governing constraint

> TITAN's problem is not capability. It has a good kernel, 27k LOC, 34 ADRs and 1180 tests.
> Its problem is that a screen executes **one trade per hypothesis**, FX is costed at
> **20 pips**, `replicated` is hard-wired `False` so **zero survivors is a constant**, Sharpe
> uses `sqrt(252)` on **4-hour bars**, Bonferroni is computed and **discarded**, and
> `walk_forward()` **does not train**.

**Therefore: nothing new gets built until the instrument is repaired and has produced one
trustworthy result.** Everything below is repair, deletion, or measurement.

---

# FIX NOW

## 1. Delete `tests/conftest.py:76-85` · 1 hour · **DO THIS FIRST**

| | |
|---|---|
| **Why now** | It is the single cause of 1180 green tests over a runtime that dies on its first signal |
| **Problem addressed** | Total operational blindness |
| **Effect** | The suite goes red at the exact production failure. That redness is correct and must stay until fixed |
| **Dependencies** | None |
| **Cost** | 1 hour |
| **Risk** | High noise on day 1. That is the point |
| **Test** | `pytest tests/` fails on `test_execution_integrity` or equivalent, naming the certificate gate |
| **Success** | The suite is red for one reason only, and that reason is a real production bug |
| **Rollback** | `git revert` — but do not |

Keep the existing exemption for `test_execution_integrity` / `e2e` / `adversarial`. Make it the
*only* exemption.

## 2. Fix the certificate + session crash · 1 day

`bridge.py:34` `certificate_ref = "dummy_cert_for_paper_session"` → `engine.py:890`
`json.loads()` → raise at `:895`; `paper_session.py:914` has **no `try/except`**.

| | |
|---|---|
| **Problem addressed** | Zero orders have ever been placed. Zero operational evidence exists |
| **Effect** | The paper session runs. **For the first time, TITAN produces operational data** |
| **Dependencies** | #1 |
| **Cost** | 1 day: make `certificate_ref` required (or mint a real cert via `create_signed_certificate`); wrap `submit_intent` in `try/except` |
| **Risk** | Low. Fail-closed defaults are intact |
| **Test** | Run `scripts/init_session.py` then `scripts/paper_session.py` during RTH; observe ≥1 accepted intent and ≥1 fill |
| **Success** | One order, in the event log, reconciled against the broker |
| **Rollback** | Revert; the session reverts to not-trading, which is the status quo |

Also in the same day: `cli.py:127` (drop `store_was_empty=`), `paper_session.py:861` (call
`engine.update_price()` so the correlation rule can fire), `engine.py:1086` (env-sourced HMAC
secret), `engine.py:1607` (pass `authorized_approvers`).

## 3. Fix the four measurement defects that voided the evidence base · 2 days

| Fix | Location | Current | Target |
|---|---|---|---|
| Allow exits | `scripts/screening/screen.py:40-61` | **1 trade per hypothesis** | N trades |
| Add a short branch | `harness.py:99-151` | long-only | two-sided |
| One PnL record per round trip | `harness.py:135-147` | **2× PnL, 2× trade count, 2×-inflated bootstrap CIs** | correct |
| `periods_per_year` argument | `results.py:100`, `metrics.py:153` | hard-coded `sqrt(252)` | caller-supplied |
| Record real `n_trades` | `traderdev_fx_screen.py:338` | reports **bars** (644) | trades |

| | |
|---|---|
| **Problem addressed** | The `0/15 concepts` row is void; EXP-00031 "reproduction" tested a different strategy; every Sharpe in the archive has an unknown annualization |
| **Effect** | Screens become capable of producing a measurement at all |
| **Cost** | 2 days, ~150 LOC |
| **Risk** | Low. These are localised |
| **Test** | The one hand-computed fixture from #4 + a symmetric-input strategy test |
| **Success** | A screen over 1,610 4h bars returns >50 trades with net PnL within 1% of an independent recomputation |

## 4. One hand-computed fixture + one strategy invariant · 1 day · **highest ratio in the plan**

```python
# tests/backtest/test_known_series.py
def test_known_return_series():
    # 253 daily returns: +0.1% every day
    eq = [100 * 1.001**i for i in range(254)]
    r = BacktestResult.compute(eq, trades=[{"pnl": 1.0}] * 253)
    assert r.sharpe_ratio == pytest.approx(0.1 / 0.0 * 252**0.5)  # exact value
    assert r.max_drawdown_pct == 0.0
    assert r.profit_factor == 100.0        # pinned, so M18 can never survive
    assert r.volatility_annual_pct == pytest.approx(0.0)

def test_strategy_can_short():
    # every registered strategy, symmetric input, must produce both BUY and SELL
```

| | |
|---|---|
| **Problem addressed** | Mutation testing: `abs()` on Sharpe, `profit_factor = 100.0`, inverted drawdown, `sqrt(252)`→`sqrt(12)`, and `dual_ma` hardcoded long-only **all survive today** |
| **Effect** | Kills 5 of the 6 surviving mutants. Makes the promotion gate's inputs falsifiable |
| **Cost** | 1 day, **~50 LOC** |
| **Risk** | It will fail on first run — the metrics are wrong. That is the discovery |
| **Test** | It is the test |
| **Success** | 12 of 12 mutants killed |
| **Rollback** | None needed |

**Then add `import-linter` to block `execution/` → `research/` (`engine.py:48`).**

## 5. Vendor the statistics layer · 1 day · **an import, not a build**

`HKUDS/Vibe-Trading/agent/src/quantlib/` — DSR, PSR, E[max N], BH-FDR, PBO, purged/group-purged/
walk-forward/CPCV, `detect_boundary_leakage`, with a 336-line leakage test suite.
Alternative: `vectorbt/returns/metrics.py:19 deflated_sharpe_ratio` — ⚠️ read open PRs
**#872 (kurtosis convention)** and **#873 (expanding minp)** first; getting kurtosis wrong
silently inflates DSR.

| | |
|---|---|
| **Problem addressed** | **Zero** statistical validation exists, though `RESEARCH_PROTOCOL.md:47` requires Monte Carlo. 546 trials at α=0.05 vs the correct 9.2×10⁻⁵ |
| **Effect** | DSR becomes the reported statistic. Multiple-testing exposure becomes visible |
| **Cost** | 1 day (vendor + licence check + wire into the gate) |
| **Risk** | Medium — licence. Verify before vendoring |
| **Test** | The vendored 336-line leakage suite must pass unmodified |
| **Success** | Every new experiment reports DSR and PBO, plus **N** |

## 6. Add the `UNDERPOWERED` verdict · 2 hours · **highest information-per-line change in the repo**

```python
se_sharpe = sqrt((1 + 0.5 * sharpe**2) / T_years)     # Lo (2002)
if se_sharpe > 0.5:
    verdict = "UNDERPOWERED"      # not "negative_result"
```

| | |
|---|---|
| **Problem addressed** | 17 of 21 results are *unmeasured*, not refuted. EQ-007 (SR 1.249), EQ-002-core7 (SR 0.486), EXP-00025 F1 (SR 0.80) were all rejected on windows where SE(SR) ≈ 0.7–1.6 |
| **Effect** | The ledger stops lying. EXP-00031, EXP-00027, EQ-001/003/006/007/008 and the whole FX 4h axis are correctly reclassified |
| **Cost** | **2 hours** |
| **Risk** | Will invalidate the headline "0/40". **That is the point** |
| **Test** | A synthetic SE=1.56 result must return `UNDERPOWERED` |
| **Success** | No experiment can be recorded as `negative_result` while `SE(SR_ann) > 0.5` |
| **Rollback** | Trivial — one branch |

## 7. One sourced cost schedule · 1 day

| Instrument | Round turn | Source |
|---|---|---|
| EURUSD, GBPUSD (raw/ECN) | **0.8–1.5 pips** | Dukascopy tick mean 0.18 pips (lower bound) + FX-Brokers.info 2026 (Exness Raw $8.65/lot) |
| EURUSD, GBPUSD (CFD) | **1.5–2.5 pips** | UltimateBrokerList Q1 2026 ($6–$18 / 24h RT) |
| Slippage | 0.3 median / 1.0–1.5 p95 | UltimateBrokerList |
| Overnight swap | 0.55–0.98 pip-equiv/night | −$5.50 to −$9.80 / std lot |
| G10 basket | **2 bp/rebalance** | not 10 bps |
| XAUUSD | 2–5 bp RT | Dukascopy-measured median $0.32 |

**Label every figure measured vs. assumed**, exactly as
`Vibe-Trading/forex.py:37` does. **Require survival at 4× the base cost.** Research and
`promotion.py` must consume the *same* schedule.

| | |
|---|---|
| **Problem addressed** | 0.9 bp vs 20 bp for the same instrument in the same month. **Killed EXP-00022 — the only t=2.67 result in the archive** |
| **Cost** | 1 day |
| **Test** | EXP-00022 at 1, 2 and 10 bps must produce three *different* answers |
| **Success** | No cost constant exists outside one module |

## 8. Restore the datasets · zero cost

`research/dukascopy_1m_ba/` (gitignored `.gitignore:101`) is referenced by **7 scripts**.
`research/crypto/data/` (`:143`) and `research/equities/data/` are also absent.
`scripts/pull_dukascopy_1m.py` and `convert_dukascopy.py` already exist; **Dukascopy data is free.**

| | |
|---|---|
| **Problem addressed** | **Every FX number in the terminal report is currently unverifiable and un-rerunnable** |
| **Effect** | 7 experiments go from *unverifiable* to *rerunnable* |
| **Cost** | **Zero** (gitignore line + a download) |
| **Risk** | Storage. Nothing else |
| **Success** | `python screen.py` runs end to end and reproduces the committed artifact |

**The best cost-to-information ratio in the entire audit.**

---

# RESEARCH NEXT

## 9. Re-run EXP-00022 and the 15 concepts · 3 days · **the experiment that most reduces uncertainty**

**Run after #3, #4, #6, #7, #8. Parameters, data and windows unchanged** — the instrument is
being repaired, not the strategy re-picked.

```bash
python scripts/pull_dukascopy_1m.py && python scripts/convert_dukascopy.py
python scripts/screening/screen.py                    # 15 concepts, now with N trades
python research/run_exp22_xs_momentum.py               # 1 bp / 2 bp / 10 bp
python research/run_exp23_carry.py                     # 1 bp/leg, with swap
```

**Report DSR and PBO, not raw Sharpe. Record N. Reject anything with SE(SR) > 0.5 as
UNDERPOWERED.**

### Prediction, recorded in advance (falsifiable)

| | |
|---|---|
| **EXP-00022 at 1–2 bps** | gross +5.4%/yr, σ≈9%/yr, t=2.67, n=412, 8y ⇒ **net +4.4 to +4.9%/yr, Sharpe 0.48–0.54** vs a 0.45 hurdle |
| **If it holds** | FX cross-sectional momentum was real and was killed by a units error. **The FX program is re-opened** |
| **If it fails** | The negative result stands on a *correct* instrument, and the class may legitimately close |

**Either outcome is a large reduction in uncertainty. That is what makes this the right first
experiment** — and it is why it must be run *after* the instrument is fixed, not before.

## 9b. Re-run F1_ema9_vwap @ 4h with a real significance test · 2 days · **highest-prior candidate**

Found in the second adversarial pass from TITAN's own committed artifact. See
`TITAN_PROFITABILITY_FORENSICS.md` §1b.

**F1_ema9_vwap at 4h is the only cell in the archive that is positive on EURUSD (+71.8 pips /
84 trades) and GBPUSD (+336.5 pips / 79 trades) simultaneously, in a frame where all twelve 1h
cells are negative.** It was modelled with the **correct** cost schedule
(`run_traderdev_families.py:23-24` = 0.9 bp RT).

It was then closed by **EXP-00031** — a "canonical reproduction" that used a **long-only**
harness, `trail_mult = 3.0` instead of `2.0 × ATR(14)`, a different fee schedule, and produced
54 trade records where the original produced 163. **That is not a test; it is a different
strategy wearing the same name.**

| | |
|---|---|
| **Why now** | It is the only result that is positive, positive on two independent pairs, frame-dependently so, and correctly costed |
| **Problem addressed** | A real candidate was closed by a non-comparable artifact |
| **Effect** | Either a genuine candidate is recovered, or it is correctly refuted with a valid test |
| **Dependencies** | #3, #4, #6, #7, #8 |
| **Cost** | 2 days |
| **Risk** | Low. Nothing else depends on it |
| **Test** | Emit `pnl_list` so per-trade t is **measured, not estimated from trailing geometry**; report DSR and PBO; extend to 3+ years if data allows |
| **Success criteria** | DSR > 0.95 **and** t > 2.0 on the pooled per-trade series, at 4× cost |
| **Rollback** | None. It is a research run |

**Current status: t ≈ 0.46–1.28 (not significant), Lo 95% CI [−1.45, +3.05].** One year of 4h FX
cannot resolve a Sharpe below ~1.15. Extending the window is the only thing that will settle it.

## 10. Significance-test EQ-002-core7 · 1 day

It carries `"verdict": "candidate"` and is **not counted** in the 0/40. IS Sharpe **−0.0296**,
OOS +0.4858, rank IC 0.1817 over 24 obs in 7 names (t≈1.78, p≈0.09). It is probably noise — but
it was **never tested for significance**, which is the finding.

**Reconcile the two gate sets** for the same hypothesis ID (`equities_factor_screen_006.py:391-401`
vs `run_eq002_core7.py:165-172`).

## 11. Re-open EQ-007 (PEAD) with turnover as a sizing variable · 3 days

TITAN's best artifact: OOS Sharpe **1.249**, DD 10.1%, monotonic quantiles, positive
adverse-cost result. Rejected on a **coin-flip gate** (`rank_ic_fraction`:
`P(≥15/24 | true 0.70) = 0.847`) and a **post-hoc tightened** criterion (EQ-008's own prereg
records that EQ-007 *"showed massive economic edge"*).

Requires: earnings calendar + adjusted prices (**no data contract exists**), and ≥60 names ×
15 years (13 ETFs × 2y cannot support cross-sectional inference). **Per
`PIVOT_DECISION.md:24-27`, acquire the data BEFORE the backtest.**

---

# BUILD LATER

| # | Item | Trigger |
|---|---|---|
| 12 | Consolidate 6 simulators → 1; 6 cost models → 1; 5 drawdown copies → 1 | After #3. **This is the fix for C8/C9/C11/C12, not a cleanup** |
| 13 | Split `engine.py` (1,752 lines) on existing boundaries | After the runtime is stable |
| 14 | Risk layer inside the backtest (constrained vs unconstrained) | After a second strategy exists |
| 15 | Portfolio construction (HRP, rebalancing, covariance) | After **two** strategies survive |
| 16 | Tick/L2 + order flow (Osler: stops = 5–10% of FX deal flow) | Only if the microstructure program is actually funded — **budget, not economics, is why it was skipped** |
| 17 | Real `correlation_id` propagation | **Or delete the subsystem** and amend `PROJECT_TITAN.md:52` |
| 18 | `ruff` in CI (already installed, 1,593 violations); coverage floor; monthly mutation run | Immediately after the above — 1 day |

---

# DO NOT BUILD

**Each of these was considered and rejected on evidence.**

| Do not build | Why |
|---|---|
| **Any new strategy or market** | 546 trials have already been run against an instrument that trades once and costs FX at 20 pips. Another hypothesis produces another uninterpretable number |
| **Reinforcement learning** | No data pipeline, no statistics layer, no running runtime, no surviving strategy. FinRL is classical RL (ElegantRL/TD3/SB3/RLlib), not what the name implies |
| **LLM trading agents** | `TauricResearch/TradingAgents`: 109,163★ / **~24 contributors**, its "backtest" is a rating sweep with **no portfolio, no positions, no cash ledger**. `ai-hedge-fund`: ~15k LOC behind 63,789★. **Not one has walk-forward, Monte Carlo, a risk engine, or reconciliation** |
| **A bigger LLM** | AI is 0.6% of LOC and entirely dead. It is not a bottleneck in either direction |
| **More data volume** | Not the problem. 20-pip costs and `sqrt(252)` on 4h bars are the problem |
| **More Rust** | The Rust that exists is the best code in the repo and is mutation-proof. Every defect is in Python |
| **More infrastructure** | 2.4% of LOC. Not the bottleneck |
| **New ADRs** | 34 exist; CI enforces only their formatting. An ADR with no executable check is a comment |
| **A dashboard / UI** | Zero orders placed. There is nothing to display |
| **Microservices, message bus, CQRS** | `PROJECT_TITAN.md:40` already got this right. Resist |
| **Vector memory / embeddings** | 172 LOC, `embedding_vector` populated nowhere. **Delete**, do not build |
| **New broker adapters** | Fincept is a stub and 3 adapters already exist unexercised |

---

# THE STOP CONDITION

> **Do not begin item 9, or any research, until items 1–8 are done and the suite is green
> for the right reasons.**

**Re-audit trigger:** when the corrected EXP-00022 and the re-run 15 concepts produce results,
re-open `TITAN_MASTER_AUDIT.md` and check whether the central claim survives. **If two
consecutive passes produce no new high-confidence findings, the audit is complete.**

---

# SUMMARY

| | Items | Cost | Effect |
|---|---|---|---|
| **FIX NOW** | 8 | **~8 days** | The suite stops lying; the runtime starts; the harness can measure; the ledger stops manufacturing zeros |
| **RESEARCH NEXT** | 3 | ~1 week | One trustworthy answer on whether FX momentum is real |
| **BUILD LATER** | 7 | weeks | Correctness of the *system*, in order |
| **DO NOT BUILD** | 12 | — | Roughly a year of work not spent |

**Eight days. Six of them are deletions or one-line gates. The output is not a bigger TITAN —
it is a TITAN whose "no" means something.**
