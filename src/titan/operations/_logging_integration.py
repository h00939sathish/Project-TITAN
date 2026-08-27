"""Integration helpers that wire StructuredLogger into runtime paths."""

from titan.operations.logging import StructuredLogger, LogSeverity


def log_risk_decision(logger: StructuredLogger, intent_id: str, accepted: bool,
                      reason: str | None, correlation_id: str = "",
                      instrument_id: str = "") -> None:
    if logger is None:
        return
    if accepted:
        logger.info("risk_gate", f"Intent {intent_id} accepted",
                    correlation_id=correlation_id,
                    payload={"intent_id": intent_id, "verdict": "accepted", "instrument_id": instrument_id})
    else:
        logger.warning("risk_gate", f"Intent {intent_id} rejected: {reason}",
                       correlation_id=correlation_id,
                       payload={"intent_id": intent_id, "verdict": "rejected",
                                "reason": reason, "instrument_id": instrument_id})


def log_adapter_event(logger: StructuredLogger, event: str, order_id: str,
                      instrument_id: str = "", correlation_id: str = "",
                      payload: dict | None = None) -> None:
    if logger is None:
        return
    logger.info("adapter", f"Order {order_id} {event}",
                correlation_id=correlation_id,
                payload={"order_id": order_id, "event": event,
                         "instrument_id": instrument_id, **(payload or {})})


def log_reconciliation(logger: StructuredLogger, result: dict,
                       correlation_id: str = "") -> None:
    if logger is None:
        return
    severity = LogSeverity.WARNING if result.get("has_drift") else LogSeverity.INFO
    logger._log(severity, "reconciliation", "Reconciliation completed",
                correlation_id=correlation_id, payload=result)
