"""safe_div 단위 테스트.

b == 0 이면 None을 반환하고, 그 외에는 a / b를 반환한다.
(제공된 구현을 그대로 사용한다.)
"""

import math

import pytest


def safe_div(a, b):
    """b가 0이면 None, 그 외에는 a / b를 반환한다."""
    if b == 0:
        return None
    return a / b


# ── 정상 입력 ─────────────────────────────────────────────

@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (10, 2, 5.0),          # 양의 정수 / 양의 정수
        (9, 3, 3.0),           # 정확한 몫
        (7, 2, 3.5),            # 소수 결과
        (6.0, 2, 3.0),          # float / int 혼합
        (1, 2, 0.5),            # 작은 몫
        (0, 5, 0.0),            # 0 나누기 (분자 0)
        (10, 1, 10.0),          # 분모 1
    ],
)
def test_정상_입력에서_올바른_값을_반환한다(a, b, expected):
    assert safe_div(a, b) == expected


def test_나누어떨어지지_않는_결과는_근사값으로_검증한다():
    assert safe_div(1, 3) == pytest.approx(1 / 3)
    assert safe_div(0.1, 0.2) == pytest.approx(0.5)


# ── 0으로 나누기 ──────────────────────────────────────────

@pytest.mark.parametrize("a", [10, 0, -10, 12345, 3.5])
def test_0으로_나누면_None을_반환한다(a):
    assert safe_div(a, 0) is None


@pytest.mark.parametrize("b", [0, 0.0, -0.0])
def test_0계열_분모는_None을_반환한다(b):
    assert safe_div(10, b) is None
    assert safe_div(3.5, b) is None


def test_0_0으로_나누는_경우에도_None을_반환한다():
    assert safe_div(0, 0) is None
    assert safe_div(0.0, 0.0) is None
    assert safe_div(-0.0, -0.0) is None


# ── 음수 입력 ─────────────────────────────────────────────

@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        (-10, 2, -5.0),        # a 음수
        (10, -2, -5.0),         # b 음수
        (-10, -2, 5.0),         # 둘 다 음수
        (10, -1, -10.0),        # b = -1
        (-6, 3, -2.0),          # a 음수
    ],
)
def test_음수_입력에서_부호가_올바르다(a, b, expected):
    assert safe_div(a, b) == expected


# ── 경계값 ────────────────────────────────────────────────

def test_매우_큰_값과_작은_값():
    assert safe_div(10**18, 3) == 10**18 / 3
    assert safe_div(1e308, 2) == 5e307
    assert safe_div(-1e308, 2) == -5e307


def test_무한대_입력():
    assert safe_div(float("inf"), 2) == float("inf")
    assert safe_div(-float("inf"), 2) == -float("inf")
    assert safe_div(10, float("inf")) == 0.0


def test_inf_inf는_NaN을_반환한다():
    assert math.isnan(safe_div(float("inf"), float("inf")))


def test_0으로_나눈_결과가_무한대가_되는_경계():
    # 1 / 가장 작은 서브노멀 = inf (예외 없이 산술 결과로 무한대)
    assert safe_div(1, 5e-324) == float("inf")


def test_큰_정수_나눗셈은_OverflowError를_발생시킨다():
    # 정수/정수 true division이 float으로 변환되지 않을 때는 예외가 전파된다.
    # safe_div는 이를 가드하지 않으므로 현재 동작을 그대로 고정한다.
    with pytest.raises(OverflowError):
        safe_div(10**400, 7)


def test_음수_0의_부호가_보존된다():
    assert math.copysign(1.0, safe_div(-0.0, 5)) == -1.0
    assert math.copysign(1.0, safe_div(0.0, -5)) == -1.0
    assert math.copysign(1.0, safe_div(0.0, 5)) == 1.0


def test_None_입력은_TypeError를_전파한다():
    with pytest.raises(TypeError):
        safe_div(None, 5)
    with pytest.raises(TypeError):
        safe_div(5, None)
