"""Min trade count gate — enforces minimum OOS trades before acceptance."""

from dataclasses import dataclass, field


@dataclass
class GateResult:
    passed: bool
    trade_count: int
    minimum_required: int
    reason: str = ""
    override_doc: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "trade_count": self.trade_count,
            "minimum_required": self.minimum_required,
            "reason": self.reason,
            "override_doc": self.override_doc,
        }


MIN_OOS_TRADES_DEFAULT = 30


def check_min_trades(trade_count: int,
                     minimum: int = MIN_OOS_TRADES_DEFAULT,
                     override_doc: str = "") -> GateResult:
    """Require minimum OOS trades, or a documented reason for low turnover.

    Args:
        trade_count: Number of OOS trades.
        minimum: Minimum acceptable trade count.
        override_doc: Path to a document explaining why a low-turnover
                      strategy is still valid (e.g. structural holding period).

    Returns GateResult with pass/fail and reason.
    """
    if trade_count >= minimum:
        return GateResult(
            passed=True,
            trade_count=trade_count,
            minimum_required=minimum,
            reason=f"Trade count {trade_count} >= minimum {minimum}",
        )

    if override_doc:
        return GateResult(
            passed=True,
            trade_count=trade_count,
            minimum_required=minimum,
            reason=f"Trade count {trade_count} below minimum {minimum}, "
                   f"accepted with override documentation: {override_doc}",
            override_doc=override_doc,
        )

    return GateResult(
        passed=False,
        trade_count=trade_count,
        minimum_required=minimum,
        reason=f"Trade count {trade_count} below minimum {minimum}. "
               f"Provide a documented reason at override_doc to accept "
               f"a low-turnover strategy.",
    )
