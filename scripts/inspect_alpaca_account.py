import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()
api_key = os.environ.get("APCA_API_KEY_ID")
secret_key = os.environ.get("APCA_API_SECRET_KEY")

client = TradingClient(api_key, secret_key, paper=True)
account = client.get_account()
positions = client.get_all_positions()

print("=" * 60)
print(f"Alpaca Paper Account: {account.account_number}")
print(f"Status:               {account.status}")
print(f"Portfolio Value:      ${float(account.portfolio_value):,.2f}")
print(f"Equity:               ${float(account.equity):,.2f}")
print(f"Cash:                 ${float(account.cash):,.2f}")
print(f"Buying Power:         ${float(account.buying_power):,.2f}")
print(f"Pattern Day Trader:   {account.pattern_day_trader}")
print(f"Daytrade Count:       {account.daytrade_count}")
print("=" * 60)
print(f"Open Positions ({len(positions)}):")
for p in positions:
    print(f"  {p.symbol:<6} | Qty: {p.qty:>4} | MktVal: ${float(p.market_value):>9.2f} | PnL: ${float(p.unrealized_pl):>8.2f} ({float(p.unrealized_plpc):.2%})")
print("=" * 60)
