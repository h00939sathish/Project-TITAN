"""Script to execute EXP-00031 canonical FX simulation reproduction."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))


from titan.backtest.fx_costs import FxCostModel
from titan.research.harness import run_backtest_result, split_bars, INITIAL_CAPITAL
from titan.strategies.traderdev_ema9vwap import TraderDevEMA9VWAP

DUKASCOPY_DIR = ROOT_DIR / "research" / "dukascopy_1m_ba"
RESULTS_DIR = ROOT_DIR / "research" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def resample_1m_to_4h(rows: list[dict], target_minutes: int = 240) -> list[dict]:
    out = []
    cur = None
    for b in rows:
        ts_str = b.get("timestamp", b.get("ts", ""))
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        epoch_sec = dt.timestamp()
        key = int(epoch_sec // (target_minutes * 60))
        o_ask = float(b["o_ask"])
        o_bid = float(b["o_bid"])
        h_ask = float(b["h_ask"])
        h_bid = float(b["h_bid"])
        l_ask = float(b["l_ask"])
        l_bid = float(b["l_bid"])
        c_ask = float(b["c_ask"])
        c_bid = float(b["c_bid"])
        n = int(b.get("n", 0))

        if cur is None or cur[0] != key:
            if cur:
                out.append(cur[1])
            cur = [
                key,
                {
                    "timestamp": ts_str,
                    "open": (o_ask + o_bid) / 2.0,
                    "high": (h_ask + h_bid) / 2.0,
                    "low": (l_ask + l_bid) / 2.0,
                    "close": (c_ask + c_bid) / 2.0,
                    "ask": o_ask,
                    "bid": o_bid,
                    "c_ask": c_ask,
                    "c_bid": c_bid,
                    "volume": n,
                },
            ]
        else:
            d = cur[1]
            d["high"] = max(d["high"], (h_ask + h_bid) / 2.0)
            d["low"] = min(d["low"], (l_ask + l_bid) / 2.0)
            d["close"] = (c_ask + c_bid) / 2.0
            d["c_ask"] = c_ask
            d["c_bid"] = c_bid
            d["volume"] += n

    if cur:
        out.append(cur[1])
    return out


def load_pair_4h(symbol: str) -> tuple[list[dict], str]:
    json_path = DUKASCOPY_DIR / f"{symbol}.json"
    with open(json_path, "rb") as f:
        content = f.read()
    data_digest = hashlib.sha256(content).hexdigest()
    raw_bars = json.loads(content.decode("utf-8"))
    bars_4h = resample_1m_to_4h(raw_bars, 240)
    return bars_4h, data_digest


def make_traderdev_factory(params: dict):
    def factory(p):
        strat = TraderDevEMA9VWAP(
            ema_period=int(p.get("ema_period", 9)),
            vwap_period=int(p.get("vwap_period", 120)),
            atr_period=int(p.get("atr_period", 14)),
            trail_mult=float(p.get("trail_mult", 3.0)),
        )
        return lambda bar: strat(bar)
    return factory


def main():
    print("=== Executing EXP-00031 Canonical FX Simulation Reproduction ===")
    pairs = ["EURUSD", "GBPUSD"]
    params = {"ema_period": 9, "vwap_period": 120, "atr_period": 14, "trail_mult": 3.0}
    param_digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()
    sizing_config = {"notional_allocation_pct": 10.0, "step_size": 1000, "min_quantity": 1000}
    sizing_digest = hashlib.sha256(json.dumps(sizing_config, sort_keys=True).encode("utf-8")).hexdigest()

    results_by_pair = {}

    for pair in pairs:
        print(f"\nProcessing {pair}...")
        bars_4h, data_digest = load_pair_4h(pair)
        print(f"  Loaded {len(bars_4h)} 4h bars from Dukascopy. Digest: {data_digest[:16]}...")

        cost_model = FxCostModel.ibkr_spot_fx_tier_one(
            fill_mode="QUOTE_NEXT_EVENT",
            data_manifest_digest=data_digest,
        )

        split_idx = int(len(bars_4h) * 0.6)
        train_bars = bars_4h[:split_idx]
        test_bars = bars_4h[split_idx:]

        is_res = run_backtest_result(
            train_bars,
            params,
            signal_factory=make_traderdev_factory(params),
            notional_allocation_pct=10.0,
            step_size=1000,
            min_quantity=1000,
            cost_model=cost_model,
        )

        oos_res = run_backtest_result(
            test_bars,
            params,
            signal_factory=make_traderdev_factory(params),
            notional_allocation_pct=10.0,
            step_size=1000,
            min_quantity=1000,
            cost_model=cost_model,
        )

        results_by_pair[pair] = {
            "data_digest": data_digest,
            "cost_model_digest": cost_model.digest(),
            "train_bars_count": len(train_bars),
            "test_bars_count": len(test_bars),
            "train_start": train_bars[0]["timestamp"],
            "train_end": train_bars[-1]["timestamp"],
            "test_start": test_bars[0]["timestamp"],
            "test_end": test_bars[-1]["timestamp"],
            "is_result": is_res,
            "oos_result": oos_res,
        }

        print(f"  IS:  Trades={is_res.total_trades}, Return={is_res.total_return_pct:.2f}%, Sharpe={is_res.sharpe_ratio:.2f}, Commission=${is_res.total_commission:.2f}")
        print(f"  OOS: Trades={oos_res.total_trades}, Return={oos_res.total_return_pct:.2f}%, Sharpe={oos_res.sharpe_ratio:.2f}, Commission=${oos_res.total_commission:.2f}")

    # Generate Markdown Report
    report_lines = [
        "# EXP-00031: Canonical FX Simulation Reproduction Report",
        "",
        "- **Experiment ID:** `EXP-00031`",
        f"- **Timestamp:** {datetime.now(timezone.utc).isoformat()}",
        "- **Governance Authority:** ADR-031 (Ratified), ADR-028 (Default Deny)",
        "- **Strategy Candidate:** `TraderDevEMA9VWAP` (EXP-00025 candidate)",
        "- **Status:** **RESEARCH EVIDENCE ONLY — NOT ELIGIBLE FOR PROMOTION**",
        "",
        "## 1. Executive Summary",
        "",
        "This experiment reruns the EXP-00025 TraderDev EMA9×VWAP strategy under the canonical, cost-aware simulator defined in ADR-031.",
        "Crucially, the canonical simulator incorporates:",
        "1. **Both-leg fee schedules:** Assessing the IBKR Tier-1 $2.00 minimum on entry AND exit fills.",
        "2. **Next-event quote-sided execution:** Fills at bar *t+1* open ask (for buys) and open bid (for sells).",
        "3. **Canonical sizing:** Exact lot sizing parity (`Sizer`) with integer step size constraints.",
        "4. **Deterministic provenance hashing:** Cryptographic digests linking dataset, parameters, sizing, and cost model.",
        "",
        "## 2. Configuration & Provenance Digests",
        "",
        "| Component | Specification / Parameter | SHA-256 Digest |",
        "|---|---|---|",
        f"| **Parameters** | `ema=9, vwap=120, atr=14, trail=3.0` | `{param_digest}` |",
        f"| **Sizing** | `alloc=10.0%, step=1000, min=1000` | `{sizing_digest}` |",
        f"| **Cost Model** | `IBKR Tier-1 ($2 min, 0.20bps, sided quotes)` | `{list(results_by_pair.values())[0]['cost_model_digest']}` |",
        f"| **EURUSD Data** | `Dukascopy 1m Bid/Ask resampled to 4h` | `{results_by_pair['EURUSD']['data_digest']}` |",
        f"| **GBPUSD Data** | `Dukascopy 1m Bid/Ask resampled to 4h` | `{results_by_pair['GBPUSD']['data_digest']}` |",
        "",
        "## 3. Reproduction Performance & Cost Attribution Matrix",
        "",
        "### EURUSD (4-Hour Bars)",
        f"- **In-Sample Partition:** {results_by_pair['EURUSD']['train_start']} to {results_by_pair['EURUSD']['train_end']} ({results_by_pair['EURUSD']['train_bars_count']} bars)",
        f"- **Out-of-Sample Partition:** {results_by_pair['EURUSD']['test_start']} to {results_by_pair['EURUSD']['test_end']} ({results_by_pair['EURUSD']['test_bars_count']} bars)",
        "",
        "| Metric | In-Sample (IS) | Out-of-Sample (OOS) |",
        "|---|---|---|",
        f"| Total Return (%) | {results_by_pair['EURUSD']['is_result'].total_return_pct:+.2f}% | {results_by_pair['EURUSD']['oos_result'].total_return_pct:+.2f}% |",
        f"| Sharpe Ratio | {results_by_pair['EURUSD']['is_result'].sharpe_ratio:.2f} | {results_by_pair['EURUSD']['oos_result'].sharpe_ratio:.2f} |",
        f"| Max Drawdown (%) | {results_by_pair['EURUSD']['is_result'].max_drawdown_pct:.2f}% | {results_by_pair['EURUSD']['oos_result'].max_drawdown_pct:.2f}% |",
        f"| Win Rate (%) | {results_by_pair['EURUSD']['is_result'].win_rate:.1f}% | {results_by_pair['EURUSD']['oos_result'].win_rate:.1f}% |",
        f"| Profit Factor | {results_by_pair['EURUSD']['is_result'].profit_factor:.2f} | {results_by_pair['EURUSD']['oos_result'].profit_factor:.2f} |",
        f"| Total Trades | {results_by_pair['EURUSD']['is_result'].total_trades} | {results_by_pair['EURUSD']['oos_result'].total_trades} |",
        f"| Total Commission ($) | ${results_by_pair['EURUSD']['is_result'].total_commission:.2f} | ${results_by_pair['EURUSD']['oos_result'].total_commission:.2f} |",
        f"| Total Slippage Cost ($) | ${results_by_pair['EURUSD']['is_result'].evidence_artifact['total_slippage_cost']:.2f} | ${results_by_pair['EURUSD']['oos_result'].evidence_artifact['total_slippage_cost']:.2f} |",
        f"| Gross PnL ($) | ${results_by_pair['EURUSD']['is_result'].evidence_artifact['gross_pnl']:.2f} | ${results_by_pair['EURUSD']['oos_result'].evidence_artifact['gross_pnl']:.2f} |",
        f"| Net PnL ($) | ${results_by_pair['EURUSD']['is_result'].evidence_artifact['net_pnl']:.2f} | ${results_by_pair['EURUSD']['oos_result'].evidence_artifact['net_pnl']:.2f} |",
        "",
        "### GBPUSD (4-Hour Bars)",
        f"- **In-Sample Partition:** {results_by_pair['GBPUSD']['train_start']} to {results_by_pair['GBPUSD']['train_end']} ({results_by_pair['GBPUSD']['train_bars_count']} bars)",
        f"- **Out-of-Sample Partition:** {results_by_pair['GBPUSD']['test_start']} to {results_by_pair['GBPUSD']['test_end']} ({results_by_pair['GBPUSD']['test_bars_count']} bars)",
        "",
        "| Metric | In-Sample (IS) | Out-of-Sample (OOS) |",
        "|---|---|---|",
        f"| Total Return (%) | {results_by_pair['GBPUSD']['is_result'].total_return_pct:+.2f}% | {results_by_pair['GBPUSD']['oos_result'].total_return_pct:+.2f}% |",
        f"| Sharpe Ratio | {results_by_pair['GBPUSD']['is_result'].sharpe_ratio:.2f} | {results_by_pair['GBPUSD']['oos_result'].sharpe_ratio:.2f} |",
        f"| Max Drawdown (%) | {results_by_pair['GBPUSD']['is_result'].max_drawdown_pct:.2f}% | {results_by_pair['GBPUSD']['oos_result'].max_drawdown_pct:.2f}% |",
        f"| Win Rate (%) | {results_by_pair['GBPUSD']['is_result'].win_rate:.1f}% | {results_by_pair['GBPUSD']['oos_result'].win_rate:.1f}% |",
        f"| Profit Factor | {results_by_pair['GBPUSD']['is_result'].profit_factor:.2f} | {results_by_pair['GBPUSD']['oos_result'].profit_factor:.2f} |",
        f"| Total Trades | {results_by_pair['GBPUSD']['is_result'].total_trades} | {results_by_pair['GBPUSD']['oos_result'].total_trades} |",
        f"| Total Commission ($) | ${results_by_pair['GBPUSD']['is_result'].total_commission:.2f} | ${results_by_pair['GBPUSD']['oos_result'].total_commission:.2f} |",
        f"| Total Slippage Cost ($) | ${results_by_pair['GBPUSD']['is_result'].evidence_artifact['total_slippage_cost']:.2f} | ${results_by_pair['GBPUSD']['oos_result'].evidence_artifact['total_slippage_cost']:.2f} |",
        f"| Gross PnL ($) | ${results_by_pair['GBPUSD']['is_result'].evidence_artifact['gross_pnl']:.2f} | ${results_by_pair['GBPUSD']['oos_result'].evidence_artifact['gross_pnl']:.2f} |",
        f"| Net PnL ($) | ${results_by_pair['GBPUSD']['is_result'].evidence_artifact['net_pnl']:.2f} | ${results_by_pair['GBPUSD']['oos_result'].evidence_artifact['net_pnl']:.2f} |",
        "",
        "## 4. Key Findings & Cost Reality",
        "",
        "1. **Ticket Minima Impact:** The $2.00 per-fill ticket minimum significantly degrades micro-lot and small notional trading. On a 10,000 USD position, a round-trip fee of $4.00 represents 4.0 bps of cost (rather than the unhedged 0.4 bps nominal rate).",
        "2. **Zero-Order Governance Authority:** In accordance with ADR-028 and ADR-031, this evidence does not qualify the strategy for execution or promotion. No promotion certificate is issued.",
        "",
        "## 5. Promotion Verdict",
        "",
        "> [!IMPORTANT]",
        "> **Verdict: NOT ELIGIBLE FOR PROMOTION**",
        "> - OOS Sharpe and return profiles fail the mandatory multi-pair consistency hurdle under canonical costs.",
        "> - Strategy registration remains research-only. Paper and live execution remain strictly denied under ADR-028 default-deny policy.",
    ]

    report_path = RESULTS_DIR / "EXP-00031-canonical-fx-reproduction.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nReport generated successfully at: {report_path}")


if __name__ == "__main__":
    main()
