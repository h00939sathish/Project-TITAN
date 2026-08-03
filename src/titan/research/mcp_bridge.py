"""Model Context Protocol (MCP) Tool Bridge Interface for TITAN Research Sandboxes."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any

from titan.research.walkforward import WalkForwardConfig, WalkForwardOptimizer
from titan.research.harness import load_bars, make_ma_signal_fn
from titan.memory.vector_memory import VectorTradeMemory, TradeMemoryRecord


@dataclass
class MCPToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]


class MCPResearchBridge:
    """Dispatches Model Context Protocol (MCP) requests for AI strategy research tools."""

    def __init__(self, memory: VectorTradeMemory | None = None):
        self.memory = memory or VectorTradeMemory()

    def get_tool_definitions(self) -> list[MCPToolDefinition]:
        """Returns registered MCP tool schemas."""
        return [
            MCPToolDefinition(
                name="list_strategies",
                description="List registered strategy identifiers in TITAN research framework",
                input_schema={"type": "object", "properties": {}},
            ),
            MCPToolDefinition(
                name="run_walkforward",
                description="Execute rolling walk-forward optimization on historical CSV bar data",
                input_schema={
                    "type": "object",
                    "properties": {
                        "data_path": {"type": "string"},
                        "train_size": {"type": "integer", "default": 250},
                        "test_size": {"type": "integer", "default": 50},
                    },
                    "required": ["data_path"],
                },
            ),
            MCPToolDefinition(
                name="query_trade_memory",
                description="Query stored advisory trade memory records by strategy ID",
                input_schema={
                    "type": "object",
                    "properties": {
                        "strategy_id": {"type": "string"},
                    },
                    "required": ["strategy_id"],
                },
            ),
        ]

    def handle_mcp_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Dispatch MCP tool execution request and return structured JSON result."""
        if method == "list_strategies":
            return {
                "status": "success",
                "strategies": ["ma_crossover", "rsi_mean_reversion", "bollinger_breakout", "momentum_trend"],
            }

        elif method == "run_walkforward":
            data_path = params.get("data_path", "")
            train_size = int(params.get("train_size", 250))
            test_size = int(params.get("test_size", 50))

            try:
                bars = load_bars(data_path)
                config = WalkForwardConfig(
                    train_size=train_size,
                    test_size=test_size,
                    param_grid={"fast": [5, 10], "slow": [20, 30]},
                )
                optimizer = WalkForwardOptimizer()
                res = optimizer.run(bars, make_ma_signal_fn, config)

                return {
                    "status": "success",
                    "num_windows": res.summary["num_windows"],
                    "is_sharpe": res.is_sharpe,
                    "oos_sharpe": res.oos_sharpe,
                    "wfe": res.wfe,
                    "passed_gate": res.passed_gate,
                }
            except Exception as e:
                return {"status": "error", "error": str(e)}

        elif method == "query_trade_memory":
            strategy_id = params.get("strategy_id", "")
            trades = self.memory.get_strategy_trades(strategy_id)
            return {
                "status": "success",
                "trade_count": len(trades),
                "trades": [asdict(t) for t in trades],
            }

        else:
            return {"status": "error", "error": f"Unknown MCP tool method: {method}"}
