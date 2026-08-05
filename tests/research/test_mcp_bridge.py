"""Unit tests for MCP Tool Bridge Interface."""

import pytest
from titan.research.mcp_bridge import MCPResearchBridge
from titan.memory.vector_memory import VectorTradeMemory, TradeMemoryRecord


class TestMCPResearchBridge:
    def test_get_tool_definitions(self):
        bridge = MCPResearchBridge()
        tools = bridge.get_tool_definitions()
        assert len(tools) >= 3
        names = [t.name for t in tools]
        assert "list_strategies" in names
        assert "run_walkforward" in names
        assert "query_trade_memory" in names

    def test_handle_list_strategies(self):
        bridge = MCPResearchBridge()
        res = bridge.handle_mcp_request("list_strategies", {})
        assert res["status"] == "success"
        assert "ma_crossover" in res["strategies"]

    def test_handle_query_trade_memory(self):
        mem = VectorTradeMemory()
        mem.store_trade(
            TradeMemoryRecord(
                trade_id="t-100",
                strategy_id="ma_crossover",
                instrument_id="AAPL",
                entry_price=100.0,
                exit_price=105.0,
                pnl=50.0,
                return_pct=0.05,
                holding_period_seconds=1000.0,
            )
        )
        bridge = MCPResearchBridge(memory=mem)

        res = bridge.handle_mcp_request("query_trade_memory", {"strategy_id": "ma_crossover"})
        assert res["status"] == "success"
        assert res["trade_count"] == 1
        assert res["trades"][0]["trade_id"] == "t-100"

    def test_unknown_method_error(self):
        bridge = MCPResearchBridge()
        res = bridge.handle_mcp_request("nonexistent_method", {})
        assert res["status"] == "error"
        assert "Unknown MCP tool method" in res["error"]
