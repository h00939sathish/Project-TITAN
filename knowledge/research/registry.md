# Experiment Registry Schema

> **Owner:** TITAN Development
> **Status:** Active — v1.0
> **Last Review:** 2026-07-13

Each experiment record is a markdown file in `knowledge/research/experiments/` following the schema below.

## Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | yes | Unique identifier, format `YYYY-MM-DD-slug` |
| `hypothesis` | `string` | yes | Concise statement of the testable hypothesis |
| `owner` | `string` | yes | Person or team responsible |
| `data_digest` | `string` | yes | Checksum or reference to the input data version |
| `code_digest` | `string` | yes | Git commit hash or code snapshot reference |
| `config_digest` | `string` | yes | Hash of the parameter configuration |
| `calendar` | `string` | yes | Date range covered (e.g. `2020-01-01 to 2024-12-31`) |
| `universe` | `string` | yes | Instrument selection (e.g. `SPY only`, `SP500 constituents`) |
| `success_criteria` | `string` | yes | Measurable conditions that validate the hypothesis |
| `failure_criteria` | `string` | yes | Measurable conditions that invalidate the hypothesis |
| `costs` | `string` | yes | Assumed transaction and slippage costs |
| `results` | `string` | yes | Outcome summary, or `"pending"` before completion |
| `reviewer` | `string` | yes | Person or team that reviewed the results |
| `disposition` | `string` | yes | One of `in_progress`, `accepted`, `rejected`, `inconclusive` |
| `notes` | `string` | no | Free-form observations, caveats, follow-up ideas |

---

## Registered strategies

| Strategy ID | Version | Description | First hypothesis |
|---|---|---|---|
| `moving-average-crossover` | v1.0.0 | SMA crossover: entry on fast > slow, exit on fast < slow | `2026-07-13-ma-crossover-baseline` |
| `mean-reversion` | v1.0.0 | Z-score based mean reversion: entry on z < -2.0, exit on z > -0.5 | `2026-07-13-mean-reversion` |
| `volatility-regime` | v1.0.0 | Volatility regime timing: long when rolling vol < median vol | `2026-07-13-volatility-regime` |
| `time-series-momentum` | v1.0.0 | Long/short on sign of N-day return (lookback=20) | `2026-07-13-momentum-spy` |

## Registered hypotheses

| ID | Strategy | Instrument | Status |
|---|---|---|---|
| `2026-07-13-ma-crossover-baseline` | `moving-average-crossover` | SPY | Rejected |
| `2026-07-13-ma-50-200` | `moving-average-crossover` | SPY | Rejected (gate) |
| `2026-07-13-mean-reversion` | `mean-reversion` | SPY | Rejected (gate) |
| `2026-07-13-volatility-regime` | `volatility-regime` | SPY | Rejected (gate) |
| `2026-07-13-volatility-regime-replication` | `volatility-regime` | QQQ | Replicated — hypothesis supported |
| `2026-07-13-volatility-regime-tlt-replication` | `volatility-regime` | TLT | Rejected — hypothesis failed |
| `2026-07-13-momentum-spy` | `time-series-momentum` | SPY | Accepted — hypothesis supported |
| `2026-07-13-momentum-qqq-replication` | `time-series-momentum` | QQQ | Replicated — hypothesis supported |

## Registered experiments

See `knowledge/research/experiments/` for frozen experiment records. Do not modify frozen records.
