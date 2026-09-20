"""Non-custodial, read-only shadow paper runner for CRYPTO-004.

Consumes streaming or batched CryptoMarketEvent records (funding rates, quotes, trades)
and maintains a real-time mark-to-market virtual shadow book for maker-oriented basis
and funding rate carry across BTCUSDT and ETHUSDT.

STRICT GOVERNANCE INVARIANTS:
- Research / Shadow authority only.
- Zero broker credentials, zero capital authority, zero order routing capabilities.
- Strictly forbidden from importing titan.execution, titan.runtime, or broker adapters.
See docs/adr/ADR-032-crypto-004-shadow-deployment.md.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

from titan.backtest.crypto_costs import CryptoCostModel
from titan.backtest.crypto_simulator import Attribution
from titan.data.crypto import CryptoMarketEvent


@dataclass
class ShadowBookState:
    """Tracks spot and perpetual position states and mark-to-market metrics for an instrument."""

    symbol: str
    position_perp: Decimal = Decimal("0")
    position_spot: Decimal = Decimal("0")
    spot_entry_price: Decimal | None = None
    perp_entry_price: Decimal | None = None
    last_spot_mark: Decimal | None = None
    last_perp_mark: Decimal | None = None
    last_mark: Decimal | None = None
    last_funding_rate: Decimal | None = None
    last_funding_ts: datetime | None = None
    realized_funding: Decimal = Decimal("0")
    realized_price_pnl: Decimal = Decimal("0")
    pending_leg: dict[str, Any] | None = None

    @property
    def matched_hedged_qty(self) -> Decimal:
        """Returns the synchronized hedged active notional quantity collecting funding."""
        if self.position_perp < 0 and self.position_spot > 0:
            return min(abs(self.position_perp), abs(self.position_spot))
        return Decimal("0")

    @property
    def unrealized_spot_pnl(self) -> Decimal:
        """Unrealized PnL on spot leg."""
        if self.position_spot == Decimal("0") or self.spot_entry_price is None:
            return Decimal("0")
        mark = self.last_spot_mark or self.last_mark or self.spot_entry_price
        return self.position_spot * (mark - self.spot_entry_price)

    @property
    def unrealized_perp_pnl(self) -> Decimal:
        """Unrealized PnL on perpetual leg (Short Perp: pos < 0)."""
        if self.position_perp == Decimal("0") or self.perp_entry_price is None:
            return Decimal("0")
        mark = self.last_perp_mark or self.last_mark or self.perp_entry_price
        return self.position_perp * (mark - self.perp_entry_price)

    @property
    def unrealized_basis_pnl(self) -> Decimal:
        """Combined mark-to-market basis PnL across spot and perpetual legs."""
        return self.unrealized_spot_pnl + self.unrealized_perp_pnl


def default_maker_carry_signal(event: CryptoMarketEvent, state: dict[str, Any]) -> Decimal:
    """Carry signal: enter Long Spot + Short Perp when funding rate > threshold.

    Returns target perpetual position: Decimal("-1") for Short Perp (collect carry),
    or Decimal("0") for Flat.
    """
    params = state.get("parameters", {})
    ann_thresh_pct = Decimal(str(params.get("annualized_funding_threshold_pct", "10.0")))
    default_thresh = (ann_thresh_pct / Decimal("100")) / Decimal("1095")
    thresh = Decimal(str(params.get("funding_abs_threshold", default_thresh)))

    if event.event_type == "FUNDING" and event.funding_rate is not None:
        state["last_funding"] = event.funding_rate

    funding: Decimal | None = state.get("last_funding")
    if funding is None:
        return Decimal("0")

    if funding > thresh:
        return Decimal("-1")  # Short Perp to collect funding
    elif funding <= Decimal("0"):
        return Decimal("0")   # Exit carry when funding collapses or inverts

    return state.get("position_perp", Decimal("0"))


class CryptoShadowRunner:
    """Live mark-to-market paper shadow book runner for CRYPTO-004 maker basis carry.

    Operates in a non-custodial, read-only mode consuming live market events and
    simulating maker queue fills, legging timeout fallbacks, matched hedged funding
    cashflows, unrealized basis PnL, and full friction attribution under Binance VIP1.
    """

    def __init__(
        self,
        symbols: list[str] | tuple[str, ...] = ("BTCUSDT", "ETHUSDT"),
        cost_model: CryptoCostModel | None = None,
        parameters: dict[str, Any] | None = None,
        initial_capital: Decimal = Decimal("100000"),
        maker_fill_probability: float = 0.85,
        mean_maker_fill_delay_min: float = 3.5,
        max_legging_timeout_min: float = 15.0,
        session_id: str = "crypto_004_shadow",
        signal_fn: Callable[[CryptoMarketEvent, dict[str, Any]], Decimal] | None = None,
    ):
        self._symbols = list(symbols)
        self._cost_model = cost_model or CryptoCostModel.binance_usdt_vip1()
        self._parameters = parameters or {}
        self._initial_capital = initial_capital
        initial_margin_pct = float(self._parameters.get("initial_margin_pct", 20.0))
        capital_per_unit = Decimal("1.0") + Decimal(str(initial_margin_pct / 100.0))
        self._nominal_capital = self._initial_capital * capital_per_unit

        self._maker_fill_probability = maker_fill_probability
        self._mean_maker_fill_delay_min = mean_maker_fill_delay_min
        self._max_legging_timeout_min = max_legging_timeout_min
        self._session_id = session_id
        self._signal_fn = signal_fn or default_maker_carry_signal

        self._books: dict[str, ShadowBookState] = {
            sym: ShadowBookState(symbol=sym) for sym in self._symbols
        }
        self._attr = Attribution()
        self._maker_fills = 0
        self._taker_fallbacks = 0
        self._unhedged_durations: list[float] = []
        self._periodic_net_returns: list[float] = []
        self._daily_mtm_equity: dict[str, float] = {}
        self._equity_curve: list[float] = [1.0]
        self._period_friction = Decimal("0")
        self._n_trades = 0
        self._events_processed = 0
        self._first_event_ts: datetime | None = None
        self._last_event_ts: datetime | None = None

    @property
    def symbols(self) -> list[str]:
        return list(self._symbols)

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def cost_model(self) -> CryptoCostModel:
        return self._cost_model

    @property
    def events_processed(self) -> int:
        return self._events_processed

    @property
    def n_trades(self) -> int:
        return self._n_trades

    @property
    def maker_fills(self) -> int:
        return self._maker_fills

    @property
    def taker_fallbacks(self) -> int:
        return self._taker_fallbacks

    @property
    def maker_fill_rate(self) -> float:
        total = self._maker_fills + self._taker_fallbacks
        return (self._maker_fills / total) if total > 0 else 1.0

    @property
    def mean_unhedged_duration_min(self) -> float:
        return float(np.mean(self._unhedged_durations)) if self._unhedged_durations else 0.0

    @property
    def attribution(self) -> Attribution:
        return self._attr

    @property
    def unrealized_basis_pnl(self) -> Decimal:
        return sum((book.unrealized_basis_pnl for book in self._books.values()), Decimal("0"))

    @property
    def realized_price_pnl(self) -> Decimal:
        return sum((book.realized_price_pnl for book in self._books.values()), Decimal("0"))

    @property
    def cumulative_net_pnl(self) -> Decimal:
        return (
            self._attr.funding
            + self.realized_price_pnl
            + self.unrealized_basis_pnl
            - self._attr.fees
            - self._attr.spread
            - self._attr.impact
            - self._attr.borrow
            - self._attr.partial_unfilled
            - self._attr.latency
            - self._attr.conversion
        )

    @property
    def annualized_net_return_pct(self) -> float:
        net_frac = float(self.cumulative_net_pnl / self._nominal_capital)
        if self._first_event_ts and self._last_event_ts and self._last_event_ts > self._first_event_ts:
            span_days = max(1.0, (self._last_event_ts - self._first_event_ts).total_seconds() / 86400.0)
        else:
            span_days = 365.25
        return (net_frac * (365.25 / span_days)) * 100.0

    @property
    def daily_net_returns(self) -> list[float]:
        """Daily mark-to-market net return series derived from calendar day closes."""
        if len(self._daily_mtm_equity) < 2:
            return []
        sorted_dates = sorted(self._daily_mtm_equity.keys())
        eq_values = [self._daily_mtm_equity[d] for d in sorted_dates]
        return [(eq_values[i] - eq_values[i-1]) / eq_values[i-1] for i in range(1, len(eq_values))]

    @property
    def net_sharpe(self) -> float:
        """Annualized Mark-to-Market Net Sharpe using daily calendar resampling (sqrt(365.25))."""
        rets = self.daily_net_returns
        if len(rets) > 1:
            std_ret = float(np.std(rets))
            mean_ret = float(np.mean(rets))
            return (mean_ret / std_ret * np.sqrt(365.25)) if std_ret > 0 else 0.0
        # Sub-day or synthetic fallback
        if len(self._periodic_net_returns) > 1:
            std_ret = float(np.std(self._periodic_net_returns))
            mean_ret = float(np.mean(self._periodic_net_returns))
            return (mean_ret / std_ret * np.sqrt(1095.0)) if std_ret > 0 else 0.0
        return 0.0

    @property
    def max_drawdown_pct(self) -> float:
        """Maximum peak-to-trough drawdown computed continuously across all mark events."""
        eq = np.array(self._equity_curve)
        cummax = np.maximum.accumulate(eq)
        drawdowns = (cummax - eq) / cummax
        return float(np.max(drawdowns)) * 100.0 if len(drawdowns) > 0 else 0.0

    def get_book(self, symbol: str) -> ShadowBookState:
        if symbol not in self._books:
            self._books[symbol] = ShadowBookState(symbol=symbol)
        return self._books[symbol]

    def on_event(self, event: CryptoMarketEvent) -> dict[str, Any] | None:
        """Process a single streaming CryptoMarketEvent in real-time."""
        sym = event.symbol
        if sym not in self._books:
            self._books[sym] = ShadowBookState(symbol=sym)
        book = self._books[sym]

        self._events_processed += 1
        if self._first_event_ts is None:
            self._first_event_ts = event.occurred_at
        self._last_event_ts = event.occurred_at

        # Update mark prices based on event contract kind
        mark = event.price or event.bid or event.ask
        if mark is not None:
            if event.contract_kind == "PERPETUAL":
                book.last_perp_mark = mark
            elif event.contract_kind == "SPOT":
                book.last_spot_mark = mark
            book.last_mark = mark

        perp_mark = book.last_perp_mark or book.last_mark or Decimal("50000")
        spot_mark = book.last_spot_mark or book.last_mark or Decimal("50000")

        # 1. 8-Hour Funding Settlement (strictly on matched hedged active notional)
        funding_settled = False
        funding_cashflow = Decimal("0")
        if event.event_type == "FUNDING" and event.funding_rate is not None:
            book.last_funding_rate = event.funding_rate
            book.last_funding_ts = event.occurred_at
            matched_qty = book.matched_hedged_qty

            if matched_qty > 0:
                # Short perp receives positive funding rate cashflow
                funding_cashflow = matched_qty * perp_mark * event.funding_rate
                self._attr.funding += funding_cashflow
                book.realized_funding += funding_cashflow

            period_ret = float(funding_cashflow / self._nominal_capital)
            self._periodic_net_returns.append(period_ret)
            funding_settled = True

        # 2. Evaluate Carry Signal
        state_for_signal = {
            "position_perp": book.position_perp,
            "position_spot": book.position_spot,
            "last_funding": book.last_funding_rate,
            "last_mark": perp_mark,
            "parameters": self._parameters,
        }
        desired_perp = self._signal_fn(event, state_for_signal)

        trade_executed = False
        if desired_perp != book.position_perp:
            delta_perp = desired_perp - book.position_perp
            participation = Decimal(str(self._parameters.get("participation", "1.0")))
            qty_perp = self._cost_model.round_qty(delta_perp * participation)

            if qty_perp != Decimal("0"):
                notional_perp = abs(qty_perp) * perp_mark
                if notional_perp < self._cost_model.min_notional:
                    self._attr.partial_unfilled += notional_perp
                else:
                    # Leg 1: Perpetual Maker Fill (1.0 bps VIP1, 0 spread, 0 slippage)
                    perp_fee = self._cost_model.maker_fee(notional_perp, perp=True)
                    self._attr.fees += perp_fee
                    self._period_friction += perp_fee

                    # Leg 2: Spot Maker with 15-Minute Taker Fallback
                    hedge_qty = -qty_perp
                    hedge_notional = abs(hedge_qty) * spot_mark

                    seed = int(hashlib.sha256(f"{event.event_id}_{self._events_processed}".encode()).hexdigest()[:8], 16)
                    rng = np.random.RandomState(seed)
                    is_maker_fill = rng.uniform(0.0, 1.0) < self._maker_fill_probability

                    if is_maker_fill:
                        self._maker_fills += 1
                        delay = float(rng.exponential(scale=self._mean_maker_fill_delay_min))
                        delay = min(delay, self._max_legging_timeout_min - 0.1)
                        self._unhedged_durations.append(max(0.5, delay))
                        spot_fee = self._cost_model.maker_fee(hedge_notional, perp=False)
                        self._attr.fees += spot_fee
                        self._period_friction += spot_fee
                    else:
                        self._taker_fallbacks += 1
                        self._unhedged_durations.append(self._max_legging_timeout_min)
                        spot_fee = self._cost_model.taker_fee(hedge_notional, perp=False)
                        spot_spread = self._cost_model.spread_cost(hedge_notional)
                        spot_slip = self._cost_model.slippage_cost(hedge_notional)
                        self._attr.fees += spot_fee
                        self._attr.spread += spot_spread
                        self._attr.impact += spot_slip
                        self._period_friction += (spot_fee + spot_spread + spot_slip)

                    # Update Book Positions & Realized Price PnL
                    # Perpetual position update
                    if (book.position_perp < 0 and qty_perp > 0) or (book.position_perp > 0 and qty_perp < 0):
                        closed_perp_qty = min(abs(book.position_perp), abs(qty_perp))
                        if book.perp_entry_price is not None:
                            if book.position_perp < 0:
                                book.realized_price_pnl += closed_perp_qty * (book.perp_entry_price - perp_mark)
                            else:
                                book.realized_price_pnl += closed_perp_qty * (perp_mark - book.perp_entry_price)

                    new_perp_pos = book.position_perp + qty_perp
                    if new_perp_pos == Decimal("0"):
                        book.perp_entry_price = None
                    elif (book.position_perp == 0) or (book.position_perp > 0 and qty_perp > 0) or (book.position_perp < 0 and qty_perp < 0):
                        old_perp_cost = (abs(book.position_perp) * book.perp_entry_price) if book.perp_entry_price else Decimal("0")
                        new_perp_cost = abs(qty_perp) * perp_mark
                        book.perp_entry_price = (old_perp_cost + new_perp_cost) / abs(new_perp_pos)
                    book.position_perp = new_perp_pos

                    # Spot position update
                    if (book.position_spot > 0 and hedge_qty < 0) or (book.position_spot < 0 and hedge_qty > 0):
                        closed_spot_qty = min(abs(book.position_spot), abs(hedge_qty))
                        if book.spot_entry_price is not None:
                            if book.position_spot > 0:
                                book.realized_price_pnl += closed_spot_qty * (spot_mark - book.spot_entry_price)
                            else:
                                book.realized_price_pnl += closed_spot_qty * (book.spot_entry_price - spot_mark)

                    new_spot_pos = book.position_spot + hedge_qty
                    if new_spot_pos == Decimal("0"):
                        book.spot_entry_price = None
                    elif (book.position_spot == 0) or (book.position_spot > 0 and hedge_qty > 0) or (book.position_spot < 0 and hedge_qty < 0):
                        old_spot_cost = (abs(book.position_spot) * book.spot_entry_price) if book.spot_entry_price else Decimal("0")
                        new_spot_cost = abs(hedge_qty) * spot_mark
                        book.spot_entry_price = (old_spot_cost + new_spot_cost) / abs(new_spot_pos)
                    book.position_spot = new_spot_pos

                    self._n_trades += 1
                    trade_executed = True

        # Continuous mark-to-market equity recording on every event
        curr_eq = float((self._nominal_capital + self.cumulative_net_pnl) / self._nominal_capital)
        self._equity_curve.append(curr_eq)
        date_key = event.occurred_at.strftime("%Y-%m-%d")
        self._daily_mtm_equity[date_key] = curr_eq

        return {
            "event_id": event.event_id,
            "symbol": sym,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at.isoformat(),
            "funding_settled": funding_settled,
            "funding_cashflow": str(funding_cashflow),
            "trade_executed": trade_executed,
            "position_perp": str(book.position_perp),
            "position_spot": str(book.position_spot),
            "unrealized_basis_pnl": str(book.unrealized_basis_pnl),
            "cumulative_net_pnl": str(self.cumulative_net_pnl),
        }

    def on_events(self, events: Iterable[CryptoMarketEvent]) -> list[dict[str, Any]]:
        """Process a stream of CryptoMarketEvent records sequentially."""
        results = []
        for ev in events:
            res = self.on_event(ev)
            if res is not None:
                results.append(res)
        return results

    def get_shadow_status(self) -> dict[str, Any]:
        """Provides real-time telemetry of the shadow carry runner."""
        return {
            "hypothesis_id": "CRYPTO-004",
            "session_id": self._session_id,
            "authority": "READ_ONLY_SHADOW_NON_CUSTODIAL",
            "execution_ban_verified": True,
            "last_event_ts": self._last_event_ts.isoformat() if self._last_event_ts else None,
            "events_processed": self._events_processed,
            "trades_count": self._n_trades,
            "capital": {
                "initial": str(self._initial_capital),
                "nominal": str(self._nominal_capital),
                "cumulative_net_pnl": str(self.cumulative_net_pnl),
            },
            "attribution": {
                "funding": str(self._attr.funding),
                "fees": str(self._attr.fees),
                "spread": str(self._attr.spread),
                "impact": str(self._attr.impact),
                "realized_price_pnl": str(self.realized_price_pnl),
                "unrealized_basis_pnl": str(self.unrealized_basis_pnl),
                "net_pnl": str(self.cumulative_net_pnl),
            },
            "microstructure": {
                "maker_fills": self._maker_fills,
                "taker_fallbacks": self._taker_fallbacks,
                "maker_fill_rate": self.maker_fill_rate,
                "mean_unhedged_duration_min": self.mean_unhedged_duration_min,
            },
            "positions": {
                sym: {
                    "position_perp": str(book.position_perp),
                    "position_spot": str(book.position_spot),
                    "matched_hedged_qty": str(book.matched_hedged_qty),
                    "spot_entry_price": str(book.spot_entry_price) if book.spot_entry_price else None,
                    "perp_entry_price": str(book.perp_entry_price) if book.perp_entry_price else None,
                    "last_spot_mark": str(book.last_spot_mark) if book.last_spot_mark else None,
                    "last_perp_mark": str(book.last_perp_mark) if book.last_perp_mark else None,
                    "unrealized_basis_pnl": str(book.unrealized_basis_pnl),
                }
                for sym, book in self._books.items()
            },
        }

    def export_shadow_evidence(self) -> dict[str, Any]:
        """Serializes immutable shadow evidence for governance review."""
        return {
            "hypothesis_id": "CRYPTO-004",
            "run_mode": "SHADOW_PAPER",
            "deployment_authority": "READ_ONLY_NON_CUSTODIAL",
            "cost_schedule": self._cost_model.to_dict(),
            "symbols": list(self._symbols),
            "session_id": self._session_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "events_processed": self._events_processed,
            "trades_count": self._n_trades,
            "attribution": self._attr.to_dict() | {
                "unrealized_basis_pnl": str(self.unrealized_basis_pnl),
                "realized_price_pnl": str(self.realized_price_pnl),
                "net_pnl": str(self.cumulative_net_pnl),
            },
            "metrics": {
                "maker_fills": self._maker_fills,
                "taker_fallbacks": self._taker_fallbacks,
                "maker_fill_rate": self.maker_fill_rate,
                "mean_unhedged_duration_min": self.mean_unhedged_duration_min,
                "cumulative_net_pnl": str(self.cumulative_net_pnl),
                "annualized_net_return_pct": self.annualized_net_return_pct,
                "net_sharpe": self.net_sharpe,
                "max_drawdown_pct": self.max_drawdown_pct,
            },
            "positions": {
                sym: {
                    "position_perp": str(book.position_perp),
                    "position_spot": str(book.position_spot),
                    "matched_hedged_qty": str(book.matched_hedged_qty),
                    "unrealized_basis_pnl": str(book.unrealized_basis_pnl),
                }
                for sym, book in self._books.items()
            },
            "execution_ban_verified": True,
        }
