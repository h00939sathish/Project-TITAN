"""Project TITAN — Autonomous Google Stitch Desktop Generation.

Fuses the architecture of the legacy 'TRADE' dashboard with TITAN's live telemetry:
- Explicit deviceType: DESKTOP
- Widescreen 1440p trading workstation layout
- Sidebar nav + Top regulatory & emergency control strip
- Holdings blotter (with actual short and long positions: AMAT, QCOM, BAC, CRM, SPY, IWM, GOOGL, TLT)
- Active pending limit orders (COST, WMT, XOM)
- Multi-asset tournament cards (Equities, Crypto, Options)
- Live terminal log console
"""

import os
import sys
import json
import urllib.request
import base64
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(_REPO_ROOT / ".env")

STITCH_TOKEN = os.getenv("STITCH_API_KEY")
if not STITCH_TOKEN:
    print("Error: STITCH_API_KEY not found in .env", file=sys.stderr)
    sys.exit(1)

STITCH_ENDPOINT = "https://stitch.googleapis.com/mcp"
PROJECT_ID = "4243797105115682806"

def call_stitch(tool_name: str, arguments: dict) -> dict:
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        STITCH_ENDPOINT,
        data=payload,
        headers={
            "X-Goog-Api-Key": STITCH_TOKEN,
            "Content-Type": "application/json"
        }
    )

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if "error" in data:
            raise RuntimeError(f"JSON-RPC Error: {data['error']}")
        content = data.get("result", {}).get("content", [])
        for c in content:
            if c.get("type") == "text":
                try:
                    return json.loads(c["text"])
                except json.JSONDecodeError:
                    return {"text": c["text"]}
        return data.get("result", {})

def download_file(resource_name: str) -> dict:
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "download_file",
            "arguments": {"name": resource_name}
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        STITCH_ENDPOINT,
        data=payload,
        headers={
            "X-Goog-Api-Key": STITCH_TOKEN,
            "Content-Type": "application/json"
        }
    )

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        txt = data.get("result", {}).get("content", [{}])[0].get("text", "")
        return json.loads(txt)


def main():
    print("=================================================================")
    print("TITAN <-> GOOGLE STITCH DESKTOP WORKSTATION GENERATION")
    print("=================================================================")

    desktop_prompt = """
Build an ultra high-density widescreen DESKTOP quantitative trading workstation for 'Project TITAN' (Resolution: 1440px wide desktop interface).
Design strictly for desktop viewport with a persistent left navigation sidebar and a multi-column command center grid.

Aesthetic:
- Theme: Deep Obsidian Navy financial terminal (#080C14 canvas, #0F172A slate cards, #1E293B dividing borders).
- Accents: Emerald green (#10B981) for profits/fills/safe status, Crimson red (#F43F5E) for losses/halts/shorts, Electric cyan (#06B6D4) for active highlights, Vivid amber (#F59E0B) for PDT warnings.
- Typography: Clean Inter for labels, strict JetBrains Mono with tabular numbers for all prices, sizes, and timestamps.
- Information Density: High institutional trading desk density (padding 8px to 12px, zero wasted whitespace).

Layout & Structure:
1. Left Navigation Sidebar (Compact 220px width):
   - Brand: TITAN QUANT with animated pulse green status dot.
   - Nav items: [Overview Dashboard, Live Execution Blotter, Active Holdings, Multi-Asset Tournament, Strategy Alpha, Engine Logs, Settings].
   - Bottom Profile & Connection: Broker: ALPACA PAPER (PA33BCWZ2NX8), Latency: 14ms.

2. Top Regulatory & Emergency Control Header Strip:
   - System Status: 'SYSTEM: PAPER LIVE' badge in emerald green border.
   - PDT Capital Corridor: Visual progress bar showing $25,000 regulatory floor vs $100,926.09 current equity with badge 'SAFE (Tier 1 Margin, +$74.6k Cushion)'.
   - Quick PnL: Today P&L '+$1,047.90 (+1.03%)'.
   - Action Controls:
     - Button '[PAUSE APPROVALS]' (amber outline).
     - Guarded Emergency Button '[KILL SWITCH]' (crimson red with shield alert icon).

3. Master KPI Metric Ribbon (Top Row, 5 Cards):
   - Card 1: Total Equity: $100,926.09 (with 24h PnL sparkline).
   - Card 2: Available Cash: $133,682.25 (elevated via short proceeds).
   - Card 3: Buying Power: $306,128.60.
   - Card 4: Margin Utilization: 24.8% (Tier 1 compliant).
   - Card 5: Engine Health: 10/10 Orders Filled, 0 Errors, 100% Pacing.

4. Central Desktop Grid (Two Columns):
   - Left Column (60% width):
     - Active Holdings Table (Blotter):
       Sortable table with columns: Symbol, Side (LONG pill in green, SHORT pill in red), Qty, Fill Price, Current Mark, Unrealized PnL, PnL %, Actions.
       Rows:
       * AMAT: SHORT -62 shs | Fill $160.47 | Mark $159.66 | PnL +$50.22 (+0.23%)
       * QCOM: SHORT -67 shs | Fill $148.73 | Mark $148.34 | PnL +$25.85 (+0.23%)
       * BAC: SHORT -237 shs | Fill $42.51 | Mark $42.52 | PnL -$2.31 (-0.02%)
       * CRM: LONG +30 shs | Fill $331.39 | Mark $330.88 | PnL -$15.30 (-0.27%)
       * SPY: LONG +7 shs | Mark $5,108.11 | PnL -$157.98
       * IWM: LONG +2 shs | Mark $536.32
       * GOOGL: LONG +1 sh | Mark $289.33
       * TLT: LONG +2 shs | Mark $160.24
     - Active Working Orders Queue:
       Pending limit orders:
       * BUY 11 COST @ $907.51 (Status: OPEN / NEW)
       * BUY 113 WMT @ $88.93 (Status: OPEN / NEW)
       * BUY 99 XOM @ $101.71 (Status: OPEN / NEW)
       Buttons per order: [CANCEL], [MODIFY].

   - Right Column (40% width):
     - Multi-Asset Alpha Tournament Cards:
       * Sleeve A (US Equities L/S): Budget $60,000 | 8 Live Positions | Rebalance Done (10:30 AM ET) | Day Return +0.84%.
       * Sleeve B (24/7 Crypto Trend): Budget $25,000 | BTC/ETH/SOL 4h Scanner | Signal: BUY ETH @ $1,801, BUY SOL @ $74.58.
       * Sleeve C (Defined-Risk Options): Budget $15,000 | SPY Bull Put Spread | Target Credit $85, Max Risk $415.
     - Intraday Equity Curve Area Chart with Session High $101.4K and volume tick marks.

5. Bottom Full-Width Console: Real-time Execution & Telemetry Log:
   - Dark monospace streaming log panel showing live Server-Sent Events (SSE), order fill receipts, Alpaca API clock heartbeats, and hourly council Telegram dispatches.
"""

    print(f"Calling Stitch MCP generate_screen_from_text (deviceType: DESKTOP) on project {PROJECT_ID}...")
    resp = call_stitch("generate_screen_from_text", {
        "projectId": PROJECT_ID,
        "prompt": desktop_prompt.strip(),
        "deviceType": "DESKTOP",
        "modelId": "GEMINI_3_8_FLASH"
    })

    print("Generation complete!")
    print("Response keys:", list(resp.keys()))

    # Extract screen files
    screen_data = resp.get("outputComponents", [{}])[0].get("design", {}).get("screens", [{}])[0]
    html_info = screen_data.get("htmlCode", {})
    img_info = screen_data.get("screenshot", {})

    print(f"HTML Resource: {html_info.get('name')}")
    print(f"Screenshot Resource: {img_info.get('name')}")

    out_dir = _REPO_ROOT / "dashboard" / "stitch_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    art_dir = Path("C:/Users/h0093/.gemini/antigravity-cli/brain/2ee61ccc-17cf-456c-86a9-1373c5de05bf")

    if html_info.get("name"):
        html_file = download_file(html_info["name"])
        html_text = html_file.get("html", "")
        (out_dir / "titan_desktop_screen.html").write_text(html_text, encoding="utf-8")
        (art_dir / "titan_desktop_screen.html").write_text(html_text, encoding="utf-8")
        # Also update titan_terminal_screen.html so /stitch serves the new desktop view!
        (out_dir / "titan_terminal_screen.html").write_text(html_text, encoding="utf-8")
        (art_dir / "titan_terminal_screen.html").write_text(html_text, encoding="utf-8")
        print(f"Saved Desktop HTML ({len(html_text)} chars)")

    if img_info.get("name"):
        img_file = download_file(img_info["name"])
        img_b64 = img_file.get("image", "")
        raw_png = base64.b64decode(img_b64)
        (out_dir / "titan_desktop_screen.png").write_bytes(raw_png)
        (art_dir / "titan_desktop_screen.png").write_bytes(raw_png)
        (out_dir / "titan_terminal_screen.png").write_bytes(raw_png)
        (art_dir / "titan_terminal_screen.png").write_bytes(raw_png)
        print(f"Saved Desktop PNG ({len(raw_png)} bytes)")

    print(f"\nALL ASSETS SAVED! Web URL: https://stitch.google.com/projects/{PROJECT_ID}")

if __name__ == "__main__":
    main()
