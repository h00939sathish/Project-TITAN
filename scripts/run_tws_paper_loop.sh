#!/usr/bin/env bash
# TWS paper session restart loop for Project TITAN.
# Restarts the paper session if it exits (crash), with a short backoff and a
# crash-loop breaker: if the session dies before MIN_RUNTIME seconds, the
# backoff grows (up to MAX_BACKOFF) so a persistently-failing startup doesn't
# hammer the console log forever.
# Logs go to paper_session_console.log (rotated per restart).

cd "/d/projects/Project TITAN" || exit 1

# Never inherit the Hermes agent's PYTHONPATH (hermes-agent venv has a broken
# pydantic_core that shadows the system/user site-packages and kills startup).
unset PYTHONPATH

# Crash-loop protection
MIN_RUNTIME=30        # seconds a successful start is expected to survive
BASE_BACKOFF=15       # initial sleep between restarts (seconds)
MAX_BACKOFF=120       # cap on backoff after repeated fast crashes
backoff=$BASE_BACKOFF

while true; do
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) starting paper_session ===" >> paper_session_restarts.log
  start_ts=$(date +%s)
  python scripts/paper_session.py --enable-fx > paper_session_console.log 2>&1
  code=$?
  runtime=$(( $(date +%s) - start_ts ))
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) paper_session exited code=$code runtime=${runtime}s backoff=${backoff}s ===" >> paper_session_restarts.log

  if [ "$runtime" -ge "$MIN_RUNTIME" ]; then
    # Ran for a meaningful time or hit a normal scheduled stop: reset to base.
    backoff=$BASE_BACKOFF
  else
    # Fast crash — escalate the backoff up to the cap.
    backoff=$(( backoff * 2 ))
    if [ "$backoff" -gt "$MAX_BACKOFF" ]; then
      backoff=$MAX_BACKOFF
    fi
  fi

  sleep "$backoff"
done