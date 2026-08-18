# Canonical FX Simulation Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one deterministic, cost-aware FX research simulator and rerun only reproducible, non-promotable evidence after its configuration, timing, fees, sizing, and provenance have been verified.

**Architecture:** Add an immutable, USD-account FX cost model using decimal arithmetic and a canonical next-event fill interface. `StrategyRunner`, qualification, walk-forward, and promotion consume that interface only through keyword arguments; scripts become thin configuration clients. Each evidence run persists digests and fidelity labels, while ADR-028 continues to deny all paper/live execution.

**Tech Stack:** Python 3.12, `decimal.Decimal`, pytest, existing TITAN Rust contracts, SQLite research artifacts.

## Global Constraints

- No broker, order-adapter, certificate, balance, or position authority is introduced or broadened.
- `ADR-031` and the amended replay specification must be **Accepted** before production-code steps begin.
- Use only versioned local data manifests; missing bid/ask/open/conversion data rejects a canonical run.
- Use `Decimal` for prices, quantities, notionals, and fees; do not round execution prices to two decimals.
- Evidence using bar-only synthetic spread is lower fidelity and cannot qualify or promote a strategy.
- Preserve all historical results, labelled non-canonical; never delete them to obtain a pass.

---

## File map

| File | Responsibility |
|---|---|
| `docs/adr/ADR-031-canonical-fx-simulation-evidence.md` | Proposed governing decision and acceptance boundary. |
| `specifications/Replay.spec.md` | Canonical FX model, error, artifact, and metric contract. |
| `src/titan/backtest/fx_costs.py` | Immutable `FxCostModel`, fee schedule, validation, and digest. |
| `src/titan/backtest/fills.py` | Next-bar/quote-sided deterministic fills and attributed fill result. |
| `src/titan/research/harness.py` | Keyword-only canonical simulator inputs and pending-order timing. |
| `src/titan/research/promotion.py` | Persisted canonical artifact admission; remove derived return shortcut. |
| `scripts/backtest_per_timeframe.py`, `scripts/optimize_fx.py`, `scripts/qualification_pipeline.py` | Explicit model construction and propagation only. |
| `tests/backtest/test_fx_costs.py`, `tests/research/test_harness.py`, `tests/research/test_walkforward.py`, `tests/research/test_promotion.py` | Unit, regression, and evidence-admission tests. |

## Task 1: Ratify the contract before code

**Files:**
- Modify: `docs/adr/ADR-031-canonical-fx-simulation-evidence.md`
- Modify: `specifications/Replay.spec.md`
- Test: `tests/backtest/test_fx_costs.py`

**Consumes:** ADR-0005 and ADR-028.

**Produces:** An Accepted ADR-031 and an active specification defining `FxCostModel`, `FillMode`, rejection reasons, digest fields, metrics, rollback, and lower-fidelity non-promotion behavior.

- [x] **Step 1: Obtain Architecture Council and Risk Owner acceptance**

Record named approvers and date in ADR-031. Do not change `Status: Proposed` autonomously.

- [x] **Step 2: Amend `Replay.spec.md`**

Add this contract:

```text
FxCostModel: version, venue, account_currency, quote_currency, commission_bps,
minimum_commission, half_spread_bps, slippage_bps, fill_mode, data_manifest_digest.
Canonical runs require Decimal values and a sha256 digest of the complete model.
BAR_NEXT_OPEN fills the order generated at t on t+1 open plus adverse synthetic
spread/slippage. QUOTE_NEXT_EVENT fills buy at ask and sell at bid. Missing required
price, quote, or USD conversion rejects the run. BAR_NEXT_OPEN is lower fidelity and
cannot qualify a candidate.
```

- [x] **Step 3: Define measurable acceptance and rollback**

Require the test commands in Task 6 to pass; verify that a lower-fidelity or digest-mismatched artifact is rejected by promotion. Rollback sets research qualification admission to disabled and preserves all prior artifacts.

## Task 2: Add fee schedule and digest tests first

**Files:**
- Create: `tests/backtest/test_fx_costs.py`
- Create: `src/titan/backtest/fx_costs.py`

**Consumes:** Accepted ADR-031 `FxCostModel` contract.

**Produces:** `FxCostModel` and `commission_for_fill(notional_usd: Decimal) -> Decimal`.

- [x] **Step 1: Write failing tests**

```python
from decimal import Decimal
from titan.backtest.fx_costs import FxCostModel

def test_tier_one_ibkr_minimum_applies_to_a_10k_usd_fill():
    model = FxCostModel.ibkr_spot_fx_tier_one()
    assert model.commission_for_fill(Decimal("10000")) == Decimal("2.00")

def test_fee_rate_applies_above_the_minimum():
    model = FxCostModel.ibkr_spot_fx_tier_one()
    assert model.commission_for_fill(Decimal("200000")) == Decimal("4.00")

def test_cost_model_digest_changes_when_a_cost_changes():
    baseline = FxCostModel.ibkr_spot_fx_tier_one()
    stressed = baseline.with_adverse_costs()
    assert baseline.digest() != stressed.digest()
```

- [x] **Step 2: Verify red**

Run: `python -m pytest tests/backtest/test_fx_costs.py -q`

Expected: import failure because `fx_costs.py` does not yet exist.

- [x] **Step 3: Implement minimal immutable model**

```python
@dataclass(frozen=True)
class FxCostModel:
    venue: str
    account_currency: str
    quote_currency: str
    commission_bps: Decimal
    minimum_commission: Decimal
    half_spread_bps: Decimal
    slippage_bps: Decimal
    fill_mode: str

    def commission_for_fill(self, notional_usd: Decimal) -> Decimal:
        variable = abs(notional_usd) * self.commission_bps / Decimal("10000")
        return max(variable, self.minimum_commission)
```

Provide `ibkr_spot_fx_tier_one()`, `with_adverse_costs()`, `to_dict()`, and a canonical JSON SHA-256 `digest()`.

- [x] **Step 4: Verify green**

Run: `python -m pytest tests/backtest/test_fx_costs.py -q`

Expected: PASS.

## Task 3: Make fills next-event, sided, and fully attributed

**Files:**
- Modify: `src/titan/backtest/fills.py`
- Modify: `tests/backtest/test_corporate_actions.py`
- Modify: `tests/backtest/test_fx_costs.py`

**Consumes:** `FxCostModel`.

**Produces:** `BarConservativeFillModel.fill(bar, side, quantity, *, cost_model) -> FillResult` with `price`, `commission`, `spread_cost`, `slippage_cost`, and `fidelity`.

- [x] **Step 1: Write failing tests**

```python
def test_buy_quote_fill_uses_ask_and_charges_commission():
    fill = model.fill({"ask": Decimal("1.1002"), "bid": Decimal("1.1000")}, "buy", Decimal("10000"))
    assert fill.fill_price == Decimal("1.1002")
    assert fill.commission == Decimal("2.00")

def test_bar_fill_requires_next_open_and_is_lower_fidelity():
    fill = model.fill({"open": Decimal("1.1000")}, "sell", Decimal("10000"))
    assert fill.fidelity == "lower"

def test_missing_required_quote_rejects_quote_fill():
    with pytest.raises(ValueError, match="ask"):
        model.fill({"bid": Decimal("1.1000")}, "buy", Decimal("10000"))
```

- [x] **Step 2: Verify red**

Run: `python -m pytest tests/backtest/test_fx_costs.py tests/backtest/test_corporate_actions.py -q`

Expected: FAIL because quote-sided fills and attributed costs do not exist.

- [x] **Step 3: Implement minimal behavior**

Use `Decimal`, preserve full price precision, calculate notional using the executable price, apply `commission_for_fill` on every call, and reject incomplete quote data. Do not silently fall back from quote to midpoint/close.

- [x] **Step 4: Verify green**

Run: `python -m pytest tests/backtest/test_fx_costs.py tests/backtest/test_corporate_actions.py -q`

Expected: PASS.

## Task 4: Repair harness, sizing, and walk-forward propagation

**Files:**
- Modify: `src/titan/research/harness.py`
- Modify: `src/titan/research/walkforward.py`
- Modify: `scripts/backtest_per_timeframe.py`
- Modify: `scripts/optimize_fx.py`
- Modify: `scripts/qualification_pipeline.py`
- Test: `tests/research/test_harness.py`
- Test: `tests/research/test_walkforward.py`

**Consumes:** `FxCostModel`; canonical `Sizer` from ADR-028.

**Produces:** A keyword-only `StrategyRunner(signal_fn, *, sizing, cost_model)` and propagation of one exact model to IS, OOS, walk-forward, and optimization.

- [x] **Step 1: Write failing tests**

```python
def test_signal_from_bar_t_fills_no_earlier_than_bar_t_plus_1_open():
    runner = StrategyRunner(lambda bar: "BUY" if bar["timestamp"] == "t0" else None,
                            sizing=sizing, cost_model=cost_model)
    _, trades = runner.run([bar("t0", "1.00"), bar("t1", "1.10")])
    assert trades[0]["timestamp"] == "t1"
    assert trades[0]["price"] == Decimal("1.10")

def test_run_backtest_result_uses_the_supplied_model_not_defaults():
    result = run_backtest_result(bars, {}, signal_factory, cost_model=cost_model)
    assert result.cost_model_digest == cost_model.digest()

def test_walk_forward_propagates_one_exact_cost_model_to_every_window():
    results = walk_forward(bars, {}, signal_factory, cost_model=cost_model)
    assert {r.cost_model_digest for r in results} == {cost_model.digest()}
```

- [x] **Step 2: Verify red**

Run: `python -m pytest tests/research/test_harness.py tests/research/test_walkforward.py -q`

Expected: FAIL because the current API accepts positional cost values and fills same-bar closes.

- [x] **Step 3: Implement minimal propagation**

Remove every `buy_qty` call. Make `notional_allocation_pct`, `step_size`, `minimum_quantity`, and `cost_model` keyword-only. Queue an approved signal and execute it only against the next eligible bar. Call `Sizer.size()` with the declared instrument constraints. Pass the same object, not reconstructed bps numbers, through all research functions.

- [x] **Step 4: Verify green**

Run: `python -m pytest tests/research/test_harness.py tests/research/test_walkforward.py -q`

Expected: PASS.

## Task 5: Deny non-canonical promotion evidence

**Files:**
- Modify: `src/titan/research/promotion.py`
- Test: `tests/research/test_promotion.py`

**Consumes:** Persisted canonical result artifact with `cost_model_digest`, data digest, parameter digest, sizing digest, `fill_model`, and fidelity.

**Produces:** Promotion rejection reason `noncanonical_simulation_evidence` for derived return series, missing digest, mismatch, or lower-fidelity fill model.

- [x] **Step 1: Write failing tests**

```python
def test_promotion_rejects_a_lower_fidelity_bar_only_artifact():
    result = gate.evaluate_from_artifact(lower_fidelity_artifact)
    assert result["passed"] is False
    assert "noncanonical_simulation_evidence" in result["reasons"]

def test_promotion_rejects_mismatched_cost_model_digest():
    result = gate.evaluate_from_artifact(artifact_with_wrong_cost_digest)
    assert result["passed"] is False
```

- [x] **Step 2: Verify red**

Run: `python -m pytest tests/research/test_promotion.py -q`

Expected: FAIL because the promotion gate can still derive returns from local bars.

- [x] **Step 3: Implement minimal denial**

Remove `_strategy_return_series` from admission logic. Load only persisted artifact metadata and verify all required digests match the registered experiment. Return a structured rejection; do not throw, create a certificate, or mutate qualification state.

- [x] **Step 4: Verify green**

Run: `python -m pytest tests/research/test_promotion.py -q`

Expected: PASS.

## Task 6: Determinism, regression, and controlled rerun

**Files:**
- Modify: `tests/replay/test_deterministic_replay.py`
- Modify: `tests/test_execution_integrity.py`
- Create: `research/results/EXP-00031-canonical-fx-reproduction.md`

**Consumes:** Tasks 2–5 and a frozen dataset manifest.

**Produces:** Golden simulator evidence and a research-only rerun report; no certificate and no execution eligibility.

- [x] **Step 1: Write failing deterministic artifact test**

```python
def test_identical_inputs_produce_identical_cost_attribution_and_digest():
    first = run_backtest_result(bars, params, signal_factory, cost_model=cost_model)
    second = run_backtest_result(bars, params, signal_factory, cost_model=cost_model)
    assert first.evidence_artifact == second.evidence_artifact
```

- [x] **Step 2: Verify red**

Run: `python -m pytest tests/replay/test_deterministic_replay.py -q`

Expected: FAIL because no canonical evidence artifact is emitted.

- [x] **Step 3: Implement artifact persistence and metrics**

Persist dataset, parameter, sizing, and cost-model digests; fill-model/fidelity; gross/net PnL; fees, spread, slippage; fill/reject counts; and partition boundaries. Emit structured research metrics only.

- [x] **Step 4: Run the affected verification suite**

Run: `python -m pytest tests/backtest/test_fx_costs.py tests/backtest/test_corporate_actions.py tests/research/test_harness.py tests/research/test_walkforward.py tests/research/test_promotion.py tests/replay/test_deterministic_replay.py tests/test_execution_integrity.py -q`

Expected: PASS, with no test-time certificate injection permitted for integrity tests.

- [x] **Step 5: Perform the controlled rerun**

Use the frozen Dukascopy EURUSD and GBPUSD bid/ask data manifest, next-event quote fills, an IBKR Tier-I fee schedule including the USD $2 minimum on every fill, and the pre-existing EXP-00025 strategy parameters. Run IS/OOS partitions without optimization. Save the report as `EXP-00031-canonical-fx-reproduction.md`, include every digest and cost-attribution table, and state `not eligible for promotion` unless all accepted gates independently pass.

- [x] **Step 6: Verify no execution authority changed**

Run: `python -m pytest tests/test_execution_integrity.py -q`

Expected: PASS; the certificate registry remains empty and no adapter submission is made.


## Plan self-review

- **Spec coverage:** Tasks 1–3 cover deterministic fill contracts, costs, timing, errors, and lower-fidelity labels; Task 4 covers sizing and all validation paths; Task 5 blocks non-canonical promotion; Task 6 supplies replay, regression, metrics, rollback, and a research-only reproduction.
- **Placeholders:** No implementation step delegates an unspecified cost/timing rule. Approval is intentionally external because AGENTS.md reserves it to Architecture Council and Risk Owner.
- **Type consistency:** `FxCostModel` is immutable and passed keyword-only; `FillResult`, harness output, artifact output, and promotion checks all use its `digest()`.

## Execution handoff

The plan is saved at `docs/superpowers/plans/2026-08-16-canonical-fx-simulation-repair.md`. Implementation remains blocked until ADR-031 and the Replay specification amendment are accepted by the Architecture Council and Risk Owner.
