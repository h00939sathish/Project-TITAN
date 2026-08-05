# Safe Multi-Timeframe Paper Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Process canonical market and operational events through one replayable runtime, evaluate approved strategies at their declared triggers, and route an order only when a qualified proposal passes TITAN's deterministic risk, execution, and reconciliation path.

**Architecture:** Do not extend the direct-Nautilus order path. It compares incompatible timeframe values and calls submit_order directly, violating ADR-0004. Introduce a pure event-driven runtime: market data, corporate actions, broker fills, heartbeats, economic releases, news, and schema-validated advisory proposals enter through one typed event envelope. A deterministic feature graph derives higher resolutions from one canonical lower-resolution stream; producer-specific trigger declarations select read-only context and emit TradeProposals; deterministic proposal validation and the risk engine then own intent/execution decisions. An IBKR paper adapter is added only after the required ADR acceptance.

**Tech Stack:** Python 3.14, pytest, NautilusTrader bar subscriptions for data ingress only, IBKR TWS paper API, TITAN Rust/PyO3 risk core, SQLite event store.

## Global Constraints

- A MarketEvent is an evaluation opportunity; it must never force an order.
- Strategy and AI/advisory producers may emit only TradeProposal. Deterministic validation may construct TradeIntent; TradeIntent → RiskGate → ApprovedOrderIntent → adapter → portfolio → reconciliation is the only capital path.
- Portfolio context is an immutable projection identified by snapshot ID. It may be supplied as declared read-only context, but strategy/agent producers cannot enforce, change, or bypass cash, exposure, correlation, sector, margin, or open-risk limits.
- Every consumed event, derived feature, producer output, proposal validation, risk verdict, portfolio snapshot ID, broker request, acknowledgement, fill, and state transition must have a correlated append-only decision trace.
- Do not enable live forex, model-based capital authority, automatic kill-switch release, or unapproved strategy/timeframe tuples.
- Fail closed on stale data, duplicate bars, adapter failure, persistence failure, and critical reconciliation drift.
- Existing daily parameters have daily-only evidence. Intraday parameters require independent research, walk-forward, Monte Carlo, cost/slippage, and paper evidence.
- Keep regular US-equity session bars and the smallest certified paper notional until the approved scope says otherwise.

---

## File map

| File | Responsibility |
|---|---|
| docs/adr/ADR-017-multitimeframe-paper-runtime.md | Records expanded frequency/broker scope, gates, and rollback. |
| specifications/StrategyRuntime.spec.md | Multi-timeframe inputs, state, errors, metrics, and acceptance evidence. |
| docs/scope/operating-scope.md | Daily-only scope changes after ADR approval. |
| specifications/MarketEvent.spec.md | Versioned market/operational event envelope and provenance contract. |
| specifications/FeatureGraph.spec.md | Deterministic resolution aggregation, correction, freshness, and dependency rules. |
| src/titan/strategies/timeframes.py | Pure timedelta to Timeframe conversion. |
| src/titan/runtime/events.py | Typed MarketEvent and TradeProposal envelopes plus event IDs, causal IDs, and provenance. |
| src/titan/runtime/feature_graph.py | Deterministic Tick → 1m → 5m → 15m → 1h → 1d aggregation and read-only context views. |
| src/titan/runtime/evaluator.py | Trigger scheduler, proposal ingress, event dispatch, and decision trace construction. |
| src/titan/strategies/multitimeframe_runtime.py | Producer evaluation, state isolation, deduplication, warm-up, TradeProposal creation. |
| src/titan/strategies/registry.py, registrations.py | Immutable parameter digest qualification by timeframe. |
| src/titan/execution/ibkr_paper_adapter.py | IBKR adapter behind TITAN's broker contract. |
| src/titan/execution/engine.py | Structural adapter protocol, risk, portfolio, and reconciliation path. |
| scripts/ibkr_paper_session.py | Closed-bar ingress only; never direct strategy-to-broker orders. |
| tests/strategies/test_timeframes.py | Duration conversion test coverage. |
| tests/runtime/test_events.py | Envelope validation, event ordering, causal correlation, and producer permissions. |
| tests/runtime/test_feature_graph.py | Deterministic aggregation, no mixed sources, correction, and replay tests. |
| tests/runtime/test_evaluator.py | Trigger/filter separation, advisory proposal validation, portfolio-context isolation, and trace tests. |
| tests/strategies/test_multitimeframe_runtime.py | State, duplicate, stale-data, and intent tests. |
| tests/adapters/test_ibkr_paper_adapter.py | Deterministic fake-transport contract tests. |
| tests/integration/test_multitimeframe_paper_path.py | Closed bar through risk gate to adapter. |
| tests/chaos/test_multitimeframe_recovery.py | Restart, disconnect, and drift-halt evidence. |

### Task 1: Approve the safety and scope contract

**Files:**
- Create: docs/adr/ADR-017-multitimeframe-paper-runtime.md
- Modify: specifications/StrategyRuntime.spec.md
- Modify: docs/scope/operating-scope.md
- Modify: docs/runbooks/paper-session.md

**Interfaces:**
- Consumes: ADR-0002, ADR-0004, ADR-0006, and existing research records.
- Produces: approved timeframe/broker boundary; versioned qualification record per active tuple.

- [ ] **Step 1: Draft ADR-017 with this exact decision.**

~~~
Timeframe is one of FIVE_MINUTES, FIFTEEN_MINUTES, ONE_HOUR, or ONE_DAY.
The runtime accepts only closed, timestamped bars and may emit no more than one
intent for (strategy_id, instrument_id, timeframe, close_timestamp). All
intents must enter PaperTradingEngine.submit_intent; no strategy or session
runner may call a broker or Nautilus submit_order directly.
~~~

- [ ] **Step 2: Add the activation gate.**

~~~
A (strategy, timeframe, parameters) tuple remains disabled until its
walk-forward, Monte Carlo, fee/slippage, data-quality, and paper-session
evidence is recorded and approved by Strategy Owner and Risk Owner.
~~~

- [ ] **Step 3: Extend StrategyRuntime.spec.md.** Add timeframe, bar-close timestamp, and data age inputs. Require indicator, warm-up, position, and deduplication state to be isolated by (strategy_id, instrument_id, timeframe). Add unsupported duration, stale bar, duplicate bar, and critical-drift failures plus halt/preserve/reconcile/manual-release rollback.

- [ ] **Step 4: Update scope and runbook after ADR approval.** Document the four allowed durations, respective TTLs, regular-session policy, required evidence, startup reconciliation, metrics, and rollback.

- [ ] **Step 5: Obtain Architecture Council and Risk Owner acceptance.** Do not implement Tasks 2–11 without it.

- [ ] **Step 6: Commit.**

~~~
git add docs/adr/ADR-017-multitimeframe-paper-runtime.md specifications/StrategyRuntime.spec.md docs/scope/operating-scope.md docs/runbooks/paper-session.md
git commit -m "docs: define safe multi-timeframe paper runtime"
~~~

### Task 2: Canonicalize closed-bar timeframes

**Files:**
- Create: src/titan/strategies/timeframes.py
- Create: tests/strategies/test_timeframes.py

**Interfaces:**
- Consumes: datetime.timedelta from bar.bar_type.spec.timedelta.
- Produces: Timeframe.from_duration(duration) -> Timeframe; raises UnsupportedTimeframeError.

- [ ] **Step 1: Write failing mapping tests.**

~~~python
from datetime import timedelta
import pytest
from titan.strategies.timeframes import Timeframe, UnsupportedTimeframeError

@pytest.mark.parametrize(("duration", "expected"), [
    (timedelta(minutes=5), Timeframe.FIVE_MINUTES),
    (timedelta(minutes=15), Timeframe.FIFTEEN_MINUTES),
    (timedelta(hours=1), Timeframe.ONE_HOUR),
    (timedelta(days=1), Timeframe.ONE_DAY),
])
def test_from_duration_maps_every_subscribed_bar(duration, expected):
    assert Timeframe.from_duration(duration) is expected

def test_from_duration_rejects_unsupported_interval():
    with pytest.raises(UnsupportedTimeframeError, match="unsupported bar duration"):
        Timeframe.from_duration(timedelta(minutes=30))
~~~

- [ ] **Step 2: Run it red.**

~~~
python -m pytest tests/strategies/test_timeframes.py -q
~~~

Expected: import error because the module does not yet exist.

- [ ] **Step 3: Implement the pure mapping.**

~~~python
from datetime import timedelta
from enum import StrEnum

class UnsupportedTimeframeError(ValueError):
    pass

class Timeframe(StrEnum):
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"

    @classmethod
    def from_duration(cls, duration: timedelta) -> "Timeframe":
        mapping = {
            timedelta(minutes=5): cls.FIVE_MINUTES,
            timedelta(minutes=15): cls.FIFTEEN_MINUTES,
            timedelta(hours=1): cls.ONE_HOUR,
            timedelta(days=1): cls.ONE_DAY,
        }
        try:
            return mapping[duration]
        except KeyError as error:
            raise UnsupportedTimeframeError(
                f"unsupported bar duration: {duration}"
            ) from error
~~~

- [ ] **Step 4: Run green and commit.**

~~~
python -m pytest tests/strategies/test_timeframes.py -q
git add src/titan/strategies/timeframes.py tests/strategies/test_timeframes.py
git commit -m "feat: canonicalize closed-bar timeframes"
~~~

Expected: five tests pass. This replaces the current failing string comparison.

### Task 3: Create the canonical MarketEvent and trigger-scheduler contracts

**Files:**
- Create: specifications/MarketEvent.spec.md
- Create: src/titan/runtime/events.py
- Create: src/titan/runtime/evaluator.py
- Create: tests/runtime/test_events.py
- Create: tests/runtime/test_evaluator.py
- Modify: specifications/StrategyRuntime.spec.md

**Interfaces:**
- Consumes: EventEnvelope plus source-specific normalized payload.
- Produces: MarketEvent, TradeProposal, TriggerSpec, StrategyDefinition, DecisionTrace, and RuntimeEvaluator.on_market_event(event).

- [ ] **Step 1: Write the failing event and trigger tests.**

~~~python
def test_only_declared_five_minute_bar_triggers_a_strategy(evaluator, event_factory):
    definition = StrategyDefinition(
        strategy_id="ma-crossover",
        trigger=TriggerSpec(event_type="BarClosed", timeframe=Timeframe.FIVE_MINUTES),
        context=(Timeframe.ONE_HOUR, Timeframe.ONE_DAY),
    )
    evaluator.register(definition)
    evaluator.on_market_event(event_factory.bar_closed(Timeframe.ONE_HOUR))
    assert evaluator.evaluations == []
    evaluator.on_market_event(event_factory.bar_closed(Timeframe.FIVE_MINUTES))
    assert evaluator.evaluations == [("ma-crossover", Timeframe.FIVE_MINUTES)]

def test_advisory_producer_cannot_emit_trade_intent(evaluator, proposal_factory):
    proposal = proposal_factory.ai_trade_proposal()
    result = evaluator.on_market_event(proposal)
    assert result.trade_intents == []
    assert result.proposal_validation.status == "PENDING_DETERMINISTIC_VALIDATION"
~~~

- [ ] **Step 2: Run them red.**

~~~
python -m pytest tests/runtime/test_events.py tests/runtime/test_evaluator.py -q
~~~

Expected: runtime event modules do not exist.

- [ ] **Step 3: Define the envelopes and scheduler.** MarketEvent must contain message_id, causation_id, correlation_id, occurred_at, received_at, schema_version, source, event_type, instrument_id, payload digest, and payload. Accepted event types are Tick, Quote, BarClosed, CorporateAction, EconomicRelease, News, Heartbeat, BrokerFill, and AdvisoryProposal. StrategyDefinition must declare exactly one TriggerSpec and an immutable context tuple; only the matching trigger invokes its producer. Auxiliary context is immutable and never creates an implicit trigger.

- [ ] **Step 4: Define TradeProposal permissions.** A strategy or advisory producer creates TradeProposal with producer_kind, package/model/prompt digest, sources, expiration, requested action, and rationale digest. ProposalValidator validates schema, provenance, expiry, producer policy, strategy qualification, and market-data freshness before it may construct TradeIntent. AI output remains advisory under AI_GOVERNANCE.md and has no broker, risk, portfolio, or configuration capability.

- [ ] **Step 5: Add event-ordering, duplicate-message, malformed-schema, expired-proposal, untrusted-news, and heartbeat routing tests.** CorporateAction and BrokerFill events update the appropriate deterministic projections; they do not accidentally trigger a strategy unless an explicit, approved TriggerSpec says so.

- [ ] **Step 6: Run and commit.**

~~~
python -m pytest tests/runtime/test_events.py tests/runtime/test_evaluator.py -q
git add specifications/MarketEvent.spec.md specifications/StrategyRuntime.spec.md src/titan/runtime/events.py src/titan/runtime/evaluator.py tests/runtime/test_events.py tests/runtime/test_evaluator.py
git commit -m "feat: add event-driven runtime scheduler"
~~~

### Task 4: Build the deterministic multi-resolution feature graph

**Files:**
- Create: specifications/FeatureGraph.spec.md
- Create: src/titan/runtime/feature_graph.py
- Create: tests/runtime/test_feature_graph.py

**Interfaces:**
- Consumes: one authoritative Tick or Quote stream per instrument, or one declared base BarClosed stream when ticks are unavailable.
- Produces: immutable FeatureSnapshot and derived BarClosed events for ONE_MINUTE, FIVE_MINUTES, FIFTEEN_MINUTES, ONE_HOUR, and ONE_DAY.

- [ ] **Step 1: Write the failing aggregation and source-integrity tests.**

~~~python
def test_ticks_derive_stable_five_minute_then_hourly_bars(graph, ticks):
    for tick in ticks.for_minutes(60):
        graph.on_market_event(tick)
    assert graph.bar("SPY", Timeframe.FIVE_MINUTES, 0).close == ticks[4].price
    assert graph.bar("SPY", Timeframe.ONE_HOUR, 0).close == ticks[-1].price

def test_graph_rejects_mixed_external_and_derived_sources(graph, event_factory):
    graph.on_market_event(event_factory.tick("SPY", 100.0))
    with pytest.raises(SourceConsistencyError):
        graph.on_market_event(event_factory.external_bar("SPY", Timeframe.FIVE_MINUTES))
~~~

- [ ] **Step 2: Run them red.**

~~~
python -m pytest tests/runtime/test_feature_graph.py -q
~~~

Expected: module import error.

- [ ] **Step 3: Implement a graph with one authoritative base source per instrument/session.** Derive each higher interval only from the immediately lower canonical resolution: Tick or Quote → ONE_MINUTE → FIVE_MINUTES → FIFTEEN_MINUTES → ONE_HOUR → ONE_DAY. When only an approved five-minute source is available, configure FIVE_MINUTES as the root and derive only upward. Reject independently sourced bars that overlap a derived interval.

- [ ] **Step 4: Implement close, gap, correction, and session behavior.** Emit a BarClosed event only after the interval is complete. Preserve source event IDs and graph/version digest in every derived bar. A correction creates a new correction event and downstream invalidation/recomputation record; it never mutates past events. Do not bridge trading-session or calendar gaps without an explicit calendar event.

- [ ] **Step 5: Add replay tests.** Replay the same event sequence twice and assert identical derived event payloads, feature snapshots, and graph digest; assert that a missing base interval marks dependent features stale rather than fabricating values.

- [ ] **Step 6: Run and commit.**

~~~
python -m pytest tests/runtime/test_feature_graph.py tests/replay/test_deterministic_replay.py -q
git add specifications/FeatureGraph.spec.md src/titan/runtime/feature_graph.py tests/runtime/test_feature_graph.py
git commit -m "feat: derive deterministic multi-resolution features"
~~~

### Task 5: Persist decision traces and add one producer-agnostic proposal ingress

**Files:**
- Modify: specifications/TradeIntent.spec.md
- Modify: specifications/Replay.spec.md
- Modify: src/titan/runtime/evaluator.py
- Modify: src/titan/execution/engine.py
- Create: tests/integration/test_decision_trace.py

**Interfaces:**
- Consumes: MarketEvent, FeatureSnapshot, TradeProposal, immutable PortfolioContextSnapshot, and deterministic proposal/risk verdicts.
- Produces: append-only DecisionTrace and, only after deterministic proposal validation, TradeIntent.

- [ ] **Step 1: Write the failing trace test.**

~~~python
def test_one_proposal_has_an_end_to_end_decision_trace(harness, event_factory):
    result = harness.process(event_factory.bar_closed(Timeframe.FIVE_MINUTES))
    trace = harness.event_store.read_decision_trace(result.correlation_id)
    assert trace.types == [
        "MarketEventReceived", "FeatureSnapshotCreated", "StrategyEvaluated",
        "TradeProposalCreated", "ProposalValidated", "RiskDecision",
        "ApprovedOrderIntent", "BrokerAcknowledgement",
    ]
    assert trace.has_single_config_and_portfolio_snapshot()
~~~

- [ ] **Step 2: Run it red.**

~~~
python -m pytest tests/integration/test_decision_trace.py -q
~~~

Expected: decision-trace projection does not exist.

- [ ] **Step 3: Persist trace events using the existing EventEnvelope/EventStore.** Each stage includes message ID, causation ID, correlation ID, configuration digest, feature-graph digest, input event IDs, portfolio snapshot ID, policy version, and immutable outcome/reason. Store full untrusted external content only under its retention policy; put its hash and provenance in the trace.

- [ ] **Step 4: Separate context from authority.** RuntimeEvaluator may attach an immutable PortfolioContextSnapshot reference to a proposal only if the producer declares it. ProposalValidator and RiskGate fetch the authoritative current portfolio projection and enforce cash, exposure, concentration/correlation, sector, margin, liquidity, drawdown, and open-risk limits. Producers cannot reject, resize, or override these limits.

- [ ] **Step 5: Update replay to use the same event dispatcher.** Replay MarketEvent records through RuntimeEvaluator, reconstruct FeatureSnapshot and DecisionTrace, and byte-compare emitted trace/event streams against a golden fixture. Include strategy and AI advisory proposals; both must use the same validator and risk path.

- [ ] **Step 6: Run and commit.**

~~~
python -m pytest tests/integration/test_decision_trace.py tests/replay/test_deterministic_replay.py tests/risk -q
git add specifications/TradeIntent.spec.md specifications/Replay.spec.md src/titan/runtime/evaluator.py src/titan/execution/engine.py tests/integration/test_decision_trace.py
git commit -m "feat: trace replayable producer-agnostic proposals"
~~~

### Task 6: Qualify strategy parameters by timeframe

**Files:**
- Modify: src/titan/strategies/registry.py
- Modify: src/titan/strategies/registrations.py
- Create: tests/strategies/test_timeframe_qualification.py

**Interfaces:**
- Consumes: registration, Timeframe, immutable parameter mapping.
- Produces: StrategyRegistration.is_qualified_for(timeframe, params) -> bool.

- [ ] **Step 1: Write the failing proof that daily evidence is not intraday evidence.**

~~~python
from titan.strategies.timeframes import Timeframe
from titan.strategies.registry import get_registry

def test_daily_ma_is_not_implicitly_intraday_qualified():
    registration = get_registry().get("ma-crossover")
    assert registration.is_qualified_for(Timeframe.ONE_DAY, {"fast": 5, "slow": 20})
    assert not registration.is_qualified_for(
        Timeframe.FIVE_MINUTES, {"fast": 5, "slow": 20}
    )
~~~

- [ ] **Step 2: Run it red.**

~~~
python -m pytest tests/strategies/test_timeframe_qualification.py -q
~~~

Expected: missing method.

- [ ] **Step 3: Add immutable qualification metadata.** Add qualified_variants: frozenset[tuple[Timeframe, str]] to a registration. The second member is the digest of json.dumps(params, sort_keys=True, separators=(",", ":")). Implement is_qualified_for(). Register only existing daily evidence initially.

- [ ] **Step 4: Run and commit.**

~~~
python -m pytest tests/strategies/test_timeframe_qualification.py tests/strategies/test_registry.py -q
git add src/titan/strategies/registry.py src/titan/strategies/registrations.py tests/strategies/test_timeframe_qualification.py
git commit -m "feat: qualify strategy parameters by timeframe"
~~~

### Task 7: Implement an event-driven multi-timeframe strategy runtime

**Files:**
- Create: src/titan/strategies/multitimeframe_runtime.py
- Create: tests/strategies/test_multitimeframe_runtime.py

**Interfaces:**
- Consumes: MarketEvent(event_type="BarClosed", instrument_id, timeframe, close, close_timestamp), FeatureSnapshot, and immutable portfolio-context reference.
- Produces: MultiTimeframeRuntime.on_market_event(event, context) -> list[TradeProposal].

- [ ] **Step 1: Write red tests for isolation, duplicates, and no-forced-trade.**

~~~python
def test_same_strategy_has_independent_state_per_timeframe(runtime, t0):
    runtime.warmup("SPY", Timeframe.FIVE_MINUTES, [100, 101, 102])
    runtime.warmup("SPY", Timeframe.ONE_DAY, [100, 99, 98])
    assert runtime.on_market_event(event_factory.bar_closed("SPY", Timeframe.FIVE_MINUTES, 103, t0))
    assert runtime.on_market_event(event_factory.bar_closed("SPY", Timeframe.ONE_DAY, 97, t0)) == []

def test_duplicate_closed_bar_emits_no_second_intent(runtime, t0):
    event = event_factory.bar_closed("SPY", Timeframe.FIVE_MINUTES, 103, t0)
    runtime.on_market_event(event)
    assert runtime.on_market_event(event) == []

def test_no_signal_on_closed_bar_creates_no_intent(runtime, t0):
    assert runtime.on_market_event(
        event_factory.bar_closed("SPY", Timeframe.FIFTEEN_MINUTES, 100, t0)
    ) == []
~~~

- [ ] **Step 2: Run it red.**

~~~
python -m pytest tests/strategies/test_multitimeframe_runtime.py -q
~~~

Expected: module import error.

- [ ] **Step 3: Implement MultiTimeframeRuntime as an event producer.** Use dictionaries keyed by (strategy_id, instrument_id, timeframe) for signal functions, warm-up direction, position state, and latest closed timestamp. Consume only matching BarClosed events, reject unqualified/stale/non-monotonic bars, and construct TradeProposal only; do not import broker, engine, or Nautilus classes.

- [ ] **Step 4: Add stale-data, unqualified-variant, SELL-while-flat, persistence/restart, auxiliary-context-nontrigger, and provenance tests.** Provenance must include strategy ID, parameter digest, timeframe, bar-close timestamp, causal event ID, feature-graph digest, and declared portfolio-context snapshot ID.

- [ ] **Step 5: Run and commit.**

~~~
python -m pytest tests/strategies/test_multitimeframe_runtime.py tests/strategies/test_bridge.py tests/strategies/test_timeframes.py -q
git add src/titan/strategies/multitimeframe_runtime.py tests/strategies/test_multitimeframe_runtime.py
git commit -m "feat: add isolated multi-timeframe strategy runtime"
~~~

### Task 8: Put IBKR paper execution behind the TITAN engine

**Files:**
- Create: src/titan/execution/ibkr_paper_adapter.py
- Modify: src/titan/execution/_broker_types.py
- Modify: src/titan/execution/engine.py
- Create: tests/adapters/test_ibkr_paper_adapter.py
- Modify: tests/adapters/test_paper_trading_engine.py

**Interfaces:**
- Consumes: ApprovedOrderIntent and injected IBKRTransport.
- Produces: session, health, acknowledgement, fills, holdings, positions, and reconciliation-snapshot broker types.

- [ ] **Step 1: Write red fake-transport contract tests.**

~~~python
def test_risk_denial_never_reaches_ibkr(engine, fake_transport, denied_intent):
    result = engine.submit_intent(denied_intent)
    assert not result.accepted
    assert fake_transport.placed_orders == []

def test_ibkr_preserves_titan_client_order_id(adapter, fake_transport, approved):
    acknowledgement = adapter.place_order(approved)
    assert acknowledgement.accepted
    assert fake_transport.placed_orders[0].client_order_id == approved.client_order_id
~~~

- [ ] **Step 2: Run it red.**

~~~
python -m pytest tests/adapters/test_ibkr_paper_adapter.py -q
~~~

Expected: adapter import error.

- [ ] **Step 3: Define IBKRTransport and implement IBKRPaperAdapter.** It translates existing TITAN broker types only. It must not accept TradeIntent, calculate signals/sizing, reset the kill switch, or retry ambiguous submission. It must supply broker truth for PaperTradingEngine.reconcile().

- [ ] **Step 4: Change engine.py from its concrete adapter union to a structural BrokerAdapter protocol.** Keep Alpaca, simulated, and backtest contracts unchanged.

- [ ] **Step 5: Add tests for authentication failure, heartbeat auto-halt, rejected order, partial fill, duplicate client ID, submit timeout/UNKNOWN state, restart recovery, and critical drift.**

- [ ] **Step 6: Run and commit.**

~~~
python -m pytest tests/adapters/test_ibkr_paper_adapter.py tests/adapters/test_paper_trading_engine.py tests/recovery tests/chaos/test_multitimeframe_recovery.py -q
git add src/titan/execution/ibkr_paper_adapter.py src/titan/execution/_broker_types.py src/titan/execution/engine.py tests/adapters/test_ibkr_paper_adapter.py tests/adapters/test_paper_trading_engine.py tests/chaos/test_multitimeframe_recovery.py
git commit -m "feat: route IBKR paper orders through TITAN execution"
~~~

### Task 9: Turn the IBKR runner into safe market-event ingress

**Files:**
- Modify: scripts/ibkr_paper_session.py
- Create: tests/integration/test_multitimeframe_paper_path.py

**Interfaces:**
- Consumes: a closed Nautilus Bar, Tick, BrokerFill, or Heartbeat transformed into MarketEvent, then RuntimeEvaluator.
- Produces: zero or more TradeProposals; only ProposalValidator may create TradeIntent, which is submitted through PaperTradingEngine.submit_intent().

- [ ] **Step 1: Write the red end-to-end test.**

~~~python
def test_every_supported_closed_timeframe_reaches_event_runtime_then_risk(harness, t0):
    for timeframe in Timeframe:
        result = harness.deliver_closed_bar("SPY", timeframe, 101.0, t0)
        assert result.market_events == 1
        assert result.runtime_calls == 1
        assert result.engine_submissions <= 1

def test_unknown_duration_reaches_neither_runtime_nor_broker(harness, t0):
    result = harness.deliver_duration("SPY", timedelta(minutes=30), 101.0, t0)
    assert result.runtime_calls == 0
    assert result.engine_submissions == 0
    assert result.alerts == ["unsupported_bar_timeframe"]
~~~

- [ ] **Step 2: Run it red.**

~~~
python -m pytest tests/integration/test_multitimeframe_paper_path.py -q
~~~

Expected: no injectible ingress and direct submission still exists.

- [ ] **Step 3: Refactor EnsembleStrategy into a MarketEvent adapter.** Canonicalize duration; emit MarketEvent records for ticks, closed bars, broker fills, heartbeats, corporate actions, and approved reference/news releases; pass every event to RuntimeEvaluator.on_market_event(). ProposalValidator, not the strategy, creates TradeIntent; submit validated intents through engine.submit_intent(). Delete order_factory.market and self.submit_order from strategy code.

- [ ] **Step 4: Subscribe only to enabled qualified trigger timeframes.** Extra bars can be subscribed solely as declared filter data and must never become an implicit trigger.

- [ ] **Step 5: Emit structured fields on every event and decision trace:** event type, instrument, timeframe, source event IDs, close timestamp, strategy or producer ID, package/model/prompt digest, parameter digest, feature-graph digest, data age, portfolio snapshot ID, proposal validation, risk verdict, client order ID, and correlation ID.

- [ ] **Step 6: Run and commit.**

~~~
python -m pytest tests/integration/test_multitimeframe_paper_path.py tests/integration/test_paper_vertical_slice.py tests/risk tests/adapters/test_broker_paper_certification.py -q
git add scripts/ibkr_paper_session.py tests/integration/test_multitimeframe_paper_path.py
git commit -m "feat: route closed IBKR bars through TITAN runtime"
~~~

### Task 10: Produce evidence before enabling intraday tuples

**Files:**
- Create: knowledge/research/experiments/<strategy>-<timeframe>-<date>.md for every proposed tuple.
- Modify: knowledge/research/registry.md
- Modify: src/titan/strategies/registrations.py

- [ ] **Step 1: Run separate backtest, walk-forward, Monte Carlo, and cost/slippage tests for each proposed (strategy, timeframe, parameters) tuple.** Do not infer intraday qualification from daily results.

- [ ] **Step 2: Record source, checksum, date range, session filter, parameters, fill model, costs, out-of-sample result, drawdown, turnover, sample size, failure conditions, and retirement condition.**

- [ ] **Step 3: Obtain Strategy Owner and Risk Owner approval, then add only approved tuple digests to qualified_variants.** Retain rejected tuples as evidence.

- [ ] **Step 4: Run qualification and regression suites.**

~~~
python scripts/qualification_pipeline.py
python -m pytest tests/research tests/strategies/test_timeframe_qualification.py -q
~~~

- [ ] **Step 5: Commit each approved tuple separately.**

~~~
git add knowledge/research/experiments knowledge/research/registry.md src/titan/strategies/registrations.py
git commit -m "research: qualify <strategy> on <timeframe>"
~~~

### Task 11: Controlled broker-paper rollout

**Files:**
- Modify: docs/runbooks/paper-session.md
- Create: knowledge/sessions/multitimeframe-paper-<start-date>.md
- Create: knowledge/incidents/<date>-<event>.md if required.

- [ ] **Step 1: Start with one US equity and one approved intraday tuple at minimum certified paper notional.** Record config digest, package digest, limits, account type, and operator approval.

- [ ] **Step 2: Preflight:** successful authentication; fresh data per timeframe; clean start reconciliation; persistent kill switch not triggered; and deliberately rejected intent that never reaches adapter.

- [ ] **Step 3: Monitor by timeframe:** closed bars, runtime evaluations, proposed/accepted/rejected intents, event lag, freshness, broker health, order lifecycle, and reconciliation age. Alert on zero evaluation in an expected session, a proposal from a disabled timeframe, or a duplicate-bar proposal.

- [ ] **Step 4: Fault drills:** duplicate delivery, stale five-minute bar, heartbeat loss, reconnect, rejected order, partial fill, restart, and critical drift. Verify halt/recovery and preserve evidence.

- [ ] **Step 5: Keep paper-only for the ADR-0006 evidence window.** Review daily reconciliation and post-session report before adding another tuple.

- [ ] **Step 6: Roll back every safety breach:** retain kill switch, stop routing, preserve raw bars/event store/broker snapshots, disable tuple, reconcile, document incident, and require manual approved release.

## Verification checklist

- [ ] timedelta(days=1) maps to Timeframe.ONE_DAY; no comparison against "1-DAY" remains.
- [ ] Tick, BarClosed, CorporateAction, EconomicRelease, News, Heartbeat, BrokerFill, and AdvisoryProposal events have schema/provenance checks and deterministic routing.
- [ ] Every enabled timeframe reaches the runtime once per matching BarClosed event; hour/day context never triggers a five-minute strategy, and no event is required to trade.
- [ ] Every higher-resolution bar has one canonical lower-resolution lineage; independently sourced overlapping bars are rejected.
- [ ] Indicator, warm-up, position, feature, and deduplication state never cross timeframes or event streams.
- [ ] Strategies and advisory agents emit only TradeProposal; invalid/expired/untrusted proposals and unqualified, stale, duplicate, unsupported, or flat-portfolio SELL signals cannot reach the adapter.
- [ ] Every proposal has an end-to-end correlated DecisionTrace, and replay produces byte-identical trace/event streams for fixed inputs.
- [ ] Every routed paper order uses PaperTradingEngine.submit_intent and passes risk, portfolio-context, persistence, idempotency, health, and reconciliation tests.
- [ ] No live promotion is in scope.

## Plan self-review

- **Spec coverage:** Tasks 1 and 11 cover approval, monitoring, rollback, and operations; Tasks 2–7 define canonical event, feature, and strategy behavior; Tasks 8–9 restore the capital path; Task 10 produces the missing intraday evidence.
- **No forced-trading gap:** Every task preserves NO_TRADE and separates an event, a proposal, a validated intent, and an executable order.
- **Type consistency:** duration becomes Timeframe in Task 2; Tasks 3–5 introduce MarketEvent, FeatureSnapshot, TradeProposal, and DecisionTrace; Task 6 qualifies a Timeframe/parameter digest; Task 7 is a producer only; Task 9 routes only validator-created TradeIntent through the engine.
- **Deliberate deferrals:** live forex, parameter mutation, automatic release, unvalidated intraday activation, and any agent broker/risk/portfolio authority are excluded.

## Execution handoff

Plan complete and saved to docs/superpowers/plans/2026-07-24-safe-multitimeframe-paper.md.

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task and review between tasks.
2. **Inline Execution** — execute tasks in this session with review checkpoints.
