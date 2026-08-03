import threading, time
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract


class IBData(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.prices = {}

    def nextValidId(self, orderId: int):
        self.reqMarketDataType(3)  # DELAYED_FROZEN

        c = Contract()
        c.symbol = "SPY"
        c.secType = "STK"
        c.exchange = "ARCA"
        c.currency = "USD"
        self.reqMktData(1001, c, "", False, False, [])

    def tickPrice(self, reqId, tickType, price, attrib):
        types = {1: "BID", 2: "ASK", 4: "LAST", 6: "HIGH", 7: "LOW", 9: "CLOSE"}
        t = types.get(tickType, str(tickType))
        self.prices[t] = price
        print(f"  {t}: {price}")

    def tickSize(self, reqId, tickType, size):
        pass

    def tickString(self, reqId, tickType, value):
        if tickType == 48:
            print(f"  RTVolume: {value}")

    def error(self, reqId, code, msg, *args):
        if code not in (2104, 2106, 2158, 2159):
            print(f"  [Err {code}] {msg}")


app = IBData()
app.connect("127.0.0.1", 7497, clientId=103)
t = threading.Thread(target=app.run, daemon=True)
t.start()
time.sleep(5)

print(f"\n=== SPY Prices (delayed) ===")
for k, v in sorted(app.prices.items()):
    print(f"  {k}: {v}")

if not app.prices:
    print("  No prices received — may need market data subscription")

app.disconnect()
