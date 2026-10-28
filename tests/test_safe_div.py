"""pytest tests for the ``safe_div`` helper.

Covers normal inputs, division by zero, negative values, and boundary/edge
values. The implementation under test lives in ``scripts/safe_div.py`` and is
importable because ``pytest.ini`` puts ``scripts`` on ``sys.path``.
"""

import math

import pytest

from safe_div import safe_div


# ---------------------------------------------------------------------------
# Normal inputs
# ---------------------------------------------------------------------------


class TestSafeDivNormal:
    def test_positive_integers(self):
        assert safe_div(10, 2) == 5.0

    def test_positive_floats(self):
        assert safe_div(7.5, 2.5) == 3.0

    def test_exact_integer_quotient_is_float(self):
        assert safe_div(9, 3) == 3.0

    def test_fractional_result(self):
        assert safe_div(1, 2) == 0.5

    def test_repeating_decimal(self):
        assert safe_div(1, 3) == pytest.approx(1 / 3)

    def test_zero_numerator(self):
        assert safe_div(0, 5) == 0.0

    def test_zero_numerator_float(self):
        assert safe_div(0.0, 5) == 0.0

    def test_division_by_one(self):
        assert safe_div(42, 1) == 42.0

    def test_large_quotient(self):
        assert safe_div(1_000_000, 1_000) == 1_000.0

    def test_negative_zero_numerator_keeps_sign(self):
        # IEEE 754: -0.0 / positive == -0.0
        assert math.copysign(1.0, safe_div(-0.0, 5)) == -1.0

    def test_positive_zero_divided_by_negative(self):
        assert math.copysign(1.0, safe_div(0.0, -5)) == -1.0

    def test_decimal_inputs(self):
        assert safe_div(0.1, 0.2) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Division by zero
# ---------------------------------------------------------------------------


class TestSafeDivByZero:
    @pytest.mark.parametrize("b", [0, 0.0, -0.0, False])
    def test_returns_none_for_zero_divisor(self, b):
        assert safe_div(10, b) is None

    def test_zero_divisor_with_zero_numerator(self):
        assert safe_div(0, 0) is None

    def test_zero_divisor_negative_numerator(self):
        assert safe_div(-5, 0) is None

    def test_zero_divisor_float_numerator(self):
        assert safe_div(3.5, 0.0) is None

    def test_zero_divisor_does_not_raise(self):
        # Must return None, never raise ZeroDivisionError.
        try:
            result = safe_div(7, 0)
        except ZeroDivisionError:  # pragma: no cover - documents the contract
            pytest.fail("safe_div raised ZeroDivisionError instead of returning None")
        assert result is None

    def test_false_divisor_is_treated_as_zero(self):
        # False == 0 in Python, so it must be treated as a zero divisor.
        assert safe_div(5, False) is None


# ---------------------------------------------------------------------------
# Negative values
# ---------------------------------------------------------------------------


class TestSafeDivNegatives:
    def test_negative_numerator(self):
        assert safe_div(-6, 2) == -3.0

    def test_negative_denominator(self):
        assert safe_div(6, -2) == -3.0

    def test_both_negative(self):
        assert safe_div(-6, -2) == 3.0

    def test_negative_fraction(self):
        assert safe_div(-1, 3) == pytest.approx(-1 / 3)

    def test_negative_large(self):
        assert safe_div(-1e308, 2) == -5e307


# ---------------------------------------------------------------------------
# Boundary / edge values
# ---------------------------------------------------------------------------


class TestSafeDivEdgeCases:
    def test_large_numerator(self):
        result = safe_div(1e308, 2)
        assert result == 5e307

    def test_very_small_divisor_finite_or_inf(self):
        result = safe_div(1, 1e-308)
        assert (math.isfinite(result) and result > 0) or result == float("inf")

    def test_divisor_infinity(self):
        assert safe_div(10, float("inf")) == 0.0

    def test_numerator_infinity(self):
        assert safe_div(float("inf"), 2) == float("inf")

    def test_negative_infinity_numerator(self):
        assert safe_div(-float("inf"), 2) == -float("inf")

    def test_inf_divided_by_inf_is_nan(self):
        assert math.isnan(safe_div(float("inf"), float("inf")))

    def test_returns_float_for_int_inputs(self):
        assert isinstance(safe_div(4, 2), float)

    def test_smallest_subnormal_denominator(self):
        # 1 / smallest subnormal overflows to +inf.
        assert safe_div(1, 5e-324) == float("inf")

    def test_huge_int_quotient_raises_overflow(self):
        # Python raises OverflowError when an int/int quotient cannot fit
        # in a float. safe_div does not guard this, so it propagates.
        with pytest.raises(OverflowError):
            safe_div(10 ** 400, 7)

    def test_nan_numerator_propagates_nan(self):
        assert math.isnan(safe_div(float("nan"), 5))

    def test_nan_divisor(self):
        # nan == 0 is False, so division proceeds and yields nan.
        assert math.isnan(safe_div(5, float("nan")))

    def test_none_numerator_raises_typeerror(self):
        with pytest.raises(TypeError):
            safe_div(None, 5)

    def test_none_denominator_raises_typeerror(self):
        with pytest.raises(TypeError):
            safe_div(5, None)

    @pytest.mark.parametrize(
        "a,b,expected",
        [
            (10, 2, 5.0),
            (-10, 2, -5.0),
            (10, -2, -5.0),
            (-10, -2, 5.0),
            (0, 5, 0.0),
            (0, -5, 0.0),
            (1, 1, 1.0),
        ],
    )
    def test_parametrized_sign_matrix(self, a, b, expected):
        assert safe_div(a, b) == expected