#!/usr/bin/env bash
# TITAN paper session supervisor — run at user login.
# If no paper session is running, start the crash-restart loop. If one is
# already running (manual start, previous supervisor), exit quietly so we
# never double-start (client-id collision would create a second session).
set -u
cd "/d/projects/Project TITAN" || exit 1

already_running() {
  # Select-Object -ExpandProperty outputs ONLY the command line (the default
  # table omits CommandLine, which made the grep never match).
  powershell -NoProfile -Command \
    "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -match 'paper_session' } | Select-Object -First 1 -ExpandProperty CommandLine" \
    2>/dev/null | grep -qi "paper_session"
}

if already_running; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) supervisor: paper session already running — exit" >> paper_session_restarts.log
  exit 0
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) supervisor: starting paper session loop" >> paper_session_restarts.log
exec bash scripts/run_tws_paper_loop.sh
