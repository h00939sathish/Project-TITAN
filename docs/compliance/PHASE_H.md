# Phase H: Scope, Legality, and Data Authority

## 1. Operating Scope
- **Jurisdiction**: US (Regulation NMS).
- **Asset Class**: US Equities (NMS stocks).
- **Venue/Broker**: Alpaca (Paper Trading Sandbox).
- **Account Type**: Individual / Proprietary (Margin disabled for phase H-K).
- **Trading Hours**: Regular Trading Hours (09:30 - 16:00 ET).
- **Strategy Family**: Mean Reversion / Momentum (End-of-day or low-frequency intraday).

## 2. Legal / Compliance Advice
- **Status**: PENDING WRITTEN REVIEW.
- **Action Required**: Retain external counsel to review proprietary trading implications in the operating jurisdiction.
- **Expiry/Review Date**: [INSERT DATE]

## 3. Data-Source Register
- **Provider**: Alpaca Data API v2.
- **License**: Standard market data terms. Proprietary use only.
- **Redistribution**: Prohibited.
- **Retention**: Indefinite for historical analysis.
- **Correction Policy**: Daily EOD reconciliation with T+1 adjustments.
- **Owner**: System Operator.

## 4. Broker Capability Register
- **Sandbox Availability**: Yes (`paper-api.alpaca.markets`).
- **Authentication**: API Key / Secret (Environment Variables).
- **Order Semantics**: Market, Limit, Stop, StopLimit, TrailingStop.
- **Rate Limits**: 200 requests / minute.
- **Market-Data Entitlement**: IEX (Free) or SIP (Paid).
- **Statement Cadence**: T+1 Daily.
- **Reconciliation Coverage**: Positions, Balances, Orders.

## 5. Threat Model (Minimal)
- **Credentials**: Stored in ENV vars. Risk: Local exfiltration. Mitigation: Read-only API keys for paper.
- **Local Dev / CI**: Risk: Supply chain attack. Mitigation: Pinned dependencies, no auto-execution of untrusted test code.
- **Broker Callbacks**: None (using polling/WebSockets).
- **Data Poisoning**: Risk: Bad ticks. Mitigation: Gross deviation checks in `DataQuality`.
- **Operator Access**: Single-user CLI.

## 6. Capital Policy
- **Status**: PAPER ONLY.
- **External Capital**: Strictly Prohibited.
- **Leverage/Margin**: 1.0x (Cash only).
- **Modification**: Requires explicit Architecture Council and Risk Owner approval.
