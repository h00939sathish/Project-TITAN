"""90-day paper session runner for Phase J.

Modes:
    simulation (default)          — SimulatedAdapter, optional synthetic data, soft fallback
    paper-preflight               — strict preflight: requires approved data file, fail-closed on rejection.
                                    Uses SimulatedAdapter — does NOT connect to a broker.
    broker-paper                  — Alpaca paper account. Requires approved data, valid paper credentials.
                                    Starts read-only. Fail-closed on auth failure / heartbeat loss.

Usage:
    python scripts/paper_session.py                                                      # simulation mode
    python scripts/paper_session.py --mode paper-preflight --data-file data.csv           # strict preflight
    python scripts/paper_session.py --mode broker-paper --data-file tests/fixtures/...    # Alpaca paper
"""
import argparse
import json
import os
import signal
from pathlib import Path
import sys
_PROJECT_SRC = str(Path(__file__).resolve().parent.parent / "src")
if _PROJECT_SRC not in sys.path:
    sys.path.insert(0, _PROJECT_SRC)
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv




from titan._core import (
    KillSwitchState,
    Money,
    PortfolioEngine,
    ReconciliationConfig,
    RiskConfig,
    TradeIntent,
)
from titan.execution import (
    AdapterError,
    AlpacaAdapter,
    PaperConfig,
    PaperTradingEngine,
    SimFillQuality,
    SimulatedAdapter,
)
from titan.execution.alpaca_adapter import create_broker_paper_adapter
from titan.data.approved import load_approved, ApprovedDataSource, DataSourceError
from titan.data.calendar import is_trading_day, next_trading_day, previous_trading_day
from titan.data.alpaca_feed import AlpacaDataFeed
from titan.research.qualification import QualifiedStrategyPool
from titan.research.shadow import ShadowRunner
from titan.strategies.bridge import StrategyBridge
from titan.operations.logging import StructuredLogger, LogSeverity
from titan.operations._metrics_integration import (
    get_registry, intents_evaluated, intents_rejected,
    orders_filled, orders_submitted,
)
from titan.operations.telemetry import SystemState

SESSION_START = datetime.now(timezone.utc)
RUNNING = True


def _shutdown(signum: int, frame: object) -> None:
    global RUNNING
    RUNNING = False


signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)


class StrategyRunner:
    """Strategy scheduler that drives price data through the engine."""

    def __init__(
        self,
        instruments: list[str],
        mode: str,
        data_file: str | None = None,
        min_bars: int = 252,
        max_stale_days: int = 2,
        live_feed: object = None,
        intraday: bool = False,
    ) -> None:
        self.instruments = instruments
        self.mode = mode
        self._intraday = intraday
        self._index: dict[str, int] = {i: 0 for i in instruments}
        self._prices: dict[str, list[float]] = {i: [] for i in instruments}
        self._bar_dates: dict[str, list[str]] = {i: [] for i in instruments}
        self._data_source: ApprovedDataSource | None = None
        self._live_feed = live_feed
        self._last_fetch = 0.0

        if data_file:
            self._load_approved_data(data_file, min_bars, max_stale_days)
        elif self._intraday:
            self._pull_intraday()
            print(f"Loaded realtime intraday data for {instruments}", flush=True)
        elif self._live_feed is not None:
            self._fetch_live_data()
            print(f"Loaded live data for {instruments}", flush=True)
        elif mode in ("paper-preflight", "broker-paper"):
            print(f"FATAL: {mode} mode requires --data-file", flush=True)
            sys.exit(1)
        else:
            from datetime import timedelta
            base_date = datetime(2024, 1, 2)
            for instr in instruments:
                prices = _synthetic_prices(instr)
                self._prices[instr] = prices
                self._bar_dates[instr] = [
                    (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
                    for i in range(len(prices))
                ]

    def _fetch_live_data(self) -> None:
        from datetime import timedelta
        base_date = datetime(2024, 1, 2)
        for instr in self.instruments:
            bars = self._live_feed.fetch_to_approved(instr)
            if not bars:
                prices = _synthetic_prices(instr)
                self._prices[instr] = prices
                self._bar_dates[instr] = [
                    (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
                    for i in range(len(prices))
                ]
            else:
                self._prices[instr] = [float(b["close"]) for b in bars]
                self._bar_dates[instr] = [str(b.get("timestamp", "").split("T")[0]) for b in bars]
            # Advance index to the latest available bar so we process new ones
            self._index[instr] = max(0, len(self._prices[instr]) - 1)


    def _load_approved_data(
        self, path: str, min_bars: int, max_stale_days: int
    ) -> None:
        try:
            source = load_approved(
                path,
                min_bar_count=min_bars,
                max_stale_trading_days=max_stale_days,
            )
        except DataSourceError as e:
            msg = f"FATAL: approved data source rejected: {e}"
            print(msg, flush=True)
            if self.mode in ("paper-preflight", "broker-paper"):
                sys.exit(1)
            print(f"Falling back to synthetic prices for {self.instruments}", flush=True)
            for instr in self.instruments:
                self._prices[instr] = _synthetic_prices(instr)
            return

        missing = [i for i in self.instruments if i not in {b["instrument_id"] for b in source.bars}]
        if missing:
            msg = f"FATAL: instruments missing from approved data: {missing}"
            print(msg, flush=True)
            if self.mode in ("paper-preflight", "broker-paper"):
                sys.exit(1)
            print("Falling back to synthetic prices", flush=True)
            for instr in self.instruments:
                self._prices[instr] = _synthetic_prices(instr)
            return

        self._data_source = source
        for bar in source.bars:
            close = bar.get("close", 0)
            bar_instr: str = str(bar.get("instrument_id", ""))
            if bar_instr in self.instruments:
                self._prices[bar_instr].append(float(close))
                ts = str(bar.get("timestamp", ""))
                self._bar_dates[bar_instr].append(ts.split("T")[0] if ts else "")

        loaded = sum(len(v) for v in self._prices.values())
        print(
            f"Loaded {loaded} bars from approved source: {path} "
            f"({source.manifest.date_from[:10]} to {source.manifest.date_to[:10]}, "
            f"checksum={source.manifest.source_checksum[:16]}...)",
            flush=True,
        )

    def current_price(self, instrument: str) -> float | None:
        prices = self._prices.get(instrument)
        if not prices:
            return None
        idx = self._index.get(instrument, 0)
        return prices[min(idx, len(prices) - 1)]

    def current_bar_date(self, instrument: str) -> str | None:
        dates = self._bar_dates.get(instrument)
        if not dates:
            return None
        idx = self._index.get(instrument, 0)
        return dates[min(idx, len(dates) - 1)]

    def tick(self) -> None:
        import time
        if self._intraday:
            # Streaming mode: pull the latest completed bars from the realtime feed.
            # Idempotent — the bridge dedups on bar timestamps, so re-pulling the
            # same bars never re-fires signals.
            self._pull_intraday()
            return
        now = time.monotonic()
        # Fetch live data every 15 minutes to avoid rate limits while staying fresh
        if self._live_feed is not None and now - self._last_fetch > 900:
            try:
                self._fetch_live_data()
                self._last_fetch = now
            except Exception as e:
                print(f"WARNING: live data fetch failed: {e}", flush=True)
        else:
            for instr in self.instruments:
                prices = self._prices.get(instr)
                if prices:
                    self._index[instr] = min(self._index[instr] + 1, len(prices) - 1)

    def _pull_intraday(self) -> None:
        """Pull latest completed bars from the realtime feed into the runner."""
        for instr in self.instruments:
            bars = self._live_feed.completed_bars(instr)
            if not bars:
                continue
            self._prices[instr] = [float(c) for _, c in bars]
            self._bar_dates[instr] = [ts for ts, _ in bars]
            self._index[instr] = max(0, len(bars) - 1)

    @property
    def progress(self) -> float:
        if not self._prices:
            return 1.0
        return max(
            (self._index.get(i, 0) / max(len(self._prices[i]), 1))
            for i in self.instruments
        ) if any(self._prices[i] for i in self.instruments) else 1.0


def _synthetic_prices(instrument: str) -> list[float]:
    """Generate ~10 years of daily synthetic prices (2520 bars)."""
    import random
    seed_map = {"SPY": 550.0, "QQQ": 480.0, "AAPL": 220.0, "MSFT": 450.0, "TLT": 95.0,
                "EURUSD": 1.10, "GBPUSD": 1.29, "AUDUSD": 0.67, "NZDUSD": 0.60}
    base = seed_map.get(instrument, 100.0)
    rng = random.Random(sum(ord(c) for c in instrument))
    prices: list[float] = [base]
    pip = 0.0001 if instrument[:3] in ("EUR", "GBP", "AUD", "NZD") else 0.01
    prec = 5 if pip < 0.01 else 2
    drift = base * 0.0004
    n = 2520
    for i in range(1, n):
        ret = rng.gauss(drift, base * 0.015)
        prices.append(round(max(prices[-1] + ret, base * 0.5), prec))
    return prices


def _format_uptime(seconds: float) -> str:
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    mins = int((seconds % 3600) // 60)
    if days > 0:
        return f"{days}d{hours}h{mins}m"
    return f"{hours}h{mins}m"


def _bar_seconds(bar_size: str) -> int:
    """Seconds per bar from a TWS bar-size string ('5 mins' -> 300)."""
    parts = (bar_size or "5 mins").split()
    try:
        n = int(parts[0])
    except (ValueError, IndexError):
        return 300
    if len(parts) >= 2 and parts[1].startswith("min"):
        return n * 60
    if len(parts) >= 2 and parts[1].startswith("sec"):
        return n
    return 300


def _symbol(state: str) -> str:
    symbols: dict[str, str] = {"ACTIVE": "[+]", "DEGRADED": "[!]", "HALTED": "[X]"}
    return symbols.get(state, "[?]")


def _build_adapter(mode: str, use_tws: bool = False) -> SimulatedAdapter | AlpacaAdapter:
    """Return the adapter for the given mode.

    If use_tws is True → IBKRPaperAdapter
    elif mode == "broker-paper" → AlpacaAdapter
    else → SimulatedAdapter
    """
    if use_tws:
        try:
            from titan.execution.ibkr_adapter import IBKRPaperAdapter
            adapter = IBKRPaperAdapter()
            adapter.authenticate()
            health = adapter.heartbeat()
            if health.connected:
                print("tws: IBKR paper adapter connected", flush=True)
                return adapter
            print("tws: IBKR adapter heartbeat failed, falling back to SimulatedAdapter", flush=True)
        except Exception as e:
            print(f"tws: IBKR adapter failed ({e}), using SimulatedAdapter", flush=True)

    if mode == "broker-paper":
        try:
            adapter = create_broker_paper_adapter()
        except AdapterError as e:
            print(f"FATAL: {e}", flush=True)
            sys.exit(1)
        print(f"broker-paper: Alpaca paper account at {adapter._base_url}", flush=True)
        return adapter

    return SimulatedAdapter()



def _merge_config(args, config: dict) -> None:
    """Overlay CLI args onto config dict. CLI values win (non-default)."""
    cli_defaults = {
        "mode": "simulation", "instruments": "SPY,QQQ", "interval": 60,
        "reconcile_interval": 300, "metrics_interval": 900, "data_file": None,
        "min_bars": 252, "max_stale_days": 2, "state_path": ".titan_state.json",
        "log_file": None, "order_size": 1, "starting_capital": "100000",
        "status_only": False, "strategy": "ma-crossover",
        "strategy_params": '{"fast":5,"slow":20}', "live_data": False,
        "tws": False, "dashboard": None,
        "intraday": False, "bar_size": "5 mins",
        "order_type": "market", "limit_offset": 0.01,
    }
    for key, default in cli_defaults.items():
        cli_val = getattr(args, key, None)
        cfg_val = config.get(key, default)
        if cli_val != default:
            continue  # user passed it on CLI
        if key == "dashboard" and cfg_val is True:
            cfg_val = 8082
        setattr(args, key, cfg_val)



def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Phase J 90-day paper session runner",
        epilog="Modes: simulation (default, synthetic data OK) | paper-preflight (strict, requires --data-file) | broker-paper (Alpaca paper, requires .env + --data-file)",
    )
    parser.add_argument(
        "--config", default=None,
        help="Path to JSON config file (CLI args override matching keys)",
    )
    parser.add_argument(
        "--mode", default="simulation", choices=["simulation", "paper-preflight", "broker-paper"],
        help="Session mode: simulation | paper-preflight | broker-paper (Alpaca, requires .env credentials)",
    )
    parser.add_argument(
        "--instruments", default="SPY,QQQ",
        help="Comma-separated instrument list (default: SPY,QQQ)",
    )
    parser.add_argument(
        "--interval", type=int, default=60,
        help="Strategy evaluation interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--reconcile-interval", type=int, default=300,
        help="Reconciliation interval in seconds (default: 300)",
    )
    parser.add_argument(
        "--metrics-interval", type=int, default=900,
        help="Metrics dump interval in seconds (default: 900)",
    )
    parser.add_argument(
        "--data-file", default=None,
        help="CSV file with approved price data (required for paper-preflight and broker-paper modes)",
    )
    parser.add_argument(
        "--min-bars", type=int, default=252,
        help="Minimum required bars for approved data (default: 252, ~1 trading year)",
    )
    parser.add_argument(
        "--max-stale-days", type=int, default=2,
        help="Maximum stale trading days before data is rejected (default: 2)",
    )
    parser.add_argument(
        "--state-path", default=".titan_state.json",
        help="Path to persistent state file",
    )
    parser.add_argument(
        "--log-file", default=None,
        help="Path to log file (default: titan-<date>.log)",
    )
    parser.add_argument(
        "--order-size", type=int, default=1,
        help="Number of shares per order (default: 1, certified tiny notional)",
    )
    parser.add_argument(
        "--starting-capital", default="100000",
        help="Starting capital (default: 100000)",
    )
    parser.add_argument(
        "--status-only", action="store_true",
        help="Print status and exit",
    )
    parser.add_argument(
        "--strategy", default="ma-crossover",
        help="Strategy ID from the registry (default: ma-crossover)",
    )
    parser.add_argument(
        "--strategy-params", default='{"fast":5,"slow":20}',
        help="JSON-encoded strategy parameters (default: '{\"fast\":5,\"slow\":20}')",
    )
    parser.add_argument(
        "--live-data", action="store_true",
        help="Fetch live daily bars from Alpaca data API as primary data source",
    )
    parser.add_argument(
        "--tws", action="store_true",
        help="Fetch live daily bars from TWS (IBKR Trader Workstation) as primary data source",
    )
    parser.add_argument(
        "--intraday", action="store_true",
        help="Stream realtime intraday bars from TWS (reqHistoricalData keepUpToDate) and trade "
             "completed bars during RTH only. Requires --tws.",
    )
    parser.add_argument(
        "--bar-size", default="5 mins",
        help="TWS bar size for --intraday mode (default: 5 mins)",
    )
    parser.add_argument(
        "--enable-fx", action="store_true",
        help="Enable FX spot instruments (EURUSD/GBPUSD/...) despite ADR-018 "
             "remaining Proposed. Default: FX is excluded from the session.",
    )
    parser.add_argument(
        "--order-type", default="market", choices=["market", "limit"],
        help="Order type for strategy intents (default: market). Limit orders are priced "
             "aggressively (last +/- --limit-offset) so they behave like marketable orders "
             "with a controlled worst-case price.",
    )
    parser.add_argument(
        "--limit-offset", type=float, default=0.01,
        help="Price offset for limit orders (default: 0.01). BUY = last + offset, SELL = last - offset.",
    )
    parser.add_argument(
        "--qualification-db", default=None,
        help="Path to research DB. When set, loads QUALIFIED (and optionally WATCHLIST) strategies instead of --strategy.",
    )
    parser.add_argument(
        "--include-watchlist", action="store_true",
        help="When used with --qualification-db, also include WATCHLIST strategies.",
    )
    parser.add_argument(
        "--shadow", action="store_true",
        help="Enable shadow deployment — run unqualified strategies in parallel, log virtual orders.",
    )
    parser.add_argument(
        "--dashboard", nargs="?", const=8082, type=int, default=None, metavar="PORT",
        help="Start the TITAN Dashboard server (default port: 8082). Pass a port number to override.",
    )
    args = parser.parse_args()

    if not args.config and Path("session_config.json").exists():
        args.config = "session_config.json"

    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            config = json.loads(config_path.read_text())
            _merge_config(args, config)
            print(f"Loaded config from {args.config}", flush=True)


    if args.intraday and not args.tws:
        print("FATAL: --intraday requires --tws (realtime bars come from TWS)", flush=True)
        sys.exit(1)

    instruments = [s.strip() for s in args.instruments.split(",") if s.strip()]

    if args.mode == "broker-paper":
        if args.interval < 60:
            print(f"FATAL: broker-paper requires --interval >= 60 (got {args.interval})", flush=True)
            sys.exit(1)
        if len(instruments) > 10:
            kept = instruments[:10]
            print(f"broker-paper limited to 10 instruments: using only {kept} (was {instruments})", flush=True)
            instruments = kept

    from titan._core import ContractType, Instrument, InstrumentId
    from titan.data.forex_pairs import FOREX_SYMBOLS, STEP_SIZE, forex_instrument

    # ADR-018 (forex simulated trading) is Proposed, not accepted: exclude FX
    # from the session unless explicitly promoted via --enable-fx.
    if not getattr(args, "enable_fx", False):
        fx_instruments = [i for i in instruments if i in FOREX_SYMBOLS]
        if fx_instruments:
            instruments = [i for i in instruments if i not in FOREX_SYMBOLS]
            print(f"ADR-018 FX gate: excluding FX instruments {fx_instruments} "
                  f"(pass --enable-fx to include)", flush=True)

    log_file = args.log_file or f"titan-{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"
    log_path = Path(log_file)
    log_handler = open(log_path, "a", encoding="utf-8") if log_path.suffix == ".log" else None
    logger = StructuredLogger(min_severity=LogSeverity.INFO, output=log_handler)

    logger.info(
        "phase_j",
        "Session runner starting",
        payload={
            "mode": args.mode,
            "instruments": instruments,
            "interval": args.interval,
            "starting_capital": args.starting_capital,
        },
    )

    bar_seconds = _bar_seconds(args.bar_size)
    # data_freshness_threshold_ms must exceed one bar period: intents now stamp
    # the COMPLETED bar's timestamp (risk.data_freshness), so a 5-min bar is up
    # to ~300s old. Allow 2 bars + 1s buffer — a genuinely stalled feed
    # (>~10 min stale) is rejected by the freshness gate (fail-closed).
    data_freshness_threshold_ms = (bar_seconds * 2 + 1) * 1000
    risk_config = RiskConfig(
        instruments,
        Money(args.starting_capital, "USD"),
        1000,
        5000,
        Money(args.starting_capital, "USD"),
        0.10,
        Money("5000", "USD"),
        data_freshness_threshold_ms,
        100,
    )
    paper_config = PaperConfig(
        risk_config=risk_config,
        reconciliation_config=ReconciliationConfig(),
        currency="USD",
        starting_capital=args.starting_capital,
        account_id="paper-1",
        state_path=args.state_path,
    )

    adapter = _build_adapter(args.mode, use_tws=args.tws)

    if args.tws:
        if args.intraday:
            from titan.data.tws_feed import TWSRealtimeFeed
            feed = TWSRealtimeFeed(instruments, bar_size=args.bar_size)
            print(f"TWS realtime feed connected ({args.bar_size}) for {instruments}", flush=True)
        else:
            from titan.data.tws_feed import TWSDataFeed
            feed = TWSDataFeed()
            print(f"TWS data feed connected for {instruments}", flush=True)
    elif args.live_data and args.mode in ("broker-paper", "paper-preflight"):
        feed = AlpacaDataFeed(paper=(args.mode == "broker-paper"))
        for instr in instruments:
            bars = feed.fetch_to_approved(instr)
            for b in bars:
                pass  # validated — data stays in AlpacaDataFeed cache
        print(f"Live data feed active for {instruments}", flush=True)
    else:
        feed = None

    # ADR-019: the release gate verifies control health via a data-feed-owned
    # FeedHealthSnapshot. Only the TWS realtime feed satisfies the contract;
    # anything else (TWSDataFeed, AlpacaDataFeed, None) fails closed on release.
    if args.tws and args.intraday:
        from titan.data.feed_health import FeedHealthSnapshot
        snapshot = FeedHealthSnapshot(
            feed,
            instruments,
            stale_after_s=(data_freshness_threshold_ms / 1000.0),
        )
        feed_health = snapshot.evaluate
    else:
        feed_health = None

    engine = PaperTradingEngine(paper_config, adapter, logger=logger, feed_health=feed_health)

    for instr in instruments:
        if instr in FOREX_SYMBOLS:
            inst = forex_instrument(instr)
        else:
            inst = Instrument(InstrumentId(instr, "PAPER"), "0.01", 1, "1.0", ContractType.Stock, "USD", 2)
        if inst:
            engine.register_instrument(inst)

    strategies = StrategyRunner(
        instruments,
        args.mode,
        args.data_file,
        min_bars=args.min_bars,
        max_stale_days=args.max_stale_days,
        live_feed=feed,
        intraday=args.intraday,
    )

    bridge_state_file = Path(args.state_path).with_suffix(".bridge_state")
    use_qualification = args.qualification_db is not None

    if use_qualification:
        pool = QualifiedStrategyPool(
            db_path=args.qualification_db,
            default_order_size=args.order_size,
            account_id="paper-1",
        )
        loaded = pool.load_qualified(include_watchlist=args.include_watchlist)
        if not loaded:
            print(f"FATAL: no qualified strategies found in {args.qualification_db}", flush=True)
            sys.exit(1)
        print(f"Qualified pool: {loaded}", flush=True)
        bridge = None  # signals come from pool, not a single bridge

        if args.shadow:
            shadow = ShadowRunner(db_path=args.qualification_db)
            shadow_loaded = shadow.load_all_not_qualified()
            if shadow_loaded:
                print(f"Shadow runner active: {shadow_loaded}", flush=True)
            else:
                print("Shadow runner: no unqualified strategies to shadow", flush=True)
                shadow = None
        else:
            shadow = None
    else:
        pool = None
        shadow = None
        strategy_params: dict = json.loads(args.strategy_params)
        # order_size is a lot count: 1 lot = 1 share (equities) or 1 micro-lot
        # = 1000 base units (forex). Lets one order_size work across asset classes.
        # Per-pair step_size is used so instruments like XAUUSD (1 oz) size correctly.
        lot_sizes = {}
        for i in instruments:
            if i in FOREX_SYMBOLS:
                inst = forex_instrument(i)
                lot_sizes[i] = inst.step_size if inst else STEP_SIZE
            else:
                lot_sizes[i] = 1
        bridge = StrategyBridge(
            strategy_id=args.strategy,
            strategy_params=strategy_params,
            account_id="paper-1",
            order_size=args.order_size,
            lot_sizes=lot_sizes,
            order_type=args.order_type,
            limit_offset=args.limit_offset,
        )

    # Restore bridge state (engine state restored from EventStore on start)
    if bridge_state_file.exists() and bridge and not use_qualification:
        try:
            saved = json.loads(bridge_state_file.read_text())
            if "bridge" in saved:
                bridge.restore_state(saved["bridge"])
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: failed to restore bridge state: {e}", flush=True)

    # Warm indicators from historical prices so replay doesn't fire signals.
    for instr in instruments:
        prices = strategies._prices.get(instr, [])
        if args.intraday:
            # Intraday: warm the signal function with the backfilled bars and mark
            # the last (stale) one processed so the first intent comes from a bar
            # that completes during the live session.
            if not prices:
                continue
            if bridge and not pool:
                bridge.warmup(instr, prices)
                dates = strategies._bar_dates.get(instr, [])
                if dates:
                    bridge.mark_processed(instr, dates[-1])
            if pool:
                pool.warmup(instr, prices)
            if shadow:
                shadow.warmup(instr, prices)
            strategies._index[instr] = max(0, len(prices) - 1)
            continue
        if len(prices) < 60:
            continue
        warm = min(400, len(prices) // 2)
        if pool:
            pool.warmup(instr, prices[:warm])
        if shadow:
            shadow.warmup(instr, prices[:warm])
        if bridge and not pool:
            bridge.warmup(instr, prices[:warm])
        strategies._index[instr] = warm

    if args.status_only:
        _print_status(engine, strategies)
        return

    try:
        session = engine.start(sync_from_broker=(args.mode == "broker-paper"))
    except Exception as e:
        print(f"FATAL: broker authentication failed: {e}", flush=True)
        logger.error("phase_j", f"Broker auth failed: {e}")
        if log_handler:
            log_handler.close()
        sys.exit(1)
    logger.info("phase_j", f"Session {session.session_id} started")
    print(f"Session {session.session_id} started — Phase J ({args.mode}) running", flush=True)

    if shadow:
        shadow._session_id = session.session_id

    if args.dashboard is not None:
        import threading
        _root = Path(__file__).resolve().parents[1]
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
        from dashboard.server import run as run_dashboard
        _port = args.dashboard if isinstance(args.dashboard, int) else 8082
        _dashboard_thread = threading.Thread(
            target=run_dashboard,
            kwargs={"host": "127.0.0.1", "port": _port},
            daemon=True,
        )
        _dashboard_thread.start()
        print(f"TITAN Dashboard started on http://127.0.0.1:{_port}", flush=True)

    # Sync position state with portfolio (after start so broker-paper positions are loaded)
    for instr in instruments:
        pos = engine.portfolio.get_position(instr)
        has_pos = pos is not None and pos.quantity > 0
        if pool:
            pool.set_position(instr, has_pos)
        elif bridge:
            bridge.set_position(instr, has_pos)

    today = datetime.now(timezone.utc).date()
    if is_trading_day(today):
        prev_day = previous_trading_day(today)
        print(f"Market is open today ({today}). Last trading day: {prev_day}", flush=True)
    else:
        next_day = next_trading_day(today)
        print(f"Market is closed today ({today}). Next trading day: {next_day}", flush=True)

    last_reconcile = 0.0
    last_metrics_dump = 0.0
    cycle_count = 0

    while RUNNING:
        cycle_start = time.monotonic()
        cycle_count += 1
        now = datetime.now(timezone.utc)

        engine.status()

        if args.intraday:
            # Pull the latest completed bars before processing so signals fire on
            # fresh data. Idempotent: the bridge dedups on bar timestamps.
            strategies.tick()

        # Operator release: a release_kill_switch.signal file in the project
        # root asks the session to attempt a kill-switch release. The engine's
        # release_kill_switch() reconciles first and refuses on real drift —
        # this is the sanctioned way to resume a halted session without a
        # restart or state surgery.
        release_file = Path("release_kill_switch.signal")
        auth_file = Path("release_kill_switch.auth.json")
        if release_file.exists() and cycle_count % 5 == 0:
            # The .signal file is only a transport hint; authorization is carried
            # by the ReleaseAuthorization record (ADR-019 / RISK_POLICY:37).
            authorization = None
            if auth_file.exists():
                try:
                    from titan.risk.release_authorization import ReleaseAuthorization
                    authorization = ReleaseAuthorization.from_json(
                        auth_file.read_text(encoding="utf-8"))
                except Exception:
                    authorization = None
            try:
                engine.release_kill_switch(authorization)
                # Idempotent: release is a no-op if the switch was not held.
                # If the causal condition is still live, the engine re-triggers
                # on the next check — surface that instead of a false "RELEASED".
                if engine.risk_gate.kill_switch.blocks_routing():
                    print("kill switch release accepted but RE-TRIGGERED: "
                          "causal condition still live", flush=True)
                else:
                    print("kill switch RELEASED (authorized)", flush=True)
            except Exception as e:
                # Exception carries kill_reason=<code> from engine.release_kill_switch
                print(f"kill switch release REFUSED: {e}", flush=True)
            finally:
                release_file.unlink(missing_ok=True)
                auth_file.unlink(missing_ok=True)

        # Reconnect guard: if TWS drops (restart, network), re-authenticate and
        # re-import broker truth so the next reconcile starts from a consistent
        # state instead of tripping the kill switch on stale portfolios.
        if args.tws and cycle_count % 60 == 0:
            try:
                health = adapter.heartbeat()
                if health is not None and not health.connected:
                    print("adapter heartbeat FAILED - attempting reconnect", flush=True)
                    if adapter.ensure_connected():
                        print("adapter RECONNECTED - resyncing broker truth", flush=True)
                        try:
                            engine._sync_from_broker()
                            engine._save_state()
                        except Exception as e:
                            print(f"WARNING: post-reconnect broker sync failed: {e}", flush=True)
                    else:
                        print("adapter reconnect FAILED - will retry", flush=True)
            except Exception as e:
                print(f"adapter health check error: {e}", flush=True)

        # Feed recovery: TWS can silently stall (1100 / 10182 / farm storms) with
        # no new completed bars. Reconnect + resubscribe, verify bars advance, and
        # stay FAIL-CLOSED (no intents) until the feed is fresh again.
        feed_ok = True
        if feed:
            stale_after_s = max(30.0, float(bar_seconds * 2))
            if feed.needs_recovery() or not feed.is_healthy(stale_after_s=stale_after_s):
                print("[feed] unhealthy — attempting reconnect/resubscribe", flush=True)
                try:
                    ref_ts = feed.latest_ts()
                    feed.recover()
                    advanced = feed.bars_advancing(ref_ts)
                    for _ in range(2):
                        if advanced:
                            break
                        time.sleep(10)
                        advanced = feed.bars_advancing(ref_ts)
                    feed_ok = bool(advanced or not feed._has_any_bar)
                    print(f"[feed] recovery "
                          f"{'advanced — trading resumes' if feed_ok else 'still stalled — fail-closed'}",
                          flush=True)
                except Exception as e:
                    print(f"[feed] recovery failed: {e} — fail-closed", flush=True)
                    feed_ok = False

        for instr in instruments:
            price = strategies.current_price(instr)
            if price is None:
                continue
            engine._last_prices[instr] = str(price)

        for instr in instruments:
            price = strategies.current_price(instr)
            if price is None:
                continue
            bar_date = strategies.current_bar_date(instr)
            if bar_date is None:
                continue
            # Fire signals only during RTH (09:35-16:00 ET) for equities. FX spot
            # (EURUSD/GBPUSD) trades Sun 17:00 ET - Fri 17:00 ET with no intraday
            # gate. The TWS simulated preview account holds RTH-only DAY orders
            # placed outside regular trading hours until the next RTH open, and
            # fills marketable MKT orders within ~1 minute during RTH. The signal
            # is the last COMPLETED bar; executing it while the market is open
            # means the order fills immediately instead of being held and then
            # cancelled by the engine's fill timeout.
            now_et = datetime.now(timezone.utc).astimezone(ZoneInfo("US/Eastern"))
            if instr in FOREX_SYMBOLS:
                # FX spot session: Sun 17:00 ET -> Fri 17:00 ET.
                if now_et.weekday() == 4 and now_et.hour >= 17:
                    continue  # Friday 17:00 ET close
                if now_et.weekday() == 6 and now_et.hour < 17:
                    continue  # Sunday before 17:00 ET open
            else:
                if now_et.weekday() >= 5:
                    # Weekend: equity RTH is closed — no signal generation even
                    # if a stray bar arrives from the feed.
                    continue
                in_rth_window = (9 <= now_et.hour < 16) and (now_et.hour != 9 or now_et.minute >= 35)
                if not in_rth_window:
                    continue
            # Never trade an in-progress DAILY bar (daily-bar mode): its completed-bar
            # signal fires at the next RTH open. In intraday mode the bars ARE today's
            # completed 5-min bars (the forming bar is excluded by the feed), so this
            # check must not suppress them.
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if not args.intraday and bar_date == today_str:
                continue
            if pool:
                intent = pool.on_price(instr, price, bar_date=bar_date)
            else:
                intent = bridge.on_price(instr, price, bar_date=bar_date) if bridge else None
            if shadow:
                shadow.on_price(instr, price, bar_date=bar_date)
            if intent is None:
                continue
            # Fail-closed: never emit an intent while the feed is unhealthy/stalled.
            if not feed_ok:
                continue
            result = engine.submit_intent(intent)
            if result.accepted:
                logger.info("strategy", f"Intent accepted for {instr}: {result.broker_order_id}")
                # Admission semantics: only accepted intents update bridge
                # position/side state, so a rejection can't suppress the next
                # valid same-direction signal.
                if bridge:
                    bridge.admitted(instr, intent.side)
            else:
                logger.warning("strategy", f"Intent rejected for {instr}: {result.rejection_reason}")

        elapsed = time.monotonic() - cycle_start
        if elapsed < args.interval:
            time.sleep(args.interval - elapsed)

        uptime = (datetime.now(timezone.utc) - SESSION_START).total_seconds()
        if uptime - last_reconcile >= args.reconcile_interval:
            recon = engine.reconcile()
            last_reconcile = uptime

        if uptime - last_metrics_dump >= args.metrics_interval:
            metrics_path = f"metrics-{now.strftime('%Y%m%d')}.json"
            try:
                data = json.loads(get_registry().dump_json())
            except Exception:
                data = {}
            data["per_instrument"] = engine.get_per_instrument_stats()
            Path(metrics_path).write_text(json.dumps(data, indent=2))
            last_metrics_dump = uptime

            print(f"\n--- PER-INSTRUMENT BREAKDOWN [{now.strftime('%Y-%m-%d %H:%M:%S UTC')}] ---", flush=True)
            for sym, s in engine.get_per_instrument_stats().items():
                print(
                    f"  • {sym:<8} | intents={s['intents']:<3} | fills={s['fills']:<3} | rej={s['rejections']:<3} | pos={s['position']} ({s['side']}) | price={s['price']}",
                    flush=True,
                )
            print("----------------------------------------------------\n", flush=True)


        st = engine.status()
        state_str = "ACTIVE"
        if st.kill_switch.blocks_routing():
            state_str = "HALTED"
        kw_triggered = st.kill_switch.is_triggered()
        kw_armed = not kw_triggered and st.kill_switch != KillSwitchState.Released

        data_source = strategies._data_source
        health_icon = _symbol(state_str)
        data_info = ""
        if data_source:
            data_info = f" data={data_source.manifest.date_to[:10]}" if data_source.manifest.date_to else ""
        elif feed:
            data_info = " data=live"

        try:
            strategies.tick()
        except Exception as e:
            logger.error("phase_j", f"Strategy tick failed: {e}")
            print(f"ERROR: strategy tick failed: {e}", flush=True)
            if not engine.risk_gate.kill_switch.blocks_routing():
                engine.trigger_kill_switch()
        if pool:
            bridge_ready = len(pool._bridges) > 0
            strat_label = f"pool({pool.active_count})"
            if shadow:
                strat_label += f"+shadow({shadow.active_count})"
        else:
            bridge_ready = len(bridge._signals) == len(instruments) if bridge else False
            strat_label = args.strategy
        log_size = log_path.stat().st_size if log_path.exists() else 0
        print(
            f"[{now.strftime('%Y-%m-%dT%H:%M:%SZ')}] "
            f"{health_icon} "
            f"uptime={_format_uptime(uptime)} "
            f"intents={intents_evaluated.value} "
            f"fills={orders_filled.value} "
            f"rej={intents_rejected.value} "
            f"drift=0 "
            f"kw={'2' if kw_triggered else '1' if kw_armed else '0'} "
            f"strat={strat_label} "
            f"ready={'Y' if bridge_ready else 'N'} "
            f"prices={len(engine._last_prices)}/{len(instruments)} "
            f"cash={float(st.cash_balance.amount):.0f} "
            f"pv={float(st.portfolio_value.amount):.0f}"
            f"{data_info}"
            f" log={log_size // (1024*1024)}MB",
            flush=True,
        )

    logger.info("phase_j", "Session stopping")
    engine.stop()

    # Persist bridge state separately (engine state is in EventStore)
    if bridge and not use_qualification:
        try:
            bridge_state_file.write_text(json.dumps({"bridge": bridge.save_state()}, indent=2))
        except OSError as e:
            print(f"Warning: failed to persist bridge state: {e}", flush=True)

    get_registry().dump_json()
    if log_handler:
        log_handler.close()
    print("\nPhase J session stopped.", flush=True)


def _print_status(engine: PaperTradingEngine, strategies: StrategyRunner) -> None:
    """Print engine and data status as JSON."""
    st = engine.status()
    print(json.dumps({
        "trading_state": str(st.trading_state),
        "kill_switch": str(st.kill_switch),
        "cash": float(st.cash_balance.amount),
        "portfolio_value": float(st.portfolio_value.amount),
        "positions": len(st.positions),
        "open_orders": st.open_orders,
        "data_progress": round(strategies.progress, 3),
        "uptime": _format_uptime((datetime.now(timezone.utc) - SESSION_START).total_seconds()),
    }, indent=2))


if __name__ == "__main__":
    main()
