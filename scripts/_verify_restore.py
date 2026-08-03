import tempfile, os
from titan._core import RiskConfig, RiskGate, Money, EventStore, KillSwitchState, TradingState

cfg = RiskConfig(
    ["AAPL"], Money("50000", "USD"), 1000, 5000,
    Money("100000", "USD"), 0.1, Money("5000", "USD"), 5000, 100,
)

# Scenario A: fresh empty store -> must start Active/Armed (not halted)
tmp = tempfile.mkdtemp()
db1 = os.path.join(tmp, "fresh.db")
s1 = EventStore(db1)
g1 = RiskGate.load_or_default(cfg, s1)
print("A fresh store   -> kill_switch:", g1.kill_switch, "| trading_state:", g1.trading_state)

# Scenario B: triggered then persisted -> restart must restore Triggered
s2 = EventStore(os.path.join(tmp, "killed.db"))
g2 = RiskGate.load_or_default(cfg, s2)
g2.trigger_kill_switch()
g2.persist_state(s2)
g3 = RiskGate.load_or_default(cfg, s2)  # restart
print("B killed restart-> kill_switch:", g3.kill_switch, "| trading_state:", g3.trading_state)
b_ok = g3.kill_switch == KillSwitchState.Triggered
print("B semantics:", "PASS fail-closed" if b_ok else "FAIL (reverted to trade)")

# Scenario C: file with a corrupt/truncated payload -> fail-closed
db3 = os.path.join(tmp, "corrupt.db")
import sqlite3
conn = sqlite3.connect(db3)
conn.execute("CREATE TABLE events (message_id TEXT PRIMARY KEY, message_type TEXT NOT NULL, schema_version INTEGER NOT NULL, occurred_at TEXT NOT NULL, correlation_id TEXT, causation_id TEXT, aggregate_type TEXT NOT NULL, aggregate_id TEXT NOT NULL, source TEXT, payload TEXT, metadata TEXT)")
conn.execute("INSERT INTO events (message_id, message_type, schema_version, occurred_at, correlation_id, causation_id, aggregate_type, aggregate_id, source, payload, metadata) VALUES ('msg-1', 'RiskStateSnapshot', 1, '2026-01-01T00:00:00Z', '', '', 'RiskGate', 'system', '', 'NOT_JSON{', '')")
conn.commit(); conn.close()
try:
    RiskGate.load_or_default(cfg, EventStore(db3))
    print("C corrupt store  -> returned (expected raise) | FAIL")
except RuntimeError as e:
    print("C corrupt store  -> raised (fail-closed):", str(e)[:50], "| PASS")
    print("C fail-closed: PASS (engine will not silently trade on corrupt risk state)")

print("A=Active expected:", "PASS" if g1.trading_state == TradingState.Active else "FAIL")