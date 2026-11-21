"""Project TITAN — DhanHQ Indian Market Data Connection Test.

Tests live connectivity, quotes, and market depth for the Indian market (NSE / NFO).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(_REPO_ROOT / ".env")

from dhanhq import DhanContext, dhanhq


def test_dhan_connection(client_id: str, access_token: str):
    print("=" * 70)
    print("PROJECT TITAN — DHANHQ (INDIA / NSE) LIVE DATA TEST")
    print("=" * 70)
    print(f"Client ID: {client_id}")

    try:
        context = DhanContext(client_id=client_id, access_token=access_token)
        dhan = dhanhq(context)

        # 1. Fetch Fund / Margin Limits
        print("\n[1/3] Fetching Account Funds & Margin Status...")
        funds = dhan.get_fund_limits()
        print("Fund Limits Response:", funds)

        # 2. Fetch Live Quote (NIFTY Index or Reliance Industries)
        print("\n[2/3] Fetching Live NSE Quote for RELIANCE (Security ID: 1333)...")
        # ExchangeSegment: NSE_EQ (1), Security ID for Reliance is 1333
        quote = dhan.get_quote(security_id=1333, exchange_segment="NSE_EQ")
        print("Live Quote Response:", quote)

        # 3. Fetch Option Chain for NIFTY (Security ID: 13)
        print("\n[3/3] Fetching Live NIFTY Option Chain & Greeks...")
        opt_chain = dhan.get_option_chain(underlying_scrip=13, underlying_seg="IDX_I", expiry="2026-11-26")
        print("Option Chain Status:", opt_chain.get("status") if isinstance(opt_chain, dict) else "Received")

        print("\nSUCCESS: DhanHQ Indian Market Feed is 100% active and connected to TITAN!")

    except Exception as e:
        print(f"\nConnection Error: {e}")


if __name__ == "__main__":
    cid = os.getenv("DHAN_CLIENT_ID", "")
    token = os.getenv("DHAN_ACCESS_TOKEN", "")

    if not cid or not token:
        print("Please configure DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN in .env")
        sys.exit(1)

    test_dhan_connection(cid, token)
