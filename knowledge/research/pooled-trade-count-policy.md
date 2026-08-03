# Pooled Trade Count Policy

> **Owner:** TITAN Development
> **Status:** Active — v1.0
> **Last Review:** 2026-07-13
> **Applies to:** Multi-instrument replication experiments

## Problem

When a hypothesis is tested across multiple instruments (e.g., SPY, QQQ, IWM), the question arises whether trades from different instruments can be pooled to meet the 30-trade Path A minimum. Naive pooling inflates statistical significance because trades within the same strategy are correlated across correlated instruments.

## Rules

### 1. Single-instrument tests use the standard gate

Path A on a single instrument requires ≥30 OOS trades from that instrument alone. Cross-instrument trades do not count.

### 2. Multi-instrument pooling requires preregistration

A hypothesis may preregister a pooled-universe design *before* running. The preregistration must specify:

- The exact universe (list of instrument IDs)
- The pooling rule (see below)
- Why pooling is appropriate (e.g., the economic mechanism is expected to work across similar instruments, and the alternative — testing each independently — is underpowered)
- Data manifests, source entitlements, adjustment policy, and exact OOS date range for every instrument
- The measured pairwise daily-return correlation and observation count, computed before strategy results are evaluated

### 3. Effective trade count formula

Pooled trades are discounted by the average pairwise correlation of daily returns across the universe:

```
effective_trades = total_pooled_trades / (1 + avg_pairwise_corr × (n_instruments − 1))
```

where:

- `avg_pairwise_corr` = mean of all pairwise Pearson correlations of daily returns over the OOS period
- `n_instruments` = number of instruments in the universe
- `total_pooled_trades` = sum of all entry events across all instruments

The effective trade count must still satisfy the Path A minimum (≥30) or the Path B alternative evidence standard.

### 4. Correlation floor

If `avg_pairwise_corr < 0.3` the discount factor is set to 1.0 (no discount), since instruments with low cross-correlation provide genuinely independent signals.

### 5. Per-instrument minimum

No single instrument may dominate the pooled result. Each instrument must contribute at least 20% of the pooled trades, or the hypothesis must document why uneven distribution is expected (e.g., structural differences in volatility across instruments).

### 6. Walk-forward and bootstrap on pooled equity

When pooling, the walk-forward and block-bootstrap must be computed on the **pooled portfolio equity curve** (sum of all instrument P&Ls), not per-instrument.

### 7. Cross-asset replications are not pooled by default

A replication on a different asset class is assessed as its own Path A or Path B experiment. It may support or weaken an economic mechanism, but it does not contribute trades to a prior instrument's gate. Pooling becomes eligible only through a separate preregistered pooled-universe hypothesis that satisfies every rule in this policy.

## Path B and pooled designs

Pooled designs may also use Path B (low-frequency) if the per-instrument trade count is expected to be low but the pooled effective count exceeds 30. The same preregistration requirements apply.

## Changelog

| Date | Change | Owner |
|---|---|---|
| 2026-07-13 | Initial policy | TITAN Development |
| 2026-07-13 | Added provenance/correlation prerequisites and standalone cross-asset rule | TITAN Development |
