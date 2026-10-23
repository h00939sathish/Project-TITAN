# Harness² Pilot — Deterministic Falsification Probe

- **Status:** pilot implemented; advisory only
- **Date:** 2026-10-21
- **Scope:** `src/titan/research/falsify.py`, `tests/research/test_falsify.py`
- **Authority:** none on the capital path; no model inference

## 1. Why this shape

The Harness² proposal has two layers: a Propose–Probe–Compose research loop and a
playbook distiller. The full loop needs an LLM proposer. ADR-0007 defers AI until
after Phase F and, even then, requires an ADR, an allow-listed tool surface,
structured work items, and prompt evaluation before enablement. Phase J (paper
operation) is active, so the timing gate is behind us, but the remaining ADR-0007
controls are not satisfied by this pilot.

This pilot therefore implements the **deterministic Probe layer** only. It is a
gate that any proposed research result must pass; it cannot propose hypotheses,
tune parameters, or touch order routing.

## 2. What was built

`titan.research.falsify` inspects a result payload (`equity_curve`, `trades`,
optional `reported`, `gates`, `verdict`, `replicated`, `n_bars`) and emits a
pass/fail dossier. Probes:

| Probe | Catches |
|---|---|
| `pnl_identity` | round-trip PnL copied onto both legs, missing exit legs |
| `trade_lifecycle` | unbalanced entries/exits, exit before entry, one-trade samples |
| `costs` | zero or implausibly low commission/spread/slippage |
| `trade_count` | entry and exit legs counted as two trades |
| `lookahead` | fill at or before its signal (when timestamps exist) |
| `gate_integrity` | failed gates or `replicated=false` hidden by a promoting verdict |
| `power` | Sharpe standard error too large to distinguish from zero |

Run:

```bash
python -m titan.research.falsify result.json
```

Exit code is `1` on a hard FAIL, `0` otherwise. A FAIL means the evidence is not
admissible for promotion until reconciled.

## 3. First live finding

A six-bar `StrategyRunner` round trip (buy at t1, sell at t4, 99 units) produced:

```text
equity:  100000.00 -> 100293.96
entry leg PnL: 294.96
exit  leg PnL: 294.96
trade log sum: 589.92   (2.0x the equity change)
reported total_trades: 2  (one round trip)
```

`pnl_identity` and `trade_count` both FAIL. This is the same defect recorded in
the 2026-09-29 forensic audit: `StrategyRunner` writes the round-trip PnL onto
both the buy and sell records, and `BacktestResult.compute` counts both legs as
trades. It inflates PnL, win rate denominators, average trade and bootstrap
inputs.

The probe also reports `lookahead: UNVERIFIABLE`: fills do not record the signal
timestamp, so execution timing cannot be proven from the artifact alone. The
separate timing test in `tests/research/test_harness.py` covers the mechanism,
but the evidence bundle should carry the timestamp.

## 4. Remediation — not applied

Fixing this is a governed change, not a silent patch:

1. Attribute the round-trip PnL to one leg only; leave the other at zero.
2. Count round trips (exit legs), not legs, in `total_trades`, win rate and
   average trade.
3. Record `signal_timestamp` on every fill.
4. Re-run every research result; pre-fix results are not comparable and must not
   be promoted.
5. Add the falsifier to the evidence-bundle/promotion path.

Until that is done, the correct verdict on affected results is **inadmissible**,
not "validated".

## 5. CRYPTO-007 correction

The proposal suggested piloting Harness² on CRYPTO-007 maker-rebate capture.
That is not compliant:

- CRYPTO-007's recorded verdict recommends against pursuit; its conclusion is
  dominated by measurement error, not by the fee. It is terminal for pursuit.
- ADR-029/030 make failed or abandoned pre-registered hypotheses absorbing.
  Re-mining CRYPTO-007 with a new harness would violate that rule.
- A maker-rebate follow-up needs a **new hypothesis ID** (for example
  `CRYPTO-008`), a fresh pre-registration, and L2 depth data. The current
  evidence says all symbols are `depth_capable: false`; without depth data the
  structural question cannot be settled at any fee tier.

The Harness² pilot therefore does not read the CRYPTO-007 OOS partition or
re-run its tests.

## 6. Next steps

1. Review and apply the remediation above under the normal change process.
2. Wire `falsify` into the evidence-bundle generator and CI; a FAIL blocks
   promotion.
3. Add the deterministic negative-results distiller (Level 2) that extracts
   failure modes from `research/neg_results/` into a reusable playbook.
4. Only then propose the LLM Propose layer: new ADR, allow-listed tools,
   structured output schema, prompt-evaluation suite, and deterministic
   validators that can veto model output.

## 7. Reproduce

```bash
pytest tests/research/test_falsify.py -q
python - <<'PY'
import json
from titan.research.harness import StrategyRunner
bars = [{"timestamp": f"t{i}", "open": 100.0+i, "close": 100.0+i, "ask": 100.0+i} for i in range(6)]
signal = lambda b: "BUY" if b["timestamp"] == "t0" else "SELL" if b["timestamp"] == "t3" else None
equity, trades = StrategyRunner(signal, notional_allocation_pct=10.0).run(bars)
json.dump({"equity_curve": equity, "trades": trades,
           "reported": {"total_trades": len(trades)}, "n_bars": len(bars),
           "verdict": "candidate"}, open("/tmp/harness2-probe.json", "w"))
PY
python -m titan.research.falsify /tmp/harness2-probe.json
```
