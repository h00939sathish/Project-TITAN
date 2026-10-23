# ADR-035: Research replay authorization — capability, not a placeholder certificate

- **Status:** Proposed (2026-10-23) — Architecture Council and Risk Owner
- **Date:** 2026-10-23
- **Owners:** Architecture Council
- **Supersedes:** N/A (amends how ADR-028 certificate enforcement applies to historical replay)

## Context

ADR-028 made `PaperTradingEngine.submit_intent` refuse any intent without a valid
Ed25519 promotion certificate: it `json.loads` `certificate_ref`, verifies the
signature against `TITAN_EXEC_PUBKEY`, then checks scope (instrument, side,
max_quantity, account) and nonce.

`ReplayEngine` (`src/titan/backtest/engine.py`) drives a `PaperTradingEngine` over a
`BacktestAdapter` and stamped every intent with the literal string
`"replay-engine-cert"`. That string is not JSON, so every replay outside pytest
failed at `json.loads` — `research/replay_traderdev_ema9vwap.py` could not run.

It only looked healthy because `tests/conftest.py` had an autouse fixture that
replaced `submit_intent` with `_submit_intent_core` (no gate at all) for every test
whose node id did not contain one of four substrings. The certificate gate was
therefore untested for most of the suite, and the replay path was untested outside
the monkeypatch.

Two bad fixes were available and rejected:

1. Sign replay intents with a real key. Research code would then hold signing
   material, and a replay certificate is indistinguishable from a promotion.
2. Accept a magic placeholder string in `submit_intent`. That is a bypass token for
   the live gate.

## Decision

1. Add `PaperTradingEngine.submit_replay_intent(intent)`. It requires no
   certificate. Authorization comes from the adapter: it proceeds only when
   `type(self.adapter) is BacktestAdapter` (exact type — a subclass could override
   `place_order` and reach a venue). Shadow intents stay forbidden. Risk checks in
   `_submit_intent_core` still apply.
2. `submit_intent` is unchanged. Placeholder strings, missing certificates and
   forged signatures are still rejected on every adapter.
3. `ReplayEngine` calls `submit_replay_intent` and no longer sets
   `certificate_ref`.
4. The autouse conftest bypass is deleted. Tests that exercise engine behaviour
   behind the gate opt in with the `sign_uncertified_intents` fixture, which issues
   a real test-key certificate scoped to the intent and then calls the *real*
   `submit_intent`. Intents that already carry a JSON certificate are passed
   through untouched, so gate tests in opted-in modules still see their forged or
   mismatched certificates.

## Consequences

- Replay runs outside pytest. Its numbers are research output, not promotion
  evidence; promotion still requires a human decision plus a signed certificate.
- Every paper-engine test now runs signature, scope and nonce verification.
- `tests/replay/test_replay_authorization.py` proves: replay needs no certificate;
  the paper gate rejects `None`, placeholder strings, a bare JSON object and a
  forged signature; `submit_replay_intent` refuses non-backtest adapters,
  `BacktestAdapter` subclasses and shadow intents.
- Not yet migrated: `scripts/backtest_multitimeframe.py`,
  `scripts/backtest_smoke.py` and `src/titan/strategies/bridge.py` still pass
  placeholder certificates to `submit_intent` and will be rejected by the gate.
  `scripts/papertrade.py` targets the paper adapter and must keep requiring a real
  certificate.
- The scope check compares `int(str(intent.quantity))`, so fractional quantities
  cannot pass the gate at all. Out of scope here; flagged for the crypto path.

## Rollback

Revert the commit. `submit_intent` was not modified, so rollback cannot weaken the
live gate; it only restores the broken replay path and the autouse test bypass.

## Monitoring

`grep -rn "submit_replay_intent" src/` must show callers only under
`src/titan/backtest/`. Any new caller elsewhere needs Architecture Council review.
