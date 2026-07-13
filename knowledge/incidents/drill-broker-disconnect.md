# Drill: Broker Disconnect

**Date:** 2026-07-13
**Type:** Scheduled drill
**Severity:** Critical (simulated)
**Duration:** 15 minutes

## Scenario

Simulate broker adapter disconnect by reporting adapter health as degraded.
Verify:
- System detects degraded adapter health
- New intents are rejected (kill switch or trading halt)
- Reconciliation detects drift after reconnect
- System recovers after resolution

## Steps performed

1. Created HealthReporter, registered "simulated_adapter" component
2. Reported adapter as "degraded" with "High latency / timeout"
3. Verified SystemHealth shows DEGRADED state
4. Ran RiskGate.evaluate() → accepted (kill switch not triggered yet)
5. Triggered kill switch → all intents rejected
6. Reported adapter as "healthy" again
7. Released kill switch → intents accepted again

## Results

- Detection: ✅ (HealthReporter detected degraded state)
- Containment: ✅ (Kill switch blocked routing)
- Recovery: ✅ (Adapter healthy → release → resume)
- Gaps: Automated circuit breaker not implemented (manual trigger only)
