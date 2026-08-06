"""Integration tests: fixture CSV → full data pipeline → engine round trip."""

from datetime import date, datetime, timezone

from titan._core import (
    ContractType,
    Instrument,
    InstrumentId,
    Money,
    ReconciliationConfig,
    RiskConfig,
    TradeIntent,
)
from titan.data.approved import load_approved
from titan.data.freshness import check_freshness
from titan.data.ingest import read_csv
from titan.data.manifest import DataManifest
from titan.data.normalize import normalize_row
from titan.data.quality import validate_and_quarantine
from titan.execution import PaperConfig, PaperTradingEngine, SimulatedAdapter
from tests.fixtures.session_init import initialize_fresh



class TestForexDataPipelineRoundTrip:
    """EUR/USD fixture through every pipeline stage into a live engine order."""

    def test_forex_data_pipeline_round_trip(self):
        rows = read_csv("tests/data/fixtures/eurusd_2026.csv")
        assert len(rows) == 6

        norm = [normalize_row(r) for r in rows]
        assert all(not isinstance(r, str) for r in norm)

        report, good = validate_and_quarantine(rows, normalize_row)
        assert report.quarantine_count == 0
        assert len(good) == 6

        manifest = DataManifest.create_from_bars(
            good, source_path="tests/data/fixtures/eurusd_2026.csv"
        )
        assert manifest.instrument_id == "EURUSD"
        assert manifest.record_count == 6

        fresh = check_freshness(manifest, reference_date=date(2026, 7, 21))
        assert fresh.fresh

        approved = load_approved(
            "tests/data/fixtures/eurusd_2026.csv",
            reference_date=date(2026, 7, 21),
        )
        assert approved.instrument_id == "EURUSD"
        assert approved.bar_count() == 6

        from titan.data.forex_pairs import forex_instrument

        inst = forex_instrument("EURUSD")
        risk = RiskConfig(
            [], Money("100000", "USD"), 100000, 100000,
            Money("1000000", "USD"), 0.10, Money("5000", "USD"), 5000, 60000,
        )
        config = PaperConfig(
            risk_config=risk,
            reconciliation_config=ReconciliationConfig(
                critical_drift_fraction=0.05, warning_drift_fraction=0.01,
            ),
            currency="USD", starting_capital="100000", account_id="forex-pipe-1",
            state_path="",
        )
        engine = PaperTradingEngine(config, SimulatedAdapter())
        engine.register_instrument(inst)
        initialize_fresh(engine)
        engine.start()
        engine._last_prices["EURUSD"] = "1.1000"


        intent = TradeIntent(
            strategy_id="test", strategy_package_digest="v1",
            account_id="forex-pipe-1", instrument_id="EURUSD",
            side="BUY", quantity="1000", order_type="MARKET",
            time_in_force="DAY", risk_profile_version="1.0",
            market_data_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        result = engine.submit_intent(intent)
        assert result.accepted, f"Order rejected: {result.rejection_reason}"
        assert result.fills
        assert result.fills[0].instrument_id == "EURUSD"
        assert result.fills[0].side.upper() == "BUY"


class TestGoldDataPipelineRoundTrip:
    """XAU/USD fixture through every pipeline stage into a live engine order."""

    def test_gold_data_pipeline_round_trip(self):
        rows = read_csv("tests/data/fixtures/xauusd_2026.csv")
        assert len(rows) == 6

        norm = [normalize_row(r) for r in rows]
        assert all(not isinstance(r, str) for r in norm)

        report, good = validate_and_quarantine(rows, normalize_row)
        assert report.quarantine_count == 0
        assert len(good) == 6

        manifest = DataManifest.create_from_bars(
            good, source_path="tests/data/fixtures/xauusd_2026.csv"
        )
        assert manifest.instrument_id == "XAUUSD"
        assert manifest.record_count == 6

        fresh = check_freshness(manifest, reference_date=date(2026, 7, 21))
        assert fresh.fresh

        approved = load_approved(
            "tests/data/fixtures/xauusd_2026.csv",
            reference_date=date(2026, 7, 21),
        )
        assert approved.instrument_id == "XAUUSD"
        assert approved.bar_count() == 6

        from titan.data.spot_metals import spot_metal_instrument

        inst = spot_metal_instrument("XAUUSD")
        risk = RiskConfig(
            [], Money("100000", "USD"), 100, 100,
            Money("1000000", "USD"), 0.10, Money("5000", "USD"), 5000, 60000,
        )
        config = PaperConfig(
            risk_config=risk,
            reconciliation_config=ReconciliationConfig(),
            currency="USD", starting_capital="100000", account_id="gold-pipe-1",
            state_path="",
        )
        engine = PaperTradingEngine(config, SimulatedAdapter())
        engine.register_instrument(inst)
        initialize_fresh(engine)
        engine.start()
        engine._last_prices["XAUUSD"] = "2350.00"


        intent = TradeIntent(
            strategy_id="test", strategy_package_digest="v1",
            account_id="gold-pipe-1", instrument_id="XAUUSD",
            side="BUY", quantity="1", order_type="MARKET",
            time_in_force="DAY", risk_profile_version="1.0",
            market_data_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        result = engine.submit_intent(intent)
        assert result.accepted, f"Order rejected: {result.rejection_reason}"
        assert result.fills
        assert result.fills[0].instrument_id == "XAUUSD"
        assert result.fills[0].side.upper() == "BUY"


class TestEquityDataPipelineRoundTrip:
    """SPY fixture through every pipeline stage into a live engine order."""

    def test_equity_data_pipeline_round_trip(self):
        rows = read_csv("tests/fixtures/market/spy_2020_2024.csv")
        assert len(rows) == 1301

        norm = [normalize_row(r) for r in rows]
        assert all(not isinstance(r, str) for r in norm)

        report, good = validate_and_quarantine(rows, normalize_row)
        assert report.quarantine_count == 0
        assert len(good) == 1301

        manifest = DataManifest.create_from_bars(
            good, source_path="tests/fixtures/market/spy_2020_2024.csv"
        )
        assert manifest.instrument_id == "SPY"
        assert manifest.record_count == 1301

        fresh = check_freshness(manifest, reference_date=date(2025, 1, 2))
        assert fresh.fresh

        approved = load_approved(
            "tests/fixtures/market/spy_2020_2024.csv",
            reference_date=date(2025, 1, 2),
        )
        assert approved.instrument_id == "SPY"
        assert approved.bar_count() == 1301

        inst = Instrument(
            InstrumentId("SPY", "NYSE"),
            "0.01", 1, "1.0", ContractType.Stock, "USD", 2,
        )
        risk = RiskConfig(
            [], Money("100000", "USD"), 1000, 10000,
            Money("1000000", "USD"), 0.10, Money("5000", "USD"), 5000, 60000,
        )
        config = PaperConfig(
            risk_config=risk,
            reconciliation_config=ReconciliationConfig(),
            currency="USD", starting_capital="100000", account_id="eq-pipe-1",
            state_path="",
        )
        engine = PaperTradingEngine(config, SimulatedAdapter())
        engine.register_instrument(inst)
        initialize_fresh(engine)
        engine.start()
        engine._last_prices["SPY"] = "500.00"


        intent = TradeIntent(
            strategy_id="test", strategy_package_digest="v1",
            account_id="eq-pipe-1", instrument_id="SPY",
            side="BUY", quantity="10", order_type="MARKET",
            time_in_force="DAY", risk_profile_version="1.0",
            market_data_timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        result = engine.submit_intent(intent)
        assert result.accepted, f"Order rejected: {result.rejection_reason}"
        assert result.fills
        assert result.fills[0].instrument_id == "SPY"
        assert result.fills[0].side.upper() == "BUY"


class TestBadDataIsQuarantined:
    """Bad rows with unknown symbols end up in the quarantine report."""

    def test_bad_data_is_quarantined(self):
        rows = read_csv("tests/data/fixtures/eurusd_2026.csv")
        rows.append({
            "symbol": "UNKNOWNSYM",
            "date": "2026-07-21",
            "open": "1.0", "high": "1.1", "low": "0.9", "close": "1.05",
            "volume": "0",
        })

        report, good = validate_and_quarantine(rows, normalize_row)
        assert report.quarantine_count == 1
        assert any("UNKNOWNSYM" in str(q) for q in report.quarantined)
        assert len(good) == 6
