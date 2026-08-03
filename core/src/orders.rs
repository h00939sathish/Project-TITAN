use chrono::Utc;
use pyo3::exceptions::PyRuntimeError;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::event_store;
use crate::messages::EventEnvelope;

/// Valid order states per EXECUTION_SPEC.md.
#[pyclass(eq, eq_int, from_py_object)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Serialize, Deserialize)]
pub enum OrderState {
    #[default]
    New,
    Validated,
    Submitted,
    Acknowledged,
    PartiallyFilled,
    Filled,
    CancelPending,
    Cancelled,
    Rejected,
    Expired,
    Unknown,
}

#[pymethods]
impl OrderState {
    fn __str__(&self) -> String {
        format!("{:?}", self)
    }

    fn __repr__(&self) -> String {
        format!("OrderState.{:?}", self)
    }

    pub fn is_terminal(&self) -> bool {
        matches!(
            self,
            OrderState::Filled
                | OrderState::Cancelled
                | OrderState::Rejected
                | OrderState::Expired
        )
    }
}

/// Event payload for order state transitions persisted to EventStore.
#[derive(Serialize)]
pub struct OrderEvent {
    pub order_id: String,
    pub from_state: String,
    pub to_state: String,
    pub reason: String,
    pub occurred_at: String,
    pub message_id: String,
}

/// Pure Rust state machine — no PyO3 dependency, testable from `cargo test`.
#[derive(Clone, Debug, Default)]
pub struct StateMachineCore {
    pub current: OrderState,
}

impl StateMachineCore {
    pub fn new() -> Self {
        Self {
            current: OrderState::New,
        }
    }

    pub fn transition(&mut self, target: OrderState) -> Result<(), String> {
        let from = self.current;

        if from == target {
            return Ok(());
        }

        if from.is_terminal() {
            return Err(format!(
                "Cannot transition from terminal state {:?} to {:?}",
                from, target
            ));
        }

        let valid = match (from, target) {
            // Normal flow
            (OrderState::New, OrderState::Validated) => true,
            (OrderState::Validated, OrderState::Submitted) => true,
            (OrderState::Submitted, OrderState::Acknowledged) => true,
            (OrderState::Acknowledged, OrderState::PartiallyFilled) => true,
            (OrderState::Acknowledged, OrderState::Filled) => true,
            (OrderState::PartiallyFilled, OrderState::Filled) => true,


            // Rejection can happen from multiple states
            (OrderState::New, OrderState::Rejected) => true,
            (OrderState::Validated, OrderState::Rejected) => true,
            (OrderState::Submitted, OrderState::Rejected) => true,
            (OrderState::Acknowledged, OrderState::Rejected) => true,

            // Cancellation
            (OrderState::Acknowledged, OrderState::CancelPending) => true,
            (OrderState::PartiallyFilled, OrderState::CancelPending) => true,
            (OrderState::CancelPending, OrderState::Cancelled) => true,

            // Expiry
            (OrderState::Acknowledged, OrderState::Expired) => true,
            (OrderState::PartiallyFilled, OrderState::Expired) => true,

            // Unknown (safety state on timeout/ambiguity)
            (OrderState::Submitted, OrderState::Unknown) => true,
            (OrderState::CancelPending, OrderState::Unknown) => true,

            // Reconciliation from Unknown
            (OrderState::Unknown, OrderState::Acknowledged) => true,
            (OrderState::Unknown, OrderState::Filled) => true,
            (OrderState::Unknown, OrderState::Rejected) => true,
            (OrderState::Unknown, OrderState::Cancelled) => true,
            (OrderState::Unknown, OrderState::Expired) => true,

            _ => false,
        };

        if valid {
            self.current = target;
            Ok(())
        } else {
            Err(format!(
                "Illegal state transition: {:?} -> {:?}",
                from, target
            ))
        }
    }

    pub fn reset_to(&mut self, state: OrderState) {
        self.current = state;
    }
}

/// PyO3 wrapper — validates and applies state transitions for an order.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, Default)]
pub struct OrderStateMachine {
    inner: StateMachineCore,
}

#[pymethods]
impl OrderStateMachine {
    #[new]
    pub fn new() -> Self {
        Self {
            inner: StateMachineCore::new(),
        }
    }

    #[getter]
    pub fn get_current(&self) -> OrderState {
        self.inner.current
    }

    pub fn transition(&mut self, target: OrderState) -> PyResult<()> {
        self.inner.transition(target).map_err(PyValueError::new_err)
    }

    pub fn reset_to(&mut self, state: OrderState) {
        self.inner.reset_to(state);
    }

    pub fn persist_transition(
        &self,
        store: &event_store::EventStore,
        order_id: &str,
        from: &OrderState,
        to: &OrderState,
        reason: &str,
    ) -> PyResult<()> {
        let now = Utc::now().to_rfc3339();
        let msg_id = Uuid::now_v7().to_string();
        let event = OrderEvent {
            order_id: order_id.to_string(),
            from_state: format!("{:?}", from),
            to_state: format!("{:?}", to),
            reason: reason.to_string(),
            occurred_at: now,
            message_id: msg_id,
        };
        let payload = serde_json::to_string(&event)
            .map_err(|e| PyRuntimeError::new_err(format!("Serialize error: {}", e)))?;
        let envelope = EventEnvelope::new(
            "OrderTransition".to_string(),
            "Order".to_string(),
            order_id.to_string(),
            "titan_core".to_string(),
            payload,
            None,
            None,
            None,
        );
        store.append(&envelope)
    }

    fn __str__(&self) -> String {
        format!("OrderStateMachine({:?})", self.inner.current)
    }

    fn __repr__(&self) -> String {
        format!("OrderStateMachine(state={:?})", self.inner.current)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normal_lifecycle() {
        let mut m = StateMachineCore::new();
        assert_eq!(m.current, OrderState::New);

        m.transition(OrderState::Validated).unwrap();
        assert_eq!(m.current, OrderState::Validated);

        m.transition(OrderState::Submitted).unwrap();
        assert_eq!(m.current, OrderState::Submitted);

        m.transition(OrderState::Acknowledged).unwrap();
        assert_eq!(m.current, OrderState::Acknowledged);

        m.transition(OrderState::PartiallyFilled).unwrap();
        assert_eq!(m.current, OrderState::PartiallyFilled);

        m.transition(OrderState::Filled).unwrap();
        assert_eq!(m.current, OrderState::Filled);
    }

    #[test]
    fn test_direct_acknowledged_to_filled() {
        let mut m = StateMachineCore::new();
        m.transition(OrderState::Validated).unwrap();
        m.transition(OrderState::Submitted).unwrap();
        m.transition(OrderState::Acknowledged).unwrap();
        m.transition(OrderState::Filled).unwrap();
        assert_eq!(m.current, OrderState::Filled);
    }


    #[test]
    fn test_rejection_from_new() {
        let mut m = StateMachineCore::new();
        m.transition(OrderState::Rejected).unwrap();
        assert_eq!(m.current, OrderState::Rejected);
        assert!(m.current.is_terminal());
    }

    #[test]
    fn test_cancel_lifecycle() {
        let mut m = StateMachineCore::new();
        m.transition(OrderState::Validated).unwrap();
        m.transition(OrderState::Submitted).unwrap();
        m.transition(OrderState::Acknowledged).unwrap();
        m.transition(OrderState::CancelPending).unwrap();
        assert_eq!(m.current, OrderState::CancelPending);
        m.transition(OrderState::Cancelled).unwrap();
        assert_eq!(m.current, OrderState::Cancelled);
    }

    #[test]
    fn test_unknown_reconciliation() {
        let mut m = StateMachineCore::new();
        m.transition(OrderState::Validated).unwrap();
        m.transition(OrderState::Submitted).unwrap();
        m.transition(OrderState::Unknown).unwrap();
        assert_eq!(m.current, OrderState::Unknown);

        m.transition(OrderState::Acknowledged).unwrap();
        assert_eq!(m.current, OrderState::Acknowledged);
    }

    #[test]
    fn test_terminal_state_rejects_transitions() {
        let mut m = StateMachineCore::new();
        // Can't go directly to Filled; use the full lifecycle
        m.transition(OrderState::Validated).unwrap();
        m.transition(OrderState::Submitted).unwrap();
        m.transition(OrderState::Acknowledged).unwrap();
        m.transition(OrderState::PartiallyFilled).unwrap();
        m.transition(OrderState::Filled).unwrap();
        assert!(m.transition(OrderState::Acknowledged).is_err());
    }

    #[test]
    fn test_illegal_transition() {
        let mut m = StateMachineCore::new();
        // Cannot go from New directly to Cancelled
        assert!(m.transition(OrderState::Cancelled).is_err());
        // Cannot go from Submitted directly to Filled
        m.transition(OrderState::Validated).unwrap();
        m.transition(OrderState::Submitted).unwrap();
        assert!(m.transition(OrderState::Filled).is_err());
    }

    #[test]
    fn test_partial_fill_then_cancel() {
        let mut m = StateMachineCore::new();
        m.transition(OrderState::Validated).unwrap();
        m.transition(OrderState::Submitted).unwrap();
        m.transition(OrderState::Acknowledged).unwrap();
        m.transition(OrderState::PartiallyFilled).unwrap();
        assert_eq!(m.current, OrderState::PartiallyFilled);
        m.transition(OrderState::CancelPending).unwrap();
        m.transition(OrderState::Cancelled).unwrap();
        assert_eq!(m.current, OrderState::Cancelled);
    }

    #[test]
    fn test_reset_to() {
        let mut m = StateMachineCore::new();
        m.transition(OrderState::Validated).unwrap();
        m.transition(OrderState::Submitted).unwrap();
        m.transition(OrderState::Acknowledged).unwrap();
        m.transition(OrderState::PartiallyFilled).unwrap();
        m.transition(OrderState::Filled).unwrap();
        assert!(m.current.is_terminal());

        m.reset_to(OrderState::New);
        assert_eq!(m.current, OrderState::New);
    }
}
