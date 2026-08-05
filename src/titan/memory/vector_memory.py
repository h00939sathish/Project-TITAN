"""Vectorized Strategy Memory & Advisory Post-Trade Reflection Engine for TITAN."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TradeMemoryRecord:
    trade_id: str
    strategy_id: str
    instrument_id: str
    entry_price: float
    exit_price: float
    pnl: float
    return_pct: float
    holding_period_seconds: float
    regime_tags: list[str] = field(default_factory=list)
    embedding_vector: list[float] = field(default_factory=list)
    reflection_note: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SimilaritySearchResult:
    record: TradeMemoryRecord
    similarity: float


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = math.sqrt(sum(a * a for a in v1))
    norm_v2 = math.sqrt(sum(b * b for b in v2))

    if norm_v1 == 0.0 or norm_v2 == 0.0:
        return 0.0

    return dot_product / (norm_v1 * norm_v2)


class VectorTradeMemory:
    """Purely advisory vector memory indexing closed trades and market reflections."""

    def __init__(self):
        self._records: dict[str, TradeMemoryRecord] = {}

    def store_trade(self, record: TradeMemoryRecord) -> None:
        """Store a trade memory record."""
        self._records[record.trade_id] = record

    def get_trade(self, trade_id: str) -> TradeMemoryRecord | None:
        return self._records.get(trade_id)

    def search_similar_trades(
        self,
        query_vector: list[float],
        top_k: int = 5,
        min_similarity: float = 0.0,
        strategy_id: str | None = None,
    ) -> list[SimilaritySearchResult]:
        """Find historical trade records with vector embeddings most similar to query_vector."""
        results: list[SimilaritySearchResult] = []

        for record in self._records.values():
            if strategy_id and record.strategy_id != strategy_id:
                continue
            if not record.embedding_vector:
                continue

            sim = cosine_similarity(query_vector, record.embedding_vector)
            if sim >= min_similarity:
                results.append(SimilaritySearchResult(record=record, similarity=sim))

        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:top_k]

    def get_regime_reflections(self, regime_tag: str) -> list[str]:
        """Retrieve reflection notes for historical trades recorded under a specific regime tag."""
        reflections: list[str] = []
        for r in self._records.values():
            if regime_tag in r.regime_tags and r.reflection_note:
                reflections.append(f"[{r.strategy_id} | {r.instrument_id}]: {r.reflection_note}")
        return reflections

    def get_strategy_trades(self, strategy_id: str) -> list[TradeMemoryRecord]:
        return [r for r in self._records.values() if r.strategy_id == strategy_id]

    def count(self) -> int:
        return len(self._records)
