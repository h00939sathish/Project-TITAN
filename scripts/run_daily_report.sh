#!/usr/bin/env bash
# Cron wrapper for the daily TITAN paper report.
# Ensures the system python (with titan + TWS access) is used and the
# project directory is the cwd. Sends via Telegram itself.
cd "/d/projects/Project TITAN" || exit 1
python scripts/daily_telegram_report.py
