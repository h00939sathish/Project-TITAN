"""Pipeline orchestrator — wires all phases into one call per tick."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from titan._core import TradeIntent
from titan.strategies.bridge import StrategyBridge
from titan.strategies.ensemble import WeightedEnsemble, StrategyVote
from titan.strategies.filters import SignalFilter
from titan.strategies.lifecycle import LifecycleEngine
from titan.strategies.manifest import TradeManifest, make_manifest
from titan.strategies.allocator import MetaAllocator
from titan.strategies.regime.base import RegimeDetector, RegimeState
from titan.strategies.shadow import ShadowDeployer, ShadowTrade
from titan.strategies.sizing import position_size


@dataclass
class PipelineResult:
    intent: TradeIntent | None
    manifest: TradeManifest | None
    ensemble: dict | None
    regime: RegimeState | None
    suppressed_by: str | None  # "filter" | "ensemble" | None


@dataclass
class StrategySlot:
    strategy_id: str
    params: dict
    weight: float = 1.0


class PipelineOrchestrator:
    """Chains: RegimeDetector → StrategyPool → Filters → Ensemble → Sizing → Manifest.

    One orchestrator per tick.  Owns all strategy bridges and pipeline state.
    """

    def __init__(
        self,
        strategies: list[StrategySlot],
        account_id: str = "paper-1",
        order_size: int = 1,
        risk_profile_version: str = "1.0",
        regime_detector: RegimeDetector | None = None,
        suppress_regimes: tuple[str, ...] = ("HIGH_VOL",),
        regime_size_multipliers: dict[str, float] | None = None,
        filters: list[SignalFilter] | None = None,
        ensemble: WeightedEnsemble | None = None,
        lifecycle: LifecycleEngine | None = None,
        allocator: MetaAllocator | None = None,
        shadow: ShadowDeployer | None = None,
        equity: float = 100000.0,
    ):
        self.account_id = account_id
        self.order_size = order_size
        self.risk_profile_version = risk_profile_version
        self.regime_detector = regime_detector
        self.suppress_regimes = suppress_regimes
        self.regime_size_multipliers = regime_size_multipliers or {
            "LOW_VOL": 1.5,
            "MODERATE_VOL": 1.0,
            "HIGH_VOL": 0.25,
        }

        self.filters = filters or []
        self.ensemble = ensemble or WeightedEnsemble()
        self.lifecycle = lifecycle
        self.allocator = allocator
        self.shadow = shadow
        self.equity = equity

        self._bridges: dict[str, StrategyBridge] = {}
        self._current_regime: RegimeState | None = None
        self._closes: dict[str, deque[float]] = {}
        self._htf_closes: dict[str, deque[float]] = {}
        self._entry_prices: dict[tuple[str, str], float] = {}
        self._last_result: PipelineResult | None = None

        for s in strategies:
            self._bridges[s.strategy_id] = StrategyBridge(
                strategy_id=s.strategy_id,
                strategy_params=s.params,
                account_id=account_id,
                order_size=order_size,
                risk_profile_version=risk_profile_version,
                regime_detector=None,  # pipeline handles regime centrally
            )
            self._closes[s.strategy_id] = deque(maxlen=1000)
            self._htf_closes[s.strategy_id] = deque(maxlen=1000)
            if self.lifecycle:
                self.lifecycle.register(s.strategy_id)
            if self.allocator:
                self.allocator.register(s.strategy_id)

    def warmup(self, instrument: str, prices: list[float], htf_prices: list[float] | None = None) -> None:
        for sid, bridge in self._bridges.items():
            bridge.warmup(instrument, prices)
            self._closes[sid].extend(prices)
            if htf_prices:
                self._htf_closes[sid].extend(htf_prices)
        if self.regime_detector:
            for p in prices:
                self._current_regime = self.regime_detector.update(p)

    def set_position(self, instrument: str, has_position: bool) -> None:
        for bridge in self._bridges.values():
            bridge.set_position(instrument, has_position)

    def run(
        self, instrument: str, price: float, bar_date: str | None = None
    ) -> PipelineResult:
        suppressed_by = None

        # 1. Regime detection
        if self.regime_detector:
            self._current_regime = self.regime_detector.update(price)

        # Determine effective ensemble thresholds and position size multiplier
        if self._current_regime:
            r = self._current_regime.regime
            buy_th = {"LOW_VOL": 0.4, "HIGH_VOL": 0.8}.get(r, 0.6)
            sell_th = {"LOW_VOL": -0.4, "HIGH_VOL": -0.8}.get(r, -0.6)
        else:
            buy_th, sell_th = 0.6, -0.6

        # 2. Collect votes from all strategies
        votes: list[StrategyVote] = []
        raw_signals: dict[str, str | None] = {}
        for sid, bridge in self._bridges.items():
            intent = bridge.on_price(instrument, price, bar_date)
            side = intent.side if intent else None
            raw_signals[sid] = side
            if side:
                self._closes[sid].append(price)
                confidence = 1.0 if side == "BUY" else -1.0
                weight = self.allocator.get_weight(sid) if self.allocator else 1.0
                votes.append(StrategyVote(strategy_id=sid, vote=side, confidence=confidence, weight=weight))

        # 3. Filters
        for f in self.filters:
            htf = list(self._htf_closes.values())[0] if self._htf_closes else None
            if not f.check(price, htf):
                suppressed_by = "filter"
                break

        # 4. Ensemble decision with regime-adaptive thresholds
        old_buy = self.ensemble.buy_threshold
        old_sell = self.ensemble.sell_threshold
        self.ensemble.buy_threshold = buy_th
        self.ensemble.sell_threshold = sell_th
        ensemble_result = self.ensemble.decide(votes)
        self.ensemble.buy_threshold = old_buy
        self.ensemble.sell_threshold = old_sell
        decision = ensemble_result.decision
        ensemble_score = ensemble_result.score

        if decision == "NO_TRADE":
            suppressed_by = suppressed_by or "ensemble"

        # 5. ATR position sizing — scaled by regime
        all_closes = list(list(self._closes.values())[0]) if self._closes else []
        qty = position_size(
            equity=self.equity,
            closes=all_closes,
            risk_per_trade_pct=0.5,
            min_shares=1,
            max_shares=self.order_size,
        )
        mult = 1.0
        if self._current_regime and self.regime_size_multipliers:
            mult = self.regime_size_multipliers.get(self._current_regime.regime, 1.0)
        qty = max(1, int(qty * mult))

        # 6. Build intent
        intent = None
        if decision in ("BUY", "SELL") and not suppressed_by:
            intent = TradeIntent(
                strategy_id="pipeline",
                strategy_package_digest="pipeline-v1",
                account_id=self.account_id,
                instrument_id=instrument,
                side=decision,
                quantity=str(qty),
                order_type="LIMIT",
                time_in_force="DAY",
                risk_profile_version=self.risk_profile_version,
                market_data_timestamp=datetime.now(timezone.utc).isoformat(),
                price=str(price),
            )

        # 7. Manifest
        regime_dict = None
        if self._current_regime:
            regime_dict = {
                "regime": self._current_regime.regime,
                "confidence": self._current_regime.confidence,
                "volatility": self._current_regime.volatility,
            }

        manifest = make_manifest(
            strategy_id="pipeline",
            strategy_version="pipeline-v1",
            strategy_params={"instrument": instrument},
            instrument_id=instrument,
            side=decision if not suppressed_by else "NO_TRADE",
            quantity=str(qty),
            price=str(price),
            regime=regime_dict,
            ensemble={
                "score": ensemble_score,
                "decision": decision,
                "votes_count": len(votes),
                "votes": ensemble_result.votes,
            },
            risk={"atr_size": qty},
        )

        # 8. Lifecycle + Allocator tracking with real PnL
        if self.lifecycle and intent:
            self.lifecycle.update_health("pipeline", trades_count=1)
            self.lifecycle.auto_suspend("pipeline")

        if self.allocator and intent:
            key = ("pipeline", instrument)
            pnl = 0.0
            if decision == "BUY":
                self._entry_prices[key] = price
            elif decision == "SELL" and key in self._entry_prices:
                entry_p = self._entry_prices.pop(key)
                pnl = (price - entry_p) / max(entry_p, 1e-10)
            self.allocator.record_trade("pipeline", pnl, decision)
            self.allocator.rebalance()


        # 9. Shadow record
        if self.shadow and intent:
            self.shadow.record(ShadowTrade(
                strategy_id="pipeline",
                instrument_id=instrument,
                side=decision,
                quantity=str(qty),
                price=price,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))

        self._last_result = PipelineResult(
            intent=intent,
            manifest=manifest,
            ensemble=ensemble_result.__dict__ if ensemble_result else None,
            regime=self._current_regime,
            suppressed_by=suppressed_by,
        )
        return self._last_result

    @property
    def last_result(self) -> PipelineResult | None:
        return self._last_result
