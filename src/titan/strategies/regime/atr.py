"""Volatility-based regime detector using rolling return std (ATR-inspired).

Classifies market regime by comparing short-term volatility to its
longer-term median.  Uses close prices only (no high/low required).
"""

import statistics
from collections import deque

from titan.strategies.regime.base import RegimeDetector, RegimeState


class ATRRegimeDetector(RegimeDetector):
    def __init__(
        self,
        vol_window: int = 14,
        median_window: int = 60,
        low_multiple: float = 0.75,
        high_multiple: float = 1.25,
    ):
        self.vol_window = vol_window
        self.median_window = median_window
        self.low_multiple = low_multiple
        self.high_multiple = high_multiple
        self._closes: deque[float] = deque(maxlen=500)

    def update(self, price: float) -> RegimeState | None:
        self._closes.append(price)
        if not self.is_ready:
            return None

        closes = list(self._closes)

        returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(-self.vol_window, 0)
        ]
        current_vol = statistics.stdev(returns) if len(returns) > 1 else 0.0

        vols = []
        for i in range(-self.median_window, 0):
            start = i - self.vol_window
            if start < -len(closes):
                continue
            segment = closes[start:i]
            if len(segment) < 3:
                continue
            seg_returns = [
                (segment[j] - segment[j - 1]) / segment[j - 1]
                for j in range(1, len(segment))
            ]
            vols.append(statistics.stdev(seg_returns))

        median_vol = statistics.median(vols) if vols else current_vol

        trend = (
            (closes[-1] - closes[-(self.vol_window + 1)])
            / closes[-(self.vol_window + 1)]
            if len(closes) >= self.vol_window + 1
            else 0.0
        )
        trend_strength = min(abs(trend) * 100, 1.0)

        low_threshold = median_vol * self.low_multiple
        high_threshold = median_vol * self.high_multiple

        if current_vol <= low_threshold:
            regime = "LOW_VOL"
            vol_label = "LOW"
            confidence = max(0.5, 1.0 - current_vol / max(median_vol, 1e-10))
        elif current_vol >= high_threshold:
            regime = "HIGH_VOL"
            vol_label = "HIGH"
            confidence = max(0.5, current_vol / max(median_vol, 1e-10) - 1.0)
            confidence = min(confidence, 0.99)
        else:
            regime = "MODERATE_VOL"
            vol_label = "MODERATE"
            confidence = 0.5

        return RegimeState(
            regime=regime,
            confidence=round(confidence, 4),
            volatility=vol_label,
            trend_strength=round(trend_strength, 4),
        )

    @property
    def is_ready(self) -> bool:
        return len(self._closes) >= self.median_window + 1
