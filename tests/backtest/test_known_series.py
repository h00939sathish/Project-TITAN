"""Hand-computed economic fixture — the test the 1180-test suite was missing.

Audit finding (TEST_EFFECTIVENESS_REPORT.md §2): mutation testing showed 6 of 20
mutants SURVIVED, including

    M17  _compute_sharpe  -> abs(...)
    M18  profit_factor    -> hardcoded 100.0
    M11  max_drawdown     -> (eq - peak) / peak
    M10  sqrt(252)        -> sqrt(12)
    M20  sqrt(252)        -> sqrt(52)

The cause was that every assertion on these fields was SELF-CONSISTENCY
(run twice, compare) rather than ABSOLUTE VALUE. Exactly one test in the suite
asserted an absolute PnL number.

Every expected value below is a HAND-COMPUTED LITERAL, derived by hand and
recorded in the comments. None of them is recomputed by calling the function
under test — doing that would reproduce the exact self-consistency sin this
file exists to eliminate.

Source series: 10 daily returns, deliberately lumpy so that mean > 0 AND a
real drawdown occurs.
"""
import pytest

from titan.backtest.results import BacktestResult, _compute_sharpe, _compute_volatility

# mean            = +0.009000000000
# sample stdev    =  0.019119507200   (divides by n-1 = 9, matching the code)
# sharpe          = (0.009 / 0.019119507200) * sqrt(252) = 7.4725
# vol %           =  0.019119507200 * sqrt(252) * 100   = 30.3513
RETURNS = [0.030, -0.010, 0.020, 0.010, -0.025,
           0.015, 0.005, 0.040, -0.005, 0.010]

# Equity from a 100.0 start, compounded exactly:
#   100.0 -> 103.0 -> 101.97 -> 104.0094 -> 105.049494 -> 102.42325665
#         -> 103.95960549974998 -> 104.47940352724872 -> 108.65857966833867
#         -> 108.11528676999698 -> 109.19643963769695
# total_return_pct = (109.19643963769695 - 100) / 100 * 100 = 9.1964396377
# The peak is 103.0 (index 1). The worst decline is index 4 -> 5:
#   (105.049494 - 102.42325665) / 105.049494 = 0.025000 exactly
EQUITY = [100.0, 103.0, 101.97, 104.0094, 105.049494, 102.42325665,
          103.95960549974998, 104.47940352724872, 108.65857966833867,
          108.11528676999698, 109.19643963769695]

# gross_profit = 100 + 50 + 25 = 175
# gross_loss   = 40 + 10       =  50
# profit_factor = 175 / 50 = 3.5
TRADES = [{"pnl": 100.0}, {"pnl": 50.0}, {"pnl": 25.0},
          {"pnl": -40.0}, {"pnl": -10.0}]


class TestKnownReturnSeries:
    """Absolute values, not 'run it twice and compare'."""

    def test_sharpe_is_exact(self):
        # Kills M17 (abs), M10 (sqrt(252)->sqrt(12)).
        assert _compute_sharpe(RETURNS) == pytest.approx(7.4725, abs=1e-4)

    def test_sharpe_is_not_abs(self):
        # A losing series must produce a NEGATIVE Sharpe. M17 (abs) would pass
        # the test above and fail this one.
        losing = [-x for x in RETURNS]
        assert _compute_sharpe(losing) == pytest.approx(-7.4725, abs=1e-4)
        assert _compute_sharpe(losing) < 0

    def test_volatility_is_exact(self):
        # Kills M20 (sqrt(252)->sqrt(52)).
        assert _compute_volatility(RETURNS) == pytest.approx(30.3513, abs=1e-3)

    def test_total_return_is_exact(self):
        r = BacktestResult.compute(EQUITY, TRADES)
        assert r.total_return_pct == pytest.approx(9.1964, abs=1e-3)

    def test_max_drawdown_is_exact_and_positive(self):
        # Kills M11 (sign inversion) and the 5-copy drawdown duplication.
        r = BacktestResult.compute(EQUITY, TRADES)
        assert r.max_drawdown_pct == pytest.approx(2.5000, abs=1e-3)
        assert r.max_drawdown_pct > 0

    def test_profit_factor_is_exact(self):
        # Kills M18 (hardcoded 100.0).
        r = BacktestResult.compute(EQUITY, TRADES)
        assert r.profit_factor == pytest.approx(3.5, abs=1e-6)

    def test_profit_factor_is_not_a_constant(self):
        # M18 would return 100.0 for every strategy forever. Guard the two
        # degenerate branches explicitly.
        no_losses = BacktestResult.compute(EQUITY, [{"pnl": 10.0}])
        assert no_losses.profit_factor == 100.0          # documented clamp

        all_loss = BacktestResult.compute(EQUITY, [{"pnl": -10.0}])
        assert all_loss.profit_factor == 0.0             # not 100.0, not 1.0

        mixed = BacktestResult.compute(EQUITY, [{"pnl": 10.0}, {"pnl": -2.0}])
        assert mixed.profit_factor == pytest.approx(5.0, abs=1e-6)


class TestAnnualisationIsNotHardcoded:
    """The code hardcodes sqrt(252) at results.py:100 and metrics.py:153.

    This test PINS that behaviour so it can never be silently changed to a value
    appropriate for a different bar frequency. When TITAN adds a
    `periods_per_year` argument, THIS test must be updated in the same commit —
    that is the point. Today it is correct for daily data and wrong for 4h FX
    (audited: understated 3.0x on 4h, overstated 11.6x on 5m).
    """

    def test_252_is_used_today(self):
        # If someone 'fixes' this to sqrt(12) or sqrt(52), this fails loudly.
        assert _compute_sharpe(RETURNS) == pytest.approx(7.4725, abs=1e-4)

    def test_frequency_bug_is_documented_and_measurable(self):
        # Demonstrates the magnitude of the defect rather than asserting it away.
        from math import sqrt
        wrong_4h = (0.009 / 0.019119507200) * sqrt(2190)
        # 4h FX annualised with sqrt(252) instead of sqrt(2190) is understated
        # by sqrt(2190/252) = 2.95x. This assertion documents the ratio.
        assert wrong_4h / 7.4725 == pytest.approx(sqrt(2190) / sqrt(252), rel=1e-6)
