# E2E Test Suite Ready

## Test Runner
- Command: `.\.venv\Scripts\python -m pytest tests/e2e/test_profit_engine_e2e.py tests/e2e/test_profit_engine_v2_integration.py -v`
- Expected: all tests pass with exit code 0

## Coverage Summary
| Tier | Count | Description |
|------|------:|-------------|
| 1. Feature Coverage | 12 | Audit failure categorization, PIT ingestion, SHA-256 manifests, corporate actions, pre-registration, absorbing negative results, FxCostModel $2.00 min fee, FactorCostModel borrow/commission, quote-sided fills, default-deny cert gate, HMAC risk token, dual-approver session init |
| 2. Boundary & Corner | 7 | Empty data/zero volume, price envelope errors, 100:1 splits/dividends, expired/forged certs, feed disconnect storms & staleness, max drawdown limits, un-resettable kill switch |
| 3. Cross-Feature | 4 | Ingestion->CA->FactorSim->NegResult; PreReg->FXSim->Cert->DefaultDeny; TWSStream->FeedHealth->RiskGate->HMAC->IBKR; Halted->DualRelease->FeedHealth->ActiveRecovery |
| 4. Real-World Application | 5 | Equities Factor Lifecycle, Multi-Pair FX Simulation, Crypto Perpetual Carry, Paper Trading with .titan_state.db persistence, Emergency Circuit Breaker & Recovery |
| Integration Suite | 24 | Complete multi-asset workflow integration (R1-R6) |
| **Total** | **52** | |

## Feature Checklist
| Feature | Tier 1 | Tier 2 | Tier 3 | Tier 4 | Integration |
|---------|:------:|:------:|:------:|:------:|:-----------:|
| R1: Code & DB Audit | 1 | 1 | 1 | 1 | 4 |
| R2: PIT Data & Manifests | 3 | 2 | 1 | 1 | 4 |
| R3: Pre-Registration & Neg Results | 2 | 1 | 1 | 1 | 4 |
| R4: Canonical Cost Simulation | 3 | 1 | 1 | 2 | 4 |
| R5: Risk Gates & Paper Ingress | 2 | 1 | 1 | 1 | 4 |
| R6: Staged Live Governance | 1 | 1 | 1 | 1 | 4 |
