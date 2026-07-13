use std::collections::HashMap;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use crate::types::Money;

// ─── PositionSide ────────────────────────────────────────────────────────────────

#[pyclass(eq, eq_int, from_py_object)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Serialize, Deserialize)]
pub enum PositionSide {
    #[default]
    Flat,
    Long,
    Short,
}

#[pymethods]
impl PositionSide {
    fn __str__(&self) -> String {
        format!("{:?}", self)
    }

    fn __repr__(&self) -> String {
        format!("PositionSide.{:?}", self)
    }
}

// ─── Position ────────────────────────────────────────────────────────────────────

#[pyclass(from_py_object)]
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Position {
    #[pyo3(get)]
    pub instrument_id: String,
    #[pyo3(get)]
    pub side: PositionSide,
    #[pyo3(get)]
    pub quantity: u64,
    #[pyo3(get)]
    pub cost_basis: Money,
}

// ─── PortfolioSnapshot ────────────────────────────────────────────────────────────

#[pyclass(from_py_object)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PortfolioSnapshot {
    #[pyo3(get, set)]
    pub gross_exposure: Money,
    #[pyo3(get, set)]
    pub drawdown_fraction: f64,
    #[pyo3(get, set)]
    pub daily_realized_loss: Money,
    #[pyo3(get, set)]
    pub position_size: u64,
}

// ─── PortfolioEngine ──────────────────────────────────────────────────────────────

#[pyclass(from_py_object)]
#[derive(Clone, Debug)]
pub struct PortfolioEngine {
    #[pyo3(get)]
    pub positions: HashMap<String, Position>,
    #[pyo3(get)]
    pub cash_balance: Money,
    #[pyo3(get)]
    pub base_currency: String,
    #[pyo3(get)]
    pub realized_pnl: Money,
}

#[pymethods]
impl PortfolioEngine {
    #[new]
    pub fn new(base_currency: &str, initial_cash: &Money) -> Self {
        Self {
            positions: HashMap::new(),
            cash_balance: initial_cash.clone(),
            base_currency: base_currency.to_string(),
            realized_pnl: Money::new("0", base_currency),
        }
    }

    /// Apply a fill to the portfolio, updating position and cash.
    ///
    /// `side` must be "buy" or "sell" (case-insensitive).
    /// `quantity` is the number of contracts/shares.
    /// `price` is the fill price per unit.
    pub fn apply_fill(
        &mut self,
        instrument_id: &str,
        side: &str,
        quantity: u64,
        price: &Money,
    ) -> PyResult<()> {
        let side_lower = side.to_lowercase();
        let is_buy = side_lower == "buy";
        if !is_buy && side_lower != "sell" {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "side must be 'buy' or 'sell'",
            ));
        }

        if quantity == 0 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "quantity must be non-zero",
            ));
        }

        let price_per_unit = parse_amount(price);
        let notional = price_per_unit * quantity as i64;

        // Update cash: buys decrease, sells increase
        let cash_amount = parse_amount(&self.cash_balance);
        let new_cash = if is_buy {
            cash_amount.checked_sub(notional)
        } else {
            cash_amount.checked_add(notional)
        };
        let new_cash = match new_cash {
            Some(v) => v,
            None => return Err(PyErr::new::<pyo3::exceptions::PyOverflowError, _>(
                "cash balance overflow",
            )),
        };
        self.cash_balance = Money::new(&new_cash.to_string(), &self.base_currency);

        let position = self.positions.get_mut(instrument_id);

        if let Some(pos) = position {
            // Existing position — apply lifecycle logic
            match (pos.side, is_buy) {
                (PositionSide::Long, true) => {
                    // Adding to long: weighted average cost basis
                    let old_cost = parse_amount(&pos.cost_basis);
                    let total = old_cost * pos.quantity as i64 + price_per_unit * quantity as i64;
                    let new_qty = pos.quantity + quantity;
                    let new_cost = total / new_qty as i64;
                    pos.quantity = new_qty;
                    pos.cost_basis = Money::new(&new_cost.to_string(), &self.base_currency);
                }
                (PositionSide::Long, false) => {
                    // Selling from long
                    let old_cost = parse_amount(&pos.cost_basis);
                    let pnl_qty = quantity.min(pos.quantity);
                    let pnl = (price_per_unit - old_cost) * pnl_qty as i64;
                    if quantity < pos.quantity {
                        pos.quantity -= quantity;
                    } else if quantity == pos.quantity {
                        pos.side = PositionSide::Flat;
                        pos.quantity = 0;
                        pos.cost_basis = Money::new("0", &self.base_currency);
                    } else {
                        let excess = quantity - pos.quantity;
                        pos.side = PositionSide::Short;
                        pos.quantity = excess;
                        pos.cost_basis = Money::new(&price_per_unit.to_string(), &self.base_currency);
                    }
                    self.add_pnl(pnl);
                }
                (PositionSide::Short, false) => {
                    // Adding to short: weighted average cost basis
                    let old_cost = parse_amount(&pos.cost_basis);
                    let total = old_cost * pos.quantity as i64 + price_per_unit * quantity as i64;
                    let new_qty = pos.quantity + quantity;
                    let new_cost = total / new_qty as i64;
                    pos.quantity = new_qty;
                    pos.cost_basis = Money::new(&new_cost.to_string(), &self.base_currency);
                }
                (PositionSide::Short, true) => {
                    // Buying to cover short
                    let old_cost = parse_amount(&pos.cost_basis);
                    let pnl_qty = quantity.min(pos.quantity);
                    let pnl = (old_cost - price_per_unit) * pnl_qty as i64;
                    if quantity < pos.quantity {
                        pos.quantity -= quantity;
                    } else if quantity == pos.quantity {
                        pos.side = PositionSide::Flat;
                        pos.quantity = 0;
                        pos.cost_basis = Money::new("0", &self.base_currency);
                    } else {
                        let excess = quantity - pos.quantity;
                        pos.side = PositionSide::Long;
                        pos.quantity = excess;
                        pos.cost_basis = Money::new(&price_per_unit.to_string(), &self.base_currency);
                    }
                    self.add_pnl(pnl);
                }
                (PositionSide::Flat, _) => {
                    pos.side = if is_buy { PositionSide::Long } else { PositionSide::Short };
                    pos.quantity = quantity;
                    pos.cost_basis = Money::new(&price_per_unit.to_string(), &self.base_currency);
                }
            }
        } else {
            // No existing position — create a new one
            let side_enum = if is_buy {
                PositionSide::Long
            } else {
                PositionSide::Short
            };
            let pos = Position {
                instrument_id: instrument_id.to_string(),
                side: side_enum,
                quantity,
                cost_basis: Money::new(&price_per_unit.to_string(), &self.base_currency),
            };
            self.positions.insert(instrument_id.to_string(), pos);
        }

        Ok(())
    }

    /// Get the position for an instrument, or None if not held.
    pub fn get_position(&self, instrument_id: &str) -> Option<Position> {
        self.positions.get(instrument_id).cloned()
    }

    pub fn get_cash_balance(&self) -> Money {
        self.cash_balance.clone()
    }

    pub fn get_realized_pnl(&self) -> Money {
        self.realized_pnl.clone()
    }

    /// Compute unrealized PnL for a given instrument at `current_price`.
    /// Returns 0 if the position is Flat.
    pub fn get_unrealized_pnl(
        &self,
        instrument_id: &str,
        current_price: &Money,
    ) -> PyResult<Money> {
        let pos = self.positions.get(instrument_id).ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyKeyError, _>(
                format!("No position for instrument '{}'", instrument_id),
            )
        })?;

        let current = parse_amount(current_price);
        let cost = parse_amount(&pos.cost_basis);
        let pnl_per_unit = match pos.side {
            PositionSide::Long => current - cost,
            PositionSide::Short => cost - current,
            PositionSide::Flat => 0,
        };
        let total_pnl = pnl_per_unit * pos.quantity as i64;
        Ok(Money::new(&total_pnl.to_string(), &self.base_currency))
    }

    /// Sum of absolute position values using cost basis as proxy price.
    pub fn total_gross_exposure(&self) -> Money {
        let mut total: i64 = 0;
        for pos in self.positions.values() {
            let cost = parse_amount(&pos.cost_basis);
            total += cost * pos.quantity as i64;
        }
        Money::new(&total.to_string(), &self.base_currency)
    }

    /// Build a portfolio snapshot of the current state.
    pub fn get_snapshot(&self) -> PortfolioSnapshot {
        PortfolioSnapshot {
            gross_exposure: self.total_gross_exposure(),
            drawdown_fraction: 0.0,
            daily_realized_loss: Money::new("0", &self.base_currency),
            position_size: self.positions.len() as u64,
        }
    }
}

// ─── Private helpers ─────────────────────────────────────────────────────────────

impl PortfolioEngine {
    fn add_pnl(&mut self, amount: i64) {
        let current = parse_amount(&self.realized_pnl);
        let new_pnl = current + amount;
        self.realized_pnl = Money::new(&new_pnl.to_string(), &self.base_currency);
    }
}

fn parse_amount(m: &Money) -> i64 {
    m.amount.parse::<i64>().expect("Invalid money amount")
}

// ─── Tests ───────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn engine() -> PortfolioEngine {
        PortfolioEngine::new("USD", &Money::new("100000", "USD"))
    }

    fn apply(engine: &mut PortfolioEngine, instrument: &str, side: &str, qty: u64, price: i64) {
        engine
            .apply_fill(instrument, side, qty, &Money::new(&price.to_string(), "USD"))
            .unwrap();
    }

    #[test]
    fn test_buy_open_long() {
        let mut e = engine();
        apply(&mut e, "AAPL", "buy", 100, 50);
        let pos = e.get_position("AAPL").unwrap();
        assert_eq!(pos.side, PositionSide::Long);
        assert_eq!(pos.quantity, 100);
        assert_eq!(pos.cost_basis, Money::new("50", "USD"));
        assert_eq!(e.get_cash_balance(), Money::new("95000", "USD"));
    }

    #[test]
    fn test_sell_open_short() {
        let mut e = engine();
        apply(&mut e, "AAPL", "sell", 100, 50);
        let pos = e.get_position("AAPL").unwrap();
        assert_eq!(pos.side, PositionSide::Short);
        assert_eq!(pos.quantity, 100);
        assert_eq!(pos.cost_basis, Money::new("50", "USD"));
        assert_eq!(e.get_cash_balance(), Money::new("105000", "USD"));
    }

    #[test]
    fn test_buy_add_to_long() {
        let mut e = engine();
        apply(&mut e, "AAPL", "buy", 100, 50);
        apply(&mut e, "AAPL", "buy", 50, 60);
        let pos = e.get_position("AAPL").unwrap();
        assert_eq!(pos.side, PositionSide::Long);
        assert_eq!(pos.quantity, 150);
        // Weighted avg: (50*100 + 60*50) / 150 = 8000/150 = 53
        assert_eq!(pos.cost_basis, Money::new("53", "USD"));
        assert_eq!(e.get_cash_balance(), Money::new("92000", "USD"));
    }

    #[test]
    fn test_sell_reduce_long_to_flat() {
        let mut e = engine();
        apply(&mut e, "AAPL", "buy", 100, 50);
        apply(&mut e, "AAPL", "sell", 100, 60);
        let pos = e.get_position("AAPL").unwrap();
        assert_eq!(pos.side, PositionSide::Flat);
        assert_eq!(pos.quantity, 0);
        assert_eq!(e.get_cash_balance(), Money::new("101000", "USD"));
        assert_eq!(e.get_realized_pnl(), Money::new("1000", "USD"));
    }

    #[test]
    fn test_sell_reduce_long_to_short() {
        let mut e = engine();
        apply(&mut e, "AAPL", "buy", 100, 50);
        apply(&mut e, "AAPL", "sell", 150, 60);
        let pos = e.get_position("AAPL").unwrap();
        assert_eq!(pos.side, PositionSide::Short);
        assert_eq!(pos.quantity, 50);
        assert_eq!(pos.cost_basis, Money::new("60", "USD"));
        assert_eq!(e.get_cash_balance(), Money::new("104000", "USD"));
        assert_eq!(e.get_realized_pnl(), Money::new("1000", "USD"));
    }

    #[test]
    fn test_buy_reduce_short_to_flat() {
        let mut e = engine();
        apply(&mut e, "AAPL", "sell", 100, 50);
        apply(&mut e, "AAPL", "buy", 100, 40);
        let pos = e.get_position("AAPL").unwrap();
        assert_eq!(pos.side, PositionSide::Flat);
        assert_eq!(pos.quantity, 0);
        assert_eq!(e.get_cash_balance(), Money::new("101000", "USD"));
        assert_eq!(e.get_realized_pnl(), Money::new("1000", "USD"));
    }

    #[test]
    fn test_buy_reduce_short_to_long() {
        let mut e = engine();
        apply(&mut e, "AAPL", "sell", 100, 50);
        apply(&mut e, "AAPL", "buy", 150, 40);
        let pos = e.get_position("AAPL").unwrap();
        assert_eq!(pos.side, PositionSide::Long);
        assert_eq!(pos.quantity, 50);
        assert_eq!(pos.cost_basis, Money::new("40", "USD"));
        assert_eq!(e.get_cash_balance(), Money::new("99000", "USD"));
        assert_eq!(e.get_realized_pnl(), Money::new("1000", "USD"));
    }

    #[test]
    fn test_cash_balance_updates() {
        let mut e = engine();
        assert_eq!(e.get_cash_balance(), Money::new("100000", "USD"));

        apply(&mut e, "AAPL", "buy", 100, 50);
        assert_eq!(e.get_cash_balance(), Money::new("95000", "USD"));

        apply(&mut e, "AAPL", "sell", 100, 60);
        assert_eq!(e.get_cash_balance(), Money::new("101000", "USD"));
    }

    #[test]
    fn test_realized_pnl() {
        let mut e = engine();
        apply(&mut e, "AAPL", "buy", 100, 100);
        apply(&mut e, "AAPL", "sell", 100, 110);
        assert_eq!(e.get_realized_pnl(), Money::new("1000", "USD"));
    }

    #[test]
    fn test_gross_exposure() {
        let mut e = engine();
        apply(&mut e, "AAPL", "buy", 100, 50);
        apply(&mut e, "GOOG", "buy", 200, 30);
        assert_eq!(e.total_gross_exposure(), Money::new("11000", "USD"));
    }

    #[test]
    fn test_get_position_not_found() {
        let e = engine();
        assert!(e.get_position("NONEXISTENT").is_none());
    }

    #[test]
    fn test_get_snapshot() {
        let mut e = engine();
        apply(&mut e, "AAPL", "buy", 100, 50);
        let snap = e.get_snapshot();
        assert_eq!(snap.gross_exposure, Money::new("5000", "USD"));
        assert!((snap.drawdown_fraction - 0.0).abs() < f64::EPSILON);
        assert_eq!(snap.daily_realized_loss, Money::new("0", "USD"));
    }

    #[test]
    fn test_unrealized_pnl_long() {
        let mut e = engine();
        apply(&mut e, "AAPL", "buy", 100, 50);
        let upnl = e.get_unrealized_pnl("AAPL", &Money::new("60", "USD")).unwrap();
        // (60 - 50) * 100 = 1000
        assert_eq!(upnl, Money::new("1000", "USD"));
    }

    #[test]
    fn test_unrealized_pnl_short() {
        let mut e = engine();
        apply(&mut e, "AAPL", "sell", 100, 50);
        let upnl = e.get_unrealized_pnl("AAPL", &Money::new("40", "USD")).unwrap();
        // (50 - 40) * 100 = 1000
        assert_eq!(upnl, Money::new("1000", "USD"));
    }

    #[test]
    fn test_invalid_side_returns_error() {
        let mut e = engine();
        let result = e.apply_fill("AAPL", "invalid", 100, &Money::new("50", "USD"));
        assert!(result.is_err());
    }

    #[test]
    fn test_zero_quantity_returns_error() {
        let mut e = engine();
        let result = e.apply_fill("AAPL", "buy", 0, &Money::new("50", "USD"));
        assert!(result.is_err());
    }

    #[test]
    fn test_unrealized_pnl_no_position_returns_error() {
        let e = engine();
        let result = e.get_unrealized_pnl("NONEXISTENT", &Money::new("50", "USD"));
        assert!(result.is_err());
    }

    #[test]
    fn test_multiple_instruments_tracked_independently() {
        let mut e = engine();
        apply(&mut e, "AAPL", "buy", 100, 50);
        apply(&mut e, "GOOG", "sell", 50, 80);

        let aapl = e.get_position("AAPL").unwrap();
        assert_eq!(aapl.side, PositionSide::Long);
        assert_eq!(aapl.quantity, 100);

        let goog = e.get_position("GOOG").unwrap();
        assert_eq!(goog.side, PositionSide::Short);
        assert_eq!(goog.quantity, 50);
    }
}
