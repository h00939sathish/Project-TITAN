"""Daily TITAN TWS paper report -> Telegram.

Reads: paper_session_console.log (heartbeats), titan-YYYYMMDD.log (events),
       metrics-YYYYMMDD.json (registry), and live TWS account state (read-only).
Sends a compact daily report to the user's Telegram chat.

Usage:
    python scripts/daily_telegram_report.py [YYYY-MM-DD]
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8555799588")


def _bot_token() -> str | None:
    env_path = Path(os.getenv("LOCALAPPDATA", "")) / "hermes" / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _send_telegram(text: str) -> bool:
    token = _bot_token()
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not found in hermes .env")
        return False
    payload = json.dumps({"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"ERROR: telegram send failed: {e}")
        return False


def _last_heartbeat() -> str | None:
    log = ROOT / "paper_session_console.log"
    if not log.exists():
        return None
    lines = log.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in reversed(lines):
        if "uptime=" in line and "kw=" in line:
            return line.strip()
    return None


def _parse_log_events(day: date) -> dict:
    """Summarize the day's titan log (JSONL)."""
    log = ROOT / f"titan-{day:%Y%m%d}.log"
    out = {
        "intents_accepted": [],
        "intents_rejected": [],
        "fills": [],
        "fill_failed": [],
        "rejected": [],
        "kill_switch": [],
        "reconcile": [],
        "errors": [],
    }
    if not log.exists():
        return out
    for line in log.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = rec.get("message", "")
        payload = rec.get("payload", {}) or {}
        sev = rec.get("severity", "")
        if "Intent accepted" in msg:
            out["intents_accepted"].append(payload.get("broker_order_id", msg))
        elif "Intent rejected" in msg:
            out["intents_rejected"].append(msg)
        elif "fill_failed" in msg:
            out["fill_failed"].append(payload.get("instrument_id", ""))
        elif "Order " in msg and "filled" in msg:
            out["fills"].append(payload.get("instrument_id", ""))
        elif "Order " in msg and "rejected" in msg:
            out["rejected"].append(payload.get("instrument_id", ""))
        elif "Kill switch" in msg or "kill switch" in msg.lower():
            out["kill_switch"].append(msg)
        elif "Reconcile" in msg or "reconciliation" in msg.lower():
            out["reconcile"].append(msg)
        if sev == "ERROR":
            out["errors"].append(msg)
    return out


def _broker_snapshot() -> dict | None:
    """Live read-only TWS query for real account truth."""
    adapter = None
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from titan.execution.ibkr_adapter import IBKRPaperAdapter

        adapter = IBKRPaperAdapter(client_id=140, account_id="DUQ284074")
        adapter.authenticate()
        pos = adapter.positions("DUQ284074")
        bal = adapter.holdings("DUQ284074")
        positions = [
            f"{p.instrument_id} {p.side} {p.quantity}" for p in pos.positions
        ]
        return {
            "cash": str(bal.cash),
            "equity": str(bal.portfolio_value),
            "positions": positions,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        # Clean disconnect is critical: os._exit() without it drops the ibapi
        # connection mid-flight, which can wedge TWS's API server (account
        # queries start timing out while market data keeps flowing).
        if adapter is not None:
            try:
                adapter._client.disconnect()
            except Exception:
                pass


def _per_instrument_metrics(day: date) -> dict:
    """Read the per-instrument breakdown from the session's metrics dump."""
    for suffix in (day.strftime("%Y%m%d"),):
        metrics_path = ROOT / f"metrics-{suffix}.json"
        if not metrics_path.exists():
            continue
        try:
            data = json.loads(metrics_path.read_text(encoding="utf-8"))
            per = data.get("per_instrument", {})
            if isinstance(per, dict):
                return per
        except Exception:
            return {}
    return {}


def main() -> None:
    label = "EOD" if "--label" in sys.argv and "EOD" in sys.argv else None
    day_arg = next((a for a in sys.argv[1:] if a[:1].isdigit()), None)
    day = date.fromisoformat(day_arg) if day_arg else date.today()
    if day.weekday() >= 5:  # weekend: no market, still report status
        pass

    hb = _last_heartbeat()
    ev = _parse_log_events(day)
    broker = _broker_snapshot()

    # Heartbeat fields: [ts] [icon] uptime=.. intents=.. fills=.. rej=.. drift=.. kw=.. strat=.. ready=.. prices=.. cash=.. pv=.. data=.. log=..
    hb_fields = {}
    if hb:
        for m in re.finditer(r"(\w+)=([\w./:+-]+)", hb):
            hb_fields[m.group(1)] = m.group(2)
        hb_fields["ts"] = hb[1:20] if hb.startswith("[") else ""

    status = "RUNNING" if "[" in (hb or "") else "STOPPED"
    kw_map = {"0": "RELEASED", "1": "ARMED", "2": "TRIGGERED"}
    kw = kw_map.get(hb_fields.get("kw", ""), "?")

    lines = []
    lines.append(f"TITAN Paper Report - {day}{' (EOD)' if label else ''}")
    lines.append("-" * 40)
    lines.append(f"Session: {status} | data={hb_fields.get('data', '?')}")
    lines.append(f"Kill switch: {kw} | uptime={hb_fields.get('uptime', '?')}")
    lines.append(
        f"Engine: cash={hb_fields.get('cash', '?')} pv={hb_fields.get('pv', '?')} "
        f"| prices={hb_fields.get('prices', '?')} ready={hb_fields.get('ready', '?')}"
    )
    lines.append(f"Strategy: {hb_fields.get('strat', '?')}")

    if broker:
        if "error" in broker:
            lines.append(f"TWS query: {broker['error']}")
        else:
            lines.append(f"TWS acct DUQ284074: cash={broker['cash']} equity={broker['equity']}")
            if broker["positions"]:
                lines.append("TWS positions: " + ", ".join(broker["positions"]))
            else:
                lines.append("TWS positions: (flat)")
    else:
        lines.append("TWS query: unavailable")

    lines.append("")
    lines.append(f"Today: intents={len(ev['intents_accepted'])} accepted, {len(ev['intents_rejected'])} rejected | fills={len(ev['fills'])} | fill_failed={len(ev['fill_failed'])} | rejected={len(ev['rejected'])}")
    if ev["intents_accepted"]:
        lines.append("Accepted: " + ", ".join(str(x) for x in ev["intents_accepted"][:8]))
    if ev["intents_rejected"]:
        lines.append("Rejected: " + "; ".join(str(x) for x in ev["intents_rejected"][:6]))
    if ev["fills"]:
        lines.append("Fills: " + ", ".join(str(x) for x in ev["fills"][:8]))
    if ev["fill_failed"]:
        lines.append("Fill-failed: " + ", ".join(str(x) for x in ev["fill_failed"][:8]))
    if ev["kill_switch"]:
        lines.append("Kill switch events: " + "; ".join(ev["kill_switch"][-3:]))
    if ev["errors"]:
        lines.append("Errors: " + "; ".join(ev["errors"][-3:]))

    # Per-instrument breakdown (from metrics-YYYYMMDD.json, written by the session).
    per_instrument = _per_instrument_metrics(day)
    if per_instrument:
        lines.append("")
        lines.append("Per instrument:")
        for sym, s in per_instrument.items():
            side = s.get("side", "NONE")
            pos = s.get("position", 0)
            pos_str = f"{pos} ({side})" if side != "NONE" else "flat"
            lines.append(
                f"  {sym:<8} in={s.get('intents', 0)} fl={s.get('fills', 0)} "
                f"rj={s.get('rejections', 0)} | {pos_str} | px={s.get('price', '?')}"
            )

    text = "\n".join(lines)
    print(text)
    ok = _send_telegram(text)
    print(f"\n[telegram send: {'OK' if ok else 'FAILED'}]")
    # The ibapi client thread keeps the process alive after disconnect; exit hard
    # so cron schedulers don't wait on a hang.
    # The ibapi client thread keeps the process alive after disconnect — exit
    # hard once the message is sent.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
