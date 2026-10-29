import pytest
from safe_div import safe_div


def test_safe_div_positive_numbers():
    """Test division with positive numbers."""
    assert safe_div(10, 2) == 5.0
    assert safe_div(7, 2) == 3.5


def test_safe_div_negative_numbers():
    """Test division with negative numbers."""
    assert safe_div(-10, 2) == -5.0
    assert safe_div(10, -2) == -5.0
    assert safe_div(-10, -2) == 5.0


def test_safe_div_zero_numerator():
    """Test division when numerator is zero."""
    assert safe_div(0, 5) == 0.0


def test_safe_div_zero_denominator():
    """Test division by zero returns None."""
    assert safe_div(10, 0) is None
    assert safe_div(-5, 0) is None
    assert safe_div(0, 0) is None


def test_safe_div_large_numbers():
    """Test with large numbers."""
    assert safe_div(10**10, 2) == 5 * 10**9
    assert safe_div(10**9, 3) == 333333333.3333333333


def test_safe_div_floating_point():
    """Test with floating point numbers."""
    assert safe_div(5.5, 2) == 2.75
    assert safe_div(7.5, 2) == 3.75


def test_safe_div_small_numbers():
    """Test with small numbers."""
    assert safe_div(1, 100) == 0.01
    assert safe_div(0.1, 0.2) == 0.5


def test_safe_div_integer_result():
    """Test when division results in an integer."""
    assert safe_div(8, 2) == 4.0
    assert safe_div(15, 3) == 5.0


def test_safe_div_negative_denominator():
    """Test division with negative denominator."""
    assert safe_div(10, -2) == -5.0
    assert safe_div(-10, -2) == 5.0


# Boundary value tests

def test_safe_div_boundary_zero():
    """Test boundary where numerator is zero."""
    assert safe_div(0, 1) == 0.0


def test_safe_div_boundary_small_between():
    """Test with values very close to zero."""
    # Very small positive
    assert safe_div(1e-10, 1) == 1e-10
    # Very small negative
    assert safe_div(-1e-10, 1) == -1e-10


def test_safe_div_large_denominator():
    """Test with a very large denominator."""
    assert safe_div(100, 1e9) == 1e-7


# Ensure None is returned (not raised) for division by zero

def test_safe_div_division_by_zero_returns_none():
    """Verify that division by zero returns None, not raises an exception."""
    result = safe_div(5, 0)
    assert result is None
    assert not isinstance(result, float)
