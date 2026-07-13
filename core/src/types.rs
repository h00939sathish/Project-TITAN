use std::fmt;
use pyo3::prelude::*;
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

    fn __repr__(&self) -> String {
        format!("Side.{:?}", self)
    }
}

/// A fixed-decimal monetary value with an explicit currency.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Money {
    #[pyo3(get)]
    pub amount: String,
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
            amount: amount.to_string(),
            currency: currency.to_string(),
        }
    }

    fn __str__(&self) -> String {
        self.to_string()
    }

    fn __repr__(&self) -> String {
        format!("Money('{}', '{}')", self.amount, self.currency)
    }
}

/// A fixed-decimal quantity.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Quantity {
    #[pyo3(get)]
    pub value: String,
}

#[pymethods]
impl Quantity {
    #[new]
    pub fn new(value: &str) -> Self {
        Self {
            value: value.to_string(),
        }
    }

    fn __str__(&self) -> String {
        self.value.clone()
    }

    fn __repr__(&self) -> String {
        format!("Quantity('{}')", self.value)
    }
}

/// A price value.
#[pyclass(from_py_object)]
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Price {
    #[pyo3(get)]
    pub value: String,
    #[pyo3(get)]
    pub precision: u32,
}

#[pymethods]
impl Price {
    #[new]
    pub fn new(value: &str, precision: u32) -> Self {
        Self {
            value: value.to_string(),
            precision,
        }
    }

    fn __str__(&self) -> String {
        self.value.clone()
    }

    fn __repr__(&self) -> String {
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

    fn __repr__(&self) -> String {
        format!("InstrumentId('{}', '{}')", self.symbol, self.venue)
    }
}
