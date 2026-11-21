"""Project TITAN — Autonomous Google Stitch Integration.

Uses the Stitch MCP API to:
1. Create a dedicated Stitch Project 'TITAN Quantitative Workstation V2'
2. Generate the high-density desktop screen using GEMINI_3_8_FLASH
3. Retrieve and download the generated HTML/Tailwind frontend code and screenshot
"""

import os
import sys
import json
import urllib.request
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

    try:
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
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise RuntimeError(f"HTTP Error {e.code}: {err_msg}")


def main():
    print("=================================================================")
    print("TITAN <-> GOOGLE STITCH AUTONOMOUS DESIGN WORKFLOW")
    print("=================================================================")

    # Step 1: Create project
    print("\n[1/3] Creating Stitch Project: 'TITAN Quantitative Workstation V2'...")
    proj_resp = call_stitch("create_project", {"title": "TITAN Quantitative Workstation V2"})
    print("Project Response:", json.dumps(proj_resp, indent=2))
    
    project_full_name = proj_resp.get("name") or proj_resp.get("project", {}).get("name")
    if not project_full_name:
        raise RuntimeError(f"Could not extract project name from {proj_resp}")
    
    project_id = project_full_name.split("/")[-1]
    print(f"SUCCESS: Project created with ID: {project_id}")

    # Step 2: Read prompt
    prompt_text = """
Create an ultra-productive, high-density institutional algorithmic trading workstation for 'Project TITAN' (Alpaca Paper PA33BCWZ2NX8).

Aesthetic:
- Theme: Deep Obsidian Navy (#080C14 canvas, #0F172A slate container cards, #1E293B subtle borders).
- Palette: Emerald green (#10B981) for gains/safe, Crimson (#F43F5E) for losses/halts, Electric cyan (#06B6D4) for active telemetry and tournament highlights, Vivid amber (#F59E0B) for PDT risk warnings.
- Typography: Sans-serif Inter for headers, JetBrains Mono with tabular numbers for all prices, sizes, and timestamps.
- Density: Compact Bloomberg/Linear trading desk density (8px to 12px padding). High signal-to-noise ratio.

Screen Hierarchy:
1. Top Global Navigation:
   - Left: TITAN brand mark with pulse badge 'Alpaca Paper (PA33BCWZ2NX8) ACTIVE' and Market Status 'Closed (Pre-Market 07:00 AM ET)'.
   - Right: 'Halt All Trading' emergency kill-switch button with confirmation guard.
2. Master KPI Ribbon:
   - Total Portfolio Equity: $101,001.64 (+1.03% 24h PnL sparkline)
   - Cash Balance: $90,495.46 | Buying Power: $391,399.16
   - FINRA PDT Safety Corridor Gauge: Visual progress meter showing $25,000 regulatory floor vs $101,001 equity (Status: TIER 1 SAFE, +$74.7k cushion).
   - Realized PnL: +$1,047.90
3. Left Column (Alpha Tournament Battleground):
   - Sleeve A: US Equities PEAD + Quality L/S ($60,000 budget, 7 open positions, 13 staged rebalance orders, status: 'Rebalancing at 10:30 AM ET').
   - Sleeve B: 24/7 Crypto Trend Scanner ($25,000 budget, signals: BUY 4.62 ETH/USD @ $1,801.10, BUY 111.7 SOL/USD @ $74.58).
   - Sleeve C: Defined-Risk Options Yield ($15,000 budget, SPY Weekly Bull Put Credit Spread, Target Credit: $85, Max Collateral Risk: $415).
4. Right Column (Live Execution & Holdings):
   - Active Holdings Table: Sortable table with live Alpaca positions (SPY 7 shs -$90.01, AAPL 10 shs +$1,047.90, IWM 2 shs, MSFT 1 sh, GOOGL 1 sh, AMZN 1 sh, TLT 2 shs).
   - Staged Order Dispatcher: 13 pending delta rebalance orders staged with estimated friction $15.94.
   - Real-time Terminal Log: Dark streaming console window showing live Server-Sent Events (SSE) and hourly telegram dispatches.
"""

    print(f"\n[2/3] Generating Desktop Screen via GEMINI_3_8_FLASH for project {project_id}...")
    gen_resp = call_stitch("generate_screen_from_text", {
        "projectId": project_id,
        "prompt": prompt_text.strip(),
        "deviceType": "DESKTOP",
        "modelId": "GEMINI_3_8_FLASH"
    })
    print("Generation Response:", json.dumps(gen_resp, indent=2))

    # Step 3: Fetch screen files
    screen_name = gen_resp.get("name") or gen_resp.get("screen", {}).get("name")
    print(f"\nSUCCESS: Generated Screen Resource: {screen_name}")

    output_dir = _REPO_ROOT / "dashboard" / "stitch_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "generation_result.json", "w") as f:
        json.dump({"project_id": project_id, "screen": gen_resp}, f, indent=2)

    print(f"\n[3/3] Output saved to: {output_dir}")
    print(f"Stitch Canvas Web URL: https://stitch.withgoogle.com/projects/{project_id}")

if __name__ == "__main__":
    main()
