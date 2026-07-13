# Knowledge Management

This directory is Project TITAN's institutional memory. It preserves decisions, research, incidents, experiments, benchmarks, and rejected ideas so that they are searchable, auditable, and never repeated unnecessarily.

## Structure

| Directory | Content | Required metadata |
|---|---|---|
| `decisions/` | ADRs and RFCs (symlink to `docs/adr/`) | Per ADR template |
| `research/` | Hypotheses, evidence records, literature notes | Date, author, hypothesis id, status (active/rejected/archived) |
| `incidents/` | Post-mortems, timeline, corrective actions | Date, severity, root cause, resolution, follow-up ADR links |
| `experiments/` | Run results, parameters, metrics | Experiment id, hypothesis link, data/strategy versions, result summary |
| `rejected-ideas/` | Why something was considered and rejected | Date, author, context, rejection reason, evidence |
| `benchmarks/` | Performance baselines and profiles | Date, hardware spec, workload description, results artifact link |

## Rules

1. Every entry has a date and author.
2. Every entry is immutable once written; corrections are new entries with a pointer to the superseded entry.
3. `decisions/` is authoritative via `docs/adr/` — this directory is a view.
4. Entries in `rejected-ideas/` are as valuable as accepted ones — they prevent repeated analysis.
5. Before starting any research task, search `knowledge/` for prior work.
