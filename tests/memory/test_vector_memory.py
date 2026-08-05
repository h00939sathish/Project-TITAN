"""Unit tests for Vectorized Strategy Memory & Advisory Reflection Engine."""

import pytest
from titan.memory.vector_memory import (
    TradeMemoryRecord,
    VectorTradeMemory,
    cosine_similarity,
)


class TestVectorMemory:
    def test_cosine_similarity_computation(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        v3 = [0.0, 1.0, 0.0]
        v4 = [-1.0, 0.0, 0.0]

        assert abs(cosine_similarity(v1, v2) - 1.0) < 1e-6
        assert abs(cosine_similarity(v1, v3) - 0.0) < 1e-6
        assert abs(cosine_similarity(v1, v4) - (-1.0)) < 1e-6

    def test_store_and_vector_search(self):
        mem = VectorTradeMemory()

        r1 = TradeMemoryRecord(
            trade_id="t-1",
            strategy_id="ma_crossover",
            instrument_id="AAPL",
            entry_price=150.0,
            exit_price=160.0,
            pnl=100.0,
            return_pct=0.0667,
            holding_period_seconds=3600.0,
            regime_tags=["TRENDING_UP", "LOW_VOLATILITY"],
            embedding_vector=[1.0, 0.5, 0.2],
            reflection_note="Clean trend continuation above 20 SMA",
        )

        r2 = TradeMemoryRecord(
            trade_id="t-2",
            strategy_id="mean_reversion",
            instrument_id="SPY",
            entry_price=440.0,
            exit_price=430.0,
            pnl=-100.0,
            return_pct=-0.0227,
            holding_period_seconds=1800.0,
            regime_tags=["HIGH_VOLATILITY"],
            embedding_vector=[0.1, -0.9, 0.8],
            reflection_note="False breakout during FOMC announcement",
        )

        mem.store_trade(r1)
        mem.store_trade(r2)

        assert mem.count() == 2
        assert mem.get_trade("t-1") == r1

        # Search with query vector close to r1
        query = [0.9, 0.4, 0.1]
        results = mem.search_similar_trades(query, top_k=1)
        assert len(results) == 1
        assert results[0].record.trade_id == "t-1"
        assert results[0].similarity > 0.95

    def test_regime_reflection_retrieval(self):
        mem = VectorTradeMemory()

        r1 = TradeMemoryRecord(
            trade_id="t-1",
            strategy_id="rsi_strat",
            instrument_id="QQQ",
            entry_price=350.0,
            exit_price=355.0,
            pnl=50.0,
            return_pct=0.014,
            holding_period_seconds=1200.0,
            regime_tags=["HIGH_VOLATILITY", "OVERBOUGHT"],
            reflection_note="Quick scalp on RSI divergence",
        )

        mem.store_trade(r1)

        reflections = mem.get_regime_reflections("HIGH_VOLATILITY")
        assert len(reflections) == 1
        assert "Quick scalp on RSI divergence" in reflections[0]

        empty = mem.get_regime_reflections("NONEXISTENT")
        assert len(empty) == 0
