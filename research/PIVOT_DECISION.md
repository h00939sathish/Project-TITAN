# TITAN Profitability Pivot Decision

> **Status:** Active — post terminal alpha-search directive (informational decision record, not an ADR)
> **Last updated:** 2026-08-18
> **Primary evidence:** `research/ALPHA_SEARCH_TERMINAL_REPORT.md`, `README.md`, `RISK_POLICY.md`

## Context

The directional/regime/macro search on liquid OHLCV data is closed on evidence.
~40 experiments across FX and spot gold did not survive realistic costs or OOS
validation. Repeating the same search class is prohibited.

## Implemented direction

1. **Accept terminal evidence as a hard boundary**
   - Treat "OHLCV directional on liquid instruments" as a closed class.
   - Preserve all negative results as first-class evidence.

2. **Shift to new alpha classes only**
   - Microstructure and order-flow hypotheses requiring sequence-valid data.
   - Cross-asset relative-value/dislocation hypotheses.
   - Event/fundamental-driven hypotheses with explicit causal mechanisms.

3. **Tighten research quality gates before further search spend**
   - Pre-register hypotheses, acceptance thresholds, and kill criteria.
   - Use explicit spread/slippage/latency/commission assumptions.
   - Require walk-forward, Monte Carlo, and paper-stage evidence before any
     promotion request.

4. **Optimize downside control over raw return**
   - Keep deterministic hard limits in the order path.
   - Enforce strict drawdown and exposure caps.
   - Keep kill-switch handling fail-closed and reconciliation-first.

5. **Keep staged deployment discipline**
   - Simulation → paper → restricted live → scale.
   - Progress only when OOS edge and operational reliability are both stable.

6. **Constrain AI to advisory authority**
   - AI may propose ideas, analyses, and challenge questions.
   - AI may not route orders, approve capital, or override risk controls.

7. **Use a strict profitability definition**
   - Profitability means risk-adjusted, net-of-cost, reproducible performance
     over time.
   - Short-term or single-window PnL spikes do not qualify as evidence.

## Required evidence artifacts for any new research program

- A program charter naming hypothesis class, data contract, and failure modes.
- Pre-registered gates with explicit reject criteria and OOS windows.
- Net-of-cost attribution and stress scenarios.
- A terminal report if no candidate survives all gates.