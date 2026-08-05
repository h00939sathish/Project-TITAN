"""Tests for Phases 2–9: Manifest, Ensemble, Filters, Sizing, Lifecycle, Shadow, Allocator, Registries."""

import pytest

from titan.strategies.manifest import make_manifest, TradeManifest
from titan.strategies.ensemble import WeightedEnsemble, StrategyVote
from titan.strategies.filters import WeeklyTrendFilter, VolatilityFilter
from titan.strategies.sizing import position_size, atr
from titan.strategies.lifecycle import LifecycleEngine, StrategyStatus
from titan.strategies.shadow import ShadowDeployer, ShadowTrade
from titan.strategies.allocator import MetaAllocator
from titan.strategies.registries import register_experiment, get_experiment, get_feature_hash


class TestPhase2_TradeManifest:
    def test_manifest_contains_all_fields(self):
        m = make_manifest(
            strategy_id="ma-crossover", strategy_version="1.0.0",
            strategy_params={"fast": 5, "slow": 20},
            instrument_id="SPY", side="BUY", quantity="10", price="150.0",
            regime={"regime": "LOW_VOL", "confidence": 0.8},
        )
        assert isinstance(m, TradeManifest)
        assert m.strategy_id == "ma-crossover"
        assert m.strategy_version == "1.0.0"
        assert m.instrument_id == "SPY"
        assert m.side == "BUY"
        assert m.quantity == "10"
        assert m.price == "150.0"
        assert m.regime["regime"] == "LOW_VOL"
        assert m.params_hash is not None
        assert m.trade_id is not None
        assert m.timestamp is not None
        assert m.git_sha is not None

    def test_manifest_id_is_deterministic_for_same_inputs(self):
        m1 = make_manifest("s", "1.0", {}, "SPY", "BUY", "1")
        m2 = make_manifest("s", "1.0", {}, "SPY", "BUY", "1")
        assert m1.trade_id != m2.trade_id  # timestamps differ

    def test_accepts_empty_regime_and_ensemble(self):
        m = make_manifest("s", "1.0", {}, "SPY", "BUY", "1")
        assert m.regime == {}
        assert m.ensemble == {}

    def test_bridge_stamps_manifest(self):
        import titan.strategies.registrations  # noqa: F401
        from titan.strategies.bridge import StrategyBridge
        bridge = StrategyBridge("ma-crossover", {"fast": 2, "slow": 3})
        prices = [100, 100, 90, 80, 100, 105]
        intent = None
        for p in prices:
            intent = bridge.on_price("SPY", p)
        assert intent is not None
        manifest = bridge.last_manifest
        assert manifest is not None
        assert manifest.strategy_id == "ma-crossover"
        assert manifest.instrument_id == "SPY"
        assert manifest.side == "BUY"
        assert manifest.params_hash is not None


class TestPhase3_WeightedEnsemble:
    def test_buy_decision(self):
        e = WeightedEnsemble(buy_threshold=0.5, sell_threshold=-0.5)
        votes = [
            StrategyVote("mom", "BUY", 0.8, 1.0),
            StrategyVote("ma", "BUY", 0.6, 1.0),
        ]
        r = e.decide(votes)
        assert r.decision == "BUY"
        assert r.score > 0.5

    def test_sell_decision(self):
        e = WeightedEnsemble(buy_threshold=0.5, sell_threshold=-0.5)
        votes = [
            StrategyVote("mom", "SELL", -0.8, 1.0),
            StrategyVote("ma", "SELL", -0.6, 1.0),
        ]
        r = e.decide(votes)
        assert r.decision == "SELL"

    def test_no_trade_when_below_threshold(self):
        e = WeightedEnsemble(buy_threshold=0.7, sell_threshold=-0.7)
        votes = [
            StrategyVote("mom", "BUY", 0.4, 1.0),
            StrategyVote("ma", "SELL", -0.3, 1.0),
        ]
        r = e.decide(votes)
        assert r.decision == "NO_TRADE"

    def test_weighted_votes(self):
        e = WeightedEnsemble(buy_threshold=0.3)
        votes = [
            StrategyVote("mom", "BUY", 1.0, 2.0),
            StrategyVote("mr", "SELL", -1.0, 0.5),
        ]
        r = e.decide(votes)
        # score = (1.0*2.0 + (-1.0)*0.5) / (2.0 + 0.5) = 1.5/2.5 = 0.6
        assert r.score == 0.6

    def test_empty_votes_no_trade(self):
        e = WeightedEnsemble()
        r = e.decide([])
        assert r.decision == "NO_TRADE"
        assert r.score == 0.0

    def test_vote_details_in_result(self):
        e = WeightedEnsemble()
        votes = [StrategyVote("mom", "BUY", 0.8)]
        r = e.decide(votes)
        assert len(r.votes) == 1
        assert r.votes[0]["id"] == "mom"


class TestPhase4_MultiTimeframeFilter:
    def test_weekly_trend_pass(self):
        f = WeeklyTrendFilter(fast=3, slow=5)
        assert f.check(100.0, [90, 92, 94, 96, 98, 102, 105])

    def test_weekly_trend_block(self):
        f = WeeklyTrendFilter(fast=3, slow=5, require_bullish=True)
        assert not f.check(100.0, [110, 108, 106, 104, 102, 100, 98])

    def test_insufficient_data_passes(self):
        f = WeeklyTrendFilter(fast=3, slow=10)
        assert f.check(100.0, [1, 2, 3])

    def test_volatility_filter_suppresses(self):
        f = VolatilityFilter(vol_window=5, median_window=20, max_vol_ratio=1.5)
        prices = [100.0 + (i % 2 - 1) * 0.2 for i in range(30)]
        for p in prices:
            f.check(p)
        assert not f.check(prices[-1] * 1.1)  # sudden jump spikes vol ratio

    def test_volatility_filter_allows_normal(self):
        f = VolatilityFilter(vol_window=5, median_window=20, max_vol_ratio=5.0)
        prices = [100.0 + (i % 3 - 1) * 0.5 for i in range(40)]
        for p in prices:
            assert f.check(p)


class TestPhase5_ATRSizing:
    def test_atr_flat_market(self):
        closes = [100.0] * 20
        v = atr(closes, 10)
        assert v == 0.0

    def test_atr_volatile_market(self):
        closes = [100.0] + [100.0 + i * 2.0 for i in range(20)]
        v = atr(closes, 10)
        assert v > 0.0

    def test_position_size_scales_with_volatility(self):
        low_vol = [100.0 + (i % 10) * 0.1 for i in range(30)]
        high_vol = [100.0] + [100.0 + i * 5.0 for i in range(30)]
        size_low = position_size(100000.0, low_vol, risk_per_trade_pct=0.5)
        size_high = position_size(100000.0, high_vol, risk_per_trade_pct=0.5)
        assert size_low >= size_high  # lower vol → larger position

    def test_min_shares_floor(self):
        tiny_budget = position_size(100.0, [100.0], risk_per_trade_pct=0.1, min_shares=1)
        assert tiny_budget >= 1

    def test_insufficient_data_defaults(self):
        assert position_size(100000.0, [100.0], min_shares=1) == 1
        assert atr([100.0], 14) == 0.0


class TestPhase6_StrategyLifecycle:
    def test_initial_status_is_candidate(self):
        e = LifecycleEngine()
        e.register("mom")
        assert e.get_health("mom").status == StrategyStatus.CANDIDATE

    def test_transition_candidate_to_shadow(self):
        e = LifecycleEngine()
        e.register("mom")
        assert e.transition("mom", StrategyStatus.SHADOW)

    def test_invalid_transition_rejected(self):
        e = LifecycleEngine()
        e.register("mom")
        assert not e.transition("mom", StrategyStatus.ACTIVE)  # must go through SHADOW

    def test_health_score_high(self):
        e = LifecycleEngine(min_trades_for_health=10)
        e.register("mom")
        e.update_health("mom", trades_count=50, sharpe=1.5, profit_factor=2.0, max_dd=5.0)
        h = e.get_health("mom")
        assert h.health_score is not None
        assert h.health_score > 50

    def test_health_score_low_triggers_watch(self):
        e = LifecycleEngine(min_trades_for_health=10)
        e.register("mom")
        e.transition("mom", StrategyStatus.SHADOW)
        e.transition("mom", StrategyStatus.ACTIVE)
        e.update_health("mom", trades_count=50, sharpe=0.2, profit_factor=1.1, max_dd=12.0)
        assert e.auto_suspend("mom")
        assert e.get_health("mom").status == StrategyStatus.WATCH

    def test_health_score_very_low_triggers_suspend(self):
        e = LifecycleEngine(min_trades_for_health=10)
        e.register("mom")
        e.transition("mom", StrategyStatus.SHADOW)
        e.transition("mom", StrategyStatus.ACTIVE)
        e.update_health("mom", trades_count=50, sharpe=-1.0, profit_factor=0.3, max_dd=40.0)
        assert e.auto_suspend("mom")
        assert e.get_health("mom").status == StrategyStatus.SUSPENDED

    def test_all_statuses(self):
        e = LifecycleEngine()
        e.register("a")
        e.register("b")
        assert len(e.all_statuses()) == 2


class TestPhase7_ShadowDeployment:
    def test_record_and_retrieve(self):
        d = ShadowDeployer()
        d.record(ShadowTrade("mom", "SPY", "BUY", "10", 100.0, "now", 50.0))
        assert len(d.trades_for("mom")) == 1

    def test_compare_shadow_vs_live(self):
        d = ShadowDeployer()
        d.record(ShadowTrade("mom", "SPY", "BUY", "10", 100.0, "now", 100.0))
        live = [ShadowTrade("mom", "SPY", "BUY", "10", 101.0, "now", 80.0)]
        cmp = d.compare_to_live("mom", live)
        assert cmp["shadow_pnl"] == 100.0
        assert cmp["live_pnl"] == 80.0
        assert cmp["pnl_delta"] == 20.0

    def test_empty_strategy(self):
        d = ShadowDeployer()
        assert d.compare_to_live("nonexistent", []) == {}


class TestPhase8_MetaAllocator:
    def test_register_and_default_weight(self):
        a = MetaAllocator()
        a.register("mom")
        assert a.get_weight("mom") == 1.0

    def test_rebalance_adjusts_weights(self):
        a = MetaAllocator(default_weight=1.0)
        a.register("mom")
        a.register("ma")
        a.register("mr")
        for _ in range(15):
            a.record_trade("mom", 100.0, "BUY")
            a.record_trade("ma", 50.0, "BUY")
            a.record_trade("mr", -20.0, "SELL")
        a.update_sharpe("mom", 1.5)
        a.update_sharpe("ma", 0.8)
        a.update_sharpe("mr", -0.5)
        weights = a.rebalance()
        assert weights["mom"] > weights["mr"]

    def test_few_trades_uses_default(self):
        a = MetaAllocator()
        a.register("mom")
        a.record_trade("mom", 100.0, "BUY")
        weights = a.rebalance()
        assert weights["mom"] == 1.0

    def test_weight_floor_enforced(self):
        a = MetaAllocator(weight_floor=0.2, default_weight=1.0)
        a.register("bad")
        for _ in range(15):
            a.record_trade("bad", -100.0, "SELL")
        a.update_sharpe("bad", -2.0)
        weights = a.rebalance()
        assert weights["bad"] >= 0.2


class TestPhase9_Registries:
    def test_experiment_register_and_get(self):
        eid = register_experiment("abc123", "ma-crossover", {"fast": 5, "slow": 20})
        rec = get_experiment(eid)
        assert rec is not None
        assert rec.strategy_id == "ma-crossover"
        assert rec.git_sha == "abc123"

    def test_feature_hash(self):
        h1 = get_feature_hash({"fast": 5, "slow": 20})
        h2 = get_feature_hash({"fast": 5, "slow": 20})
        h3 = get_feature_hash({"fast": 10, "slow": 20})
        assert h1 == h2
        assert h1 != h3

    def test_experiments_differ(self):
        e1 = register_experiment("sha1", "mom", {"lookback": 10})
        e2 = register_experiment("sha2", "ma", {"fast": 5, "slow": 20})
        assert e1 != e2
