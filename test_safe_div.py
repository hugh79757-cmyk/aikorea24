import pytest

def safe_div(a, b):
    if b == 0:
        return None
    return a / b


@pytest.mark.parametrize("a,b,expected", [
    (10, 2, 5.0),          # basic positive division
    (9, 3, 3.0),             # exact integer quotient
    (1, 2, 0.5),             # fractional result
    (7, 4, 1.75),            # repeating decimal
    (-10, 2, -5.0),          # negative numerator
    (10, -2, -5.0),          # negative denominator
    (-10, -2, 5.0),          # both negative
    (0, 5, 0.0),             # zero numerator
    (0, 0, None),            # zero by zero -> None
    (5, 0, None),            # divide by zero -> None
    (-5, 0, None),           # negative numerator divided by zero -> None
    (0, -3, 0.0),            # zero numerator with negative denominator
])
def test_safe_div(a, b, expected):
    assert safe_div(a, b) == expected


def test_division_by_zero_returns_none():
    assert safe_div(10, 0) is None


def test_none_check_exact():
    # b == 0 should return None, including 0.0
    assert safe_div(10, 0.0) is None
    assert safe_div(3.5, 0) is None
    assert safe_div(3.5, 0.0) is None
    # 0.0 == 0 is True in Python
    assert safe_div(3.5, 0) is None

def test_large_values():
    assert safe_div(1e308, 2) == 5e307
    assert safe_div(-1e308, 2) == -5e307

def test_float_precision_boundary():
    assert safe_div(0.1, 0.2) == pytest.approx(0.5)
    assert safe_div(1, 3) == pytest.approx(1/3)


# --- negative boundary sweep via parametrize ---
@pytest.mark.parametrize("a,b,expected", [
    (-0.0001, -0.0001, 1.0),
    (float("inf"), 2, float("inf")),
    (-float("inf"), 2, -float("inf")),
    (10, float("inf"), 0.0),
])
def test_edge_values(a, b, expected):
    result = safe_div(a, b)
    if expected is None:
        assert result is None
    else:
        assert result == expected
