"""Replay engine: drives a historical bar loop through PaperTradingEngine."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol


class StrategyLike(Protocol):
    def update(self, price: float) -> str | None: ...

from ..execution.backtest_adapter import BacktestAdapter
from ..execution.engine import PaperConfig, PaperTradingEngine
from ..backtest.fills import BarConservativeFillModel
from .._core import ContractType, Instrument, InstrumentId, TradeIntent, Money, RiskConfig
from ..risk.session_initialization import (
    InitializerApproval,
    SessionInitialization,
    new_nonce as _init_nonce,
)



@dataclass
class BacktestBar:
    instrument_id: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float | int


@dataclass
class BacktestResult:
    trades: int = 0
    total_pnl: str = "0"
    final_cash: str = "0"
    total_commission: str = "0"
    max_drawdown: str = "0"
    bars_processed: int = 0
    rejected_intents: int = 0
    bar_results: list = field(default_factory=list)


@dataclass
class BarResult:
    timestamp: str
    instrument_id: str
    signal: str | None
    accepted: bool
    fill_qty: int
    fill_price: str
    position_qty: int
    cash: str


class ReplayEngine:
    """Drives a strategy through PaperTradingEngine over historical bar data.

    Usage::

        engine = ReplayEngine(strategy, bars, risk_config, ...)
        result = engine.run()
    """

    def __init__(
        self,
        strategy: StrategyLike,
        bars: list[dict],
        risk_config: RiskConfig | None = None,
        account_id: str = "backtest-1",
        currency: str = "USD",
        initial_capital: str = "100000",
        client_order_prefix: str = "bt-",
        slippage_bps: float = 0.0,
        commission_bps: float = 0.0,
        intent_qty: int = 10,
    ):
        self._strategy = strategy
        self._bars = list(bars)
        self._fill_model = BarConservativeFillModel(slippage_bps=slippage_bps, commission_bps=commission_bps)
        self._slippage_bps = slippage_bps
        self._intent_qty = intent_qty

        if risk_config is None:
            from .._core import RiskConfig as RC
            instruments = {b["instrument_id"] for b in bars}
            risk_config = RC(
                list(instruments),
                Money("10000000", currency),
                5000,
                50000,
                Money("10000000", currency),
                0.25,
                Money("50000", currency),
                1_000_000_000_000,
                1_000_000_000_000,
            )

        self._config = PaperConfig(
            account_id=account_id,
            currency=currency,
            starting_capital=initial_capital,
            client_order_prefix=client_order_prefix,
            risk_config=risk_config,
            state_path="",
        )

    def run(self) -> BacktestResult:
        bars = self._bars
        if not bars:
            return BacktestResult()

        instrument_ids = list({b["instrument_id"] for b in bars})
        adapter = BacktestAdapter(bars, fill_model=self._fill_model)
        engine = PaperTradingEngine(self._config, adapter)
        for instr_id in instrument_ids:
            inst = Instrument(InstrumentId(instr_id, "BACKTEST"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
            engine.register_instrument(inst)
        now = datetime.now(timezone.utc)
        engine.initialize_new_session(SessionInitialization(
            approvers=[
                InitializerApproval("backtest-engine", now.isoformat()),
                InitializerApproval("replay-runner", now.isoformat()),
            ],
            rationale="ReplayEngine explicitly arms its fresh in-memory session (ADR-020)",
            issued_at=now.isoformat(),
            expiry=(now + timedelta(minutes=30)).isoformat(),
            nonce=_init_nonce("backtest"),
        ))
        engine.start()

        result = BacktestResult()

        for bar in bars:
            adapter.advance_to(bar)
            engine._check_adapter_health()

            side_str = self._strategy.update(bar["close"])
            # Prefer the full-OHLC path when the strategy supports it (intrabar
            # stop/trail), so replay and live execution use the same bar shape.
            if hasattr(self._strategy, "update_bar"):
                side_str = self._strategy.update_bar(bar)
            if not side_str:
                result.bars_processed += 1
                continue

            intent_qty = self._intent_qty
            if self._slippage_bps or self._fill_model.commission_bps:
                fill_result = self._fill_model.fill(bar, side_str.lower(), intent_qty)
                fill_price = fill_result.fill_price
                result.total_commission = str(float(result.total_commission) + fill_result.commission)
            else:
                fill_price = bar["close"]

            intent = TradeIntent(
                strategy_id=getattr(self._strategy, "strategy_id", "replay"),
                strategy_package_digest="",
                account_id=self._config.account_id,
                instrument_id=bar["instrument_id"],
                side=side_str.upper(),
                quantity=str(intent_qty),
                order_type="LIMIT",
                time_in_force="DAY",
                risk_profile_version="1.0",
                market_data_timestamp=bar["timestamp"] if "T" in str(bar["timestamp"]) else bar["timestamp"] + "T00:00:00Z",
                price=str(round(fill_price, 2)),
            )

            order_result = engine.submit_intent(intent)

            if order_result.accepted:
                result.trades += 1
                fill_qty = 0
                fill_price = "0"
                if order_result.fills:
                    fill_qty = sum(int(f.quantity) for f in order_result.fills)
                    fill_price = order_result.fills[0].price
                pos = engine.portfolio.get_position(bar["instrument_id"])
                pos_qty = pos.quantity if pos else 0
                cash = engine.portfolio.get_cash_balance()
                result.bar_results.append(BarResult(
                    timestamp=bar["timestamp"],
                    instrument_id=bar["instrument_id"],
                    signal=side_str,
                    accepted=True,
                    fill_qty=fill_qty,
                    fill_price=fill_price,
                    position_qty=pos_qty,
                    cash=str(cash.amount),
                ))
            else:
                result.rejected_intents += 1
                result.bar_results.append(BarResult(
                    timestamp=bar["timestamp"],
                    instrument_id=bar["instrument_id"],
                    signal=side_str,
                    accepted=False,
                    fill_qty=0,
                    fill_price="0",
                    position_qty=0,
                    cash="0",
                ))

            result.bars_processed += 1

            engine._last_prices[bar["instrument_id"]] = str(bar["close"])
            try:
                engine.portfolio.update_market_price(bar["instrument_id"], str(bar["close"]))
            except Exception:
                pass

        engine.stop()

        cash = engine.portfolio.get_cash_balance()
        result.final_cash = str(cash.amount)
        result.total_pnl = str(float(cash.amount) - float(self._config.starting_capital))

        return result
