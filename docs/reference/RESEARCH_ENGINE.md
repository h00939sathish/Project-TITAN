# Research Engine

> **Owner:** Quantitative Research Leadership
> **Status:** Active — v1.0
> **Last Review:** 2026-07-12
> **Decision Authority:** Research Owner; Risk Owner for promotion gates
> **Depends On:** [RESEARCH_PROTOCOL.md](RESEARCH_PROTOCOL.md), [DATA_PIPELINE.md](DATA_PIPELINE.md), [SYSTEM_CONTRACTS.md](SYSTEM_CONTRACTS.md)
> **Supersedes:** None
> **Review Frequency:** Per methodology change; quarterly otherwise

## Purpose

The Research Engine turns governed questions and versioned data into reproducible, falsifiable strategy candidates. It may automate analysis and candidate generation; it cannot create capital authority. The scientific and AI boundaries extend the source findings in `../STRATEGY_ENGINE_COMPARISON.md` and `../AI_AGENT_COMPARISON.md`.

## Hypothesis lifecycle

`Question → evidence review → falsifiable hypothesis → research plan → experiment → challenge/replication → candidate package → validation → paper promotion or rejection → retain evidence`. Every hypothesis has an identifier, economic rationale, universe, expected holding period, data/feature versions, prediction direction, predeclared success and falsification criteria, owner, and expiry. Negative and inconclusive results remain searchable evidence.

## Alpha and factor discovery

Factors are versioned transformations with economic definition, units, universe, frequency, lookback, missing-data behavior, leakage assessment, and source lineage. Discovery may use theory, systematic screening, or AI-assisted proposals, but candidates must be challenged for survivorship, look-ahead, selection, liquidity, capacity, turnover, and regime bias. Alpha generation produces a structured signal candidate, not an executable order. Correlation, redundancy, stability, and incremental portfolio contribution determine whether a factor enters an ensemble.

## Feature engineering and experiment record

Feature computation is point-in-time correct: at timestamp *t*, only information available at *t* may be used. Feature definitions, transforms, imputation, normalization fit windows, code digest, input partitions, and output digest are recorded in the feature store. Every run records hypothesis id, dataset/feature versions, code/environment digest, random seed, parameters, cost/latency assumptions, result metrics, artifacts, and reviewer. The experiment database is the authority for research lineage; notebooks are views, not evidence.

## Promotion criteria

A candidate advances only when it is reproducible; economically plausible; out-of-sample and walk-forward credible; robust under fees, slippage, latency, impact, and parameter variation; non-duplicative in its target portfolio; operationally implementable; and has explicit failure/retirement conditions. Promotion creates an immutable strategy package for [STRATEGY_ENGINE.md](STRATEGY_ENGINE.md) and uses [BACKTEST_ENGINE.md](BACKTEST_ENGINE.md) plus the gates in [IMPLEMENTATION_PLAYBOOK.md](IMPLEMENTATION_PLAYBOOK.md). No result is promoted on in-sample return, model confidence, or narrative alone.

