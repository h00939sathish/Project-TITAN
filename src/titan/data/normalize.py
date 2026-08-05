from datetime import datetime, timezone

from titan.data.forex_pairs import FOREX_SYMBOLS
from titan.data.spot_metals import SPOT_METAL_SYMBOLS

ALLOWED_SYMBOLS = frozenset({
    "AAPL", "MSFT", "GOOGL", "AMZN", "SPY", "QQQ", "IWM", "TLT", "GLD",
}) | FOREX_SYMBOLS | SPOT_METAL_SYMBOLS


def _parse_timestamp(date_str: str) -> datetime:
    date_str = date_str.strip()
    if not date_str:
        raise ValueError("Empty timestamp string")
    if date_str.isdigit():
        return datetime.fromtimestamp(float(date_str), tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    raise ValueError(f"Invalid timestamp format: {date_str}")


def normalize_row(row: dict, source: str = "csv") -> dict | str:
    try:
        symbol = row.get("symbol", "").strip().upper()
        if symbol not in ALLOWED_SYMBOLS:
            return f"Unknown symbol: {symbol}"

        date_str = (row.get("date") or row.get("timestamp") or "").strip()
        try:
            dt = _parse_timestamp(date_str)
        except ValueError:
            return f"Invalid date: {date_str}"



        fields = {"open", "high", "low", "close"}
        parsed = {}
        for f in fields:
            val = row.get(f, "").strip()
            try:
                parsed[f] = float(val)
            except (ValueError, TypeError):
                return f"Invalid {f}: {val}"

        vol_val = row.get("volume", "").strip()
        if vol_val:
            try:
                parsed["volume"] = int(float(vol_val))
            except (ValueError, TypeError):
                return f"Invalid volume: {vol_val}"

        else:
            parsed["volume"] = 0

        if parsed["volume"] < 0:
            return f"Negative volume: {parsed['volume']}"
        if parsed["low"] > parsed["high"]:
            return f"Low > high: low={parsed['low']} high={parsed['high']}"
        if parsed["close"] < parsed["low"] or parsed["close"] > parsed["high"]:
            return (f"Close outside range: close={parsed['close']} "
                    f"low={parsed['low']} high={parsed['high']}")

        return {
            "instrument_id": symbol,
            "timestamp": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open": parsed["open"],

            "high": parsed["high"],
            "low": parsed["low"],
            "close": parsed["close"],
            "volume": parsed["volume"],
        }
    except Exception as e:
        return f"Processing error: {e}"
