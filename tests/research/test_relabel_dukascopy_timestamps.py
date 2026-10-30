"""Relabel correctness: timestamps follow the stored minute, nothing else moves."""

from scripts.relabel_dukascopy_timestamps import relabel, serialize


def bar(timestamp, minute, n=3):
    return {"timestamp": timestamp, "minute": minute, "n": n,
            "o_bid": 1.1, "h_bid": 1.1002, "l_bid": 1.0998, "c_bid": 1.1}


def test_relabel_uses_stored_minute_not_ordinal():
    rows = [bar("2025-08-01T13:00:00Z", 0),
            bar("2025-08-01T13:01:00Z", 2),
            bar("2025-08-01T13:02:00Z", 7)]

    out, fixed = relabel(rows, "EURUSD")

    assert [r["timestamp"] for r in out] == [
        "2025-08-01T13:00:00Z", "2025-08-01T13:02:00Z", "2025-08-01T13:07:00Z"]
    assert fixed == 2


def test_relabel_preserves_order_and_all_other_fields():
    rows = [bar("2025-08-01T23:00:00Z", 0, n=11),
            bar("2025-08-01T23:01:00Z", 59, n=4)]

    out, fixed = relabel(rows, "EURUSD")

    assert [r["timestamp"] for r in out] == [
        "2025-08-01T23:00:00Z", "2025-08-01T23:59:00Z"]
    assert [r["minute"] for r in out] == [0, 59]
    assert out[0]["n"] == 11 and out[1]["n"] == 4
    assert out[1] == {**rows[1], "timestamp": "2025-08-01T23:59:00Z"}
    assert fixed == 1


def test_relabel_refuses_minute_outside_the_hour():
    for bad in (-1, 60, None, "5"):
        try:
            relabel([bar("2025-08-01T13:00:00Z", bad)])
        except ValueError:
            continue
        raise AssertionError(f"minute {bad!r} was accepted")


def test_relabel_refuses_a_non_monotonic_result():
    rows = [bar("2025-08-01T13:00:00Z", 7),
            bar("2025-08-01T13:01:00Z", 2)]
    try:
        relabel(rows, "EURUSD")
    except ValueError:
        return
    raise AssertionError("a backwards minute was accepted")


def test_serialization_is_compact_and_stable():
    rows = [bar("2025-08-01T13:00:00Z", 0)]
    assert serialize(rows) == (
        '[{"timestamp":"2025-08-01T13:00:00Z","minute":0,"n":3,'
        '"o_bid":1.1,"h_bid":1.1002,"l_bid":1.0998,"c_bid":1.1}]')
    assert " " not in serialize(rows)
