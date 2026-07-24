"""Live paper session — closed-bar ingress through TITAN runtime.

Architecture:
  Nautilus subscribes to bars (data ingress only; no exec client).
  Each closed bar becomes a MarketEvent → RuntimeEvaluator → MultiTimeframeRuntime
  → TradeProposal → TradeIntent → PaperTradingEngine.submit_intent() → IBKR adapter.
  No strategy or script calls submit_order directly.
"""

import logging
import os
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

import titan.strategies.registrations  # noqa: F401
from nautilus_trader.adapters.interactive_brokers.common import IB
from nautilus_trader.adapters.interactive_brokers.config import (
    IBMarketDataTypeEnum,
    InteractiveBrokersDataClientConfig,
    InteractiveBrokersInstrumentProviderConfig,
    SymbologyMethod,
)
from nautilus_trader.adapters.interactive_brokers.factories import (
    InteractiveBrokersLiveDataClientFactory,
)
from nautilus_trader.config import LoggingConfig, StrategyConfig, TradingNodeConfig, LiveDataEngineConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy

from titan._core import Money, RiskConfig, TradeIntent
from titan.execution.engine import PaperConfig, PaperTradingEngine
from titan.runtime.events import MarketEvent, StrategyDefinition, TriggerSpec
from titan.runtime.evaluator import RuntimeEvaluator
from titan.strategies.multitimeframe_runtime import MultiTimeframeRuntime
from titan.strategies.registry import get_registry
from titan.strategies.timeframes import Timeframe

log = logging.getLogger("titan.paper")

# ---------- config ----------

IB_HOST = "127.0.0.1"
IB_PORT = 7497
DATA_CLIENT_ID = int(os.getenv("IB_DATA_CLIENT_ID", "1201"))
ACCOUNT_ID = os.getenv("TWS_ACCOUNT", "DUQ284074")
AUTO_STOP_SECS = int(os.getenv("AUTO_STOP_SECS", "0"))

INSTRUMENT_CONFIG = {
    "SPY.ARCA": {
        "price_type": "LAST",
        "timeframes": ["5-MINUTE", "15-MINUTE", "1-HOUR", "1-DAY"],
    },
}

NAUTILUS_TO_TITAN_TIMEFRAME = {
    "5-MINUTE": Timeframe.FIVE_MINUTES,
    "15-MINUTE": Timeframe.FIFTEEN_MINUTES,
    "1-HOUR": Timeframe.ONE_HOUR,
    "1-DAY": Timeframe.ONE_DAY,
}

STRATEGY_IDS = [
    "time-series-momentum",
    "ma-crossover",
    "mean-reversion",
    "volatility-regime",
    "dual-ma",
]

STRATEGY_PARAMS = {
    "time-series-momentum": {"lookback": 20},
    "ma-crossover": {"fast": 5, "slow": 20},
    "mean-reversion": {"window": 20, "entry_z": -2.0, "exit_z": -0.5},
    "volatility-regime": {"vol_window": 20, "median_window": 60, "vol_multiple": 1.0},
    "dual-ma": {"fast": 5, "slow": 20},
}


def _bar_type_str(inst_id: str, timeframe: str, price_type: str) -> str:
    return f"{inst_id}-{timeframe}-{price_type}-EXTERNAL"


# ---------- startup summary ----------

def _print_qualification_summary():
    reg = get_registry()
    qualified: dict[str, list[str]] = defaultdict(list)
    for sid in STRATEGY_IDS:
        try:
            r = reg.get(sid)
            for tf, _ in r.qualified_variants:
                qualified[tf.value].append(sid)
        except KeyError:
            pass

    print("\n========== TITAN Paper Qualification Summary ==========")
    for tf_name in ("1d", "1h", "15m", "5m"):
        strs = qualified.get(tf_name, [])
        label = {"1d": "Daily", "1h": "1 Hour", "15m": "15 Minute", "5m": "5 Minute"}.get(tf_name, tf_name)
        if strs:
            print(f"  Qualified  [{label}]: {', '.join(sorted(strs))}")
        else:
            print(f"  BLOCKED    [{label}]: (none qualified)")
    print("========================================================\n")


# ---------- nautilus strategy (data ingress only) ----------

class DataIngestConfig(StrategyConfig, kw_only=True, frozen=True):
    pass


class DataIngestStrategy(Strategy):
    """Minimal Nautilus strategy for closed-bar ingress only.

    Every bar becomes a MarketEvent dispatched through the TITAN runtime.
    No orders are placed through Nautilus.
    """

    def __init__(self, config: DataIngestConfig) -> None:
        super().__init__(config)
        self._evaluator: RuntimeEvaluator | None = None
        self._engine: PaperTradingEngine | None = None
        self._counter = 0
        self._counts = {"qualified": 0, "blocked": 0, "submitted": 0, "filled": 0}
        self._last_bar_time: dict[str, float] = {}
        self._stale_warn_secs = 300

    def set_titan(self, evaluator: RuntimeEvaluator, engine: PaperTradingEngine) -> None:
        self._evaluator = evaluator
        self._engine = engine

    def on_start(self) -> None:
        for inst_id, cfg in INSTRUMENT_CONFIG.items():
            iid = InstrumentId.from_str(inst_id)
            if self.cache.instrument(iid) is None:
                self.log.error(f"Instrument not found: {inst_id}")
                self.stop()
                return
            for tf in cfg["timeframes"]:
                bt = BarType.from_str(_bar_type_str(inst_id, tf, cfg["price_type"]))
                self.subscribe_bars(bt)
                self.log.info(f"[ingress] subscribed {bt}")

    def on_bar(self, bar: Bar) -> None:
        if self._evaluator is None or self._engine is None:
            return

        inst_id = str(bar.bar_type.instrument_id)
        tf_raw = str(bar.bar_type.spec.timedelta)

        titan_tf = self._nautilus_tf_to_titan(bar)
        if titan_tf is None:
            self.log.warning(f"[ingress] unsupported timeframe: {tf_raw}")
            return

        now = time.time()
        self._last_bar_time[f"{inst_id}/{titan_tf.value}"] = now

        self._counter += 1
        ts = datetime.now(timezone.utc)
        close = float(bar.close.as_double())
        event = MarketEvent(
            message_id=f"bar-{self._counter}",
            causation_id=f"bar-{inst_id}-{titan_tf.value}",
            correlation_id=f"corr-{self._counter}",
            occurred_at=ts,
            received_at=ts,
            schema_version=1,
            source="ibkr",
            event_type="BarClosed",
            instrument_id=inst_id,
            payload={
                "timeframe": titan_tf.value,
                "close": close,
                "open": float(bar.open.as_double()) if bar.open else close,
                "high": float(bar.high.as_double()) if bar.high else close,
                "low": float(bar.low.as_double()) if bar.low else close,
                "volume": int(bar.volume.as_double()) if bar.volume else 0,
            },
            payload_digest="",
        )

        result = self._evaluator.on_market_event(event)

        for proposal in result.proposals:
            self._counts["qualified"] += 1
            intent = TradeIntent(
                strategy_id=proposal.strategy_id,
                strategy_package_digest="",
                account_id=self._engine.config.account_id,
                instrument_id=proposal.instrument_id,
                side=proposal.side,
                quantity=str(int(proposal.quantity)) if proposal.quantity else "0",
                order_type="MARKET",
                time_in_force="DAY",
                risk_profile_version="1.0",
                market_data_timestamp=datetime.now(timezone.utc).isoformat(),
                price=str(proposal.price) if proposal.price else None,
            )
            order_result = self._engine.submit_intent(intent, correlation_id=event.correlation_id)
            if order_result.accepted:
                self._counts["submitted"] += 1
                bid = str(order_result.broker_order_id.id) if order_result.broker_order_id else "?"
                self.log.info(
                    f"[order] {proposal.strategy_id} | {proposal.timeframe} "
                    f"| {proposal.side} {proposal.quantity} @ {proposal.price} "
                    f"| ib_order_id={bid}"
                )
            else:
                self.log.info(
                    f"[order] {proposal.strategy_id} | {proposal.timeframe} "
                    f"| {proposal.side} rejected: {order_result.rejection_reason}"
                )

    @staticmethod
    def _nautilus_tf_to_titan(bar: Bar) -> Timeframe | None:
        td = bar.bar_type.spec.timedelta
        for nautilus_key, titan_tf in NAUTILUS_TO_TITAN_TIMEFRAME.items():
            if str(td) == nautilus_key or _timedelta_matches(td, titan_tf):
                return titan_tf
        return None


def _timedelta_matches(td, titan_tf: Timeframe) -> bool:
    from datetime import timedelta
    mapping = {
        Timeframe.FIVE_MINUTES: timedelta(minutes=5),
        Timeframe.FIFTEEN_MINUTES: timedelta(minutes=15),
        Timeframe.ONE_HOUR: timedelta(hours=1),
        Timeframe.ONE_DAY: timedelta(days=1),
    }
    return td == mapping.get(titan_tf)


# ---------- TITAN runtime setup ----------

def _build_titan_runtime():
    risk_config = RiskConfig(
        list(INSTRUMENT_CONFIG.keys()),
        Money("50000", "USD"),
        1000, 5000,
        Money("100000", "USD"),
        0.10,
        Money("5000", "USD"),
        5000, 100,
    )

    try:
        from titan.execution.ibkr_adapter import IBKRPaperAdapter
        adapter = IBKRPaperAdapter()
        log.info("adapter: IBKRPaperAdapter (live IBKR paper)")
    except Exception:
        from titan.execution.simulated_adapter import SimulatedAdapter
        log.warning("adapter: IBKR unavailable, using SimulatedAdapter")
        adapter = SimulatedAdapter()

    engine = PaperTradingEngine(
        PaperConfig(
            risk_config=risk_config,
            currency="USD",
            starting_capital=os.getenv("EQUITY", "100000"),
            account_id=os.getenv("TWS_ACCOUNT", "paper"),
            client_order_prefix="tit-paper-",
        ),
        adapter,
    )

    multirt = MultiTimeframeRuntime()
    evaluator = RuntimeEvaluator()

    for sid in STRATEGY_IDS:
        params = STRATEGY_PARAMS[sid]
        for tf in (Timeframe.FIVE_MINUTES, Timeframe.FIFTEEN_MINUTES, Timeframe.ONE_HOUR, Timeframe.ONE_DAY):
            evaluator.register(StrategyDefinition(
                strategy_id=sid,
                trigger=TriggerSpec(event_type="BarClosed", timeframe=tf),
                params=params,
            ))
            multirt.register(StrategyDefinition(
                strategy_id=sid,
                trigger=TriggerSpec(event_type="BarClosed", timeframe=tf),
                params=params,
            ))

    evaluator.set_producer(multirt)
    return evaluator, engine, multirt


# ---------- main ----------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    _print_qualification_summary()

    inst_provider = InteractiveBrokersInstrumentProviderConfig(
        symbology_method=SymbologyMethod.IB_SIMPLIFIED,
        load_ids=frozenset(INSTRUMENT_CONFIG.keys()),
    )

    config_node = TradingNodeConfig(
        trader_id="TITAN-001",
        logging=LoggingConfig(log_level="INFO"),
        data_clients={
            IB: InteractiveBrokersDataClientConfig(
                ibg_host=IB_HOST,
                ibg_port=IB_PORT,
                ibg_client_id=DATA_CLIENT_ID,
                handle_revised_bars=False,
                use_regular_trading_hours=False,
                market_data_type=IBMarketDataTypeEnum.REALTIME,
                instrument_provider=inst_provider,
            ),
        },
        data_engine=LiveDataEngineConfig(
            time_bars_timestamp_on_close=False,
            validate_data_sequence=True,
        ),
        timeout_connection=90.0,
        timeout_reconciliation=5.0,
        timeout_portfolio=5.0,
        timeout_disconnection=5.0,
        timeout_post_stop=2.0,
    )

    evaluator, engine, multirt = _build_titan_runtime()

    strategy = DataIngestStrategy(config=DataIngestConfig())
    strategy.set_titan(evaluator, engine)

    node = TradingNode(config=config_node)
    node.trader.add_strategy(strategy)
    node.add_data_client_factory(IB, InteractiveBrokersLiveDataClientFactory)
    node.build()

    if AUTO_STOP_SECS > 0:
        def stop():
            time.sleep(AUTO_STOP_SECS)
            log.info(f"Counts: qualified={strategy._counts['qualified']} "
                     f"blocked={strategy._counts['blocked']} "
                     f"submitted={strategy._counts['submitted']} "
                     f"filled={strategy._counts['filled']}")
            node.stop()
        threading.Thread(target=stop, daemon=True).start()

    try:
        node.run()
    finally:
        node.dispose()


if __name__ == "__main__":
    main()
