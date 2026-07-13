"""Normalize raw market data to canonical format."""

from datetime import datetime


VENDOR_SYMBOL_MAP = {
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
}


def normalize_row(row: dict, source: str = "csv") -> dict | str:
    """Normalize a single row. Returns normalized dict or error message string."""
    try:
        symbol = row.get("symbol", "").strip().upper()
        canonical = VENDOR_SYMBOL_MAP.get(symbol)
        if not canonical:
            return f"Unknown symbol: {symbol}"

        date_str = row.get("date", "").strip()
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return f"Invalid date: {date_str}"

        fields = {"open", "high", "low", "close", "volume"}
        parsed = {}
        for f in fields:
            val = row.get(f, "").strip()
            try:
                parsed[f] = float(val) if f != "volume" else int(val)
            except (ValueError, TypeError):
                return f"Invalid {f}: {val}"

        if parsed["volume"] < 0:
            return f"Negative volume: {parsed['volume']}"
        if parsed["low"] > parsed["high"]:
            return f"Low > high: low={parsed['low']} high={parsed['high']}"
        if parsed["close"] < parsed["low"] or parsed["close"] > parsed["high"]:
            return f"Close outside range: close={parsed['close']} low={parsed['low']} high={parsed['high']}"

        return {
            "instrument_id": canonical,
            "timestamp": dt.isoformat(),
            "open": parsed["open"],
            "high": parsed["high"],
            "low": parsed["low"],
            "close": parsed["close"],
            "volume": parsed["volume"],
        }
    except Exception as e:
        return f"Processing error: {e}"
