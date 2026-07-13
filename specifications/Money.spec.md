# Money Specification

> **Owner:** Core Platform Architecture
> **Status:** Active — Phase -1
> **Last Review:** 2026-07-13
> **Supersedes:** None
> **Implemented in:** Phase B (core/src/types.rs)

## Purpose

Provide a safe, deterministic representation of monetary values, quantities, prices, and currency that eliminates floating-point errors at the economic boundary.

## Boundary / Ownership

Owns: `Money`, `Quantity`, `Price`, `Currency`, `Side` (BUY/SELL) domain types.
Delegates to: Nothing.
Called by: Every subsystem that reasons about economic value.

## Inputs

- Decimal strings from external sources (JSON, CSV, adapter messages)
- Integer/string representations of currency codes (ISO 4217)

## Outputs

- Fixed-decimal `Money` values with explicit currency
- Fixed-decimal `Price` values with explicit precision
- Fixed-decimal `Quantity` values (whole units for instruments, fractional for some asset classes)
- `Side` enum (BUY, SELL)

## State machine

None — Money types are immutable value objects.

## Dependencies

None.

## Error taxonomy

| Error | Classification | Recovery |
|---|---|---|
| Invalid decimal string | Data-quality | Reject input, return error to caller |
| Currency mismatch in arithmetic operation | Operational | Return error; do not coerce |
| Overflow in arithmetic | Terminal (should not occur within configured bounds) | Return error |
| Division by zero | Terminal | Return error |
| Precision loss in rounding | Data-quality | Return error; caller must specify rounding mode explicitly |

## Metrics

None — value objects produce no telemetry.

## Configuration

| Key | Type | Default | Description |
|---|---|---|---|
| `money.default_precision` | integer | 8 | Default decimal places for Money display/parsing |
| `money.max_precision` | integer | 18 | Maximum supported decimal places |
| `money.max_magnitude` | string (decimal) | "1000000000000" | Maximum absolute value (1 trillion) |

## Performance budget

- Construction from string: p99 <1 μs
- Arithmetic (add, sub, mul, div): p99 <500 ns
- Comparison: p99 <200 ns

See `PERFORMANCE_SPEC.md`.

## Failure behavior

Money operations do not interact with external systems. All failure modes are data-quality or terminal errors surfaced to the caller. See `FAILURE_MATRIX.md` (no external-failure rows for Money).
