# RISK / PORTFOLIO AUDIT — 2026-09-29

Question: are risk controls too weak, appropriate, too restrictive, or correct-but-unwired?
Verdict: **correct-but-dormant, with real weaknesses at the edges — and two genuine
miswires. NOT too restrictive.** The risk system has not blocked any valid strategy: it has
simply never been exercised in production, because the certificate gate upstream of it has
no issuance path.

---

## 1. Control inventory (real vs documented-only)

| Control | Location | Real/wired? | Tested? |
|---|---|---|---|
| $10M gross exposure (long+short, dollar M2M) | core/src/risk.rs:614-626; portfolio.rs:288-298 | Real + wired | Yes — incl. exact-limit rejection, end-to-end (tests/adapters/test_paper_trading_engine.py:217-339) |
| Order notional $1M / qty 5,000 / position 50,000 units | risk.rs:547-612 | Real + wired | Yes |
| Drawdown 10% | risk.rs:628-640; portfolio.rs:311-318 | Real + wired | Yes |
| Daily loss $50k — **realized only, no MTM** | risk.rs:642-654; portfolio.rs:350-366 | Real + wired | Yes |
| Data freshness 5,000ms | risk.rs:485-512 | Real + wired | Yes |
| Correlation (mean r > 0.70) | risk.rs:707-728; engine.py:1015-1027 | Real + wired | Yes |
| Kill switch (Armed→Triggered→Releasing→Released, no auto-reset) | risk.rs:92-109; triggers at engine.py:578/1149/1384/880/525 | Real + wired | Yes |
| Two-person release w/ nonce replay protection + reconciliation predicate | release_authorization.py; engine.py:1623-1711 | Real + wired | Yes |
| Circuit breaker (10/s, 100/min, 3 consecutive broker errors → TRIPPED) | circuit_breaker.py:18-25; engine.py:996-1003 | Real + wired | Yes |
| Certificate admission (default deny, Ed25519, scope-bound, nonce) | engine.py:886-946 | Real + wired | Yes — **and it is the binding constraint** |
| Risk token on approved orders | messages.rs:397-423; engine.py:1086-1094 | Real + wired — but secret hardcoded default `'TITAN_RISK_SECRET_KEY'` | Yes |
| Instrument eligibility | risk.rs:515-526 | Real (empty = allow-all) | Yes |
| Net exposure / sector / volatility limits | RISK_POLICY.md documents them | **Absent from code** | No |
| Liquidity / market-impact sizing | Sizer (sizing.py:43-54) takes no liquidity input | Absent | No |
| Re-evaluate active orders after material changes | RISK_POLICY | Not implemented; kill switch never cancels open orders | No |
| Account/session eligibility whitelist | RISK_POLICY | `TradeIntent.account_id` never validated | No |

## 2. Weaknesses that matter (if trading ever starts)

1. **No leverage/margin constraint.** PortfolioEngine.apply_fill never rejects insufficient
   cash; cash can go negative (portfolio.rs:134-146). The $10M gross cap is the ONLY
   leverage bound — on a $100k paper account that is 100×. Correct for a paper test
   harness, wrong for anything with real money behind it.
2. **Daily loss counts realized PnL only** (portfolio.rs:350-366): an open position can sit
   20% underwater and never trip the daily limit. No MTM component.
3. **Cost-free runtime fills** (engine.py:736 fees=0) overstate paper performance — a risk
   of false confidence, not a risk of loss.
4. **Circuit breaker THROTTLED stage is soft**: one successful intent resets to NORMAL
   (circuit_breaker.py:83).
5. **Kill switch blocks new orders but never cancels open ones** — policy says cancel
   "where safe"; no code path exists.
6. **Risk token secret is a public constant** (engine.py:1086) — token provides no
   integrity against anyone who can read the source. Cosmetic security theater as shipped.

## 3. The two genuine miswires (CONFIRMED)

1. **scripts/papertrade.py:49-59** passes `Money(daily_loss_limit, "USD")` (default "5000")
   as `max_gross_exposure` — a **$5,000 gross cap** on the Alpaca CLI instead of a $50k
   daily-loss limit. Positional argument error.
2. **scripts/paper_session.py:540-550** caps gross at starting capital (1×) with 1,000 max
   order qty — a real paper session can never hold more than its starting cash in gross.
   (Deliberate-looking but undocumented; combined with cost-free fills it makes paper
   economics meaningless.)

Also: engine.py:962's trading-state pre-check evaluates the enum CLASS
(`TradingState.Active`) rather than `self.risk_gate.trading_state` — dead code; the real
check is in Rust (risk.rs:473-482).

## 4. Is the risk system unintentionally blocking valid strategies?

**No.** Evidence:
- The crypto `execution_constrained` outcomes are research-gate verdicts about fee tiers
  and latency (CRYPTO-003/005/006), not risk-gate rejections. The risk gate never saw a
  crypto order — no credentials, adapters, intents, or certificates were ever issued for
  crypto (CRYPTO_DISCOVERY_REPORT.md §Capital & Execution Boundary).
- Risk defaults would admit a small crypto order (empty eligibility; $5 min notional
  passes all checks).
- What actually blocks strategies today is the **certificate admission gate** — a
  governance control, not a risk control — with no issuance path, plus the absent session
  initialization (fail-closed HALTED).

Do not weaken risk controls to raise returns: they are not what's suppressing returns.

## 5. Recommendations

- FIX NOW: the two miswires (paper_session.py gross cap, papertrade.py positional bug).
- FIX NOW: MTM component in daily loss, or document why realized-only is intentional.
- FIX NOW: risk token secret from config/env, fail-closed if unset (the certificate gate
  already does this correctly — do the same for the token).
- WHEN PAPER RUNS: add leverage cap relative to account equity; add cancel-open-orders to
  kill switch; wire the documented net/sector/vol limits or delete them from RISK_POLICY.
- PRESERVE: the fail-closed restore, the kill-switch state machine, the dual-approval
  release with reconciliation predicate, and the dollar-based gross exposure math — all
  correct, tested, and worth keeping as the execution authority.
