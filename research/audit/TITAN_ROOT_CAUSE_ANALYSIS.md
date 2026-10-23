# TITAN ROOT CAUSE ANALYSIS

**Date:** 2026-09-29. Each chain is proved or rejected with evidence. The example chain given
in the audit brief was tested first and is **REJECTED** at step 3.

---

## CHAIN 1 — "Zero strategies promoted" (the project's own question)

```
SYMPTOM          No strategy has ever been promoted; no paper trade has ever been placed
   ↓
IMMEDIATE CAUSE  The paper session dies on the first signal, and the promotion gate says no
   ↓
SYSTEMIC CAUSE   The certificate gate is unreachable in the runtime, and the gate's own
                 logic cannot detect failures
   ↓
PROCESS CAUSE    Tests were made to pass by bypassing the gate, so the break was invisible
   ↓
ROOT CAUSE       Correctness was measured by "does the suite pass", never by "does the
                 production path run". conftest.py:81-85 is an autouse fixture that removes
                 the exact gate the runtime hits.
```

**Proved.** `bridge.py:34` defaults `certificate_ref = "dummy_cert_for_paper_session"`;
`engine.py:890` `json.loads()` it → `JSONDecodeError` → `raise` at `:895`;
`paper_session.py:914` has no `try/except`. 1180 tests pass because the fixture replaces
`submit_intent` with `_submit_intent_core` for every test lacking `e2e`/`adversarial`/
`test_execution_integrity` in its node id.

---

## CHAIN 2 — "0 survivors across ~40 experiments" (the central claim)

```
SYMPTOM          Terminal report: liquid OHLCV directional alpha does not exist
   ↓
IMMEDIATE CAUSE  Screens returned 0 survivors
   ↓
SYSTEMIC CAUSE   Five independent instrument defects, any one sufficient:
                 (a) 1/3 of the base ran ONE trade per hypothesis
                 (b) `replicated` hard-wired False ⇒ 0 is a constant
                 (c) FX cost 10–100× overstated
                 (d) SE(SR) ≈ 1/√T ⇒ tests had ~0 power
                 (e) datasets absent ⇒ nothing is reproducible
   ↓
PROCESS CAUSE    Screens were written as one-off research scripts, not as a gated harness.
                 6+ independent simulators, 6 cost models, 5 copies of max-drawdown.
                 Nothing was ever cross-checked against a second implementation.
   ↓
ROOT CAUSE       The research instrument was never itself subjected to a correctness gate.
                 The promotion gate was rigorously applied to STRATEGIES and never once
                 applied to the MEASUREMENT CODE.
```

**Proved.** See `TITAN_PROFITABILITY_FORENSICS.md` D1–D5, each independently verified.

**The brief's example chain is REJECTED at step 3:** the hypothesis "insufficient hypothesis
generation / research loop optimized infrastructure" is not supported. Infrastructure is 2.4%
of LOC and AI is 0.6%. The research loop did not optimize infrastructure — it produced **40
experiments**, which is not a shortage of hypotheses. The failure is in measurement.

---

## CHAIN 3 — "Two experiments reached `decision: promote` with failing gates"

```
SYMPTOM          EXP-00017 and EXP-00019 evidence bundles both record "decision": "promote"
   ↓
IMMEDIATE CAUSE  make_decision never saw a failure
   ↓
SYSTEMIC CAUSE  validator.py:262-265 treats a check as failed only if it is `False` or a
                 string containing "❌" — and NO message string in the file contains "❌"
                 (auditor-verified: exactly 1 occurrence, at line 265, the detector itself)
   ↓
PROCESS CAUSE  Checks are stored as a heterogeneous dict{bool, str}. The failure encoding
                 was never tested end-to-end, only unit-by-unit.
   ↓
ROOT CAUSE      A fail-closed design with an untyped failure channel. Storing a failure as a
                 human-readable string is a type error the system cannot see.
```

**Proved.** `validator.py:376`: `checks["Survives transaction costs"] = cost_ok if cost_ok else cost_msg`.
EXP-00019's committed bundle carries `"IC statistically significant": "IC 0.0298 below threshold 0.03"`
(FAILED) **and** `"Survives transaction costs": "Net spread -0.0020 <= 0 after 10.0 bps"` (FAILED)
→ `"decision": "promote"`.

**Note the accidental save:** the project was rescued from its own broken gate by the EXP-00017
retest — an *honest experiment* that failed, not by the gate. The gate said yes; a human check
said no.

---

## CHAIN 4 — "The one viable FX result was killed by a cost constant"

```
SYMPTOM          EXP-00022 (G10 cross-sectional currency momentum) nets exactly 0.00%/yr
   ↓
IMMEDIATE CAUSE  COST_BPS = 10.0 → 5.20%/yr drag against a 5.4%/yr gross edge
   ↓
SYSTEMIC CAUSE  10 bps was labelled "1 pip" (run_fx_experiments.py:11). On EURUSD 1 pip =
                 0.01% = 1 bp. The constant is 10× the comment that describes it, and 10–100×
                 the plausible figure. The same repo uses 0.9 bp elsewhere.
   ↓
PROCESS CAUSE   No per-instrument cost schedule existed, so each author hard-coded a constant,
                 and the conservative-looking one was used for the studies that failed.
   ↓
ROOT CAUSE      Costs were modelled as a scalar constant chosen by intuition per script, with
                 no single source of truth, no calibration against real quotes, and no
                 sensitivity requirement.
```

**Proved.** `run_exp22_xs_momentum.py:26,78,82`. Auditor arithmetic:
`gross +5.4%/yr, σ ≈ 9%/yr, t = 2.67, n = 412 weekly obs, 8 years`.
At 2 bps/period → net +4.36%/yr, Sharpe ≈ 0.48, vs a 0.45 hurdle. At 1 bp → Sharpe ≈ 0.54.
The project's own memo (`neg_results/EXP-00022_g10_xs_momentum.md`) records "+2.6 to +3.9%/yr net
at institutional 5-2.5bps/leg" and rejects anyway.

---

## CHAIN 5 — "The 1180-test suite did not protect the trading math"

```
SYMPTOM          Coverage is 85% and the suite is green
   ↓
IMMEDIATE CAUSE  Mutation testing: 8 of 20 mutants survived
   ↓
SYSTEMIC CAUSE  Every assertion on Sharpe/DD/profit-factor is SELF-CONSISTENCY
                 (run twice, compare), never ABSOLUTE VALUE.
                   test_independent_reproduction.py:102  assert r1.sharpe == r2.sharpe
                   test_deterministic_replay.py:45        assert result1 == result2
                   test_deterministic_replay.py:74        assert cash_amount > 0
   ↓
PROCESS CAUSE   The testing standard asks for determinism and idempotence — both of which
                 are satisfied by a completely wrong implementation.
   ↓
ROOT CAUSE      Determinism was mistaken for correctness. Exactly ONE test in 1180 asserts an
                 absolute PnL number (test_exit_intents.py:434, == -95.0).
```

**Proved.** Surviving mutants: `dual_ma` hardcoded to `"BUY"` (never shorts) · `abs()` on
Sharpe (every loser reports a positive Sharpe) · `profit_factor` → `100.0` ·
drawdown sign inverted · `sqrt(252)`→`sqrt(12)` (Sharpe off 4.6×) · `sqrt(252)`→`sqrt(52)`
(vol off 2.2×). **Killed** mutants: risk-gate bypass, 10× looser risk limits, fill slippage
sign, trailing stop direction, 10× position size, crypto taker fee zeroed, total-PnL sign.
A full realized-PnL sign-flip across the suite failed **35 tests**.

**The boundary is sharp and diagnostic:** the **Rust kernel is genuinely protected**;
the **Python strategy-signal and performance-metric layers are not tested at all** — and those
are exactly the layers that decide whether the system makes money.

---

## CHAIN 6 — "1180 tests pass but 0 orders have ever been placed"

```
SYMPTOM          Green CI, zero operational history
   ↓
IMMEDIATE CAUSE  The CI workflow triggered only on branch `main`, which does not exist
   ↓
SYSTEMIC CAUSE  Commit 698cd7b ("repoint dead workflow trigger to master trunk") — the
                 entire gate had never run. Four commits landed ungated.
   ↓
PROCESS CAUSE  A test asserts the *absence* of a gate: tests/test_ci_workflow.py:47-56
                 requires mypy to stay continue-on-error. ruff is installed and never
                 invoked (1,593 violations). A comment says "387 mypy errors"; reality is 2,368.
   ↓
ROOT CAUSE      Governance was written to specify the *state* of the gates rather than to
                 enforce them. check_adr_gate.py runs in CI — it gates document formatting,
                 not behavior. 34 ADRs and 13.8k doc LOC coexist with profit_factor = 100.0.
```

**Proved.** `.github/workflows/ci.yml`. `tests/test_ci_workflow.py:2-6` documents the dead
trigger; `:47-56` locks in the advisory posture.

---

## CHAIN 7 — "The research cannot be reproduced or falsified"

```
SYMPTOM          546 trials, 0 survivors, and no one can check any of it
   ↓
IMMEDIATE CAUSE  research/dukascopy_1m_ba/, crypto/data/, equities/data/ are gitignored
                 and absent from the working tree
   ↓
SYSTEMIC CAUSE  EXP-00025 is missing the pnl_list its runner writes (run_traderdev_families.py:369);
                 traderdev_fx_screen.py returns only aggregates, so its "≥60 trades" claim has
                 no supporting trade count anywhere. knowledge/experiments/ is empty.
   ↓
PROCESS CAUSE  Preregs and results were committed in the SAME commit (80ee522, 2026-09-20 for
                 EQ-006/007/008), and prereg JSONs carry no timestamp field. The documented
                 "absorbing negative result" protocol (RESEARCH_CONSTITUTION.md §124) is
                 implemented nowhere.
   ↓
ROOT CAUSE      There is no trial ledger. N is never recorded as data, so the multiple-testing
                 exposure is invisible — and Bailey et al.: "A backtest that does not report
                 the number of trials N makes it impossible to assess the risk of overfitting."
```

**Proved.** `.gitignore:101,143`; `git log --diff-filter=A` dates; `knowledge/experiments/`
contains only `.gitkeep`.

---

## Root-cause ranking

| # | Root cause | Confidence | Cost to fix |
|---|---|---|---|
| **1** | Correctness was never required of the **measurement code** — only of strategies | **PROVED** | Architectural/process |
| **2** | Determinism was treated as correctness; no absolute-value assertions on economic outputs | **PROVED** | ~1 day, 4 assertions |
| **3** | Global test fixture bypassed the production gate, hiding a total runtime failure | **PROVED** | ~1 hour |
| 4 | No single source of truth for costs; each script hard-coded its own | **PROVED** | ~1 day |
| 5 | No trial ledger (N), so multiple-testing exposure was never visible | **PROVED** | ~2 days |
| 6 | Governance documents specify process; CI enforces formatting | **PROVED** | ~2 days |
| 7 | Datasets kept local and gitignored, making research non-reproducible | **PROVED** | Process decision |

**Every one of the top three is a measurement failure, not a trading failure.** No root cause
found in this audit points at the market, the strategies, or the risk system.

## What is explicitly NOT a root cause

- **Not insufficient AI** — AI is 0.6% of LOC and entirely dead. It cannot be a cause.
- **Not insufficient infrastructure** — infrastructure is 2.4% of LOC. The kernel is the
  best-engineered part of the repo.
- **Not insufficient strategies** — 40+ experiments, ~546 trials, 6 structural axes, 2 asset
  classes, then 2 more programs. Hypothesis generation is not the shortage.
- **Not insufficient data volume** — the problem is not too little data; it is that the data
  present was instrumented with 20-pip costs and `sqrt(252)` on 4h bars.
- **Not risk controls suppressing edge** — the risk gate is sound, correctly wired, and
  mutation-resistant. Nothing reaches it, so it has suppressed nothing.
