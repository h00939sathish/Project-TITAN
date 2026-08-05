#!/usr/bin/env bash
# End-of-day TITAN paper report -> Telegram. Runs 16:05 ET (01:35 IST) daily.
# The ET date is passed so the report reads the correct trading day's logs
# (at 16:05 ET the UTC date and ET date are the same).
cd "/d/projects/Project TITAN" || exit 1
DAY=$(TZ=America/New_York date +%F)
exec python scripts/daily_telegram_report.py "$DAY" --label EOD
