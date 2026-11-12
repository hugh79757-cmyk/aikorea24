import pytest
import sys
import os

# scripts 디렉토리를 모듈 검색 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from safe_div import safe_div


@pytest.mark.parametrize(
    "a, b, expected",
    [
        # Normal division cases
        (10, 2, 5.0),
        (7, 2, 3.5),
        (-10, 2, -5.0),
        (10, -2, -5.0),
        (-10, -2, 5.0),
        (0, 5, 0.0),
        (0, -3, 0.0),
        # Float inputs
        (1.5, 0.5, 3.0),
        (-3.5, 2.0, -1.75),
        # Large numbers
        (1000000, 1000, 1000.0),
        # Small numbers
        (1, 100000, 1e-05),
    ],
)
def test_safe_div_normal(a, b, expected):
    """Test safe_div with normal inputs."""
    result = safe_div(a, b)
    assert result == expected


def test_safe_div_by_zero():
    """Test safe_div when divisor is zero."""
    result = safe_div(10, 0)
    assert result is None


def test_safe_div_zero_dividend():
    """Test safe_div when dividend is zero."""
    result = safe_div(0, 5)
    assert result == 0.0


def test_safe_div_both_zero():
    """Test safe_div when both a and b are zero."""
    result = safe_div(0, 0)
    assert result is None