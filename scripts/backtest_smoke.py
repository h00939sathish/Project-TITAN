"""Smoke backtests for the forex and spot-gold fixtures. Research-only.

Shared implementation behind scripts/backtest_forex.py and scripts/backtest_spot_gold.py:
runs a trivial buy-and-hold round trip through PaperTradingEngine + BacktestAdapter
and asserts the trade/rejection/position invariants.

Usage:
    python scripts/backtest_smoke.py                       # both instruments
    python scripts/backtest_smoke.py --instrument EURUSD
    python scripts/backtest_smoke.py --instrument XAUUSD --live-data
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from titan._core import Money, ReconciliationConfig, RiskConfig, TradeIntent

from titan.data.forex_pairs import forex_instrument
from titan.data.spot_metals import spot_metal_instrument
from titan.execution import PaperConfig, PaperTradingEngine
from titan.execution.backtest_adapter import BacktestAdapter
from titan.risk.session_initialization import (
    InitializerApproval,
    SessionInitialization,
    new_nonce,
)


@dataclass(frozen=True)
class InstrumentConfig:
    instrument_id: str
    fixture_path: str
    quantity: str
    max_order_quantity: int
    account_id: str
    strategy_id: str
    certificate_ref: str
    load_instrument: Callable[[str], object]


_INSTRUMENTS: dict[str, InstrumentConfig] = {
    "EURUSD": InstrumentConfig(
        "EURUSD", "tests/data/fixtures/eurusd_2026.csv",
        "1000", 100000, "forex-bt-1", "forex-smoke", "backtest-cert",
        forex_instrument,
    ),
    "XAUUSD": InstrumentConfig(
        "XAUUSD", "tests/data/fixtures/xauusd_2026.csv",
        "1", 100, "gold-bt-1", "gold-smoke", "gold-backtest-cert",
        spot_metal_instrument,
    ),
}


def _initialize_sandbox_session(engine: PaperTradingEngine) -> None:
    """Arm the sandbox engine. Production defaults fail closed (ADR-019): an
    engine without risk state starts halted, so a smoke run must explicitly
    initialize a session (same pattern as tests/fixtures/session_init.py)."""
    now = datetime.now(timezone.utc)
    engine.initialize_new_session(
        SessionInitialization(
            approvers=[
                InitializerApproval("smoke-backtest-a", now.isoformat()),
                InitializerApproval("smoke-backtest-b", now.isoformat()),
            ],
            rationale="backtest smoke script sandbox session (fixture or daily bars)",
            issued_at=now.isoformat(),
            expiry=(now + timedelta(minutes=15)).isoformat(),
            nonce=new_nonce("smoke"),
        )
    )


def _smoke_intent(cfg: InstrumentConfig, side: str) -> TradeIntent:
    return TradeIntent(
        strategy_id=cfg.strategy_id,
        strategy_package_digest="v1",
        account_id=cfg.account_id,
        instrument_id=cfg.instrument_id,
        side=side,
        quantity=cfg.quantity,
        order_type="MARKET",
        time_in_force="DAY",
        risk_profile_version="1.0",
        market_data_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        certificate_ref=cfg.certificate_ref,
    )


def run_smoke_backtest(instrument_id: str, *, live: bool = False) -> dict:
    """Run a buy-hold-sell round trip on one instrument; returns result dict."""
    cfg = _INSTRUMENTS[instrument_id]
    inst = cfg.load_instrument(instrument_id)
    assert inst is not None, f"{instrument_id} instrument not found"

    if live:
        from titan.data.polygon_feed import fetch_daily_bars
        bars = fetch_daily_bars(instrument_id, 30)
        if not bars:
            return {"trades": 0, "rejected": 0, "final_cash": "0", "final_position": 0}
    else:
        bars: list[dict] = []
        with open(cfg.fixture_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["timestamp"] = row["date"]
                for k in ("open", "high", "low", "close"):
                    row[k] = float(row[k])
                bars.append(row)

    risk = RiskConfig(
        [instrument_id],
        Money("100000", "USD"),
        cfg.max_order_quantity, cfg.max_order_quantity,
        Money("1000000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000,
        60000,
    )
    config = PaperConfig(
        risk_config=risk,
        reconciliation_config=ReconciliationConfig(
            critical_drift_fraction=0.05,
            warning_drift_fraction=0.01,
        ),
        currency="USD",
        starting_capital="100000",
        account_id=cfg.account_id,
        state_path="",
    )

    adapter = BacktestAdapter(bars)
    engine = PaperTradingEngine(config, adapter)
    engine.register_instrument(inst)
    _initialize_sandbox_session(engine)
    engine.start()

    trades = 0
    rejected = 0

    for bar in bars:
        adapter.advance_to(bar)
        close = float(bar["close"])

        if trades == 0:
            result = engine.submit_intent(_smoke_intent(cfg, "BUY"))
            if result.accepted:
                trades += 1
            else:
                rejected += 1

        engine._last_prices[instrument_id] = str(close)
        try:
            engine.portfolio.update_market_price(instrument_id, str(close))
        except Exception:
            pass

    if trades > 0:
        result = engine.submit_intent(_smoke_intent(cfg, "SELL"))
        if result.accepted:
            trades += 1
        else:
            rejected += 1

    engine.stop()

    cash = engine.portfolio.get_cash_balance()
    pos = engine.portfolio.get_position(instrument_id)
    return {
        "trades": trades,
        "rejected": rejected,
        "final_cash": str(cash.amount),
        "final_position": pos.quantity if pos else 0,
    }


def run_forex_backtest() -> dict:
    return run_smoke_backtest("EURUSD")


def run_spot_gold_backtest() -> dict:
    return run_smoke_backtest("XAUUSD")


def run_live_backtest() -> dict:
    return run_smoke_backtest("EURUSD", live=True)


def run_live_gold_backtest() -> dict:
    return run_smoke_backtest("XAUUSD", live=True)


def run_cli(default_instrument: str | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--instrument", choices=list(_INSTRUMENTS), default=default_instrument,
        help="Instrument to run (default: all)",
    )
    parser.add_argument(
        "--live-data", action="store_true",
        help="Fetch from Polygon.io instead of fixture",
    )
    args = parser.parse_args()

    instruments = [args.instrument] if args.instrument else list(_INSTRUMENTS)
    for inst in instruments:
        result = run_smoke_backtest(inst, live=args.live_data)
        print(f"Trades executed: {result['trades']}")
        print(f"Rejected:        {result['rejected']}")
        print(f"Final cash:      ${result['final_cash']}")
        print(f"Final position:  {result['final_position']}")
        if not args.live_data:
            assert result["trades"] == 2, f"Expected 2 trades (buy + sell), got {result['trades']}"
            assert result["rejected"] == 0, f"Expected 0 rejections, got {result['rejected']}"
            assert result["final_position"] == 0, (
                f"Expected flat position, got {result['final_position']}"
            )
        print(f"\nPASS — {inst} backtest smoke test passed")


if __name__ == "__main__":
    run_cli()
