"""test_hallucination_gate.py — validate_final_cards 신규 오염 게이트 (2026-09-13)

사고 배경: groq2-gpt20b 파열 어미("한다임"/"있다이이") 발행 3건, "大学和" 한자 혼입,
"죄송합니다" LLM 거부문 초안 저장 — 사용자 수동 삭제 4건+.
게이트: CJK 혼입 / LLM 거부문 / 어미 파열 — validate_final_cards 3차 방어에 추가.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "threads"))

from main_v3 import validate_final_cards  # noqa: E402


def _cards(*texts):
    return list(texts)


OK_CARD = ("AI 에이전트가 항공권을\n몇 초 만에 찾아준다.\n\n"
           "가격 비교부터 옵션 추리기까지\n하던 일을 순식간에 함.")


def _gate_hit(issues, keyword):
    return [i for i in issues if keyword in i]


def test_burst_ending_blocked():
    """'한다임' 파열 어미 — groq2-gpt20b 사고 (root 50155/50016/50269)."""
    cards = _cards(*[OK_CARD] * 4, "그래서 그런 것이다 한다임")
    ok, issues = validate_final_cards(cards)
    assert not ok
    assert _gate_hit(issues, "파열"), issues


def test_burst_ending_yida_yi():
    """'있다이이' 연쇄 파열 — MeckaAI 초안 사고."""
    cards = _cards(*[OK_CARD] * 4, "결국 승자는 정해져 있다이이")
    ok, issues = validate_final_cards(cards)
    assert not ok
    assert _gate_hit(issues, "파열"), issues


def test_normal_yim_passes():
    """정상 평어체 '~임' 종결은 파열 오탐 없어야 (green 유지)."""
    for ending in ("몫임.", "있음.", "함.", "됨.", "것임.", "한다."):
        cards = _cards(*[OK_CARD] * 4, f"마지막 카드 내용이 이렇게 마무리되는 {ending}")
        _, issues = validate_final_cards(cards)
        assert not _gate_hit(issues, "파열"), f"오탐: {ending} → {issues}"


def test_cjk_blocked():
    """'大学和' 한자 혼입 — k7_50235 대기 오염."""
    cards = _cards("코넬大学和 구글이 만든 것\n이렇게 됐다.", *[OK_CARD] * 4)
    ok, issues = validate_final_cards(cards)
    assert not ok
    assert _gate_hit(issues, "혼입"), issues


def test_llm_refusal_blocked():
    """LLM 거부문 초안 저장 — Algorithmicagedcaref 사고."""
    cards = _cards("죄송합니다. 요청하신 내용을 충족할 수 없습니다.", *[OK_CARD] * 4)
    ok, issues = validate_final_cards(cards)
    assert not ok
    assert _gate_hit(issues, "거부문"), issues


def test_refusal_prefix_only():
    """문장 중간 '피할 수 없습니다' 인용문은 오탐 아니어야 (k7_49238 사례)."""
    quote = ('샘 올트먼은 영화 티저 속에서 "미래는 피할 수 없습니다. '
             '국가들은 몰락할 것"이라고 말한다. 가필드가 밝혔다.')
    cards = _cards(*[OK_CARD] * 3, quote, OK_CARD)
    _, issues = validate_final_cards(cards)
    assert not _gate_hit(issues, "거부문"), issues
