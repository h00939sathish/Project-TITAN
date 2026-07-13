use crate::messages::TradeIntent;
use crate::types::Money;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

// ─── TradingState ────────────────────────────────────────────────────────────────

#[pyclass(eq, eq_int, from_py_object)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Serialize, Deserialize)]
pub enum TradingState {
    #[default]
    Active,
    Reducing,
    Halted,
}

#[pymethods]
impl TradingState {
    fn __str__(&self) -> String {
        format!("{:?}", self)
    }

    fn __repr__(&self) -> String {
        format!("TradingState.{:?}", self)
    }

    fn is_active(&self) -> bool {
        self.accepts_intents()
    }
}

impl TradingState {
    pub fn transition(&mut self, target: TradingState) -> Result<(), String> {
        let ok = matches!(
            (*self, target),
            (Self::Active, Self::Reducing)
                | (Self::Active, Self::Halted)
                | (Self::Reducing, Self::Halted)
                | (Self::Halted, Self::Active)
                | (Self::Halted, Self::Reducing)
        );
        if ok {
            *self = target;
            Ok(())
        } else {
            Err(format!("Cannot transition from {:?} to {:?}", self, target))
        }
    }

    pub fn accepts_intents(&self) -> bool {
        matches!(self, Self::Active)
    }
}

// ─── KillSwitchState ─────────────────────────────────────────────────────────────

#[pyclass(eq, eq_int, from_py_object)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Serialize, Deserialize)]
pub enum KillSwitchState {
    #[default]
    Armed,
    Triggered,
    Releasing,
    Released,
}

#[pymethods]
impl KillSwitchState {
    fn __str__(&self) -> String {
        format!("{:?}", self)
    }

    fn __repr__(&self) -> String {
        format!("KillSwitchState.{:?}", self)
    }

    fn is_triggered(&self) -> bool {
        matches!(self, Self::Triggered)
    }

    fn blocks_routing(&self) -> bool {
        matches!(self, Self::Triggered | Self::Releasing)
    }
}

impl KillSwitchState {
    pub fn transition(&mut self, target: KillSwitchState) -> Result<(), String> {
        let ok = matches!(
            (*self, target),
            (Self::Armed, Self::Triggered)
                | (Self::Triggered, Self::Releasing)
                | (Self::Releasing, Self::Released)
                | (Self::Releasing, Self::Triggered)
                | (Self::Released, Self::Armed)
        );
        if ok {
            *self = target;
            Ok(())
        } else {
            Err(format!("Cannot transition from {:?} to {:?}", self, target))
        }
    }
}

// ─── RiskConfig ──────────────────────────────────────────────────────────────────

#[pyclass(from_py_object)]
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct RiskConfig {
    #[pyo3(get, set)]
    pub instrument_eligibility: Vec<String>,
    #[pyo3(get, set)]
    pub max_order_notional: Money,
    #[pyo3(get, set)]
    pub max_order_quantity: u64,
    #[pyo3(get, set)]
    pub max_position_size: u64,
    #[pyo3(get, set)]
    pub max_gross_exposure: Money,
    #[pyo3(get, set)]
    pub max_drawdown_fraction: f64,
    #[pyo3(get, set)]
    pub max_daily_loss: Money,
    #[pyo3(get, set)]
    pub data_freshness_threshold_ms: u64,
}

#[pymethods]
impl RiskConfig {
    #[new]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        instrument_eligibility: Vec<String>,
        max_order_notional: Money,
        max_order_quantity: u64,
        max_position_size: u64,
        max_gross_exposure: Money,
        max_drawdown_fraction: f64,
        max_daily_loss: Money,
        data_freshness_threshold_ms: u64,
    ) -> Self {
        Self {
            instrument_eligibility,
            max_order_notional,
            max_order_quantity,
            max_position_size,
            max_gross_exposure,
            max_drawdown_fraction,
            max_daily_loss,
            data_freshness_threshold_ms,
        }
    }
}

impl Default for RiskConfig {
    fn default() -> Self {
        Self {
            instrument_eligibility: Vec::new(),
            max_order_notional: Money::new("1000000", "USD"),
            max_order_quantity: 10_000,
            max_position_size: 50_000,
            max_gross_exposure: Money::new("10000000", "USD"),
            max_drawdown_fraction: 0.10,
            max_daily_loss: Money::new("50000", "USD"),
            data_freshness_threshold_ms: 5_000,
        }
    }
}

// ─── RiskReasonCode ──────────────────────────────────────────────────────────────

#[pyclass(eq, eq_int, from_py_object)]
#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub enum RiskReasonCode {
    NotRoutable,
    InstrumentNotEligible,
    DataStale,
    OrderNotionalExceeded,
    OrderQuantityExceeded,
    PositionLimitExceeded,
    GrossExposureExceeded,
    DrawdownExceeded,
    DailyLossExceeded,
    TradingHalted,
    KillSwitchTriggered,
    InternalError,
}

#[pymethods]
impl RiskReasonCode {
    fn __str__(&self) -> String {
        format!("{:?}", self)
    }

    fn __repr__(&self) -> String {
        format!("RiskReasonCode.{:?}", self)
    }
}

// ─── RiskVerdict ──────────────────────────────────────────────────────────────────

#[pyclass(from_py_object)]
#[derive(Clone, Debug)]
pub struct RiskVerdict {
    #[pyo3(get)]
    pub accepted: bool,
    #[pyo3(get)]
    pub reason: Option<RiskReasonCode>,
    #[pyo3(get)]
    pub reason_detail: String,
}

// ─── RiskGate ─────────────────────────────────────────────────────────────────────

#[pyclass(from_py_object)]
#[derive(Clone, Debug)]
pub struct RiskGate {
    #[pyo3(get, set)]
    pub config: RiskConfig,
    #[pyo3(get)]
    pub trading_state: TradingState,
    #[pyo3(get)]
    pub kill_switch: KillSwitchState,
}

#[pymethods]
impl RiskGate {
    #[new]
    pub fn new(config: RiskConfig) -> Self {
        Self {
            config,
            trading_state: TradingState::Active,
            kill_switch: KillSwitchState::Armed,
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub fn evaluate(
        &self,
        intent: &TradeIntent,
        current_position_size: Option<u64>,
        current_gross_exposure: Option<&Money>,
        current_drawdown: Option<f64>,
        current_daily_loss: Option<&Money>,
    ) -> RiskVerdict {
        // a. Kill switch check
        if self.kill_switch.blocks_routing() {
            return RiskVerdict {
                accepted: false,
                reason: Some(RiskReasonCode::KillSwitchTriggered),
                reason_detail: "Kill switch is blocking routing".to_string(),
            };
        }

        // b. Trading state check
        if !self.trading_state.accepts_intents() {
            return RiskVerdict {
                accepted: false,
                reason: Some(RiskReasonCode::TradingHalted),
                reason_detail: "Trading is not accepting intents".to_string(),
            };
        }

        // c. Instrument eligibility
        if !self.config.instrument_eligibility.is_empty()
            && !self.config.instrument_eligibility.contains(&intent.instrument_id)
        {
            return RiskVerdict {
                accepted: false,
                reason: Some(RiskReasonCode::InstrumentNotEligible),
                reason_detail: format!("Instrument {} is not eligible", intent.instrument_id),
            };
        }

        // d. Order limits — notional
        let qty: i64 = intent.quantity.parse().unwrap_or(0);
        let px: i64 = intent
            .price
            .as_ref()
            .and_then(|p| p.parse().ok())
            .unwrap_or(0);
        let notional = qty * px;
        let max_notional: i64 = self.config.max_order_notional.amount.parse().unwrap_or(0);
        if notional > max_notional {
            return RiskVerdict {
                accepted: false,
                reason: Some(RiskReasonCode::OrderNotionalExceeded),
                reason_detail: format!("Order notional {} exceeds max {}", notional, max_notional),
            };
        }

        // e. Order limits — quantity
        let qi: u64 = intent.quantity.parse().unwrap_or(0);
        if qi > self.config.max_order_quantity {
            return RiskVerdict {
                accepted: false,
                reason: Some(RiskReasonCode::OrderQuantityExceeded),
                reason_detail: format!("Order quantity {} exceeds max {}", qi, self.config.max_order_quantity),
            };
        }

        // f. Position/exposure limits
        if let Some(pos) = current_position_size
            && pos > self.config.max_position_size
        {
            return RiskVerdict {
                accepted: false,
                reason: Some(RiskReasonCode::PositionLimitExceeded),
                reason_detail: format!("Position size {} exceeds max {}", pos, self.config.max_position_size),
            };
        }

        // g. Gross exposure check
        if let Some(exp) = current_gross_exposure {
            let exp_amt: i64 = exp.amount.parse().unwrap_or(0);
            let max_exp: i64 = self.config.max_gross_exposure.amount.parse().unwrap_or(0);
            if exp_amt > max_exp {
                return RiskVerdict {
                    accepted: false,
                    reason: Some(RiskReasonCode::GrossExposureExceeded),
                    reason_detail: format!("Gross exposure {} exceeds max {}", exp_amt, max_exp),
                };
            }
        }

        // h. Drawdown check
        if let Some(dd) = current_drawdown
            && dd > self.config.max_drawdown_fraction
        {
            return RiskVerdict {
                accepted: false,
                reason: Some(RiskReasonCode::DrawdownExceeded),
                reason_detail: format!("Drawdown {} exceeds max {}", dd, self.config.max_drawdown_fraction),
            };
        }

        // i. Daily loss check
        if let Some(dl) = current_daily_loss {
            let dl_amt: i64 = dl.amount.parse().unwrap_or(0);
            let max_dl: i64 = self.config.max_daily_loss.amount.parse().unwrap_or(0);
            if dl_amt > max_dl {
                return RiskVerdict {
                    accepted: false,
                    reason: Some(RiskReasonCode::DailyLossExceeded),
                    reason_detail: format!("Daily loss {} exceeds max {}", dl_amt, max_dl),
                };
            }
        }

        RiskVerdict {
            accepted: true,
            reason: None,
            reason_detail: String::new(),
        }
    }

    pub fn set_trading_state(&mut self, state: TradingState) -> PyResult<()> {
        self.trading_state
            .transition(state)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    pub fn trigger_kill_switch(&mut self) -> PyResult<()> {
        self.kill_switch
            .transition(KillSwitchState::Triggered)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    pub fn release_initiated(&mut self) -> PyResult<()> {
        self.kill_switch
            .transition(KillSwitchState::Releasing)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }

    pub fn release_completed(&mut self) -> PyResult<()> {
        self.kill_switch
            .transition(KillSwitchState::Released)
            .map_err(pyo3::exceptions::PyValueError::new_err)
    }
}

// ─── Tests ───────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── TradingState ──

    #[test]
    fn test_trading_state_default_is_active() {
        let state = TradingState::default();
        assert_eq!(state, TradingState::Active);
    }

    #[test]
    fn test_trading_state_active_accepts_intents() {
        assert!(TradingState::Active.accepts_intents());
        assert!(!TradingState::Reducing.accepts_intents());
        assert!(!TradingState::Halted.accepts_intents());
    }

    #[test]
    fn test_trading_state_valid_transitions() {
        let mut s = TradingState::Active;
        assert!(s.transition(TradingState::Reducing).is_ok());
        assert_eq!(s, TradingState::Reducing);

        assert!(s.transition(TradingState::Halted).is_ok());
        assert_eq!(s, TradingState::Halted);

        assert!(s.transition(TradingState::Active).is_ok());
        assert_eq!(s, TradingState::Active);

        assert!(s.transition(TradingState::Halted).is_ok());
        assert_eq!(s, TradingState::Halted);

        assert!(s.transition(TradingState::Reducing).is_ok());
        assert_eq!(s, TradingState::Reducing);
    }

    #[test]
    fn test_trading_state_illegal_transitions() {
        let mut s = TradingState::Reducing;
        assert!(s.transition(TradingState::Active).is_err());

        let mut s = TradingState::Active;
        assert!(s.transition(TradingState::Active).is_err());

        let mut s = TradingState::Reducing;
        assert!(s.transition(TradingState::Reducing).is_err());

        let mut s = TradingState::Halted;
        assert!(s.transition(TradingState::Halted).is_err());
    }

    #[test]
    fn test_trading_state_is_active() {
        assert!(TradingState::Active.is_active());
        assert!(!TradingState::Reducing.is_active());
        assert!(!TradingState::Halted.is_active());
    }

    // ── KillSwitchState ──

    #[test]
    fn test_kill_switch_default_is_armed() {
        let ks = KillSwitchState::default();
        assert_eq!(ks, KillSwitchState::Armed);
    }

    #[test]
    fn test_kill_switch_is_triggered() {
        assert!(KillSwitchState::Triggered.is_triggered());
        assert!(!KillSwitchState::Armed.is_triggered());
        assert!(!KillSwitchState::Releasing.is_triggered());
        assert!(!KillSwitchState::Released.is_triggered());
    }

    #[test]
    fn test_kill_switch_blocks_routing() {
        assert!(KillSwitchState::Triggered.blocks_routing());
        assert!(KillSwitchState::Releasing.blocks_routing());
        assert!(!KillSwitchState::Armed.blocks_routing());
        assert!(!KillSwitchState::Released.blocks_routing());
    }

    #[test]
    fn test_kill_switch_state_machine() {
        let mut ks = KillSwitchState::Armed;
        assert!(ks.transition(KillSwitchState::Triggered).is_ok());
        assert_eq!(ks, KillSwitchState::Triggered);

        assert!(ks.transition(KillSwitchState::Releasing).is_ok());
        assert_eq!(ks, KillSwitchState::Releasing);

        assert!(ks.transition(KillSwitchState::Released).is_ok());
        assert_eq!(ks, KillSwitchState::Released);

        assert!(ks.transition(KillSwitchState::Armed).is_ok());
        assert_eq!(ks, KillSwitchState::Armed);
    }

    #[test]
    fn test_kill_switch_release_re_trigger() {
        let mut ks = KillSwitchState::Triggered;
        assert!(ks.transition(KillSwitchState::Releasing).is_ok());
        assert!(ks.transition(KillSwitchState::Triggered).is_ok());
        assert_eq!(ks, KillSwitchState::Triggered);
    }

    #[test]
    fn test_kill_switch_no_auto_reset() {
        let mut ks = KillSwitchState::Triggered;
        assert!(ks.transition(KillSwitchState::Armed).is_err());
        assert_eq!(ks, KillSwitchState::Triggered);
    }

    #[test]
    fn test_kill_switch_illegal_self_transitions() {
        for s in [
            KillSwitchState::Armed,
            KillSwitchState::Triggered,
            KillSwitchState::Releasing,
            KillSwitchState::Released,
        ] {
            let mut copy = s;
            assert!(copy.transition(s).is_err());
        }
    }

    // ── RiskConfig ──

    #[test]
    fn test_risk_config_defaults() {
        let cfg = RiskConfig::default();
        assert!(cfg.instrument_eligibility.is_empty());
        assert_eq!(cfg.max_order_notional.to_string(), "1000000 USD");
        assert_eq!(cfg.max_order_quantity, 10_000);
        assert_eq!(cfg.max_position_size, 50_000);
        assert_eq!(cfg.max_gross_exposure.to_string(), "10000000 USD");
        assert!((cfg.max_drawdown_fraction - 0.10).abs() < f64::EPSILON);
        assert_eq!(cfg.max_daily_loss.to_string(), "50000 USD");
        assert_eq!(cfg.data_freshness_threshold_ms, 5_000);
    }

    #[test]
    fn test_risk_config_custom() {
        let cfg = RiskConfig::new(
            vec!["AAPL".to_string()],
            Money::new("500000", "USD"),
            5000,
            25000,
            Money::new("5000000", "USD"),
            0.05,
            Money::new("25000", "USD"),
            2000,
        );
        assert_eq!(cfg.instrument_eligibility, vec!["AAPL"]);
        assert_eq!(cfg.max_order_notional.to_string(), "500000 USD");
        assert_eq!(cfg.max_order_quantity, 5000);
    }

    // ── RiskReasonCode ──

    #[test]
    fn test_risk_reason_code_variants() {
        let codes = vec![
            RiskReasonCode::NotRoutable,
            RiskReasonCode::InstrumentNotEligible,
            RiskReasonCode::DataStale,
            RiskReasonCode::OrderNotionalExceeded,
            RiskReasonCode::OrderQuantityExceeded,
            RiskReasonCode::PositionLimitExceeded,
            RiskReasonCode::GrossExposureExceeded,
            RiskReasonCode::DrawdownExceeded,
            RiskReasonCode::DailyLossExceeded,
            RiskReasonCode::TradingHalted,
            RiskReasonCode::KillSwitchTriggered,
            RiskReasonCode::InternalError,
        ];
        assert_eq!(codes.len(), 12);
    }

    // ── RiskGate ──

    fn make_intent(instrument_id: &str, quantity: &str, price: Option<&str>) -> TradeIntent {
        TradeIntent::new(
            "strat1".to_string(),
            "digest1".to_string(),
            "acc1".to_string(),
            instrument_id.to_string(),
            "BUY".to_string(),
            quantity.to_string(),
            "LIMIT".to_string(),
            "DAY".to_string(),
            "v1".to_string(),
            price.map(|p| p.to_string()),
            None,
        )
    }

    #[test]
    fn test_gate_accepts_valid_intent() {
        let config = RiskConfig::default();
        let gate = RiskGate::new(config);
        let intent = make_intent("AAPL", "10", Some("50000"));
        let verdict = gate.evaluate(&intent, None, None, None, None);
        assert!(verdict.accepted);
        assert!(verdict.reason.is_none());
        assert!(verdict.reason_detail.is_empty());
    }

    #[test]
    fn test_gate_rejects_when_kill_switch_triggered() {
        let config = RiskConfig::default();
        let mut gate = RiskGate::new(config);
        gate.trigger_kill_switch().unwrap();
        let intent = make_intent("AAPL", "10", Some("50000"));
        let verdict = gate.evaluate(&intent, None, None, None, None);
        assert!(!verdict.accepted);
        assert_eq!(verdict.reason, Some(RiskReasonCode::KillSwitchTriggered));
    }

    #[test]
    fn test_gate_rejects_when_trading_halted() {
        let config = RiskConfig::default();
        let mut gate = RiskGate::new(config);
        gate.set_trading_state(TradingState::Halted).unwrap();
        let intent = make_intent("AAPL", "10", Some("50000"));
        let verdict = gate.evaluate(&intent, None, None, None, None);
        assert!(!verdict.accepted);
        assert_eq!(verdict.reason, Some(RiskReasonCode::TradingHalted));
    }

    #[test]
    fn test_gate_rejects_instrument_not_eligible() {
        let config = RiskConfig::new(
            vec!["MSFT".to_string(), "GOOGL".to_string()],
            Money::new("1000000", "USD"),
            10_000,
            50_000,
            Money::new("10000000", "USD"),
            0.10,
            Money::new("50000", "USD"),
            5_000,
        );
        let gate = RiskGate::new(config);
        let intent = make_intent("AAPL", "10", Some("50000"));
        let verdict = gate.evaluate(&intent, None, None, None, None);
        assert!(!verdict.accepted);
        assert_eq!(verdict.reason, Some(RiskReasonCode::InstrumentNotEligible));
    }

    #[test]
    fn test_gate_rejects_notional_exceeded() {
        let config = RiskConfig::new(
            vec![],
            Money::new("50000", "USD"),
            10_000,
            50_000,
            Money::new("10000000", "USD"),
            0.10,
            Money::new("50000", "USD"),
            5_000,
        );
        let gate = RiskGate::new(config);
        let intent = make_intent("AAPL", "1000", Some("100"));
        let verdict = gate.evaluate(&intent, None, None, None, None);
        assert!(!verdict.accepted);
        assert_eq!(verdict.reason, Some(RiskReasonCode::OrderNotionalExceeded));
    }

    #[test]
    fn test_gate_rejects_quantity_exceeded() {
        let config = RiskConfig::new(
            vec![],
            Money::new("1000000", "USD"),
            100,
            50_000,
            Money::new("10000000", "USD"),
            0.10,
            Money::new("50000", "USD"),
            5_000,
        );
        let gate = RiskGate::new(config);
        let intent = make_intent("AAPL", "200", Some("100"));
        let verdict = gate.evaluate(&intent, None, None, None, None);
        assert!(!verdict.accepted);
        assert_eq!(verdict.reason, Some(RiskReasonCode::OrderQuantityExceeded));
    }

    #[test]
    fn test_gate_rejects_position_size_exceeded() {
        let config = RiskConfig::new(
            vec![],
            Money::new("1000000", "USD"),
            10_000,
            100,
            Money::new("10000000", "USD"),
            0.10,
            Money::new("50000", "USD"),
            5_000,
        );
        let gate = RiskGate::new(config);
        let intent = make_intent("AAPL", "10", Some("100"));
        let verdict = gate.evaluate(&intent, Some(150), None, None, None);
        assert!(!verdict.accepted);
        assert_eq!(verdict.reason, Some(RiskReasonCode::PositionLimitExceeded));
    }

    #[test]
    fn test_gate_rejects_gross_exposure_exceeded() {
        let config = RiskConfig::new(
            vec![],
            Money::new("1000000", "USD"),
            10_000,
            50_000,
            Money::new("1000000", "USD"),
            0.10,
            Money::new("50000", "USD"),
            5_000,
        );
        let gate = RiskGate::new(config);
        let intent = make_intent("AAPL", "10", Some("100"));
        let exp = Money::new("2000000", "USD");
        let verdict = gate.evaluate(&intent, None, Some(&exp), None, None);
        assert!(!verdict.accepted);
        assert_eq!(verdict.reason, Some(RiskReasonCode::GrossExposureExceeded));
    }

    #[test]
    fn test_gate_rejects_drawdown_exceeded() {
        let config = RiskConfig::new(
            vec![],
            Money::new("1000000", "USD"),
            10_000,
            50_000,
            Money::new("10000000", "USD"),
            0.05,
            Money::new("50000", "USD"),
            5_000,
        );
        let gate = RiskGate::new(config);
        let intent = make_intent("AAPL", "10", Some("100"));
        let verdict = gate.evaluate(&intent, None, None, Some(0.10), None);
        assert!(!verdict.accepted);
        assert_eq!(verdict.reason, Some(RiskReasonCode::DrawdownExceeded));
    }

    #[test]
    fn test_gate_rejects_daily_loss_exceeded() {
        let config = RiskConfig::new(
            vec![],
            Money::new("1000000", "USD"),
            10_000,
            50_000,
            Money::new("10000000", "USD"),
            0.10,
            Money::new("50000", "USD"),
            5_000,
        );
        let gate = RiskGate::new(config);
        let intent = make_intent("AAPL", "10", Some("100"));
        let dl = Money::new("75000", "USD");
        let verdict = gate.evaluate(&intent, None, None, None, Some(&dl));
        assert!(!verdict.accepted);
        assert_eq!(verdict.reason, Some(RiskReasonCode::DailyLossExceeded));
    }

    #[test]
    fn test_gate_triggers_kill_switch() {
        let config = RiskConfig::default();
        let mut gate = RiskGate::new(config);
        assert_eq!(gate.kill_switch, KillSwitchState::Armed);
        assert!(gate.trigger_kill_switch().is_ok());
        assert_eq!(gate.kill_switch, KillSwitchState::Triggered);
    }

    #[test]
    fn test_gate_sets_trading_state() {
        let config = RiskConfig::default();
        let mut gate = RiskGate::new(config);
        assert_eq!(gate.trading_state, TradingState::Active);

        assert!(gate.set_trading_state(TradingState::Reducing).is_ok());
        assert_eq!(gate.trading_state, TradingState::Reducing);

        assert!(gate.set_trading_state(TradingState::Halted).is_ok());
        assert_eq!(gate.trading_state, TradingState::Halted);

        assert!(gate.set_trading_state(TradingState::Active).is_ok());
        assert_eq!(gate.trading_state, TradingState::Active);
    }

    #[test]
    fn test_gate_kill_switch_lifecycle() {
        let config = RiskConfig::default();
        let mut gate = RiskGate::new(config);
        assert_eq!(gate.kill_switch, KillSwitchState::Armed);

        assert!(gate.trigger_kill_switch().is_ok());
        assert_eq!(gate.kill_switch, KillSwitchState::Triggered);

        assert!(gate.release_initiated().is_ok());
        assert_eq!(gate.kill_switch, KillSwitchState::Releasing);

        assert!(gate.release_completed().is_ok());
        assert_eq!(gate.kill_switch, KillSwitchState::Released);
    }
}
