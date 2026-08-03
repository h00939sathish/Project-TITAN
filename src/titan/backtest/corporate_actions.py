from dataclasses import dataclass, field
from copy import deepcopy


@dataclass
class SplitEvent:
    date: str
    instrument_id: str
    ratio: float


@dataclass
class DividendEvent:
    date: str
    instrument_id: str
    amount: float


@dataclass
class CorporateActionsDB:
    splits: list[SplitEvent] = field(default_factory=list)
    dividends: list[DividendEvent] = field(default_factory=list)

    def register_split(self, date: str, instrument_id: str, ratio: float) -> None:
        self.splits.append(SplitEvent(date, instrument_id, ratio))

    def register_dividend(self, date: str, instrument_id: str, amount: float) -> None:
        self.dividends.append(DividendEvent(date, instrument_id, amount))

    def adjust_bars(self, bars: list[dict]) -> list[dict]:
        adjusted = deepcopy(bars)
        sorted_splits = sorted(self.splits, key=lambda e: e.date)
        sorted_divs = sorted(self.dividends, key=lambda e: e.date)
        price_keys = {"open", "high", "low", "close"}

        for bar in adjusted:
            bar_date = bar.get("date") or bar.get("timestamp", "")
            if bar_date and "T" in bar_date:
                bar_date = bar_date[:10]
            bar_inst = bar.get("instrument_id") or bar.get("symbol", "")

            for ev in sorted_splits:
                if bar_inst and ev.instrument_id != bar_inst:
                    continue
                if ev.date >= bar_date:
                    for k in price_keys:
                        bar[k] = bar[k] / ev.ratio
                    bar["volume"] = bar["volume"] * ev.ratio

            for ev in sorted_divs:
                if bar_inst and ev.instrument_id != bar_inst:
                    continue
                if ev.date >= bar_date:
                    for k in price_keys:
                        bar[k] = bar[k] - ev.amount

        return adjusted


_SPY_DIVIDENDS: list[tuple[str, float]] = [
    ("2020-01-02", 1.50), ("2020-04-01", 1.40), ("2020-07-01", 1.35),
    ("2020-10-01", 1.40), ("2021-01-04", 1.45), ("2021-04-01", 1.45),
    ("2021-07-01", 1.45), ("2021-10-01", 1.50), ("2022-01-03", 1.55),
    ("2022-04-01", 1.55), ("2022-07-01", 1.60), ("2022-10-03", 1.60),
    ("2023-01-03", 1.65), ("2023-04-03", 1.65), ("2023-07-03", 1.70),
    ("2023-10-02", 1.70), ("2024-01-02", 1.75), ("2024-04-01", 1.75),
    ("2024-07-01", 1.80), ("2024-10-01", 1.80), ("2025-01-02", 1.85),
    ("2025-04-01", 1.85), ("2025-07-01", 1.90), ("2025-10-01", 1.90),
    ("2026-01-02", 1.95), ("2026-04-01", 1.95), ("2026-07-01", 2.00),
    ("2026-10-01", 2.00),
]


def common_adjustments() -> CorporateActionsDB:
    db = CorporateActionsDB()
    for date, amount in _SPY_DIVIDENDS:
        db.register_dividend(date, "SPY", amount)
    return db
