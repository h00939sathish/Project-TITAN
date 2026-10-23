# TEST EFFECTIVENESS REPORT — 2026-09-29

1180 passed, 17 skipped (2026-09-29, 68s). The question is not whether tests pass — it is
what they protect. Verdict: **the suite is large and honest in parts, but it currently
validates a code path that does not exist in production, and it is structured to hide the
single most damaging bug in the project.**

---

## 1. The masking problem (the headline finding)

`tests/conftest.py:76-85` — an autouse fixture monkeypatches
`PaperTradingEngine.submit_intent` to skip (a) certificate verification and (b) the shadow
intent guard, for every suite except `test_execution_integrity`, `e2e/`, `adversarial/`.
Consequences:
- All 47 replay/exit tests are green while the REAL ReplayEngine crashes on its first
  intent (Bug B1). The suite cannot detect that the canonical backtest path is dead.
- tests/certification uses fake `certificate_ref="test-cert"` strings (test_paper_trading_certification.py:83) — ADR-006/028 enforcement is not exercised there.
- tests/integration/test_multitimeframe_paper_path.py runs under the same patch.

The single most important fix to TITAN's verification is not a new test — it is making the
default path the REAL path and pushing the bypass into a small, explicitly-named fixture
used by the handful of tests that need it.

## 2. What the suites actually protect

| Suite | Protects | Behavior vs implementation | Evidence |
|---|---|---|---|
| tests/backtest (exit intents) | ADR-021 exit pricing | **BEHAVIOR — the best suite in the repo**: exact PnL/cash asserts (`assert float(result.total_pnl) == -45.0` at test_exit_intents.py:207-208; gap -55.0; TP +15.0) | test_exit_intents.py:207-234 |
| tests/e2e | Real cert + FakeTransport, real submit_intent | Closest to production; sets real pubkey (test_profit_engine_e2e.py:93-95), valid cert (:212-232), full accepted path (:946-966) | — |
| tests/adversarial | Cert forgery, tokens, kill-switch states | Implementation-level but thorough; runs the REAL gate (excluded from patch) | test_adversarial_execution_security.py |
| tests/risk | Kill switch, gates, $10M gross exposure incl. end-to-end | Behavior on gate outcomes; but `test_full_lifecycle` asserts NOTHING (test_kill_switch.py:32-37) | test_paper_trading_engine.py:217-339 |
| tests/adapters | Adapter contracts | Heavy MagicMock (test_alpaca_adapter.py:28-50) — mocks hide real broker quirks (price-less fills, "long"/"short" side vocabulary) that B5/L1 prove exist | — |
| tests/integration (vertical slice) | "Crown jewel" pipeline | **IMPLEMENTATION**: manually calls `gate.evaluate → adapter.submit_order → portfolio.apply_fill` (test_paper_vertical_slice.py:64-89); never drives `PaperTradingEngine.submit_intent` → engine wiring (fill absorption, poll, nonce, state machine) invisible | :74 |
| tests/replay | Determinism | Weak behavior (`final_cash > 0`, counts); under cert-bypass; `results[0]==results[1]==results[2]` (test_replay_engine.py:54) | :26-54 |
| tests/chaos + execution_recovery | Recovery | recovery_matrix monkeypatches `submit_intent` itself (:566) — recovery of the REAL submit path untested | test_recovery_matrix.py:566 |
| tests/certification | Paper cycle + reconciliation | Mixed; InSync recon asserted (test_paper_trading_certification.py:90-106) but cert gate bypassed | :83 |
| tests/failure_matrix | Duplicate fills | Documents that PortfolioEngine has no dedup (pos2.quantity == 200, test_duplicate_fill.py:15) and claims EventStore message_id dedup protects — **but engine._absorb_broker_fill mints a fresh message_id per absorption (engine.py:688,699), so that dedup never protects the fill path** | :6-28 |
| tests/research | Screens/harness/gates | Mixed; gate tests assert row/status outcomes; some reach into `db._conn` privates (test_shadow_events_path.py:64-69) | — |
| tests/strategies | Indicator math | Implementation | — |
| tests/ffi_boundary | Rust↔Python enum safety | Implementation | — |
| tests/operations/memory/data | Feeds, metrics | Mocks (`patch("titan.data.macro_rates.urllib.request.urlopen")`, test_macro_rates.py:47) | — |

## 3. "If these tests pass, what failure could still happen?"

Ranked by economic impact (all currently untested):

1. Production backtest crash at the cert gate (B1) — masked by conftest.
2. Crash-restart double-application of fills (B4) — no test does crash → restart → poll
   with a multi-poll partial fill.
3. Trailing stop lost across bars (B6) — all trailing tests are single-bar
   (test_exit_intents.py:71-98); none asserts a ratchet surviving bar N→N+1.
4. Broker-held positions at startup crash (B5) — only a failing-adapter test exists
   (test_paper_trading_engine.py:432-437).
5. Price-less broker fills → "0" cost basis phantom PnL (L1).
6. Concurrent nonce replay (L2) — zero threading tests.
7. Wall-clock daily-loss gate silently halting long backtests (B8) — no test runs a lossy
   multi-day backtest asserting `rejected_intents == 0`.
8. Reconcile cash self-comparison (L4).
9. Expired orders polling forever (B10).
10. Sizer staleness fail-open (B11) — only missing-rate/min-lot paths tested.

## 4. False-confidence summary

- A green suite while every production entrypoint crashes = the definition of false
  confidence. Root cause: the monkeypatch, not missing coverage numbers.
- The suite is strong where it is economic (exit pricing asserts) and weak where it is
  wiring (vertical slice never calls the engine's own submit path).
- 868 rows in test_inventory.csv include ≥13 marked `fixed` for **wheel-vs-src drift**
  (the packaged wheel diverged from source and tests were updated after discovery) — the
  packaged artifact and the source tree have diverged at least once; there is no CI gate
  in evidence that would catch it again (ADR-034 repointed a dead workflow trigger to
  master; mypy made advisory).

## 5. Minimal effective changes

1. Invert the conftest patch: real gate by default; bypass fixture opt-in, named
   (e.g. `bypass_cert_for_unit_tests`) and restricted to suites that test pre-gate logic.
2. Add 3 economic regression tests: (a) multi-poll partial fill + restart → same position;
   (b) broker-held long AND short positions at `start(sync_from_broker=True)` → correct
   portfolio and no crash; (c) trailing stop across ≥3 bars → exits at ratcheted level.
3. Drive the engine through `submit_intent` in the vertical slice (drop the manual
   gate→adapter→portfolio re-wiring).
4. Add a nightly job that runs ReplayEngine and paper_session against the UNPATCHED
   engine on a fixture — the current suite cannot fail when these paths break; this job can.
