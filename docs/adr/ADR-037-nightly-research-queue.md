# ADR-037: Nightly WF-v2 research queue

- **Status:** Proposed (2026-10-24) — awaiting project-owner approval
- **Date:** 2026-10-24
- **Owners:** Project owner (sole decision-maker for TITAN research protocol)
- **Supersedes:** N/A (builds on ADR-036 and `titan research run`)

## Context

Phase 2 made a hypothesis cost one entry in `research/hypotheses.py` plus one
`titan research run EXP-id`. Phase 3 runs queued hypotheses unattended every
night, and Phase 4 measures that loop for 3–4 weeks. An unattended runner is
only acceptable if it can't reach anything that changes money or the rules.

## Decision

1. **Queue file.** `research/queue.toml` lists `[[experiment]]` tables
   (`id`, optional `note`) and `max_runs_per_night` (1..20, default 5). Humans
   edit it; the runner never writes it. Unknown keys, malformed ids and
   duplicates abort the night. TOML is used instead of YAML because `tomllib`
   is in the standard library and PyYAML is not a project dependency.
2. **Runner.** `titan research queue` (`src/titan/research/queue.py`) calls
   `wf_v2.run` for each queued id in order, up to the nightly cap, and defers
   the rest. One crashing hypothesis is logged and the night continues.
   Exit codes: 0 all attempts completed (any verdict), 1 at least one crashed,
   3 aborted.
3. **Run log.** Every attempt, whether manual (`research run`) or queued, appends
   one JSON line to `research/wf_v2/run_log.jsonl`. Each line records the
   trigger, mode, status, reasons, error, bundle and memo paths, duration, git
   HEAD and protocol hash. Refusals, crashes and aborts are logged too. This log
   is the Phase 4 measurement record and the input to the Phase 5
   harness-failure count.
4. **Hard limits, enforced in code rather than by convention:**
   - The runner's only writes are `wf_v2.run`'s outputs under
     `research/wf_v2/results/` and the run log. A test snapshots a whole
     temporary repository before and after a run to check this.
   - **No promotion.** The runner has no code path to the promotion gate or to
     certificates. Promotion stays a human decision backed by a certificate.
   - **No live config.** Nothing in the runner reads or writes live or paper
     trading config.
   - **Frozen protocol pin.** `PINNED_PROTOCOL_SHA256` holds the hash of
     `research/protocol_WF_v2_PRE_FROZEN.md`, with CRLF normalized to LF so
     Windows and Linux checkouts agree. A mismatch aborts the night before
     any hypothesis runs and is logged as an `exp_id: "*"` error.
5. **Changing the pin** requires a new owner-approved ADR. A protocol edit
   without one is exactly what the pin exists to catch, so don't "fix" an abort
   by updating the constant.
6. **Scheduling.** A local Qoder cron job runs `titan research queue` nightly
   inside a second-brain session and posts the report. It runs with auto-approval
   (not full access). Its prompt forbids editing code, config or the protocol,
   promoting, committing and pushing. The owner commits results and the log.

## Consequences

- A new idea costs one hypothesis entry plus one queue line.
- Results and the log build up uncommitted in the working tree until the owner
  reviews and commits them.
- The queue is empty until a hypothesis passes eligibility. Right now every
  hypothesis is refused, and the 2022-08..2025-07 Dukascopy prior data for
  EURUSD/GBPUSD has not been pulled yet.
