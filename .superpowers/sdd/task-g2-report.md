# Task G2 Report — Structured logging wired into runtime

**Status:** DONE

## Commits

- `4abb4de` — feat(operations): add structured JSON logging wired into runtime

## Files created

| File | Purpose |
|---|---|
| `src/titan/operations/logging.py` | LogEvent, LogSeverity, StructuredLogger |
| `src/titan/operations/_logging_integration.py` | log_risk_decision, log_adapter_event, log_reconciliation |
| `tests/operations/test_logging.py` | 7 tests covering JSON output, severity filtering, correlation IDs, payloads, empty fields, direct log_event, integration helpers |

## Files modified

| File | Change |
|---|---|
| `src/titan/operations/telemetry.py` | Added `StructuredLogger` import; `health()` method now accepts optional `logger: StructuredLogger \| None = None` param; logs health check when logger is provided |
| `src/titan/operations/__init__.py` | Exports `StructuredLogger`, `LogSeverity`, `LogEvent`, `HealthReporter`, `SystemHealth`, `SystemState`, `ComponentHealth` |

## Test results

| Command | Result |
|---|---|
| `python -m pytest tests/operations/test_logging.py -v` | 7 passed |
| `python -m pytest tests/operations/ -v` | 14 passed (7 telemetry + 7 logging) |
| `python -m pytest tests/ -v` | **130 passed** (123 original + 7 new, no regressions) |

## Concerns

- `health()` method signature is backward-compatible — `logger` defaults to `None`, all existing callers (HealthReporter tests, vertical slice) continue to work unchanged.
- The `logging.py` module name shadows Python's stdlib `logging` module, but only within the `titan.operations` package boundary. Qualified imports like `from titan.operations.logging import ...` disambiguate correctly.
