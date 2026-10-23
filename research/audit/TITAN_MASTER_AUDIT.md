# TITAN MASTER AUDIT — Hostile Institutional Review

**Date:** 2026-09-29
**Method:** Full source inspection, mutation testing, execution-path tracing, evidence-base forensics, live GitHub research (curl of repo HTML + commit/release Atom feeds + source tarball parsing).
**Verification:** Every load-bearing claim below was re-verified independently by the auditor, not taken from a subagent or a document.

> **THE HEADLINE:** TITAN's central claim — "~40 experiments, 0 survivors, therefore
> liquid OHLCV directional alpha does not exist" — **is not supported by the evidence.**
> At least five independent, individually sufficient defects make the "0" an artifact of
> the instrument, not a measurement of the market. One third of the evidence base ran
> **exactly one trade per hypothesis**. A second defect makes "0 survivors"
> **arithmetically guaranteed** for every equities and crypto screen. A third applied a
> **10–100× overstated FX cost constant** to the studies that produced negatives. The
> dataset for the entire FX axis **does not exist on disk**, so none of it is reproducible.
>
> **And the terminal report closed a live candidate without testing it.** TITAN's own memo
> (`research/neg_results/EXP-00025_traderdev_families.md`) records
> *"F1_ema9_vwap 4h pooled +408.3 pips (84+79 trades) — NET POSITIVE… **Decision: F1_ema9_vwap
> @4h is a CANDIDATE**"*, and the results file shows **4 of 24 cells net positive, all four at
> 4h, zero of twelve at 1h**. It is not statistically significant (t ≈ 0.46–1.28, Lo 95% CI
> [−1.45, +3.05]) and must not be treated as an edge. But the report closed it with EXP-00031 —
> a long-only, differently-parameterised "reproduction" producing 54 records where the original
> produced 163 — rather than with a significance test. **A candidate was killed by a
> non-comparable artifact.**

Separately and independently: **the paper-trading runtime cannot place a single order.** It
raises on the first signal, and the 1180-test suite is green only because a global
`conftest.py` fixture monkeypatches away the exact gate it hits.

---

## 1. WHAT IS TITAN TODAY?

A well-built, honest, **economically empty** trading research platform.

- **It is:** ~27k LOC Python + 4.1k LOC Rust. A real event store, a real 11-rule Rust risk
  gate, a real `rust_decimal` portfolio ledger, a real order state machine, a real
  reconciliation engine, real IBKR and Alpaca adapters, 1180 passing tests, 34 ADRs.
- **It is not:** a system with a demonstrated edge, a running paper-trading loop, a
  statistically competent research harness, or a reproducible evidence base.
- **Its demonstrated accomplishment is negative results — but the negative results are
  not sound.** The culture is rigorous; the instrumentation is not.

**Classification per subsystem (traced, not documented):**

| Layer | Architecture | Implemented | Tested | Operationally verified | Economically useful |
|---|---|---|---|---|---|
| Rust core (risk, portfolio, orders, event store, recon) | Sound | **Yes** | **Yes (92 `#[test]`)** | No | n/a (correct plumbing) |
| Execution engine (Python) | Over-complex | Yes | Yes | **NO — crashes on first signal** | No |
| Broker adapters (IBKR/Alpaca/Sim) | Sound | Yes | Yes | Unverified | No |
| Fincept adapter | n/a | **Stub** | n/a | No | No |
| Research harness (`harness.py`) | **Broken** | Yes, wrongly | **No** | No | **No** |
| Research metrics / Sharpe | **Broken** | Yes, wrongly | **No** | No | **No** |
| Research screens (equities/crypto) | **Broken by construction** | Yes | Yes (of the bug) | No | **No** |
| Paper session runner | **Broken** | Yes | **No (bypassed)** | **No** | No |
| Strategy signals | Minimal | Yes | **No (mutation-survived)** | No | No |
| AI / memory / MCP | **Dead** | 172 LOC, no LLM call | Yes | No | No |
| Data pipeline | Sound | Yes | Yes | Partial; **core datasets absent** | No |
| Walk-forward ("walk_forward") | **Fake** | **No** | Yes | No | No |
| Monte Carlo | **Absent entirely** | **No** | No | No | No |
| Risk / portfolio | Sound | Yes | **Yes — genuinely good** | No | No |

---

## 2. WHAT WAS TITAN SUPPOSED TO BECOME?

From `PROJECT_TITAN.md:50-52`:

> "TITAN is successful when a senior engineer can trace every live action from source
> event through deterministic risk decision and broker acknowledgement; reproduce its
> validation; detect and reconcile divergence; halt safely..."

**Every clause of that definition is currently unmet:**
- *Trace every live action* — no action is ever placed.
- *Reproduce its validation* — the FX dataset is absent; the artifacts are truncated.
- *Detect and reconcile divergence* — 15 of 25 Prometheus metrics are never written;
  the health check reads an always-zero counter and reports "Broker truth matches: YES".

---

## 3. WHERE DID THE PROJECT DEVIATE?

Deviation was **not** toward too little infrastructure. It was toward *infrastructure and
process in place of measurement*.

| Evidence | Number |
|---|---|
| Governance/speculation docs | **~14,500 LOC** across ~140 files |
| 34 ADRs | 1 per ~5 source files |
| Test suite | 1180 tests, **0 of which** catch a broken Sharpe |
| **Monte Carlo** | **0 implementations, anywhere** — required by `docs/reference/RESEARCH_PROTOCOL.md:47` |
| Rust `#[test]` functions | **92**, none reachable from pytest |
| Core research datasets on disk | **0 of 3** (dukascopy, crypto, equities — all gitignored) |

`AGENTS.md`, `OPERATING_PRINCIPLES.md`, `AI_GOVERNANCE.md`, 34 ADRs, 23 specifications,
and a `check_adr_gate.py` that CI runs — this gates **document formatting, not behavior**.
Meanwhile `ruff` is installed and **never invoked** (1,593 violations), and `mypy --strict`
is `continue-on-error: true`; `tests/test_ci_workflow.py:47-56` *actively asserts mypy stays
non-blocking*. Commit `698cd7b` reveals the workflow triggered only on a branch named `main`
that **does not exist** — **CI never ran** until that fix. Four commits landed ungated.

---

## 4. WHAT DOES TITAN DO BEST? → `TITAN_PRESERVE.md`

1. **The Rust core.** `core/src/risk.rs:273`, `portfolio.rs:103`, `orders.rs:74`,
   `reconciliation.rs:131`, `event_store.rs:25`. `rust_decimal` for money, WAL SQLite,
   a 20-edge order state machine. Mutation testing **could not break it** — a full
   realized-PnL sign-flip across the suite failed **35 tests**. This is the single
   best-engineered asset in the repo.
2. **Fail-closed defaults.** `risk.rs:450 load_or_default` → Triggered/Halted on an
   empty store. Verified empirically. Correct.
3. **Circuit breakers are genuinely wired** — `engine.py:996/1131/1171`. Mutation M16
   (bypassing the risk gate) and M12 (10× looser limits) were both **killed**.
4. **The honesty of the negative-results culture**, and `exp17_2fold_retest.py`'s
   self-diagnosis: *"The original EXP-17 'temporal' thirds were same-window
   sub-periods, NOT out-of-sample — so the effect was never OOS-validated before
   promotion."* That is the most valuable sentence in the archive.

---

## 5. WHAT IS ACTUALLY BROKEN? → `BUG_AND_RELIABILITY_REPORT.md`

**Confirmed by direct auditor reproduction:**

| # | Defect | Location | Impact |
|---|---|---|---|
| **B1** | Screen never exits a position → **1 trade per hypothesis** | `scripts/screening/screen.py:40-61` | **The "0/15 concepts" evidence is void.** `results.json` shows `trades: 1` in every cell |
| **B2** | `replicated` defaults `False`, never `True` in prod | 6 screen modules | **"0 survivors" is guaranteed.** CRYPTO-001 passed 4/5 gates and was filed as a failure |
| **B3** | Failed gates stored as message strings; detector tests for a `"❌"` that never appears | `validator.py:265` + `:376` | EXP-00017 and EXP-00019 both recorded `"decision": "promote"` **with failing gates** |
| **B4** | `cost_bps = 10.0` — 10 bps ≠ "1 pip" | 4 scripts; `run_fx_experiments.py:10` | 10–100× overstated. Kills EXP-00022 (**t = 2.67 over 8 years**) at exactly 0.00% net |
| **B5** | `harness.py` is **long-only**; no short branch | `harness.py:99-151` | Every short signal discarded. The "canonical reproduction" EXP-00031 tested a different strategy |
| **B6** | PnL written to entry record **and** a new record | `harness.py:135-147` | 2× PnL, 2× trade count, **2×-inflated bootstrap CIs** → under-powered results look *more* significant |
| **B7** | `walk_forward()` does no training, no test partition | `harness.py:383-412` | Exported as `walk_forward.mean_sharpe` — a key any reader takes for OOS |
| **B8** | Sharpe hard-codes `sqrt(252)` on per-**bar** returns | `results.py:100`, `metrics.py:153` | 4h FX Sharpe understated 3.0×; 5m overstated 11.6×. Untraceable from artifacts |
| **B9** | `profit_factor = 100.0` when `gross_loss < 0.01` | `results.py:62` | Perfect score for any strategy with no losing trades |
| **B9b** | The promotion gate **directly consumes** the mutation-survivable fields | `promotion.py:488,494-495` reads `baseline.sharpe_ratio` / `with_candidate.sharpe_ratio` | Confirms the chain: a field that can be `abs()`'d without failing a test **feeds the live-promotion decision** |
| **B10** | Same-bar lookahead: enter at bar *i* close, collect bar *i*'s return | `p2_gold_macro_momentum.py:118-124` | P2 is the one result this *flatters* — so its FAIL survives |
| **B11** | Power gate checked against **bar count**, not trades | `traderdev_fx_screen.py:361` | All 16 cells report `n = 644` bars. The gate never bound |
| **B12** | Cumulative-since-entry returns appended per bar, then annualized | `p4_multi_tf_confluence.py:139` | Committed artifact reports **Sharpe 19.25 and 21.13** on 4h FX. The bootstrap "decisive test" pairs misaligned series |
| **B13** | Bonferroni α computed, written to a string, **never used** | `validator.py:271` | 546 trials evaluated at α=0.05 instead of 9.2×10⁻⁵ |
| **B14** | Prereg thresholds non-binding — code invents missing keys | `equities_factor_screen_006.py:384-389` | Imposes Sharpe≥1.0, IC-frac≥0.70, DD≤12% that appear in **no** preregistration |
| **B15** | `submit_intent` raises; runner has no `try/except` | `paper_session.py:914` | **One bad intent kills the session process** |
| **B16** | Default `certificate_ref = "dummy_cert_for_paper_session"` | `bridge.py:34` vs `engine.py:890` | `json.loads()` → `JSONDecodeError` → **runtime dies on first signal** |
| **B17** | `conftest.py` autouse fixture bypasses the certificate gate globally | `tests/conftest.py:81-85` | **Why 1180 tests are green.** The suite proves the runtime works by not running it |
| **B18** | `transition_on_boot(..., store_was_empty=...)` — wrong arity | `cli.py:127` vs `restart.py:121` | `TypeError` |
| **B19** | 6+ independent backtest simulators; `_compute_max_drawdown` copy-pasted **5×** | see `ARCHITECTURE_HEALTH_REPORT.md` | 5 chances to disagree; 6 cost models |
| **B20** | `RiskDecision(...)` constructed **nowhere** | vs `Risk.spec.md:44` "All decisions are persisted" | Spec claim is false |
| **B21** | Impossible metrics archived as evidence: Sharpe **−32.47**, DD 99.9% | `EQ-Micro-001-evidence-bundle.json` | No validator rejects out-of-range values |
| **B22** | `correlation_id` never passed; `_trace_decision` no-ops on empty | `engine.py:585`, `messages.rs:60` | The entire decision-trace subsystem is inert |
| **B23** | HMAC risk secret is the literal string `"TITAN_RISK_SECRET_KEY"` | `engine.py:1086` | Hardcoded secret |
| **B24** | Dual-auth on *release* doesn't pass `authorized_approvers` | `engine.py:1607` vs `:1524` | Any 2 distinct strings pass |

---

## 6. WHAT IS ONLY DOCUMENTED?

- `contracts/*.schema.json` — "imported by all producers/consumers" (`PROJECT_STRUCTURE.md:44`).
  **Zero Python imports.** Written events use `schema_version=100` vs the schema's `v1`.
- `correlation_id` "follows a decision end to end" (`ARCHITECTURE.md`) — never populated.
- `RiskDecisionRecorded` "includes every evaluated rule/version, inputs digest, limit
  snapshot" (`SYSTEM_CONTRACTS.md`) — fields exist in Rust, never written.
- `AI_GOVERNANCE.md:17` vector memory with "embedding model/version" — `embedding_vector`
  is populated **nowhere**; `search_similar_trades` can never match.
- `specifications/StrategyRuntime.spec.md` — the only importer crashes with `TypeError`.
- `scripts/monitor.py` — assumed by the ops layer; has no argparse, no `--help`.
- 15 of 25 Prometheus metrics — never written by anything.

---

## 7. WHAT IS NOT MAKING A DIFFERENCE?

- **AI (172 LOC, 0.6% of code, zero LLM calls anywhere).** ADR-0007's "no LLM on the capital
  path" is true because there is no LLM on **any** path. `mcp_bridge.py:66` returns
  **fabricated** strategy names (`"ma_crossover"`, `"bollinger_breakout"`) — neither exists
  in the registry.
- **Rust.** Not a criticism (it is good), but the *Rust-vs-Python debate is a distraction*:
  the defects are in the Python research and runtime layers, not the kernel.
- **The 34 ADRs.** They document decisions they do not enforce.
- **6 dead entrypoints**, 4 of which crash on invocation.

---

## 8. WHY ARE CURRENT STRATEGIES NOT PRODUCING USEFUL RESULTS?

**Because the measurement instrument is broken, not because the strategies were rejected
for cause.** Five independent reasons, any one of which is sufficient:

1. **One third of the evidence base is a null artifact.** A screen that never exits a
   position cannot detect anything. Verified: `results.json` has `trades: 1` in every cell.
2. **Zero was guaranteed by construction.** `replicated` is hard-wired `False`. CRYPTO-001
   passed 4/5 gates; EQ-007 passed 5/9 including OOS Sharpe 1.249 vs a 1.0 hurdle, DD 10.1%,
   monotonic quantiles, positive adverse-cost result. Both filed as failures.
3. **The cost model is 10–100× too high on the studies that produced negatives.** The repo
   uses **0.9 bp** in `run_traderdev_families.py:23` and **20 bp** in `validator.py:214` for
   the same instrument in the same month. At realistic costs, EXP-00022 — the *only*
   statistically significant FX result in the archive (t = 2.67, 412 weekly obs, 8 years,
   a published Menkhoff-style anomaly) — nets **+3.3 to +4.2%/yr, Sharpe 0.37–0.47**,
   against a 0.45 hurdle. The project's own memo records this and rejects anyway.
4. **The tests had no power to detect anything.** Per **Lo (2002)**,
   `SE(SR_ann) = √((1+0.5·SR²)/T_years)` — bounded by 1/√T **regardless of trade count**.
   With T = 0.41 yr (EXP-00031) SE = **1.56**; with T = 2 yr (equities) SE = **0.94**. A true
   Sharpe of 1.0 and a true Sharpe of 0.0 are **statistically indistinguishable**. FX-001,
   the most honest experiment in the repo, has **~16% power** against its own preregistered
   hurdle. The "≥60 trades" gate was set for the wrong failure mode: at σ/μ = 1.5, N = 9
   suffices; the real trades had σ/μ ≈ 16.
5. **The evidence is not reproducible.** `research/dukascopy_1m_ba/`, `research/crypto/data/`
   and `research/equities/data/` are **all gitignored and absent**. `EXP-00025` is missing
   the `pnl_list` the script writes. `knowledge/experiments/` is **empty** despite the
   constitution mandating it. The N=1, N=0, Sharpe=−32 artifacts were accepted without challenge.

**What the evidence base genuinely does establish — three valid results:**
- **EXP-00016**: intraday momentum *falsified*. IC −0.0834, n = 12,384, bootstrap CI
  [−0.102, −0.067], consistent across 3 temporal thirds and 2 pairs. **Real, significant,
  opposite-sign. A sound negative result.**
- **EXP-00017 retest**: the one promoted effect correctly failed honest OOS
  (IC 0.121 → 0.053; 0.098 → 0.038), and the script correctly notes the effect was never
  OOS-validated before promotion, and that its target (forward |return|) **is not a tradable
  signal** — knowing the magnitude of the next move is not knowing its direction.
- **EXP-00025 / F1@4h is a live candidate the project itself flagged, and never tested.** TITAN's
  own memo says *"CANDIDATE"*. Positive on both pairs at 4h, negative on all twelve 1h cells,
  modelled at 0.9 bp RT (the one correct cost schedule in the repo), and closed by
  **EXP-00031 — a long-only, differently-parameterised artifact producing 54 records where the
  original produced 163.** **Not significant** (t ≈ 0.46–1.28). It deserves a powered re-test,
  not a verdict. **This is the strongest reason to believe the harness can find something.**

**The 0/40 ledger is also internally inconsistent.** `EQ-002-core7-evidence-bundle.json`
carries `"verdict": "candidate"` with all 4 gates true. It is not in the survivor count.
(To be fair to the project: its IS Sharpe is **−0.0296** and its rank-IC of 0.1817 over
24 obs in 7 names is not significant, t ≈ 1.78. It is probably noise too — but it was
**never tested for significance**, which is itself the finding.)

---

## 9. IS THE PROBLEM DATA, STRATEGY, VALIDATION, EXECUTION, RISK, PORTFOLIO, INFRASTRUCTURE, OR RESEARCH?

| Candidate | Verdict |
|---|---|
| Data | **Real but secondary.** 0 of 3 core datasets on disk; no tick/L2; no borrow costs verified. Blocking for reproduction, not for the current null result. |
| **Validation** | **#1 — CATASTROPHIC.** Fake walk-forward, no Monte Carlo, Bonferroni discarded, preregs non-binding, power gate on bars, 2×-inflated bootstrap CIs, n=1 screens. |
| **Research** | **#2.** The 198-cell parameter surface reports **no significance statistic at all**. ~546 trials with no trial ledger. |
| Strategy | **Unproven — untested, not refuted.** Given defects 1–5, the honest verdict is *unmeasured*. |
| Infrastructure | **#3 for runtime** (cannot place an order), but **#1 for the kernel is sound**. |
| Execution | Not the bottleneck. Costs were *overstated*, not understated — in the wrong direction for finding edge. |
| Risk | **Sound and correctly wired.** Not preventing anything; nothing reaches it. |
| Portfolio | **Underbuilt** (HRP, rebalancing, covariance all dead code) but not the bottleneck. |
| AI | **0.6% of LOC, entirely dead.** Not a bottleneck. Not a solution either. |

---

## 10. TOP VERIFIED BOTTLENECKS

1. **Validation is fake** (B3, B7, B8, B13, B14, B11) — the gate cannot reject or accept correctly.
2. **The paper runtime cannot trade** (B15, B16, B17, B18) — no operational evidence exists.
3. **Zero survivors was manufactured** (B1, B2) — the headline result is an artifact.
4. **Cost model inverted** (B4) — real edge killed by a units error.
5. **Nothing is reproducible** (absent datasets, empty `knowledge/experiments/`).
6. **Strategy signal logic is untested** — `dual_ma` hardcoded to `"BUY"` survives 1180 tests;
   `dual_ma` and `vwap_reversion` have **zero** references in `tests/`.
7. **Performance metrics are unfalsifiable** — `abs()` on Sharpe, `profit_factor = 100.0`,
   inverted drawdown sign, and 4.6×/2.2× Sharpe and vol errors **all survive the suite**.

---

## 11. WHAT DO CURRENT GITHUB PROJECTS DO THAT TITAN DOES NOT? → `CURRENT_GITHUB_COMPETITIVE_MATRIX.md`

Verified 2026-09-29 by curl of repo pages + Atom feeds + parsing source tarballs.

| Capability | TITAN | Who has it, and the evidence |
|---|---|---|
| **Deflated Sharpe / PSR / E[max N]** | **absent** | `HKUDS/Vibe-Trading` → `agent/src/quantlib/multipletesting.py` (DSR, PSR, expected-max-Sharpe, BH-FDR, PBO) with a 336-line leakage test suite. Also `vectorbt/returns/metrics.py:19 deflated_sharpe_ratio` |
| **Purged / CPCV with embargo** | **absent** | `Vibe-Trading` `quantlib/crossvalidation.py:451 combinatorial_purged_splits`, `:524 detect_boundary_leakage`, + 6 named leakage tests |
| **Matching engine** | fill-price fudge | `nautechsystems/nautilus_trader` → `nautilus-execution/{matching_core, matching_engine}` |
| **Rust IBKR adapter** | hand-written, crashing | `nautilus-interactive-brokers` — a real crate (2.0.0rc5, 2026-09-15, commits 2026-09-29) |
| **Queue-aware fills + latency** | absent | `nkaz001/hftbacktest` `src/backtest/models/queue.rs:1130` (6 depth backends, each tested) |
| **IBKR divergence forensics** | none | `Lumiwealth/lumibot` — dated audits: `2026-01-19_..._FIRST_DIVERGENCE_AUDIT.md`, 199 IBKR-referencing files, 435 test files |
| **Agentic R&D loop** | 172 LOC, dead | `microsoft/RD-Agent` **v1.0.0, 2026-09-23**, 133 open PRs — an actual hypothesis→experiment→evaluate loop |
| **Postgres idempotency + order contracts** | none | `OpenByteInc/QuantDinger` `order_fill_contracts.json`, `test_agent_idempotency_postgres.py` |

**TITAN should adopt `quantlib/multipletesting.py` + `crossvalidation.py`.** That is the
single highest-leverage import in this entire report. Everything else is optional.

---

## 12. ADOPT / ADAPT / REJECT / STOP

**ADOPT (external, verified, MIT-ish — check licence):** DSR/PSR/PBO/purged-CPCV
(`Vibe-Trading/quantlib`); order-state-machine design (`nautilus-core`); adapter-CI
`correctness` gate pattern (`nautilus`); documented FX spread table (`Vibe-Trading
forex.py:25-40`, which is honest about which figures are measured vs. assumed).

**ADAPT (own, fix in place):** the promotion gate — make DSR the reported statistic instead
of raw Sharpe. The pre-registration process — make missing keys a hard failure, not a default.
The test philosophy — keep it, close the mutation holes.

**REJECT:** the "OHLCV directional is a closed class" doctrine, until re-tested with a
correct harness. The n=1 screen. The 10 bps FX cost. Long-only harness. `sqrt(252)` on bars.

**STOP BUILDING:** new strategies, new markets, new ADRs, Rust kernels, dashboards, the
Fincept adapter, vector memory, LLM agents, and any further infrastructure. See
`TITAN_STOP_BUILDING.md`.

---

## 13. WHAT EXPERIMENT WOULD MOST REDUCE UNCERTAINTY?

**One experiment: rebuild the harness correctly, then re-run the 15 concepts and EXP-00022.**

Specifically:
1. Fix `screen.py:40-61` (allow exits), add a short branch to `harness.py`, write one PnL
   record per round trip, add a `periods_per_year` argument, and record true `n_trades`.
2. Set a **per-instrument pip schedule**: EURUSD 0.8–1.5 pips RT, G10 basket 2 bp/rebalance,
   XAUUSD 2–5 bp RT. Sensitivity at 1× / 2× / 4×.
3. Re-run the 15 concepts and EXP-00022/23/24 **unchanged** — same parameters, same data,
   same windows. Nothing is being re-cherry-picked; the instrument is being repaired.
4. Report **DSR and PBO**, not raw Sharpe. Record N. Reject anything with `SE(SR_ann) > 0.5`
   as **UNDERPOWERED**, not `negative_result`.

**Cost:** ~1 week, ~200 LOC. **Expected information:** it converts the project's central
claim from *unknown* to *known*. Every one of the 546 trials run to date is uninterpretable
without it.

**Prediction (falsifiable, recorded in advance):** EXP-00022 will land at Sharpe 0.37–0.47.
If it does, the FX momentum result was real and was killed by a units error. If it does not,
the negative result stands on corrected instruments and the project may legitimately close
the class. **Either outcome is a large reduction in uncertainty.** That is what makes this the
right first experiment.

---

## 14. FINAL PRINCIPLE — HONEST ANSWER

**TITAN does not currently possess a demonstrable edge, and it does not currently possess
the instruments to determine whether it has one.** Both statements are true simultaneously,
and the project has been conflating the second with the first for two months.

The negative result is not worthless — **EXP-00016 is a sound falsification**, and the
governance instincts (fail-closed, pre-register, record negatives) are genuinely good and
should be preserved. But the headline "0/40" is not a finding about markets. It is a
finding about a harness that trades once per hypothesis, costs FX at 20 pips, computes
Bonferroni and throws it away, calls a buy-and-hold loop "walk-forward," and stores Sharpe
with a hard-coded `sqrt(252)` on 4-hour bars.

**The project is not short of infrastructure. It is short of measurement.**

The shortest evidence-backed path: repair the instrument, re-run the two experiments the
defects most plausibly corrupted, and let the answer be whatever it is.

---

### Companion documents
`TITAN_CURRENT_STATE.md` · `CURRENT_RUNTIME_MAP.md` · `TITAN_PROFITABILITY_FORENSICS.md` ·
`TITAN_ROOT_CAUSE_ANALYSIS.md` · `STRATEGY_GAP_ANALYSIS.md` · `DATA_GAP_ANALYSIS.md` ·
`EXECUTION_ECONOMICS.md` · `RISK_PORTFOLIO_AUDIT.md` · `BUG_AND_RELIABILITY_REPORT.md` ·
`TEST_EFFECTIVENESS_REPORT.md` · `ARCHITECTURE_HEALTH_REPORT.md` ·
`CURRENT_GITHUB_COMPETITIVE_MATRIX.md` · `TRENDING_TRADING_PROJECTS.md` ·
`CAPABILITY_GAP_REPORT.md` · `OVERENGINEERING_REPORT.md` · `UNDERENGINEERING_REPORT.md` ·
`TITAN_PRESERVE.md` · `TITAN_STOP_BUILDING.md` · `TITAN_NEXT_ACTIONS.md`
