# TITAN STOP BUILDING — 2026-09-29

Things to stop building, with classification: DELETE / FREEZE / DEFER / SIMPLIFY.
(Consolidated from OVERENGINEERING_REPORT + the external evidence.)

---

## DELETE

| Item | Evidence |
|---|---|
| Path-1 direct DB qualification writes (scripts/qualification_pipeline.py:479-488) | contradicts ADR-022; weak thresholds (IS Sharpe ≥0.5, OOS ≥0.0); OOS leaks into stability gate |
| TWAP disabled branch in engine (engine.py:1053-1064) | dead code in the critical path, frozen by policy |
| Feature graph layer (runtime/feature_graph.py) | imported only by tests; strategies carry their own indicators |
| Memory subsystem (vector_memory, distillation, mcp_bridge) | imported by nothing; ADR-007 policy text stays, code goes to archive |
| Phase-j/docs references to non-existent classes (HealthReporter) and non-existent metrics (evaluations.<tf>) | docs that contradict code are worse than no docs |
| Windows-only ops scripts (monitor_paper.py PID 7736, supervise_paper_session.sh, run_tws_paper_loop.sh, paper_session_observer.py) | dead on this host; replace with a Linux systemd/uv-run equivalent when paper works |

## FREEZE (do not maintain, do not extend; archive and revisit)

| Item | Why |
|---|---|
| HRP/ensemble allocators, rebalancing, bar_aggregator, "full pipeline" orchestrator | need ≥2 qualified strategies (currently 0) |
| Multitimeframe runtime (ADR-017) | a second runtime architecture on top of an engine that cannot run the first |
| Regime classifier | EXP-00015/P4 evidence: regime gating hurt the tested strategies |
| Fincept adapter/feed | dead path; harmless; revisit only if Fincept becomes a real broker option |
| Monte Carlo | portfolio CV matters first; vectorbt/bootstrap exists |

## DEFER (not now; would be needed only after a triggering event)

| Item | Trigger |
|---|---|
| LOB/queue-position execution simulation (hftbacktest-style) | a microstructure hypothesis surviving a real-data screen |
| Tick/L2 data (Databento/Polygon paid tiers) | same trigger |
| Options/IV data and VRP research | a pre-registered VRP hypothesis |
| More broker integrations | a strategy whose economics require a specific venue |
| LLM/agent layer beyond ADR-007 advisory | never on hype — the 2026 evidence (AI-Trader: most agents lose money; 0/19 reproducible studies) says adopt evaluation checklists, not agents |

## SIMPLIFY

| Item | How |
|---|---|
| Four fill/cost models → one canonical cost object | consumed by harness AND engine; delete zero-cost ReplayEngine defaults |
| Two backtest systems → one | route candidate evidence through the harness (next-bar) until ReplayEngine matches its semantics; do not maintain both forever |
| conftest blanket monkeypatch → opt-in fixture | default = real gate (see TEST_EFFECTIVENESS_REPORT) |
| ADR volume → wiring-gated | an ADR lands with its wiring commit or not at all |

## What to STOP doing culturally

1. Stop writing architecture for capabilities with no triggering experiment.
2. Stop running new experiments on the exhausted 2025-08..2026-07 window (the freeze is
   real even if unenforced — enforce it).
3. Stop treating "more AI", "more strategies", or "more infrastructure" as progress —
   every surviving hypothesis in this audit is blocked by data re-pulls and one broken
   seam, not by missing technology.
4. Stop counting green tests as verification while the production entrypoints crash.
