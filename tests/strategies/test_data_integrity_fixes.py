"""Unit tests verifying data integrity fixes for strategies and data pipeline."""

from titan.strategies.traderdev_ema9vwap import TraderDevEMA9VWAP
from titan.strategies.orb import make_orb_signal_fn
from titan.strategies.bridge import StrategyBridge


def test_traderdev_ema9vwap_volume_weighting():
    """Verify that TraderDevEMA9VWAP computes volume-weighted average price when volume is present, and falls back to SMA when volume is 0."""
    strat = TraderDevEMA9VWAP(ema_period=2, vwap_period=3, atr_period=2)
    
    # Feed bars with price=10 and volume=100
    b1 = {"close": 10.0, "high": 10.5, "low": 9.5, "volume": 100}
    b2 = {"close": 12.0, "high": 12.5, "low": 11.5, "volume": 100}
    b3 = {"close": 20.0, "high": 20.5, "low": 19.5, "volume": 1000}  # Large volume weight at 20.0
    
    strat.update_bar(b1)
    strat.update_bar(b2)
    strat.update_bar(b3)
    
    # Cumulative VWAP should be heavily weighted towards 20.0:
    # PV = (10*100) + (12*100) + (20*1000) = 1000 + 1200 + 20000 = 22200
    # V = 100 + 100 + 1000 = 1200
    # VWAP = 22200 / 1200 = 18.5
    # Whereas SMA = (10 + 12 + 20) / 3 = 14.0
    
    closes = list(strat.closes)[-3:]
    vols = list(strat.volumes)[-3:]
    vwap = sum(p * v for p, v in zip(closes, vols)) / sum(vols)
    sma = sum(closes) / 3
    
    assert vwap == 18.5
    assert sma == 14.0


def test_orb_zero_volume_handling():
    """Verify that ORB strategy does not suppress signals when fed zero-volume FX data."""
    params = {"atr_period": 2, "min_volume_ratio": 1.5, "breakout_mult": 1.0}
    orb = make_orb_signal_fn(params)
    
    # Bars with 0 volume (FX feed)
    bars = [
        {"high": 10.0, "low": 9.0, "close": 9.5, "volume": 0},
        {"high": 10.0, "low": 9.0, "close": 9.5, "volume": 0},
        {"high": 12.0, "low": 9.5, "close": 11.5, "volume": 0},  # Upside breakout with 0 volume
    ]
    
    # Feed bars step by step as the strategy expects
    orb(bars[:1])
    orb(bars[:2])
    signal = orb(bars[:3])
    assert signal == 1.0


def test_bridge_warmup_with_ohlcv_dict():
    """Verify that StrategyBridge.warmup accepts full OHLCV dicts and passes high/low bounds."""
    bridge = StrategyBridge(
        strategy_id="traderdev-ema9-vwap",
        strategy_params={"ema_period": 2, "vwap_period": 2, "atr_period": 2},
    )
    
    # Warmup with list of OHLCV dicts
    bars = [
        {"timestamp": "2026-08-08T00:00:00Z", "open": 10.0, "high": 12.0, "low": 8.0, "close": 10.0, "volume": 100},
        {"timestamp": "2026-08-08T01:00:00Z", "open": 10.0, "high": 14.0, "low": 9.0, "close": 11.0, "volume": 100},
    ]
    
    bridge.warmup("EURUSD", bars)
    
    fn = bridge._signals["EURUSD"]
    strat = getattr(fn, "strat", None)
    assert strat is not None
    assert len(strat.ranges) > 0
    # Range of 2nd bar = max(high-low, abs(close-prev_close)) = max(14-9, 11-10) = 5.0
    assert strat.ranges[-1] == 5.0
