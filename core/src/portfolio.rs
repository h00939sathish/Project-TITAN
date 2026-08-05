use std::collections::HashMap;
use std::str::FromStr;
use chrono::Utc;
use pyo3::prelude::*;
use rust_decimal::Decimal;
use rust_decimal::prelude::ToPrimitive;
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
    peak_total_value: Decimal,
    daily_realized_loss: Decimal,
    loss_date: String,
    market_prices: HashMap<String, String>,
}

#[pymethods]
impl PortfolioEngine {
    #[new]
    pub fn new(base_currency: &str, initial_cash: &Money) -> Self {
        let initial_amount = initial_cash.amount;
        Self {
            positions: HashMap::new(),
            cash_balance: initial_cash.clone(),
            base_currency: base_currency.to_string(),
            realized_pnl: Money::new("0", base_currency),
            peak_total_value: initial_amount,
            daily_realized_loss: Decimal::ZERO,
            loss_date: String::new(),
            market_prices: HashMap::new(),
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

        let qty = Decimal::from(quantity);
        let notional = match price.amount.checked_mul(qty) {
            Some(n) => n,
            None => {
                return Err(PyErr::new::<pyo3::exceptions::PyOverflowError, _>(
                    "position notional overflow",
                ));
            }
        };

        // Update cash: buys decrease, sells increase
        let new_cash = if is_buy {
            self.cash_balance.amount.checked_sub(notional)
        } else {
            self.cash_balance.amount.checked_add(notional)
        };
        let new_cash = match new_cash {
            Some(v) => v,
            None => return Err(PyErr::new::<pyo3::exceptions::PyOverflowError, _>(
                "cash balance overflow",
            )),
        };
        self.cash_balance.amount = new_cash;

        let position = self.positions.get_mut(instrument_id);

        if let Some(pos) = position {
            // Existing position — apply lifecycle logic
            match (pos.side, is_buy) {
                (PositionSide::Long, true) => {
                    // Adding to long: weighted average cost basis
                    let old_total = match pos.cost_basis.amount.checked_mul(Decimal::from(pos.quantity)) {
                        Some(v) => v,
                        None => {
                            return Err(PyErr::new::<pyo3::exceptions::PyOverflowError, _>(
                                "cost basis overflow",
                            ));
                        }
                    };
                    let new_total = old_total + notional;
                    let new_qty = pos.quantity + quantity;
                    let new_cost = new_total / Decimal::from(new_qty);
                    pos.quantity = new_qty;
                    pos.cost_basis.amount = new_cost;
                }
                (PositionSide::Long, false) => {
                    // Selling from long
                    let pnl_per_unit = price.amount - pos.cost_basis.amount;
                    let pnl_qty = Decimal::from(quantity.min(pos.quantity));
                    let pnl = pnl_per_unit * pnl_qty;
                    if quantity < pos.quantity {
                        pos.quantity -= quantity;
                    } else if quantity == pos.quantity {
                        pos.side = PositionSide::Flat;
                        pos.quantity = 0;
                        pos.cost_basis.amount = Decimal::ZERO;
                    } else {
                        let excess = quantity - pos.quantity;
                        pos.side = PositionSide::Short;
                        pos.quantity = excess;
                        pos.cost_basis.amount = price.amount;
                    }
                    self.add_pnl(pnl);
                }
                (PositionSide::Short, false) => {
                    // Adding to short: weighted average cost basis
                    let old_total = match pos.cost_basis.amount.checked_mul(Decimal::from(pos.quantity)) {
                        Some(v) => v,
                        None => {
                            return Err(PyErr::new::<pyo3::exceptions::PyOverflowError, _>(
                                "cost basis overflow",
                            ));
                        }
                    };
                    let new_total = old_total + notional;
                    let new_qty = pos.quantity + quantity;
                    let new_cost = new_total / Decimal::from(new_qty);
                    pos.quantity = new_qty;
                    pos.cost_basis.amount = new_cost;
                }
                (PositionSide::Short, true) => {
                    // Buying to cover short
                    let pnl_per_unit = pos.cost_basis.amount - price.amount;
                    let pnl_qty = Decimal::from(quantity.min(pos.quantity));
                    let pnl = pnl_per_unit * pnl_qty;
                    if quantity < pos.quantity {
                        pos.quantity -= quantity;
                    } else if quantity == pos.quantity {
                        pos.side = PositionSide::Flat;
                        pos.quantity = 0;
                        pos.cost_basis.amount = Decimal::ZERO;
                    } else {
                        let excess = quantity - pos.quantity;
                        pos.side = PositionSide::Long;
                        pos.quantity = excess;
                        pos.cost_basis.amount = price.amount;
                    }
                    self.add_pnl(pnl);
                }
                (PositionSide::Flat, _) => {
                    pos.side = if is_buy { PositionSide::Long } else { PositionSide::Short };
                    pos.quantity = quantity;
                    pos.cost_basis.amount = price.amount;
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
                cost_basis: Money { amount: price.amount, currency: self.base_currency.clone() },
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

    pub fn set_realized_pnl(&mut self, pnl: &Money) {
        self.realized_pnl.amount = pnl.amount;
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

        let pnl_per_unit = match pos.side {
            PositionSide::Long => current_price.amount - pos.cost_basis.amount,
            PositionSide::Short => pos.cost_basis.amount - current_price.amount,
            PositionSide::Flat => Decimal::ZERO,
        };
        let total_pnl = pnl_per_unit * Decimal::from(pos.quantity);
        Ok(Money { amount: total_pnl, currency: self.base_currency.clone() })
    }

    /// Sum of absolute position values using market price (M2M) with cost-basis fallback.
    pub fn total_gross_exposure(&self) -> Money {
        let mut total = Decimal::ZERO;
        for pos in self.positions.values() {
            let price = self.market_prices
                .get(&pos.instrument_id)
                .and_then(|p| Decimal::from_str(p).ok())
                .unwrap_or(pos.cost_basis.amount);
            total += price * Decimal::from(pos.quantity);
        }
        Money { amount: total, currency: self.base_currency.clone() }
    }

    /// Build a portfolio snapshot of the current state.
    pub fn get_snapshot(&self) -> PortfolioSnapshot {
        let dd = self.drawdown_fraction();
        PortfolioSnapshot {
            gross_exposure: self.total_gross_exposure(),
            drawdown_fraction: dd,
            daily_realized_loss: Money { amount: self.daily_realized_loss, currency: self.base_currency.clone() },
            position_size: self.positions.len() as u64,
        }
    }

    pub fn drawdown_fraction(&self) -> f64 {
        let total = self.total_value();
        if self.peak_total_value <= Decimal::ZERO || total <= Decimal::ZERO {
            return 0.0;
        }
        let dd = (self.peak_total_value - total) / self.peak_total_value;
        dd.to_f64().unwrap_or(0.0).max(0.0)
    }

    pub fn get_daily_loss(&self) -> Money {
        Money { amount: self.daily_realized_loss, currency: self.base_currency.clone() }
    }

    /// Store a market price and recalculate peak total value for drawdown tracking.
    pub fn update_market_price(&mut self, instrument_id: &str, price: &str) -> PyResult<()> {
        // Validate price is parseable
        let _ = Decimal::from_str(price).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("Invalid market price '{}': {}", price, e))
        })?;
        self.market_prices.insert(instrument_id.to_string(), price.to_string());
        let total = self.total_value();
        if total > self.peak_total_value {
            self.peak_total_value = total;
        }
        Ok(())
    }

    /// Bulk update market prices.
    pub fn update_market_prices(&mut self, prices: Vec<(String, String)>) -> PyResult<()> {
        for (instrument_id, price) in prices {
            self.update_market_price(&instrument_id, &price)?;
        }
        Ok(())
    }
}

// ─── Private helpers ─────────────────────────────────────────────────────────────

impl PortfolioEngine {
    fn add_pnl(&mut self, amount: Decimal) {
        self.realized_pnl.amount += amount;
        // Track peak total value for drawdown
        let total = self.total_value();
        if total > self.peak_total_value {
            self.peak_total_value = total;
        }
        // Track daily realized loss
        if amount < Decimal::ZERO {
            let today = Utc::now().format("%Y-%m-%d").to_string();
            if self.loss_date != today {
                self.loss_date = today;
                self.daily_realized_loss = Decimal::ZERO;
            }
            self.daily_realized_loss += amount;
        }
    }

    fn total_value(&self) -> Decimal {
        let mut total = self.cash_balance.amount;
        for pos in self.positions.values() {
            let price = self.market_prices
                .get(&pos.instrument_id)
                .and_then(|p| Decimal::from_str(p).ok())
                .unwrap_or(pos.cost_basis.amount);
            match pos.side {
                PositionSide::Long => total += price * Decimal::from(pos.quantity),
                PositionSide::Short => total -= price * Decimal::from(pos.quantity),
                PositionSide::Flat => {}
            }
        }
        total
    }
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
        // Weighted avg: (50*100 + 60*50) / 150 = 8000/150 = 53.333...
        assert_eq!(pos.cost_basis, Money::new("53.333333333333333333333333333", "USD"));
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
        // No realized PnL yet, so no drawdown
        assert!((snap.drawdown_fraction - 0.0).abs() < f64::EPSILON);
        assert_eq!(snap.daily_realized_loss, Money::new("0", "USD"));
    }

    #[test]
    fn test_drawdown_after_losing_trade() {
        let mut e = engine();
        apply(&mut e, "AAPL", "buy", 100, 100);
        // Sell at a loss: 100 -> 80
        apply(&mut e, "AAPL", "sell", 100, 80);
        let dd = e.drawdown_fraction();
        assert!(dd > 0.0);
        // Loss = (80 - 100) * 100 = -2000 on 100000 equity = 2% drawdown
        assert!((dd - 0.02).abs() < 1e-10 || (dd - 0.02).abs() < 0.001);
    }

    #[test]
    fn test_daily_loss_tracked() {
        let mut e = engine();
        apply(&mut e, "AAPL", "buy", 100, 100);
        apply(&mut e, "AAPL", "sell", 100, 80);
        let dl = e.get_daily_loss();
        assert!(dl.amount < Decimal::ZERO);
    }

    #[test]
    fn test_zero_drawdown_on_no_trades() {
        let e = engine();
        let dd = e.drawdown_fraction();
        assert!((dd - 0.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_peak_equity_tracking() {
        let mut e = engine();
        apply(&mut e, "AAPL", "buy", 100, 50);
        apply(&mut e, "AAPL", "sell", 100, 60);  // profit
        apply(&mut e, "MSFT", "buy", 200, 30);
        apply(&mut e, "MSFT", "sell", 200, 20);  // loss
        let dd = e.drawdown_fraction();
        assert!(dd > 0.0, "Drawdown should be positive after a loss");
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
