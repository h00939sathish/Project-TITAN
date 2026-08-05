from titan.data.normalize import normalize_row


def test_normalize_valid():
    row = {
        "symbol": "AAPL",
        "date": "2024-01-15",
        "open": "150.0",
        "high": "155.0",
        "low": "149.0",
        "close": "153.0",
        "volume": "1000000",
    }
    result = normalize_row(row)
    assert isinstance(result, dict)
    assert result["instrument_id"] == "AAPL"
    assert result["volume"] == 1000000


def test_normalize_unknown_symbol():
    row = {"symbol": "INVALID", "date": "2024-01-15", "open": "100", "high": "110", "low": "90", "close": "105", "volume": "1000"}
    result = normalize_row(row)
    assert isinstance(result, str)
    assert "Unknown symbol" in result


def test_normalize_invalid_date():
    row = {"symbol": "AAPL", "date": "not-a-date", "open": "100", "high": "110", "low": "90", "close": "105", "volume": "1000"}
    result = normalize_row(row)
    assert isinstance(result, str)
    assert "Invalid date" in result


def test_normalize_negative_volume():
    row = {"symbol": "AAPL", "date": "2024-01-15", "open": "100", "high": "110", "low": "90", "close": "105", "volume": "-5"}
    result = normalize_row(row)
    assert isinstance(result, str)
    assert "Negative volume" in result


def test_normalize_low_gt_high():
    row = {"symbol": "AAPL", "date": "2024-01-15", "open": "100", "high": "90", "low": "110", "close": "105", "volume": "1000"}
    result = normalize_row(row)
    assert isinstance(result, str)
    assert "Low > high" in result


def test_normalize_close_outside():
    row = {"symbol": "AAPL", "date": "2024-01-15", "open": "100", "high": "105", "low": "95", "close": "110", "volume": "1000"}
    result = normalize_row(row)
    assert isinstance(result, str)
    assert "Close outside range" in result


def test_normalize_forex_pair():
    row = {"symbol": "EURUSD", "date": "2026-07-20", "open": "1.1000",
           "high": "1.1050", "low": "1.0950", "close": "1.1020"}
    result = normalize_row(row)
    assert isinstance(result, dict)
    assert result["instrument_id"] == "EURUSD"


def test_normalize_forex_no_volume():
    row = {"symbol": "EURUSD", "date": "2026-07-20", "open": "1.1000",
           "high": "1.1050", "low": "1.0950", "close": "1.1020"}
    result = normalize_row(row)
    assert isinstance(result, dict)
    assert result["volume"] == 0


def test_normalize_forex_with_volume():
    row = {"symbol": "EURUSD", "date": "2026-07-20", "open": "1.1000",
           "high": "1.1050", "low": "1.0950", "close": "1.1020", "volume": "15000"}
    result = normalize_row(row)
    assert isinstance(result, dict)
    assert result["volume"] == 15000


def test_normalize_xauusd_without_volume():
    from titan.data.normalize import normalize_row
    result = normalize_row({
        "symbol": "XAUUSD", "date": "2026-07-20",
        "open": "2348.00", "high": "2355.00",
        "low": "2345.00", "close": "2350.25",
    })
    assert result["instrument_id"] == "XAUUSD"
    assert result["volume"] == 0
