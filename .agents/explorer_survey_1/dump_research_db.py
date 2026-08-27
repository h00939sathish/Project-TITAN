import sqlite3
import json

conn = sqlite3.connect('research_data/titan_research.db')
cursor = conn.cursor()

print("=== QUALIFICATIONS TABLE ===")
cursor.execute("SELECT * FROM qualifications")
for row in cursor.fetchall():
    print(row)

print("\n=== RUNS TABLE ===")
cursor.execute("SELECT id, strategy_id, instrument, label, n_bars, n_trades, return_pct, sharpe, max_dd_pct, win_rate, profit_factor, commission, data_source FROM runs")
for row in cursor.fetchall():
    print(row)

print("\n=== SHADOW EVENTS SUMMARY ===")
cursor.execute("SELECT strategy_id, instrument, count(*), min(bar_date), max(bar_date) FROM shadow_events GROUP BY strategy_id, instrument")
for row in cursor.fetchall():
    print(row)

conn.close()
