"""Power / underpowered-detection tests.

Audit finding (UNDERENGINEERING_REPORT.md §2): TITAN had three verdicts —
promote, reject, negative_result — and NO WAY TO SAY "I DON'T KNOW".
17 of 21 archived results had SE(SR_ann) >= 0.5, meaning a true Sharpe of 1.0
and a true Sharpe of 0.0 were statistically indistinguishable on the available
data, and every one of them was filed as a rejection.

The primitive is sharp, per Lo (2002), Financial Analysts Journal 58(4):36-52,
DOI 10.2469/faj.v58.n4.2453:

    SE(SR_ann) = sqrt((1 + 0.5*SR^2) / T_years)

The decisive property is that SE >= 1/sqrt(T_years) REGARDLESS of trade count.
This is why TITAN's frozen ">= 60 OOS trades" gate was aimed at the wrong
failure mode: at sigma/mu = 1.5, 9 trades give |t| > 1.96, while the FX
trailing-stop strategies in the archive ran at sigma/mu ~ 16, where no trade
count inside a 12-month window helps.

Every number below is a hand-computed literal, not a call into the function
under test.
"""
import pytest

from titan.research.validator import (
    UNDERPOWERED_SE_THRESHOLD,
    is_underpowered,
    sharpe_standard_error,
)

SQRT = lambda x: x ** 0.5  # noqa: E731


class TestSharpeStandardError:
    def test_matches_hand_computation(self):
        # SR=1.0, T=1.0 -> sqrt(1.5) = 1.224744871
        assert sharpe_standard_error(1.0, 1.0) == pytest.approx(1.2247449, abs=1e-6)
        # SR=0.8, T=1.0 -> sqrt(1 + 0.5*0.64) = sqrt(1.32) = 1.148912529
        assert sharpe_standard_error(0.8, 1.0) == pytest.approx(1.1489125, abs=1e-6)
        # SR=0.5, T=8.0 -> sqrt(1.125/8) = sqrt(0.140625) = 0.375
        assert sharpe_standard_error(0.5, 8.0) == pytest.approx(0.375, abs=1e-6)

    def test_bound_is_independent_of_trade_count(self):
        """The whole point. More trades do NOT shrink SE below 1/sqrt(T)."""
        for years, floor in ((0.41, 1.5617), (1.0, 1.0), (2.0, 0.7071)):
            # Any SR, including 0, has SE strictly above the floor (except at SR=0).
            assert sharpe_standard_error(0.0, years) == pytest.approx(floor, rel=1e-3)
            # A large SR only makes it worse, never better.
            assert sharpe_standard_error(5.0, years) > sharpe_standard_error(0.0, years)

    def test_rejects_non_positive_window(self):
        with pytest.raises(ValueError):
            sharpe_standard_error(1.0, 0.0)
        with pytest.raises(ValueError):
            sharpe_standard_error(1.0, -1.0)


class TestArchivedWindowsAreUnderpowered:
    """Regression-pins the audit's central arithmetic.

    If someone shortens the observation window in a way that makes these
    non-underpowered, the test fails. That is intended: it forces the
    shortening to be noticed rather than absorbed.
    """

    @pytest.mark.parametrize("name, sr, years", [
        # EXP-00031 canonical FX, 644 4h bars = 0.41y
        ("EXP-00031 EUR", 0.03, 0.41),
        ("EXP-00031 GBP", 0.66, 0.41),
        # EXP-00027 16-cell 4h screen, 644 bars = 0.41y
        ("EXP-00027", 0.66, 0.41),
        # EXP-00025 F1 pooled, 1 year
        ("EXP-00025 F1", 0.80, 1.0),
        # equities, 2-year OOS window
        ("EQ-007 PEAD", 1.2485, 2.0),
        ("EQ-001 momentum", 0.700, 2.0),
        # FX-001, best-powered FX study, 2 years
        ("FX-001", 0.676, 2.0),
    ])
    def test_underpowered(self, name, sr, years):
        under, se = is_underpowered(sr, years)
        assert under is True, f"{name}: SE={se:.3f} should be > {UNDERPOWERED_SE_THRESHOLD}"
        assert se > 0.5

    def test_exp00023_carry_is_also_underpowered(self):
        # 8 years, t=1.14 -> SR 0.403. SE 0.368, which CLEARS the 0.5 gate,
        # but the point is different: its 95% CI is [-0.32, +1.12], which
        # contains the literature carry Sharpe of 0.5-1.0. Power, not
        # underpoweredness, is what rejects it.
        under, se = is_underpowered(0.403, 8.0)
        assert under is False
        assert se == pytest.approx(0.3676, abs=1e-3)
        ci = (0.403 - 1.96 * se, 0.403 + 1.96 * se)
        assert ci[0] < 0.5 < ci[1], "carry rejection rests on power, not on a null"


class TestThresholdBehaves:
    def test_a_long_window_can_clear_it(self):
        # 25 years, SR 0.5 -> sqrt(1.125/25) = 0.2121, clears 0.5.
        under, se = is_underpowered(0.5, 25.0)
        assert under is False
        assert se == pytest.approx(0.21213, abs=1e-4)

    def test_returns_both_flag_and_magnitude(self):
        result = is_underpowered(1.0, 1.0)
        assert isinstance(result, tuple) and len(result) == 2
        assert result[0] is True
        assert result[1] > 0
