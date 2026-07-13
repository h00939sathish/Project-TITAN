use std::collections::HashMap;
use pyo3::prelude::*;
use crate::portfolio::{PortfolioEngine, PositionSide};
use crate::types::Money;

// ─── ReconciliationDriftSeverity ────────────────────────────────────────────────

#[pyclass(eq, eq_int)]
#[derive(Clone, Debug, PartialEq)]
pub enum ReconciliationDriftSeverity {
    InSync,
    Warning,
    Critical,
}

// ─── PositionDrift ──────────────────────────────────────────────────────────────

#[pyclass]
#[derive(Clone, Debug)]
pub struct PositionDrift {
    #[pyo3(get)]
    pub instrument_id: String,
    #[pyo3(get)]
    pub expected_side: String,
    #[pyo3(get)]
    pub expected_quantity: i64,
    #[pyo3(get)]
    pub actual_side: String,
    #[pyo3(get)]
    pub actual_quantity: i64,
    #[pyo3(get)]
    pub quantity_drift: i64,
}

// ─── ReconciliationResult ────────────────────────────────────────────────────────

#[pyclass]
#[derive(Clone, Debug)]
pub struct ReconciliationResult {
    #[pyo3(get)]
    pub severity: ReconciliationDriftSeverity,
    #[pyo3(get)]
    pub position_drifts: Vec<PositionDrift>,
    #[pyo3(get)]
    pub cash_expected: Money,
    #[pyo3(get)]
    pub cash_actual: Money,
    #[pyo3(get)]
    pub cash_drift: Money,
    #[pyo3(get)]
    pub summary: String,
}

// ─── ReconciliationConfig ────────────────────────────────────────────────────────

#[pyclass]
#[derive(Clone, Debug)]
pub struct ReconciliationConfig {
    #[pyo3(get, set)]
    pub critical_drift_fraction: f64,
    #[pyo3(get, set)]
    pub warning_drift_fraction: f64,
}

#[pymethods]
impl ReconciliationConfig {
    #[new]
    #[pyo3(signature = (critical_drift_fraction=None, warning_drift_fraction=None))]
    pub fn new(critical_drift_fraction: Option<f64>, warning_drift_fraction: Option<f64>) -> Self {
        Self {
            critical_drift_fraction: critical_drift_fraction.unwrap_or(0.05),
            warning_drift_fraction: warning_drift_fraction.unwrap_or(0.01),
        }
    }
}

impl Default for ReconciliationConfig {
    fn default() -> Self {
        Self {
            critical_drift_fraction: 0.05,
            warning_drift_fraction: 0.01,
        }
    }
}

// ─── BrokerPosition ────────────────────────────────────────────────────────────

#[pyclass]
#[derive(Clone, Debug)]
pub struct BrokerPosition {
    #[pyo3(get)]
    pub instrument_id: String,
    #[pyo3(get)]
    pub side: String,
    #[pyo3(get)]
    pub quantity: i64,
}

#[pymethods]
impl BrokerPosition {
    #[new]
    pub fn new(instrument_id: String, side: String, quantity: i64) -> Self {
        Self {
            instrument_id,
            side,
            quantity,
        }
    }
}

// ─── ReconciliationEngine ────────────────────────────────────────────────────────

#[pyclass]
#[derive(Clone, Debug)]
pub struct ReconciliationEngine {
    config: ReconciliationConfig,
}

#[pymethods]
impl ReconciliationEngine {
    #[new]
    #[pyo3(signature = (config=None))]
    pub fn new(config: Option<ReconciliationConfig>) -> Self {
        Self {
            config: config.unwrap_or_default(),
        }
    }

    pub fn compare(
        &self,
        portfolio: &PortfolioEngine,
        broker_positions: Vec<BrokerPosition>,
        broker_cash: &Money,
    ) -> ReconciliationResult {
        let broker_map: HashMap<&str, &BrokerPosition> = broker_positions
            .iter()
            .map(|bp| (bp.instrument_id.as_str(), bp))
            .collect();

        let mut position_drifts: Vec<PositionDrift> = Vec::new();

        for (inst_id, pos) in &portfolio.positions {
            let broker_pos = broker_map.get(inst_id.as_str());
            let (expected_side, expected_qty) = signed_position(pos.side, pos.quantity);
            let (actual_side, actual_qty) = match broker_pos {
                Some(bp) => (bp.side.clone(), signed_broker(&bp.side, bp.quantity)),
                None => ("FLAT".to_string(), 0),
            };
            let quantity_drift = (expected_qty - actual_qty).unsigned_abs() as i64;
            position_drifts.push(PositionDrift {
                instrument_id: inst_id.clone(),
                expected_side,
                expected_quantity: expected_qty,
                actual_side,
                actual_quantity: actual_qty,
                quantity_drift,
            });
        }

        for bp in &broker_positions {
            if !portfolio.positions.contains_key(&bp.instrument_id) {
                let (actual_side, actual_qty) = (bp.side.clone(), signed_broker(&bp.side, bp.quantity));
                position_drifts.push(PositionDrift {
                    instrument_id: bp.instrument_id.clone(),
                    expected_side: "FLAT".to_string(),
                    expected_quantity: 0,
                    actual_side,
                    actual_quantity: actual_qty,
                    quantity_drift: actual_qty.unsigned_abs() as i64,
                });
            }
        }

        let cash_expected = portfolio.get_cash_balance();
        let cash_actual = broker_cash.clone();
        let cash_exp_amount = parse_amount(&cash_expected).unwrap_or(0);
        let cash_act_amount = parse_amount(&cash_actual).unwrap_or(0);
        let cash_drift_amount = (cash_exp_amount - cash_act_amount).unsigned_abs() as i64;

        // Determine severity
        let severity = self.compute_severity(&position_drifts, cash_exp_amount, cash_act_amount);

        let summary = format!(
            "Reconciliation: {:?} — {} position drift(s), cash drift {}",
            severity,
            position_drifts.len(),
            cash_drift_amount,
        );

        let cash_drift = Money::new(&cash_drift_amount.to_string(), &cash_expected.currency);

        ReconciliationResult {
            severity,
            position_drifts,
            cash_expected,
            cash_actual,
            cash_drift,
            summary,
        }
    }
}

impl ReconciliationEngine {
    fn compute_severity(
        &self,
        drifts: &[PositionDrift],
        cash_exp_amount: i64,
        cash_act_amount: i64,
    ) -> ReconciliationDriftSeverity {
        let mut severity = ReconciliationDriftSeverity::InSync;

        for pd in drifts {
            let max_qty = pd
                .expected_quantity
                .abs()
                .max(pd.actual_quantity.abs())
                .max(1);
            let drift_fraction = pd.quantity_drift as f64 / max_qty as f64;

            if drift_fraction > self.config.critical_drift_fraction {
                return ReconciliationDriftSeverity::Critical;
            }
            if drift_fraction > self.config.warning_drift_fraction {
                severity = ReconciliationDriftSeverity::Warning;
            }
        }

        // Cash drift check
        if severity != ReconciliationDriftSeverity::Critical {
            let cash_drift_amount = (cash_exp_amount - cash_act_amount).unsigned_abs() as i64;
            let max_cash = cash_exp_amount
                .abs()
                .max(cash_act_amount.abs())
                .max(1);
            let cash_drift_fraction = cash_drift_amount as f64 / max_cash as f64;

            if cash_drift_fraction > self.config.critical_drift_fraction {
                return ReconciliationDriftSeverity::Critical;
            }
            if cash_drift_fraction > self.config.warning_drift_fraction {
                severity = ReconciliationDriftSeverity::Warning;
            }
        }

        severity
    }
}

// ─── Private helpers ─────────────────────────────────────────────────────────────

fn signed_broker(side: &str, quantity: i64) -> i64 {
    match side {
        "LONG" => quantity,
        "SHORT" => -quantity.abs(),
        _ => 0,
    }
}

fn signed_position(side: PositionSide, quantity: u64) -> (String, i64) {
    match side {
        PositionSide::Flat => ("FLAT".to_string(), 0),
        PositionSide::Long => ("LONG".to_string(), quantity as i64),
        PositionSide::Short => ("SHORT".to_string(), -(quantity as i64)),
    }
}

fn parse_amount(m: &Money) -> Option<i64> {
    m.amount.parse::<i64>().ok()
}

// ─── Tests ───────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::portfolio::PortfolioEngine;

    fn engine() -> PortfolioEngine {
        PortfolioEngine::new("USD", &Money::new("100000", "USD"))
    }

    fn apply(engine: &mut PortfolioEngine, instrument: &str, side: &str, qty: u64, price: i64) {
        engine
            .apply_fill(instrument, side, qty, &Money::new(&price.to_string(), "USD"))
            .unwrap();
    }

    fn broker_pos(instrument: &str, side: &str, qty: i64) -> BrokerPosition {
        BrokerPosition {
            instrument_id: instrument.to_string(),
            side: side.to_string(),
            quantity: qty,
        }
    }

    #[test]
    fn test_in_sync() {
        let mut p = engine();
        apply(&mut p, "AAPL", "buy", 100, 50);
        let re = ReconciliationEngine::new(None);
        let result = re.compare(
            &p,
            vec![broker_pos("AAPL", "LONG", 100)],
            &Money::new("95000", "USD"),
        );
        assert_eq!(result.severity, ReconciliationDriftSeverity::InSync);
        assert_eq!(result.position_drifts.len(), 1);
        assert_eq!(result.position_drifts[0].quantity_drift, 0);
    }

    #[test]
    fn test_small_position_drift_warning() {
        let mut p = engine();
        apply(&mut p, "AAPL", "buy", 100, 50);
        let re = ReconciliationEngine::new(None);
        let result = re.compare(
            &p,
            vec![broker_pos("AAPL", "LONG", 98)],
            &Money::new("95000", "USD"),
        );
        assert_eq!(result.severity, ReconciliationDriftSeverity::Warning);
    }

    #[test]
    fn test_large_position_drift_critical() {
        let mut p = engine();
        apply(&mut p, "AAPL", "buy", 100, 50);
        let re = ReconciliationEngine::new(None);
        let result = re.compare(
            &p,
            vec![broker_pos("AAPL", "LONG", 80)],
            &Money::new("95000", "USD"),
        );
        assert_eq!(result.severity, ReconciliationDriftSeverity::Critical);
    }

    #[test]
    fn test_cash_drift_critical() {
        let mut p = engine();
        apply(&mut p, "AAPL", "buy", 100, 50);
        let re = ReconciliationEngine::new(None);
        let result = re.compare(
            &p,
            vec![broker_pos("AAPL", "LONG", 100)],
            &Money::new("90000", "USD"),
        );
        assert_eq!(result.severity, ReconciliationDriftSeverity::Critical);
    }

    #[test]
    fn test_broker_has_unknown_position() {
        let mut p = engine();
        apply(&mut p, "AAPL", "buy", 100, 50);
        let re = ReconciliationEngine::new(None);
        let result = re.compare(
            &p,
            vec![
                broker_pos("AAPL", "LONG", 100),
                broker_pos("GOOG", "SHORT", 50),
            ],
            &Money::new("95000", "USD"),
        );
        assert_eq!(result.severity, ReconciliationDriftSeverity::Critical);
        assert_eq!(result.position_drifts.len(), 2);
    }

    #[test]
    fn test_portfolio_has_unknown_position() {
        let mut p = engine();
        apply(&mut p, "AAPL", "buy", 100, 50);
        apply(&mut p, "MSFT", "sell", 50, 200);
        let re = ReconciliationEngine::new(None);
        let result = re.compare(
            &p,
            vec![broker_pos("AAPL", "LONG", 100)],
            &Money::new("105000", "USD"),
        );
        assert_eq!(result.severity, ReconciliationDriftSeverity::Critical);
        assert_eq!(result.position_drifts.len(), 2);
    }

    #[test]
    fn test_empty_portfolio() {
        let p = engine();
        let re = ReconciliationEngine::new(None);
        let result = re.compare(&p, vec![], &Money::new("100000", "USD"));
        assert_eq!(result.severity, ReconciliationDriftSeverity::InSync);
        assert_eq!(result.position_drifts.len(), 0);
    }

    #[test]
    fn test_multiple_drifts_collected() {
        let mut p = engine();
        apply(&mut p, "AAPL", "buy", 100, 50);
        apply(&mut p, "MSFT", "sell", 50, 200);
        apply(&mut p, "SPY", "buy", 200, 400);
        let re = ReconciliationEngine::new(None);
        let result = re.compare(
            &p,
            vec![
                broker_pos("AAPL", "LONG", 100),
                broker_pos("MSFT", "SHORT", 48),
                broker_pos("SPY", "LONG", 200),
            ],
            &Money::new("25000", "USD"),
        );
        assert_eq!(result.severity, ReconciliationDriftSeverity::Warning);
        assert_eq!(result.position_drifts.len(), 3);
    }
}
