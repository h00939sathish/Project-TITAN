from titan._core import RiskConfig, TradeIntent, RiskGate, Money
from datetime import datetime, timezone

cfg = RiskConfig(
    ["AAPL"], Money("50000", "USD"), 1000, 5000,
    Money("100000", "USD"), 0.1, Money("5000", "USD"), 5000, 100,
)
gate = RiskGate(cfg)
ts = datetime.now(timezone.utc).isoformat()


def verb(s): return "REJECTED" if not s else "accepted"


neg = TradeIntent("s", "p", "a", "AAPL", "BUY", "-5", "MARKET", "DAY", "1.0", ts)
print("neg qty    ->", verb(gate.evaluate(neg, None, None, None, None, None, None).accepted))
zero = TradeIntent("s", "p", "a", "AAPL", "BUY", "0", "MARKET", "DAY", "1.0", ts)
print("zero qty   ->", verb(gate.evaluate(zero, None, None, None, None, None, None).accepted))
bad = TradeIntent("s", "p", "a", "AAPL", "BUY", "abc", "MARKET", "DAY", "1.0", ts)
print("bad qty    ->", verb(gate.evaluate(bad, None, None, None, None, None, None).accepted))
ok = TradeIntent("s", "p", "a", "AAPL", "BUY", "10", "MARKET", "DAY", "1.0", ts)
print("valid qty  ->", verb(gate.evaluate(ok, None, None, None, None, None, None).accepted))