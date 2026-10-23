"""Deterministic adversarial falsification probes for research backtests.

No model inference, no broker access, no capital-path authority. A FAIL means
the evidence bundle is not admissible for promotion until it is reconciled.

This is the Probe layer of the Harness² pilot (see
``docs/proposals/HARNESS2-PILOT.md``). The checks are intentionally structural:
they catch accounting and lifecycle errors that make a result look better than
the executable strategy could have been.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from titan.research.validator import is_underpowered

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
UNVERIFIABLE = "UNVERIFIABLE"

_PROMOTION_VERDICTS = {"promote", "promoted", "candidate", "pass", "passed", "accept"}


@dataclass(frozen=True)
class Finding:
    probe: str
    status: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class FalsificationReport:
    findings: list[Finding]

    @property
    def verdict(self) -> str:
        if any(f.status == FAIL for f in self.findings):
            return FAIL
        if any(f.status == UNVERIFIABLE for f in self.findings):
            return "INCONCLUSIVE"
        return PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "findings": [asdict(f) for f in self.findings],
        }

    def to_markdown(self) -> str:
        lines = [
            "# Falsification report",
            "",
            f"**Verdict:** {self.verdict}",
            "",
            "| Probe | Status | Detail |",
            "|---|---|---|",
        ]
        for f in self.findings:
            lines.append(f"| {f.probe} | {f.status} | {f.detail} |")
        return "\n".join(lines)

    def exit_code(self) -> int:
        return 1 if self.verdict == FAIL else 0


def _side(trade: dict[str, Any]) -> str:
    side = str(trade.get("side", "")).lower()
    if side in {"buy", "entry", "long", "open"}:
        return "buy"
    if side in {"sell", "exit", "short", "close"}:
        return "sell"
    return side or "unknown"


def _num(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _pnl_identity(equity: list[float], trades: list[dict[str, Any]]) -> Finding:
    buys = [t for t in trades if _side(t) == "buy"]
    sells = [t for t in trades if _side(t) == "sell"]
    if not trades:
        return Finding("pnl_identity", UNVERIFIABLE, "no trades to reconcile")
    if not sells:
        return Finding(
            "pnl_identity",
            FAIL,
            "no exit leg: an open position at the end is not recorded as a trade",
            {"buys": len(buys), "sells": 0},
        )

    buy_pnl = sum(_num(t.get("pnl")) for t in buys)
    sell_pnl = sum(_num(t.get("pnl")) for t in sells)
    equity_delta = equity[-1] - equity[0] if len(equity) >= 2 else None
    evidence = {
        "entry_leg_pnl": round(buy_pnl, 4),
        "exit_leg_pnl": round(sell_pnl, 4),
        "equity_delta": None if equity_delta is None else round(equity_delta, 4),
    }

    tolerance = max(1.0, abs(equity_delta or 0.0) * 1e-4)
    if abs(buy_pnl) > tolerance and abs(sell_pnl) > tolerance:
        return Finding(
            "pnl_identity",
            FAIL,
            "round-trip pnl is recorded on both legs; summing the trade log double-counts it",
            evidence,
        )
    if equity_delta is None:
        return Finding("pnl_identity", UNVERIFIABLE, "equity curve is missing", evidence)
    if abs(sell_pnl - equity_delta) <= tolerance:
        return Finding("pnl_identity", PASS, "exit-leg pnl reconciles with equity change", evidence)
    if abs(buy_pnl - equity_delta) <= tolerance:
        return Finding("pnl_identity", PASS, "entry-leg pnl reconciles with equity change", evidence)
    return Finding(
        "pnl_identity",
        FAIL,
        "neither leg reconciles with the equity change",
        evidence,
    )


def _trade_lifecycle(
    trades: list[dict[str, Any]], n_bars: int | None
) -> Finding:
    buys = [t for t in trades if _side(t) == "buy"]
    sells = [t for t in trades if _side(t) == "sell"]
    if not trades:
        return Finding("trade_lifecycle", UNVERIFIABLE, "no trades")
    if len(buys) != len(sells):
        return Finding(
            "trade_lifecycle",
            FAIL,
            "unbalanced entries and exits; the final position is not logged",
            {"entries": len(buys), "exits": len(sells)},
        )
    if len(sells) == 1 and (n_bars is None or n_bars > 20):
        return Finding(
            "trade_lifecycle",
            WARN,
            "only one round trip; exit logic was barely exercised",
            {"round_trips": 1, "n_bars": n_bars},
        )
    for buy, sell in zip(buys, sells):
        entry_ts = str(buy.get("timestamp", ""))
        exit_ts = str(sell.get("timestamp", ""))
        if entry_ts and exit_ts and exit_ts <= entry_ts:
            return Finding(
                "trade_lifecycle",
                FAIL,
                "an exit is not after its entry",
                {"entry": entry_ts, "exit": exit_ts},
            )
    return Finding(
        "trade_lifecycle",
        PASS,
        "every entry has a later exit",
        {"round_trips": len(sells)},
    )


def _costs(trades: list[dict[str, Any]]) -> Finding:
    if not trades:
        return Finding("costs", UNVERIFIABLE, "no trades")
    total = sum(
        _num(t.get("commission"))
        + _num(t.get("spread_cost"))
        + _num(t.get("slippage_cost"))
        for t in trades
    )
    if total <= 0.0:
        return Finding("costs", FAIL, "trades carry no commission, spread or slippage")
    gross = sum(
        abs(_num(t.get("price")) * _num(t.get("qty")))
        for t in trades
        if _side(t) == "buy"
    )
    evidence = {"total_cost": round(total, 4), "gross_notional": round(gross, 4)}
    if gross > 0:
        cost_bps = total / gross * 10_000
        evidence["cost_bps"] = round(cost_bps, 3)
        if cost_bps < 0.1:
            return Finding(
                "costs",
                WARN,
                "costs are implausibly low relative to notional",
                evidence,
            )
    return Finding("costs", PASS, "frictions are charged", evidence)


def _trade_count(
    trades: list[dict[str, Any]], reported: dict[str, Any]
) -> Finding:
    sells = [t for t in trades if _side(t) == "sell"]
    reported_trades = reported.get("total_trades")
    if reported_trades is None:
        return Finding("trade_count", UNVERIFIABLE, "reported trade count is missing")
    reported_trades = _num(reported_trades)
    evidence = {"reported": reported_trades, "round_trips": len(sells), "legs": len(trades)}
    if reported_trades == len(sells):
        return Finding("trade_count", PASS, "reported count matches round trips", evidence)
    if reported_trades == len(trades):
        return Finding(
            "trade_count",
            FAIL,
            "reported count counts entry and exit legs as two trades",
            evidence,
        )
    return Finding("trade_count", FAIL, "reported count matches neither legs nor round trips", evidence)


def _lookahead(trades: list[dict[str, Any]]) -> Finding:
    checked = 0
    for trade in trades:
        signal_ts = trade.get("signal_timestamp")
        fill_ts = trade.get("timestamp")
        if signal_ts is None or fill_ts is None:
            continue
        checked += 1
        if str(fill_ts) <= str(signal_ts):
            return Finding(
                "lookahead",
                FAIL,
                "a fill is not after its signal",
                {"signal": str(signal_ts), "fill": str(fill_ts)},
            )
    if checked == 0:
        return Finding(
            "lookahead",
            UNVERIFIABLE,
            "trade log has no signal timestamp; execution timing cannot be proven",
        )
    return Finding("lookahead", PASS, "every fill is after its signal", {"checked": checked})


def _gate_integrity(payload: dict[str, Any]) -> Finding:
    gates = payload.get("gates") or []
    if isinstance(gates, dict):
        gates = [
            {"name": name, **(value if isinstance(value, dict) else {"passed": value})}
            for name, value in gates.items()
        ]
    failed = [
        str(g.get("name", g.get("gate", "unnamed")))
        for g in gates
        if isinstance(g, dict) and not g.get("passed", True)
    ]
    verdict = str(payload.get("verdict", "")).lower()
    promoting = verdict in _PROMOTION_VERDICTS
    evidence = {"failed_gates": failed, "verdict": verdict}
    if failed and promoting:
        return Finding(
            "gate_integrity",
            FAIL,
            "a promoting verdict contains failed gates",
            evidence,
        )
    if payload.get("replicated") is False and promoting:
        return Finding(
            "gate_integrity",
            FAIL,
            "an unreplicated result is marked for promotion",
            evidence,
        )
    return Finding("gate_integrity", PASS, "no failed gate is hidden by the verdict", evidence)


def _power(payload: dict[str, Any], reported: dict[str, Any]) -> Finding:
    sharpe = reported.get("sharpe_ratio", payload.get("sharpe_ratio"))
    years = reported.get("years", payload.get("years"))
    if sharpe is None or years is None:
        return Finding("power", UNVERIFIABLE, "Sharpe ratio or sample length is missing")
    underpowered, se = is_underpowered(_num(sharpe), _num(years))
    evidence = {"sharpe": _num(sharpe), "years": _num(years), "se": round(se, 3)}
    if underpowered:
        return Finding(
            "power",
            WARN,
            "sample cannot distinguish this Sharpe from zero; do not record it as a negative result",
            evidence,
        )
    return Finding("power", PASS, "sample has enough power to distinguish Sharpe from zero", evidence)


def falsify(payload: dict[str, Any]) -> FalsificationReport:
    """Run every probe against a research result payload."""
    equity = [_num(x) for x in (payload.get("equity_curve") or payload.get("equity") or [])]
    trades = list(payload.get("trades") or [])
    reported = payload.get("reported") or payload.get("metrics") or {}
    n_bars = payload.get("n_bars")

    findings = [
        _pnl_identity(equity, trades),
        _trade_lifecycle(trades, n_bars),
        _costs(trades),
        _trade_count(trades, reported),
        _lookahead(trades),
        _gate_integrity(payload),
        _power(payload, reported),
    ]
    return FalsificationReport(findings=findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic falsification probes on a research result JSON.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", type=Path, default=None, help="write the report as JSON")
    args = parser.parse_args(argv)

    try:
        payload = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read {args.path}: {exc}")
        return 2
    if not isinstance(payload, dict):
        print("result JSON must be an object")
        return 2

    report = falsify(payload)
    print(report.to_markdown())
    if args.json:
        args.json.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return report.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
