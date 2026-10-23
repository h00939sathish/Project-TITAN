"""`titan research run <EXP-id>`: research/protocol_WF_v2_PRE_FROZEN.md, executed as written.

No parameter search, no LLM, no promotion. A run either refuses (not eligible under
protocol sections 1 and 3, or a sealed negative already covers it) or produces an evidence
bundle plus a verdict memo under research/wf_v2/results/.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import statistics
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from titan.research.bundle_io import write_bundle

REPO_ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = "research/protocol_WF_v2_PRE_FROZEN.md"
RESULTS_DIR = "research/wf_v2/results"

DATASETS = {
    "dukascopy_1m_ba": "research/dukascopy_1m_ba",
    "dukascopy_1m_ba_prior": "research/dukascopy_1m_ba_prior",
}
EXHAUSTED_PAIRS = frozenset({"EURUSD", "GBPUSD"})
EXHAUSTED_MONTHS = ("2025-08", "2026-07")

# Public policy-rate turning points. Section 1 needs one inside the window.
CENTRAL_BANK_PIVOTS = (
    ("2019-07-31", "Fed first cut of the 2019 cycle"),
    ("2021-12-16", "BoE first hike of the 2021-23 cycle"),
    ("2022-03-16", "Fed first hike of the 2022-23 cycle"),
    ("2022-07-21", "ECB first hike of the 2022-23 cycle"),
    ("2024-03-19", "BoJ ends negative rates"),
    ("2024-06-06", "ECB first cut of the 2024 cycle"),
    ("2024-08-01", "BoE first cut of the 2024 cycle"),
    ("2024-09-18", "Fed first cut of the 2024 cycle"),
)

# Cost engine of the original screens (research/traderdev_fx_screen.py).
COST_RT = 0.8e-4
FX_TICK = "0.00001"
VOL_TARGET = 0.10
EST_VOL = 0.08
LEVERAGE = VOL_TARGET / EST_VOL

MIN_MONTHS = 24
MAX_MISSING_RATE = 0.05
MIN_TRAIN_MONTHS = 6
SHARPE_MIN = 0.0
IC_MIN = 0.02
WINDOW_PASS_RATE = 0.70
MAX_TURNOVER = 60.0

INTERPRETATION = {
    "folds": "Test month k for every k >= 6; train = months [0, k). Parameters are frozen, "
             "so train is indicator warm-up only; signals are computed causally in one pass, "
             "which equals re-running on each expanding train.",
    "window_pass": "Sharpe > 0.0 and Spearman IC(position at bar close, next-bar return) > 0.02; "
                   "an undefined Sharpe or IC fails the window.",
    "aggregate_pass": "Window pass rate >= 0.70, mean Sharpe > 0 and mean IC > 0 "
                      "(undefined values count as 0).",
    "turnover": "Sum of |position change| x leverage over OOS bars, annualized "
                "(one-way traded notional / NAV). Ratified in ADR-036.",
    "costs": "Screen engine: 0.8e-4 of price per round trip, charged as half per unit of "
             "leveraged notional traded on each bar where the position changes (a flip "
             "pays a full round trip), and that bar earns no return; 10% vol target at an "
             "assumed 8% vol. Ratified in ADR-036.",
    "returns": "Shorts earn the negative of the bar return (fixed in the screen as well). "
               "Ratified in ADR-036.",
    "prices": "Bid OHLC resampled from 1m bars; the screen engine has no separate spread term. "
              "Ratified in ADR-036.",
    "missing_ticks": "Expected minutes are all minutes except Fri 22:00 to Sun 22:00 UTC. DST "
                     "and holidays are not modelled, which overstates the missing rate.",
    "regime_pivot": "At least one CENTRAL_BANK_PIVOTS date inside the window.",
    "multi_instrument": "Every instrument must pass on its own.",
    "verdict": "PASS only if every instrument passes every criterion; anything else is FAIL.",
}

_TRADING_MINUTES = (1440, 1440, 1440, 1440, 1320, 0, 120)  # Mon..Sun, UTC
_SPEC_KEYS = {"strategy_id", "strategy_params", "instruments", "timeframe_minutes",
              "window", "position_mode", "evidence_record", "mechanism_id"}
_REQUIRED_SPEC_KEYS = _SPEC_KEYS - {"mechanism_id"}
_EXP_TOKEN = re.compile(r"EXP-0*(\d+)")
_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@dataclass(frozen=True)
class WFv2Spec:
    strategy_id: str
    strategy_params: dict
    instruments: tuple[str, ...]
    timeframe_minutes: int
    window: tuple[str, str]
    position_mode: str
    evidence_record: str
    mechanism_id: str | None = None


@dataclass
class Outcome:
    exp_id: str
    status: str  # REFUSED | ELIGIBLE | PASS | FAIL
    reasons: list[str] = field(default_factory=list)
    bundle_path: Path | None = None
    memo_path: Path | None = None
    report: str = ""

    @property
    def exit_code(self) -> int:
        return {"PASS": 0, "ELIGIBLE": 0, "FAIL": 1}.get(self.status, 2)


# ---- registries --------------------------------------------------------------


def load_hypotheses(root: Path) -> tuple[dict, dict]:
    """Return ({id: Experiment}, {id: legacy kwargs}) from research/hypotheses.py."""
    path = root / "research" / "hypotheses.py"
    spec = importlib.util.spec_from_file_location("titan_research_hypotheses", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    experiments: dict = {}
    for exp in module.hypotheses:
        if exp.id in experiments:
            raise ValueError(f"duplicate hypothesis id {exp.id} in {path}")
        experiments[exp.id] = exp
    legacy = {entry["id"]: entry for entry in getattr(module, "LEGACY_WITHOUT_RATIONALE", [])}
    return experiments, legacy


def _exp_number(exp_id: str) -> int | None:
    m = _EXP_TOKEN.fullmatch(exp_id)
    return int(m.group(1)) if m else None


def sealed_negative_matches(root: Path, exp_id: str, strategy_id: str | None) -> list[str]:
    """Files in research/neg_results/ that seal this experiment or this strategy."""
    number = _exp_number(exp_id)
    strategy_token = (re.compile(rf"(?<![\w-]){re.escape(strategy_id)}(?![\w-])", re.IGNORECASE)
                      if strategy_id else None)
    hits = []
    for path in sorted((root / "research" / "neg_results").glob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        header = path.name + "\n" + next((ln for ln in text.splitlines() if ln.startswith("#")), "")
        ids = {int(n) for n in _EXP_TOKEN.findall(header)}
        if number is not None and number in ids:
            hits.append(f"{path.name} (seals {exp_id})")
        elif strategy_token and strategy_token.search(text):
            hits.append(f"{path.name} (mentions strategy {strategy_id})")
    return hits


def mechanism_statuses(root: Path) -> dict[str, str]:
    """`M-00N` -> status text from docs/MECHANISM_REGISTRY.md."""
    statuses: dict[str, str] = {}
    current = None
    path = root / "docs" / "MECHANISM_REGISTRY.md"
    if not path.exists():
        return statuses
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^###\s+`(M-\d+)`", line)
        if heading:
            current = heading.group(1)
            continue
        status = re.match(r"^\*\s+\*\*Status:\*\*\s*(.+)$", line)
        if current and status and current not in statuses:
            # ASCII only: the status emoji breaks cp1252 stdout when the CLI is piped.
            statuses[current] = status.group(1).encode("ascii", "ignore").decode().strip()
    return statuses


def evidence_verdict(root: Path, rel: str) -> tuple[str | None, str | None]:
    """(verdict, problem) for an evidence record path relative to the repo root."""
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()):
        return None, f"evidence_record {rel} is outside the repository"
    if not path.is_file():
        return None, f"evidence_record {rel} does not exist"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None, f"evidence_record {rel} is not JSON"
    verdict = record.get("verdict") or (record.get("gates") or {}).get("verdict")
    return verdict, None


# ---- spec and static eligibility ----------------------------------------------


def parse_spec(raw: Any) -> tuple[WFv2Spec | None, list[str]]:
    if not isinstance(raw, dict):
        return None, ["hypothesis has no params['wf_v2'] spec, so it is not a WF-v2 candidate"]
    reasons = []
    missing = sorted(_REQUIRED_SPEC_KEYS - raw.keys())
    unknown = sorted(raw.keys() - _SPEC_KEYS)
    if missing:
        reasons.append(f"wf_v2 spec missing keys: {', '.join(missing)}")
    if unknown:
        reasons.append(f"wf_v2 spec has unknown keys: {', '.join(unknown)}")
    if reasons:
        return None, reasons
    window = tuple(raw["window"]) if isinstance(raw["window"], (list, tuple)) else ()
    if len(window) != 2 or not all(isinstance(m, str) and _MONTH.match(m) for m in window):
        reasons.append("window must be two 'YYYY-MM' months (inclusive)")
    elif window[0] > window[1]:
        reasons.append("window start is after window end")
    tf = raw["timeframe_minutes"]
    if not isinstance(tf, int) or tf <= 0 or 1440 % tf:
        reasons.append("timeframe_minutes must be a positive divisor of 1440")
    if raw["position_mode"] not in ("long_short", "long_flat"):
        reasons.append("position_mode must be 'long_short' or 'long_flat'")
    instruments = raw["instruments"]
    if (not isinstance(instruments, (list, tuple)) or not instruments
            or not all(isinstance(i, str) and i for i in instruments)):
        reasons.append("instruments must be a non-empty list of symbols")
    if not isinstance(raw["strategy_params"], dict):
        reasons.append("strategy_params must be a dict")
    if reasons:
        return None, reasons
    return WFv2Spec(
        strategy_id=raw["strategy_id"], strategy_params=dict(raw["strategy_params"]),
        instruments=tuple(instruments), timeframe_minutes=tf, window=window,
        position_mode=raw["position_mode"], evidence_record=raw["evidence_record"],
        mechanism_id=raw.get("mechanism_id"),
    ), []


def months_between(start: str, end: str) -> list[str]:
    y, m = map(int, start.split("-"))
    end_y, end_m = map(int, end.split("-"))
    out = []
    while (y, m) <= (end_y, end_m):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def window_reasons(spec: WFv2Spec) -> list[str]:
    reasons = []
    months = months_between(*spec.window)
    if len(months) < MIN_MONTHS:
        reasons.append(f"window {spec.window[0]}..{spec.window[1]} is {len(months)} months; "
                       f"section 1 needs >= {MIN_MONTHS}")
    banned = set(months_between(*EXHAUSTED_MONTHS))
    burned = sorted(set(spec.instruments) & EXHAUSTED_PAIRS)
    if burned and banned & set(months):
        reasons.append(f"window overlaps the exhausted {EXHAUSTED_MONTHS[0]}..{EXHAUSTED_MONTHS[1]} "
                       f"in-sample window for {', '.join(burned)} (sections 1 and 5)")
    first = date.fromisoformat(months[0] + "-01")
    last_y, last_m = map(int, months[-1].split("-"))
    after = date(last_y + (last_m == 12), last_m % 12 + 1, 1)
    if not any(first <= date.fromisoformat(d) < after for d, _ in CENTRAL_BANK_PIVOTS):
        reasons.append("no central-bank pivot inside the window (section 1 regime coverage)")
    return reasons


# ---- data ---------------------------------------------------------------------


def load_minutes(path: Path) -> Iterable[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_minutes(months: list[str]) -> int:
    total = 0
    for mk in months:
        y, m = map(int, mk.split("-"))
        d = date(y, m, 1)
        while d.month == m:
            total += _TRADING_MINUTES[d.weekday()]
            d += timedelta(days=1)
    return total


def _is_trading_minute(dt: datetime) -> bool:
    wd = dt.weekday()
    if wd == 5:
        return False
    if wd == 4:
        return dt.hour < 22
    if wd == 6:
        return dt.hour >= 22
    return True


def resample_window(rows: Iterable[dict], months: list[str], minutes: int) -> tuple[list[dict], dict]:
    """Bid OHLC bars for `months` at `minutes`, plus the 1m coverage of that window."""
    wanted = set(months)
    step = minutes * 60
    bars: list[dict] = []
    cur: dict | None = None
    cur_key = None
    last_ts = ""
    present = 0
    months_seen: set[str] = set()
    for row in rows:
        ts = row["timestamp"]
        if ts < last_ts:
            raise ValueError(f"1m data is not time-ordered at {ts}")
        last_ts = ts
        mk = ts[:7]
        if mk not in wanted:
            continue
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        months_seen.add(mk)
        present += _is_trading_minute(dt)
        key = int(dt.timestamp()) // step
        if key != cur_key:
            if cur:
                bars.append(cur)
            cur_key = key
            start = datetime.fromtimestamp(key * step, timezone.utc)
            cur = {"timestamp": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "open": row["o_bid"], "high": row["h_bid"], "low": row["l_bid"],
                   "close": row["c_bid"], "volume": row.get("n", 0)}
        else:
            cur["high"] = max(cur["high"], row["h_bid"])
            cur["low"] = min(cur["low"], row["l_bid"])
            cur["close"] = row["c_bid"]
            cur["volume"] += row.get("n", 0)
    if cur:
        bars.append(cur)
    expected = expected_minutes(months)
    coverage = {
        "months_in_window": len(months),
        "months_with_data": len(months_seen),
        "months_without_data": [mk for mk in months if mk not in months_seen],
        "expected_minutes": expected,
        "present_minutes": present,
        "missing_rate": round(1 - min(present, expected) / expected, 6) if expected else 1.0,
    }
    return bars, coverage


def coverage_reasons(instrument: str, coverage: dict) -> list[str]:
    reasons = []
    if coverage["months_without_data"]:
        reasons.append(f"{instrument}: not contiguous, no data in "
                       f"{', '.join(coverage['months_without_data'])}")
    if coverage["missing_rate"] >= MAX_MISSING_RATE:
        reasons.append(f"{instrument}: missing-tick rate {coverage['missing_rate']:.2%} "
                       f">= {MAX_MISSING_RATE:.0%}")
    return reasons


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---- evaluation ---------------------------------------------------------------


def _strategy_factory(strategy_id: str):
    import titan.strategies.registrations  # noqa: F401  populates the registry
    from titan.strategies.registry import get_registry
    return get_registry().get(strategy_id).factory


def positions(bars: list[dict], spec: WFv2Spec, instrument: str) -> list[int]:
    """Position held after each bar's close, from the strategy's BUY/SELL signals."""
    signal_fn = _strategy_factory(spec.strategy_id)(dict(spec.strategy_params))
    short = -1 if spec.position_mode == "long_short" else 0
    pos, out = 0, []
    for bar in bars:
        sig = signal_fn(dict(bar, instrument_id=instrument))
        if sig == "BUY":
            pos = 1
        elif sig == "SELL":
            pos = short
        out.append(pos)
    return out


def fold_returns(closes: list[float], pos: list[int], start: int, end: int) -> tuple[list[float], float]:
    """Screen-engine returns on bars [start, end) and the traded notional (NAV units)."""
    rets: list[float] = []
    held = 0
    traded = 0.0
    for i in range(max(start, 1), end):
        target = pos[i - 1]
        if target != held:
            traded_units = abs(target - held) * LEVERAGE
            rets.append(-COST_RT / 2.0 * traded_units)
            traded += traded_units
            held = target
        else:
            rets.append(held * (closes[i] / closes[i - 1] - 1.0) * LEVERAGE)
    return rets, traded


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=xs.__getitem__)
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    rx, ry = _ranks(x), _ranks(y)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return None
    return cov / math.sqrt(vx * vy)


def sharpe(rets: list[float], bars_per_year: float) -> float | None:
    if len(rets) < 2:
        return None
    sd = statistics.stdev(rets)
    if sd == 0:
        return None
    return statistics.fmean(rets) / sd * math.sqrt(bars_per_year)


def evaluate(bars: list[dict], pos: list[int], months: list[str], minutes: int) -> dict:
    closes = [float(b["close"]) for b in bars]
    bars_per_year = 365 * 1440 / minutes
    span: dict[str, list[int]] = {}
    for i, bar in enumerate(bars):
        span.setdefault(bar["timestamp"][:7], [i, i])[1] = i + 1

    windows, oos_rets, traded_total = [], [], 0.0
    for k in range(MIN_TRAIN_MONTHS, len(months)):
        month = months[k]
        start, end = span.get(month, (0, 0))
        rets, traded = fold_returns(closes, pos, start, end) if end > start else ([], 0.0)
        ic = spearman([float(pos[i]) for i in range(start, end - 1)],
                      [closes[i + 1] / closes[i] - 1.0 for i in range(start, end - 1)])
        sh = sharpe(rets, bars_per_year)
        windows.append({
            "test_month": month, "train_months": k, "bars": end - start,
            "sharpe": sh, "ic": ic, "net_return": sum(rets),
            "passed": sh is not None and ic is not None and sh > SHARPE_MIN and ic > IC_MIN,
        })
        oos_rets += rets
        traded_total += traded

    n = len(windows)
    pass_rate = sum(w["passed"] for w in windows) / n if n else 0.0
    mean_sharpe = sum(w["sharpe"] or 0.0 for w in windows) / n if n else 0.0
    mean_ic = sum(w["ic"] or 0.0 for w in windows) / n if n else 0.0
    turnover = traded_total / len(oos_rets) * bars_per_year if oos_rets else 0.0
    net = sum(oos_rets)
    criteria = {
        "window_pass_rate": {"value": pass_rate, "threshold": f">= {WINDOW_PASS_RATE}",
                             "passed": n > 0 and pass_rate >= WINDOW_PASS_RATE},
        "mean_sharpe": {"value": mean_sharpe, "threshold": "> 0", "passed": mean_sharpe > 0},
        "mean_ic": {"value": mean_ic, "threshold": "> 0", "passed": mean_ic > 0},
        "annual_turnover": {"value": turnover, "threshold": f"<= {MAX_TURNOVER}",
                            "passed": turnover <= MAX_TURNOVER},
        "net_oos_return": {"value": net, "threshold": "> 0", "passed": net > 0},
    }
    return {
        "windows": windows,
        "oos_bars": len(oos_rets),
        "criteria": criteria,
        "passed": all(c["passed"] for c in criteria.values()),
    }


def execution_check(bars: list[dict], spec: WFv2Spec, instrument: str) -> dict:
    """Run the strategy through ReplayEngine to confirm the execution path accepts its
    intents. Non-gating: ReplayEngine is not the protocol's cost engine, so its PnL is
    not evidence and is not recorded."""
    from titan.backtest.engine import ReplayEngine

    signal_fn = _strategy_factory(spec.strategy_id)(dict(spec.strategy_params))
    strat = getattr(signal_fn, "strat", None)
    if strat is None:
        return {"skipped": "strategy exposes no .strat object for ReplayEngine"}
    try:
        result = ReplayEngine(strat, [dict(b, instrument_id=instrument) for b in bars],
                              tick_size=FX_TICK).run()
    except Exception as exc:  # diagnostic only; the verdict does not depend on it
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {"trades": result.trades, "rejected_intents": result.rejected_intents,
            "bars_processed": result.bars_processed}


# ---- orchestration ------------------------------------------------------------


def check(exp_id: str, root: Path = REPO_ROOT) -> tuple[Any, WFv2Spec | None, list[str]]:
    """Static eligibility: (experiment, spec, reasons). Empty reasons = may load data."""
    experiments, legacy = load_hypotheses(root)
    if exp_id in legacy:
        return None, None, [f"{exp_id} is a legacy hypothesis with no economic rationale; "
                            "add one in research/hypotheses.py before it can run"]
    exp = experiments.get(exp_id)
    if exp is None:
        known = ", ".join(sorted(experiments) + sorted(legacy))
        return None, None, [f"unknown hypothesis {exp_id}; known: {known}"]

    spec, reasons = parse_spec(exp.params.get("wf_v2"))
    reasons += [f"sealed negative: {hit}" for hit in
                sealed_negative_matches(root, exp_id, spec.strategy_id if spec else None)]
    if spec is None:
        return exp, None, reasons

    if exp.dataset_id not in DATASETS:
        reasons.append(f"dataset_id {exp.dataset_id!r} is not a WF-v2 dataset "
                       f"({', '.join(sorted(DATASETS))})")
    try:
        _strategy_factory(spec.strategy_id)
    except KeyError as exc:
        reasons.append(str(exc).strip("'\""))
    if spec.mechanism_id:
        status = mechanism_statuses(root).get(spec.mechanism_id)
        if status is None:
            reasons.append(f"mechanism {spec.mechanism_id} is not in docs/MECHANISM_REGISTRY.md")
        elif "retired" in status.lower():
            reasons.append(f"mechanism {spec.mechanism_id} is retired: {status}")
    verdict, problem = evidence_verdict(root, spec.evidence_record)
    if problem:
        reasons.append(f"section 3: {problem}")
    elif verdict != "candidate":
        reasons.append(f"section 3: evidence_record verdict is {verdict!r}, not 'candidate'")
    reasons += window_reasons(spec)
    for instrument in spec.instruments:
        if exp.dataset_id in DATASETS:
            path = root / DATASETS[exp.dataset_id] / f"{instrument}.json"
            if not path.is_file():
                reasons.append(f"{instrument}: no data file {path.relative_to(root).as_posix()}")
    return exp, spec, reasons


def _refused(exp_id: str, reasons: list[str]) -> Outcome:
    lines = [f"{exp_id}: REFUSED (not WF-v2 eligible)"] + [f"  - {r}" for r in reasons]
    return Outcome(exp_id, "REFUSED", reasons, report="\n".join(lines))


def run(exp_id: str, root: Path = REPO_ROOT, check_only: bool = False) -> Outcome:
    exp, spec, reasons = check(exp_id, root)
    if reasons:
        return _refused(exp_id, reasons)

    months = months_between(*spec.window)
    data_dir = root / DATASETS[exp.dataset_id]
    loaded, data_reasons = {}, []
    for instrument in spec.instruments:
        path = data_dir / f"{instrument}.json"
        bars, coverage = resample_window(load_minutes(path), months, spec.timeframe_minutes)
        loaded[instrument] = (path, bars, coverage)
        data_reasons += coverage_reasons(instrument, coverage)
    if data_reasons:
        return _refused(exp_id, data_reasons)
    if check_only:
        return Outcome(exp_id, "ELIGIBLE", report=f"{exp_id}: ELIGIBLE for WF-v2 "
                       f"({', '.join(spec.instruments)}, {spec.window[0]}..{spec.window[1]})")

    protocol_path = root / PROTOCOL
    bundle: dict[str, Any] = {
        "experiment_id": exp_id,
        "experiment_fingerprint": exp.fingerprint,
        "question": exp.question,
        "protocol": PROTOCOL,
        "protocol_sha256": _sha256(protocol_path) if protocol_path.exists() else None,
        "interpretation": INTERPRETATION,
        "spec": asdict(spec),
        "dataset_id": exp.dataset_id,
        "data": {},
        "instruments": {},
        "execution_check": {},
    }
    for instrument, (path, bars, coverage) in loaded.items():
        bundle["data"][instrument] = {"path": path.relative_to(root).as_posix(),
                                      "sha256": _sha256(path), "bars": len(bars),
                                      "coverage": coverage}
        pos = positions(bars, spec, instrument)
        bundle["instruments"][instrument] = evaluate(bars, pos, months, spec.timeframe_minutes)
        bundle["execution_check"][instrument] = execution_check(bars, spec, instrument)
    bundle["verdict"] = "PASS" if all(r["passed"] for r in bundle["instruments"].values()) else "FAIL"
    bundle["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bundle = json.loads(json.dumps(bundle))  # tuples -> lists, so reruns compare equal on disk

    out_dir = root / RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = out_dir / f"{exp_id}-wf_v2-bundle.json"
    memo_path = out_dir / f"{exp_id}-wf_v2-verdict.md"
    write_bundle(bundle_path, bundle)
    memo = render_memo(bundle, bundle_path.name)
    if not memo_path.exists() or memo_path.read_text(encoding="utf-8") != memo:
        memo_path.write_text(memo, encoding="utf-8")

    lines = [f"{exp_id}: {bundle['verdict']}"]
    for instrument, result in bundle["instruments"].items():
        failed = [k for k, c in result["criteria"].items() if not c["passed"]]
        lines.append(f"  {instrument}: {'PASS' if result['passed'] else 'FAIL'}"
                     + (f" ({', '.join(failed)})" if failed else ""))
    lines += [f"  bundle: {bundle_path.relative_to(root).as_posix()}",
              f"  memo:   {memo_path.relative_to(root).as_posix()}"]
    return Outcome(exp_id, bundle["verdict"], bundle_path=bundle_path, memo_path=memo_path,
                   report="\n".join(lines))


def _fmt(value: Any) -> str:
    if value is None:
        return "undefined"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def render_memo(bundle: dict, bundle_name: str) -> str:
    spec = bundle["spec"]
    lines = [
        f"# WF-v2 verdict — {bundle['experiment_id']}: {bundle['verdict']}",
        "",
        f"- Question: {bundle['question']}",
        f"- Protocol: {bundle['protocol']} (sha256 {(bundle['protocol_sha256'] or 'missing')[:12]})",
        f"- Strategy: `{spec['strategy_id']}` {json.dumps(spec['strategy_params'], sort_keys=True)}, "
        f"{spec['position_mode']}",
        f"- Window: {spec['window'][0]}..{spec['window'][1]}, {spec['timeframe_minutes']}m bars, "
        f"dataset `{bundle['dataset_id']}`",
        f"- Evidence record: {spec['evidence_record']}",
        f"- Mechanism: {spec['mechanism_id'] or 'none registered'}",
        f"- Bundle: {bundle_name} (generated {bundle['generated_at']})",
        "",
    ]
    for instrument, result in bundle["instruments"].items():
        data = bundle["data"][instrument]
        passed_windows = sum(w["passed"] for w in result["windows"])
        lines += [
            f"## {instrument} — {'PASS' if result['passed'] else 'FAIL'}",
            "",
            f"Data: {data['path']} (sha256 {data['sha256'][:12]}), {data['bars']} bars, "
            f"missing-tick rate {data['coverage']['missing_rate']:.2%}. "
            f"{passed_windows}/{len(result['windows'])} test windows passed.",
            "",
            "| Criterion | Value | Threshold | Result |",
            "|---|---|---|---|",
        ]
        for name, c in result["criteria"].items():
            lines.append(f"| {name} | {_fmt(c['value'])} | {c['threshold']} | "
                         f"{'PASS' if c['passed'] else 'FAIL'} |")
        check_result = bundle["execution_check"].get(instrument, {})
        lines += ["", f"Execution check (ReplayEngine, non-gating): "
                      f"{json.dumps(check_result, sort_keys=True)}", ""]
    lines += ["## Decision (protocol section 7)", ""]
    if bundle["verdict"] == "PASS":
        lines.append("PASS: a paper-trading pilot with strict risk limits may be proposed. "
                     "Promotion still needs a human decision and a signed certificate.")
    else:
        lines.append("FAIL: no promotion. Record a sealed negative in research/neg_results/ and "
                     "do not loop on this strategy and data.")
    lines += ["", "## Interpretation applied", ""]
    lines += [f"- **{k}**: {v}" for k, v in bundle["interpretation"].items()]
    return "\n".join(lines) + "\n"
