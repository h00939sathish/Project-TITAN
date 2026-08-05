pub mod types;
pub mod messages;
pub mod event_store;
pub mod orders;
pub mod portfolio;
pub mod reconciliation;
pub mod risk;
pub mod validation;

use pyo3::prelude::*;

/// Returns the TITAN core library version.
#[pyfunction]
fn version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

/// A TITAN Python module implemented in Rust.
#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;

    // Domain types
    m.add_class::<types::Side>()?;
    m.add_class::<types::Money>()?;
    m.add_class::<types::Quantity>()?;
    m.add_class::<types::Price>()?;
    m.add_class::<types::InstrumentId>()?;
    m.add_class::<types::ContractType>()?;
    m.add_class::<types::Instrument>()?;

    // Messages
    m.add_class::<messages::EventEnvelope>()?;
    m.add_class::<messages::TradeIntent>()?;
    m.add_class::<messages::RiskDecision>()?;
    m.add_class::<messages::ApprovedOrderIntent>()?;

    // Event store
    m.add_class::<event_store::EventStore>()?;

    // Order state machine
    m.add_class::<orders::OrderState>()?;
    m.add_class::<orders::OrderStateMachine>()?;

    // Portfolio types
    m.add_class::<portfolio::PositionSide>()?;
    m.add_class::<portfolio::Position>()?;
    m.add_class::<portfolio::PortfolioEngine>()?;
    m.add_class::<portfolio::PortfolioSnapshot>()?;

    // Reconciliation types
    m.add_class::<reconciliation::ReconciliationEngine>()?;
    m.add_class::<reconciliation::ReconciliationConfig>()?;
    m.add_class::<reconciliation::ReconciliationResult>()?;
    m.add_class::<reconciliation::ReconciliationDriftSeverity>()?;
    m.add_class::<reconciliation::PositionDrift>()?;
    m.add_class::<reconciliation::BrokerPosition>()?;

    // Risk types
    m.add_class::<risk::TradingState>()?;
    m.add_class::<risk::KillSwitchState>()?;
    m.add_class::<risk::RiskConfig>()?;
    m.add_class::<risk::RiskReasonCode>()?;
    m.add_class::<risk::RiskVerdict>()?;
    m.add_class::<risk::RiskGate>()?;

    // Risk state snapshot
    m.add_class::<messages::RiskStateSnapshot>()?;

    Ok(())
}
