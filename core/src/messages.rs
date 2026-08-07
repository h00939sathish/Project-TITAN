use chrono::Utc;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Canonical event envelope for all TITAN domain events.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EventEnvelope {
    #[pyo3(get)]
    #[serde(deserialize_with = "crate::validation::deserialize_uuid")]
    pub message_id: String,
    #[pyo3(get)]
    pub message_type: String,
    #[pyo3(get)]
    #[serde(deserialize_with = "crate::validation::deserialize_schema_version")]
    pub schema_version: u32,
    #[pyo3(get)]
    #[serde(deserialize_with = "crate::validation::deserialize_rfc3339")]
    pub occurred_at: String,
    #[pyo3(get)]
    #[serde(deserialize_with = "crate::validation::deserialize_uuid")]
    pub correlation_id: String,
    #[pyo3(get, set)]
    #[serde(default, deserialize_with = "crate::validation::deserialize_opt_uuid")]
    pub causation_id: Option<String>,
    #[pyo3(get)]
    pub aggregate_type: String,
    #[pyo3(get)]
    pub aggregate_id: String,
    #[pyo3(get)]
    pub source: String,
    #[pyo3(get)]
    pub payload: String,
    #[pyo3(get)]
    pub metadata: Option<String>,
}

#[pymethods]
impl EventEnvelope {
    #[new]
    #[allow(clippy::too_many_arguments)]
    #[pyo3(signature = (message_type, aggregate_type, aggregate_id, source, payload, correlation_id=None, causation_id=None, metadata=None))]
    pub fn new(
        message_type: String,
        aggregate_type: String,
        aggregate_id: String,
        source: String,
        payload: String,
        correlation_id: Option<String>,
        causation_id: Option<String>,
        metadata: Option<String>,
    ) -> Self {
        let now = Utc::now().to_rfc3339();
        Self {
            message_id: Uuid::now_v7().to_string(),
            message_type,
            schema_version: 100,
            occurred_at: now,
            correlation_id: correlation_id.unwrap_or_else(|| Uuid::now_v7().to_string()),
            causation_id,
            aggregate_type,
            aggregate_id,
            source,
            payload,
            metadata,
        }
    }

    pub fn to_json(&self) -> PyResult<String> {
        serde_json::to_string(self).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Serialization error: {}", e))
        })
    }

    #[staticmethod]
    pub fn from_json(json: &str) -> PyResult<Self> {
        serde_json::from_str(json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Deserialization error: {}", e))
        })
    }

    fn __str__(&self) -> String {
        format!("{}[{}] {}", self.message_type, self.aggregate_id, self.message_id)
    }

    fn __repr__(&self) -> String {
        format!(
            "EventEnvelope(type={}, agg={}/{}, id={})",
            self.message_type, self.aggregate_type, self.aggregate_id, self.message_id
        )
    }
}

/// Trailing-stop configuration in price terms (broker-agnostic).
///
/// - activation_distance: how far price must move from the fill (entry) before
///   the trail arms; 0/none means arm immediately.
/// - trail_distance: how far the stop lags the current price once armed.
/// Both are absolute price distances. Validation requires
/// activation_distance >= trail_distance.
#[pyclass(get_all)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TrailingConfig {
    #[serde(deserialize_with = "crate::validation::deserialize_decimal_string")]
    pub activation_distance: String,
    #[serde(deserialize_with = "crate::validation::deserialize_decimal_string")]
    pub trail_distance: String,
}

#[pymethods]
impl TrailingConfig {
    #[new]
    #[pyo3(signature = (activation_distance, trail_distance))]
    pub fn new(activation_distance: String, trail_distance: String) -> Self {
        Self { activation_distance, trail_distance }
    }

    /// Validation: activation distance must be >= trail distance.
    /// Returns Ok(()) or a ValueError with a stable machine-readable code.
    pub fn validate(&self) -> PyResult<()> {
        let act: f64 = self.activation_distance.parse().map_err(|_| {
            pyo3::exceptions::PyValueError::new_err("trailing_activation_invalid")
        })?;
        let trl: f64 = self.trail_distance.parse().map_err(|_| {
            pyo3::exceptions::PyValueError::new_err("trailing_distance_invalid")
        })?;
        if act < trl {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "trailing_activation_less_than_distance",
            ));
        }
        Ok(())
    }
}

/// A typed trade intent emitted by a strategy.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TradeIntent {
    #[pyo3(get)]
    pub strategy_id: String,
    #[pyo3(get)]
    pub strategy_package_digest: String,
    #[pyo3(get)]
    pub account_id: String,
    #[pyo3(get)]
    pub instrument_id: String,
    #[pyo3(get)]
    pub side: String,
    #[pyo3(get)]
    #[serde(deserialize_with = "crate::validation::deserialize_decimal_string")]
    pub quantity: String,
    #[pyo3(get)]
    #[serde(default, deserialize_with = "crate::validation::deserialize_opt_decimal_string")]
    pub price: Option<String>,
    #[pyo3(get)]
    #[serde(default, deserialize_with = "crate::validation::deserialize_opt_decimal_string")]
    pub stop_price: Option<String>,
    #[pyo3(get)]
    #[serde(default, deserialize_with = "crate::validation::deserialize_opt_decimal_string")]
    pub take_profit_price: Option<String>,
    #[pyo3(get)]
    #[serde(default)]
    pub trailing: Option<TrailingConfig>,
    #[pyo3(get)]
    pub order_type: String,
    #[pyo3(get)]
    pub time_in_force: String,
    #[pyo3(get)]
    pub risk_profile_version: String,
    #[pyo3(get)]
    #[serde(deserialize_with = "crate::validation::deserialize_rfc3339")]
    pub market_data_timestamp: String,
    #[pyo3(get)]
    #[serde(default, deserialize_with = "crate::validation::deserialize_opt_rfc3339")]
    pub expiry: Option<String>,
}

#[pymethods]
impl TradeIntent {
    #[new]
    #[allow(clippy::too_many_arguments)]
    #[pyo3(signature = (
        strategy_id, strategy_package_digest, account_id, instrument_id,
        side, quantity, order_type, time_in_force, risk_profile_version, market_data_timestamp,
        price=None, stop_price=None, take_profit_price=None, trailing=None, expiry=None
    ))]
    pub fn new(
        strategy_id: String,
        strategy_package_digest: String,
        account_id: String,
        instrument_id: String,
        side: String,
        quantity: String,
        order_type: String,
        time_in_force: String,
        risk_profile_version: String,
        market_data_timestamp: String,
        price: Option<String>,
        stop_price: Option<String>,
        take_profit_price: Option<String>,
        trailing: Option<TrailingConfig>,
        expiry: Option<String>,
    ) -> Self {
        Self {
            strategy_id,
            strategy_package_digest,
            account_id,
            instrument_id,
            side: side.to_uppercase(),
            quantity,
            price,
            stop_price,
            take_profit_price,
            trailing,
            order_type: order_type.to_uppercase(),
            time_in_force: time_in_force.to_uppercase(),
            risk_profile_version,
            market_data_timestamp,
            expiry,
        }
    }

    pub fn to_json(&self) -> PyResult<String> {
        serde_json::to_string(self).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Serialization error: {}", e))
        })
    }

    #[staticmethod]
    pub fn from_json(json: &str) -> PyResult<Self> {
        serde_json::from_str(json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Deserialization error: {}", e))
        })
    }

    fn __str__(&self) -> String {
        format!("{} {} {} @ {}", self.side, self.quantity, self.instrument_id, self.strategy_id)
    }
}

/// A deterministic risk decision.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RiskDecision {
    #[pyo3(get)]
    #[serde(deserialize_with = "crate::validation::deserialize_uuid")]
    pub intent_id: String,
    #[pyo3(get)]
    pub decision: String,
    #[pyo3(get)]
    #[serde(deserialize_with = "crate::validation::deserialize_rfc3339")]
    pub evaluated_at: String,
    #[pyo3(get)]
    pub reason_codes: Vec<String>,
    #[pyo3(get)]
    pub evaluated_rules: String,
    #[pyo3(get)]
    pub inputs_digest: Option<String>,
    #[pyo3(get)]
    pub limit_snapshot_digest: Option<String>,
}

#[pymethods]
impl RiskDecision {
    #[new]
    #[pyo3(signature = (intent_id, decision, reason_codes, evaluated_rules, inputs_digest=None, limit_snapshot_digest=None))]
    pub fn new(
        intent_id: String,
        decision: String,
        reason_codes: Vec<String>,
        evaluated_rules: String,
        inputs_digest: Option<String>,
        limit_snapshot_digest: Option<String>,
    ) -> Self {
        Self {
            intent_id,
            decision: decision.to_uppercase(),
            evaluated_at: Utc::now().to_rfc3339(),
            reason_codes,
            evaluated_rules,
            inputs_digest,
            limit_snapshot_digest,
        }
    }

    pub fn to_json(&self) -> PyResult<String> {
        serde_json::to_string(self).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Serialization error: {}", e))
        })
    }

    #[staticmethod]
    pub fn from_json(json: &str) -> PyResult<Self> {
        serde_json::from_str(json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Deserialization error: {}", e))
        })
    }

    fn __str__(&self) -> String {
        format!("RiskDecision({}) for intent {}", self.decision, self.intent_id)
    }
}

/// An order intent that passed the risk gate.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ApprovedOrderIntent {
    #[pyo3(get)]
    #[serde(deserialize_with = "crate::validation::deserialize_uuid")]
    pub risk_decision_id: String,
    #[pyo3(get)]
    #[serde(deserialize_with = "crate::validation::deserialize_uuid")]
    pub intent_id: String,
    #[pyo3(get)]
    #[serde(deserialize_with = "crate::validation::deserialize_uuid")]
    pub client_order_id: String,
    #[pyo3(get)]
    pub instrument_id: String,
    #[pyo3(get)]
    pub side: String,
    #[pyo3(get)]
    #[serde(deserialize_with = "crate::validation::deserialize_decimal_string")]
    pub quantity: String,
    #[pyo3(get)]
    #[serde(default, deserialize_with = "crate::validation::deserialize_opt_decimal_string")]
    pub price: Option<String>,
    #[pyo3(get)]
    #[serde(default, deserialize_with = "crate::validation::deserialize_opt_decimal_string")]
    pub stop_price: Option<String>,
    #[pyo3(get)]
    pub order_type: String,
    #[pyo3(get)]
    pub time_in_force: String,
    #[pyo3(get)]
    pub risk_profile_version: String,
    #[pyo3(get)]
    pub risk_token: Option<String>,
}

#[pymethods]
impl ApprovedOrderIntent {
    #[new]
    #[allow(clippy::too_many_arguments)]
    #[pyo3(signature = (
        risk_decision_id, intent_id, client_order_id, instrument_id,
        side, quantity, order_type, time_in_force, risk_profile_version,
        price=None, stop_price=None, risk_token=None
    ))]
    pub fn new(
        risk_decision_id: String,
        intent_id: String,
        client_order_id: String,
        instrument_id: String,
        side: String,
        quantity: String,
        order_type: String,
        time_in_force: String,
        risk_profile_version: String,
        price: Option<String>,
        stop_price: Option<String>,
        risk_token: Option<String>,
    ) -> Self {
        Self {
            risk_decision_id,
            intent_id,
            client_order_id,
            instrument_id,
            side: side.to_uppercase(),
            quantity,
            price,
            stop_price,
            order_type: order_type.to_uppercase(),
            time_in_force: time_in_force.to_uppercase(),
            risk_profile_version,
            risk_token,
        }
    }

    pub fn compute_expected_token(&self, secret_key: &str) -> String {
        use sha2::{Sha256, Digest};
        let mut hasher = Sha256::new();
        let payload = format!(
            "{}:{}:{}:{}:{}:{}",
            self.risk_decision_id,
            self.client_order_id,
            self.instrument_id,
            self.side,
            self.quantity,
            self.price.as_deref().unwrap_or("0")
        );
        hasher.update(secret_key.as_bytes());
        hasher.update(payload.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    pub fn attach_risk_token(&mut self, secret_key: &str) {
        self.risk_token = Some(self.compute_expected_token(secret_key));
    }

    pub fn verify_risk_token(&self, secret_key: &str) -> bool {
        match &self.risk_token {
            Some(token) => token == &self.compute_expected_token(secret_key),
            None => false,
        }
    }


    pub fn to_json(&self) -> PyResult<String> {
        serde_json::to_string(self).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Serialization error: {}", e))
        })
    }

    #[staticmethod]
    pub fn from_json(json: &str) -> PyResult<Self> {
        serde_json::from_str(json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Deserialization error: {}", e))
        })
    }

    fn __str__(&self) -> String {
        format!("ApprovedOrder({}) {}", self.client_order_id, self.instrument_id)
    }
}

/// Snapshot of risk gate state for persistence across restarts.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RiskStateSnapshot {
    #[pyo3(get)]
    pub message_id: String,
    #[pyo3(get)]
    pub kill_switch_state: String,
    #[pyo3(get)]
    pub trading_state: String,
    #[pyo3(get)]
    pub occurred_at: String,
}

#[pymethods]
impl RiskStateSnapshot {
    pub fn to_json(&self) -> PyResult<String> {
        serde_json::to_string(self).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Serialization error: {}", e))
        })
    }

    #[staticmethod]
    pub fn from_json(json: &str) -> PyResult<Self> {
        serde_json::from_str(json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Deserialization error: {}", e))
        })
    }

    fn __str__(&self) -> String {
        format!("RiskStateSnapshot({}, ks={}, ts={})", self.message_id, self.kill_switch_state, self.trading_state)
    }

    fn __repr__(&self) -> String {
        format!("RiskStateSnapshot(id={}, ks={}, ts={}, at={})", self.message_id, self.kill_switch_state, self.trading_state, self.occurred_at)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn intent_with_exits(tp: Option<&str>, trailing: Option<(&str, &str)>) -> TradeIntent {
        let tr = trailing.map(|(a, d)| TrailingConfig {
            activation_distance: a.to_string(),
            trail_distance: d.to_string(),
        });
        TradeIntent::new(
            "strat1".to_string(), "digest1".to_string(), "acc1".to_string(),
            "EURUSD".to_string(), "BUY".to_string(), "10000".to_string(),
            "MARKET".to_string(), "DAY".to_string(), "v1".to_string(),
            "2026-08-07T00:00:00Z".to_string(),
            Some("1.10".to_string()), Some("1.095".to_string()),
            tp.map(|s| s.to_string()), tr, None,
        )
    }

    #[test]
    fn trailing_config_accepts_valid_distances() {
        let tc = TrailingConfig { activation_distance: "0.002".into(), trail_distance: "0.001".into() };
        assert!(tc.validate().is_ok());
    }

    #[test]
    fn trailing_config_rejects_activation_less_than_distance() {
        let tc = TrailingConfig { activation_distance: "0.001".into(), trail_distance: "0.002".into() };
        assert!(tc.validate().is_err());
    }

    #[test]
    fn trade_intent_carries_take_profit_and_trailing() {
        let it = intent_with_exits(Some("1.12"), Some(("0.002", "0.001")));
        assert_eq!(it.take_profit_price.as_deref(), Some("1.12"));
        let tr = it.trailing.unwrap();
        assert_eq!(tr.activation_distance, "0.002");
        assert_eq!(tr.trail_distance, "0.001");
    }

    #[test]
    fn trade_intent_serializes_exit_fields() {
        let it = intent_with_exits(Some("1.12"), Some(("0.002", "0.001")));
        let json = it.to_json().unwrap();
        assert!(json.contains("take_profit_price"));
        assert!(json.contains("trailing"));
        let back: TradeIntent = TradeIntent::from_json(&json).unwrap();
        assert_eq!(back.take_profit_price.as_deref(), Some("1.12"));
        assert!(back.trailing.is_some());
    }

    #[test]
    fn trade_intent_backwards_compatible_without_exits() {
        // Legacy construction (no exit args) still works and round-trips.
        let it = intent_with_exits(None, None);
        let json = it.to_json().unwrap();
        let back: TradeIntent = TradeIntent::from_json(&json).unwrap();
        assert!(back.take_profit_price.is_none());
        assert!(back.trailing.is_none());
        assert!(back.stop_price.is_some());
    }
}
