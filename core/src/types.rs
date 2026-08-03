use std::fmt;
use std::str::FromStr;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

/// Order side.
#[pyclass(eq, eq_int, from_py_object)]
#[derive(Clone, Copy, Debug, PartialEq, Serialize, Deserialize)]
pub enum Side {
    Buy,
    Sell,
}

#[pymethods]
impl Side {
    fn __str__(&self) -> String {
        format!("{:?}", self)
    }

    fn __repr(&self) -> String {
        format!("Side.{:?}", self)
    }
}

/// A fixed-decimal monetary value with an explicit currency.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Money {
    #[serde(with = "rust_decimal::serde::str")]
    pub(crate) amount: Decimal,
    #[pyo3(get)]
    pub currency: String,
}

impl fmt::Display for Money {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} {}", self.amount, self.currency)
    }
}

#[pymethods]
impl Money {
    #[new]
    pub fn new(amount: &str, currency: &str) -> Self {
        Self {
            amount: Decimal::from_str(amount).unwrap_or(Decimal::ZERO),
            currency: currency.to_string(),
        }
    }

    #[getter]
    fn get_amount(&self) -> String {
        self.amount.to_string()
    }

    fn __str__(&self) -> String {
        self.to_string()
    }

    fn __repr(&self) -> String {
        format!("Money('{}', '{}')", self.amount, self.currency)
    }
}

/// A fixed-decimal quantity.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Quantity {
    #[serde(with = "rust_decimal::serde::str")]
    pub(crate) value: Decimal,
}

#[pymethods]
impl Quantity {
    #[new]
    pub fn new(value: &str) -> Self {
        Self {
            value: Decimal::from_str(value).unwrap_or(Decimal::ZERO),
        }
    }

    #[getter]
    fn get_value(&self) -> String {
        self.value.to_string()
    }

    fn __str__(&self) -> String {
        self.value.to_string()
    }

    fn __repr(&self) -> String {
        format!("Quantity('{}')", self.value)
    }
}

/// A price value.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Price {
    #[serde(with = "rust_decimal::serde::str")]
    pub(crate) value: Decimal,
    #[pyo3(get)]
    pub precision: u32,
}

#[pymethods]
impl Price {
    #[new]
    pub fn new(value: &str, precision: u32) -> Self {
        Self {
            value: Decimal::from_str(value).unwrap_or(Decimal::ZERO),
            precision,
        }
    }

    #[getter]
    fn get_value(&self) -> String {
        self.value.to_string()
    }

    fn __str__(&self) -> String {
        self.value.to_string()
    }

    fn __repr(&self) -> String {
        format!("Price('{}', {})", self.value, self.precision)
    }
}

/// A canonical instrument identifier.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct InstrumentId {
    #[pyo3(get)]
    pub symbol: String,
    #[pyo3(get)]
    pub venue: String,
}

#[pymethods]
impl InstrumentId {
    #[new]
    pub fn new(symbol: &str, venue: &str) -> Self {
        Self {
            symbol: symbol.to_string(),
            venue: venue.to_string(),
        }
    }

    fn __str__(&self) -> String {
        format!("{}.{}", self.symbol, self.venue)
    }

    fn __repr(&self) -> String {
        format!("InstrumentId('{}', '{}')", self.symbol, self.venue)
    }
}

impl fmt::Display for InstrumentId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}.{}", self.symbol, self.venue)
    }
}

/// Asset class of an instrument.
#[pyclass(eq, eq_int, from_py_object)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Serialize, Deserialize)]
pub enum ContractType {
    #[default]
    Stock,
    Option,
    Future,
    Crypto,
    Forex,
    Commodity,
}

#[pymethods]
impl ContractType {
    fn __str__(&self) -> String {
        format!("{:?}", self)
    }

    fn __repr(&self) -> String {
        format!("ContractType.{:?}", self)
    }
}

/// Full instrument definition with order-validation metadata.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Instrument {
    #[pyo3(get)]
    pub instrument_id: InstrumentId,
    #[serde(with = "rust_decimal::serde::str")]
    pub(crate) tick_size: Decimal,
    #[pyo3(get)]
    pub step_size: u64,
    #[serde(with = "rust_decimal::serde::str")]
    pub(crate) multiplier: Decimal,
    #[pyo3(get)]
    pub contract_type: ContractType,
    #[pyo3(get)]
    pub currency: String,
    #[pyo3(get)]
    pub precision: u32,
}

#[pymethods]
impl Instrument {
    #[new]
    pub fn new(
        instrument_id: InstrumentId,
        tick_size: &str,
        step_size: u64,
        multiplier: &str,
        contract_type: ContractType,
        currency: &str,
        precision: u32,
    ) -> PyResult<Self> {
        let ts = Decimal::from_str(tick_size)
            .map_err(|e| PyValueError::new_err(format!("Invalid tick_size '{}': {}", tick_size, e)))?;
        let mult = Decimal::from_str(multiplier)
            .map_err(|e| PyValueError::new_err(format!("Invalid multiplier '{}': {}", multiplier, e)))?;
        if ts <= Decimal::ZERO {
            return Err(PyValueError::new_err("tick_size must be positive"));
        }
        if step_size == 0 {
            return Err(PyValueError::new_err("step_size must be positive"));
        }
        if mult <= Decimal::ZERO {
            return Err(PyValueError::new_err("multiplier must be positive"));
        }
        Ok(Self {
            instrument_id,
            tick_size: ts,
            step_size,
            multiplier: mult,
            contract_type,
            currency: currency.to_string(),
            precision,
        })
    }

    #[getter]
    fn get_tick_size(&self) -> String { self.tick_size.to_string() }

    #[getter]
    fn get_multiplier(&self) -> String { self.multiplier.to_string() }

    /// Check that a price is aligned to the instrument's tick size.
    #[allow(clippy::manual_is_multiple_of)]
    pub fn is_price_aligned(&self, price: &str) -> bool {
        let p = match Decimal::from_str(price) {
            Ok(v) => v,
            Err(_) => return false,
        };
        p % self.tick_size == Decimal::ZERO
    }

    /// Check that a quantity is aligned to the instrument's step size (lot size).
    #[allow(clippy::manual_is_multiple_of)]
    pub fn is_quantity_aligned(&self, quantity: u64) -> bool {
        quantity % self.step_size == 0
    }

    /// Compute the notional value of an order: quantity * price * multiplier.
    pub fn compute_notional(&self, quantity: u64, price: &str) -> PyResult<String> {
        let p = Decimal::from_str(price)
            .map_err(|e| PyValueError::new_err(format!("Invalid price '{}': {}", price, e)))?;
        let q = Decimal::from(quantity);
        let notional = q * p * self.multiplier;
        Ok(notional.to_string())
    }

    /// Validate an order against instrument metadata. Returns an error message string
    /// on failure, or None on success.
    pub fn validate_order(&self, side: &str, quantity: u64, price: &str) -> Option<String> {
        let side_upper = side.to_uppercase();
        if side_upper != "BUY" && side_upper != "SELL" {
            return Some(format!("Invalid side '{}'", side));
        }
        if !self.is_quantity_aligned(quantity) {
            return Some(format!(
                "Quantity {} is not aligned to step size {}",
                quantity, self.step_size
            ));
        }
        if !self.is_price_aligned(price) {
            return Some(format!(
                "Price {} is not aligned to tick size {}",
                price, self.tick_size
            ));
        }
        None
    }

    fn __str__(&self) -> String {
        format!("{} ({:?})", self.instrument_id, self.contract_type)
    }

    fn __repr(&self) -> String {
        format!(
            "Instrument({}, tick={}, step={}, mult={}, type={:?}, cur={}, prec={})",
            self.instrument_id, self.tick_size, self.step_size, self.multiplier,
            self.contract_type, self.currency, self.precision
        )
    }
}