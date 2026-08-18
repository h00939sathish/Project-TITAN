"""Live paper session — closed-bar ingress through TITAN runtime.

Architecture:
  Nautilus subscribes to bars (data ingress only; no exec client).
  Each closed bar becomes a MarketEvent → RuntimeEvaluator → MultiTimeframeRuntime
  → TradeProposal → TradeIntent → PaperTradingEngine.submit_intent() → IBKR adapter.
  No strategy or script calls submit_order directly.
"""

import logging
import os
import subprocess
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

from titan._core import ContractType, Instrument, InstrumentId as TitanInstrumentId, Money, RiskConfig, TradeIntent
from titan.execution.engine import PaperConfig, PaperTradingEngine
from titan.research.db import ResearchDB, DEFAULT_DB_PATH
from titan.research.shadow import ShadowRunner
from titan.runtime.events import MarketEvent, StrategyDefinition, TriggerSpec
from titan.runtime.evaluator import RuntimeEvaluator
from titan.strategies.bar_aggregator import BarAggregator
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
    "SPY=STK.ARCA": {
        "price_type": "LAST",
        "timeframes": ["5-MINUTE", "15-MINUTE", "1-HOUR", "1-DAY"],
    },
    "QQQ=STK.NASDAQ": {
        "price_type": "LAST",
        "timeframes": ["5-MINUTE", "15-MINUTE", "1-HOUR", "1-DAY"],
    },
    "EUR.USD=CASH.IDEALPRO": {
        "price_type": "MIDPOINT",
        "timeframes": ["5-MINUTE", "15-MINUTE", "1-HOUR"],
    },
    "GBP.USD=CASH.IDEALPRO": {
        "price_type": "MIDPOINT",
        "timeframes": ["5-MINUTE", "15-MINUTE", "1-HOUR"],
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

# 4h-shadow candidates: strategies whose native edge is 4h, fed by aggregating
# the session's existing 1h bars (ADR-024 Track 1). Kept OUT of STRATEGY_IDS
# so the runtime never evaluates them at 5m-1h (whips). Each candidate gets a
# ShadowRunner entry; fills are simulated and logged to shadow_events.
SHADOW_4H_CANDIDATES = {
    "traderdev-ema9-vwap": {
        "params": {"ema_period": 3, "vwap_period": 20,
                   "atr_period": 5, "trail_mult": 2.0},
        "instruments": ["EURUSD", "GBPUSD"],
    },
}


def _paper_instruments() -> dict[str, Instrument]:
    """Return the canonical TITAN contracts for the configured data ingress."""
    return {
        "SPY=STK.ARCA": Instrument(
            TitanInstrumentId("SPY", "ARCA"), "0.01", 1, "1.0",
            ContractType.Stock, "USD", 2,
        ),
        "QQQ=STK.NASDAQ": Instrument(
            TitanInstrumentId("QQQ", "NASDAQ"), "0.01", 1, "1.0",
            ContractType.Stock, "USD", 2,
        ),
        "EUR.USD=CASH.IDEALPRO": Instrument(
            TitanInstrumentId("EURUSD", "IDEALPRO"), "0.0001", 1000, "1.0",
            ContractType.Forex, "EUR", 5,
        ),
        "GBP.USD=CASH.IDEALPRO": Instrument(
            TitanInstrumentId("GBPUSD", "IDEALPRO"), "0.0001", 1000, "1.0",
            ContractType.Forex, "GBP", 5,
        ),
    }


def _start_paper_engine(engine: PaperTradingEngine) -> None:
    """Register canonical contracts before the fail-closed broker synchronization."""
    for instrument_id, instrument in _paper_instruments().items():
        engine.register_instrument(instrument, instrument_id)
    engine.start(sync_from_broker=True)


def _bar_type_str(inst_id: str, timeframe: str, price_type: str) -> str:
    return f"{inst_id}-{timeframe}-{price_type}-EXTERNAL"


# ---------- startup summary ----------

def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "?"


def _print_qualification_summary():
    reg = get_registry()
    qualified: dict[str, list[str]] = defaultdict(list)
    total_qf = 0
    for sid in STRATEGY_IDS:
        try:
            r = reg.get(sid)
            for tf, _ in r.qualified_variants:
                qualified[tf.value].append(sid)
                total_qf += 1
        except KeyError:
            pass

    print(f"\n========== TITAN Runtime — Paper Session ==========")
    print(f"  Git SHA:       {_git_sha()}")
    print(f"  Account:       {ACCOUNT_ID}")
    print(f"  Instruments:   {', '.join(INSTRUMENT_CONFIG.keys())}")
    print(f"  Strategies:    {len(STRATEGY_IDS)} registered, {total_qf} qualified variants")
    print("")
    for tf_name in ("1d", "1h", "15m", "5m"):
        strs = qualified.get(tf_name, [])
        label = {"1d": "Daily", "1h": "1 Hour", "15m": "15 Minute", "5m": "5 Minute"}.get(tf_name, tf_name)
        if strs:
            for s in sorted(strs):
                print(f"  {s:25s} [{label:10s}] QUALIFIED")
        else:
            print(f"  {'(none)':25s} [{label:10s}] BLOCKED")
    print("====================================================\n")


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
        # ADR-024 Track 1: 4h shadow — aggregator + shadow runner
        self._shadow_runner: ShadowRunner | None = None
        self._aggregators: dict[str, BarAggregator] = {}

    def set_titan(self, evaluator: RuntimeEvaluator, engine: PaperTradingEngine) -> None:
        self._evaluator = evaluator
        self._engine = engine
        if SHADOW_4H_CANDIDATES:
            db_path = os.getenv("TITAN_RESEARCH_DB", str(DEFAULT_DB_PATH))
            self._shadow_runner = ShadowRunner(
                db_path=db_path,
                session_id=f"ibkr-{os.getpid()}",
            )
            for sid, cfg in SHADOW_4H_CANDIDATES.items():
                self._shadow_runner.add_strategy(sid, cfg["params"])
                for inst in cfg["instruments"]:
                    self._aggregators[f"{sid}|{inst}"] = BarAggregator(None)
            log.info(f"[shadow-4h] candidates: {list(SHADOW_4H_CANDIDATES)} -> shadow_events")
        else:
            log.info("[shadow-4h] no 4h shadow candidates configured")

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

        self._feed_4h_shadow(inst_id, titan_tf, ts, event.payload)

        for proposal in result.proposals:
            if proposal.producer_kind == "shadow":
                self._counts["shadow"] += 1
                self.log.info(
                    f"[shadow] {proposal.strategy_id} | {proposal.timeframe} "
                    f"| {proposal.side} {proposal.quantity} @ {proposal.price}"
                )
                
                # Write to ResearchDB shadow ledger
                db_path = os.getenv("TITAN_RESEARCH_DB", str(DEFAULT_DB_PATH))
                db = ResearchDB(db_path)
                try:
                    db.log_shadow_event(
                        strategy_id=proposal.strategy_id,
                        event_type="PROPOSAL",
                        event_data={
                            "instrument_id": str(proposal.instrument_id),
                            "side": proposal.side,
                            "quantity": proposal.quantity,
                            "price": proposal.price,
                            "timeframe": proposal.timeframe
                        },
                        timestamp=datetime.now(timezone.utc).isoformat()
                    )
                except Exception as e:
                    self.log.error(f"Failed to log shadow proposal to ResearchDB: {e}")
                finally:
                    db.close()
                continue

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
                certificate_ref=self._load_certificate(proposal.strategy_id),
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

    def _feed_4h_shadow(self, inst_id: str, titan_tf: Timeframe,
                        ts: datetime, payload: dict) -> None:
        """ADR-024 Track 1: aggregate 1h bars into 4h and feed shadow runner.

        Only 1h bars feed the aggregator. When a complete 4h bucket closes,
        forward the synthesized 4h bar to ShadowRunner.on_price, which
        simulates fills and logs them to shadow_events. The qualified runtime
        and all non-1h timeframes are completely unaffected.
        """
        if self._shadow_runner is None or titan_tf != Timeframe.ONE_HOUR:
            return
        for sid, cfg in SHADOW_4H_CANDIDATES.items():
            if inst_id not in cfg["instruments"]:
                continue
            agg = self._aggregators.get(f"{sid}|{inst_id}")
            if agg is None:
                continue
            ts_dt = ts if isinstance(ts, datetime) else None
            completed = agg.on_1h_bar(
                inst_id,
                ts_dt,
                payload.get("open", payload.get("close", 0.0)),
                payload.get("high", payload.get("close", 0.0)),
                payload.get("low", payload.get("close", 0.0)),
                payload.get("close", 0.0),
                payload.get("volume", 0),
            )
            for bar4h in completed:
                self._shadow_runner.on_price(
                    inst_id,
                    bar4h["close"],
                    bar_date=bar4h["timestamp"],
                    bar=bar4h,
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

    EXEC_CLIENT_ID = int(os.getenv("IB_EXEC_CLIENT_ID", "1202"))
    try:
        from titan.execution.ibkr_adapter import IBKRPaperAdapter
        adapter = IBKRPaperAdapter(client_id=EXEC_CLIENT_ID)
        log.info(f"adapter: IBKRPaperAdapter (live IBKR paper, client_id={EXEC_CLIENT_ID})")
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

    # ADR-022 transition: these strategies were previously qualified by baked-in
    # registry variants; qualification is now gate-only. Route them through the
    # watchlist so they keep producing shadow/paper proposals (and live through
    # the promotion gate) rather than being gated silent by the runtime.
    multirt = MultiTimeframeRuntime(watchlist_ids=set(STRATEGY_IDS))
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
        symbology_method=SymbologyMethod.IB_RAW,
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

    _start_paper_engine(engine)

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
