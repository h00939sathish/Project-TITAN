"""Project TITAN — DhanHQ 24-Hour Token Auto-Renewer Daemon.

SEBI regulations mandate that Indian broker access tokens expire every 24 hours.
This script uses DhanHQ's native /RenewToken API to automatically renew the session
every 18-20 hours, updating .env seamlessly without requiring manual web login.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dhan-renewer")


def get_token_expiration(token: str) -> datetime | None:
    """Decodes JWT payload to extract expiration timestamp."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
        exp_ts = payload.get("exp")
        if exp_ts:
            return datetime.fromtimestamp(exp_ts, tz=timezone.utc)
    except Exception as e:
        logger.warning("Could not parse JWT expiration: %s", e)
    return None


def renew_dhan_token() -> bool:
    load_dotenv(_REPO_ROOT / ".env", override=True)
    client_id = os.getenv("DHAN_CLIENT_ID")
    token = os.getenv("DHAN_ACCESS_TOKEN")

    if not client_id or not token:
        logger.error("DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN missing from .env")
        return False

    from dhanhq import DhanLogin

    login = DhanLogin(client_id)
    try:
        logger.info("Calling DhanHQ /RenewToken for Client ID: %s...", client_id)
        res = login.renew_token(token)
        new_token = res.get("token") or res.get("data", {}).get("token")
        expiry = res.get("expiryTime") or res.get("data", {}).get("expiryTime")

        if not new_token:
            logger.error("DhanHQ did not return a valid new token: %s", res)
            return False

        # Update .env
        env_path = _REPO_ROOT / ".env"
        lines = env_path.read_text(encoding="utf-8").splitlines()
        updated_lines = []
        found = False
        for line in lines:
            if line.startswith("DHAN_ACCESS_TOKEN="):
                updated_lines.append(f"DHAN_ACCESS_TOKEN={new_token}")
                found = True
            else:
                updated_lines.append(line)
        if not found:
            updated_lines.append(f"DHAN_ACCESS_TOKEN={new_token}")

        env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
        logger.info("SUCCESS: Token renewed! Valid until: %s", expiry)
        return True

    except Exception as exc:
        logger.error("Exception during Dhan token renewal: %s", exc)
        return False


def run_renewer_loop(check_interval_seconds: int = 3600):
    logger.info("=================================================================")
    logger.info("TITAN DHANHQ AUTO-RENEWER DAEMON STARTED")
    logger.info("=================================================================")

    while True:
        try:
            load_dotenv(_REPO_ROOT / ".env", override=True)
            token = os.getenv("DHAN_ACCESS_TOKEN", "")
            exp_dt = get_token_expiration(token)

            if exp_dt:
                now_utc = datetime.now(timezone.utc)
                remaining_hours = (exp_dt - now_utc).total_seconds() / 3600.0
                logger.info("Current Dhan token expires in: %.1f hours (at %s)", remaining_hours, exp_dt.isoformat())

                # If less than 6 hours remain, renew it proactively
                if remaining_hours <= 6.0:
                    logger.info("Token has <= 6 hours remaining. Triggering renewal...")
                    renew_dhan_token()
            else:
                # Fallback renewal
                renew_dhan_token()

            time.sleep(check_interval_seconds)

        except KeyboardInterrupt:
            logger.info("Renewer daemon stopped by user.")
            break
        except Exception as e:
            logger.error("Error in renewer loop: %s. Retrying in 60s...", e)
            time.sleep(60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DhanHQ Token Renewer")
    parser.add_argument("--now", action="store_true", help="Renew token immediately once and exit")
    args = parser.parse_args()

    if args.now:
        renew_dhan_token()
    else:
        run_renewer_loop()
