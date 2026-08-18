# CRYPTO-001 — Funding / basis carry

- **Status:** Preregistered 2026-08-14. Parameters frozen before OOS read.
- **Economic mechanism:** Perp longs pay shorts when funding is positive. A hedged short-perp / long-spot inventory collects that transfer if it exceeds round-trip fees, spread, and slippage.
- **Not:** an OHLCV directional indicator. No MA/RSI/VWAP/breakout.

## Frozen parameters
See `CRYPTO-001-prereg.json`. Threshold `0.0001` per 8h funding. Universe BTCUSDT+ETHUSDT. IS 2024-08-14..2026-02-13, OOS 2026-02-14..2026-08-14.

## Expected failure modes
Crowded funding mean-reverts inside the fee envelope; basis and fees eat the transfer; concentration if one coin dominates.
