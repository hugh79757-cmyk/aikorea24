"""AIK24-FREE-PIPE-01 작업 3 — 카드 선정 규칙 테스트.

지시서: ① 현재 무료 상태인 모델만 ② 리더보드 평가 점수 상위 순 (미평가 모델은 평가 완료 후 편입)
③ 동점이면 컨텍스트 길이 순. 무료 모델이 4개 미만이면 있는 만큼만 표시한다 (채우기 금지).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from free_models_page import pick_cards  # noqa: E402


def _row(mid, ctx, provider="openrouter", prompt=0.0, completion=0.0):
    return {"provider": provider, "model_id": mid, "name": mid.split("/")[-1],
            "pricing": {"prompt": prompt, "completion": completion}, "context_length": ctx}


def test_only_evaluated_models_get_cards():
    rows = [_row("a:free", 1000), _row("b:free", 2000)]
    scores = {"a:free": {"score": 5, "max_score": 12}}
    assert [c["model_id"] for c in pick_cards(rows, scores, {}, {})] == ["a:free"]


def test_empty_when_nothing_evaluated():
    """지시서: 빈자리를 채우려고 모델을 임의로 고르지 않는다."""
    rows = [_row("a:free", 1000), _row("b:free", 2000)]
    assert pick_cards(rows, {}, {}, {}) == []


def test_higher_score_wins_over_longer_context():
    rows = [_row("a:free", 1_000_000), _row("b:free", 1000)]
    scores = {"a:free": {"score": 5, "max_score": 12}, "b:free": {"score": 9, "max_score": 12}}
    assert [c["model_id"] for c in pick_cards(rows, scores, {}, {})] == ["b:free", "a:free"]


def test_tie_broken_by_context_length():
    rows = [_row("a:free", 1000), _row("b:free", 1000), _row("c:free", 999_999)]
    scores = {m: {"score": 7, "max_score": 12} for m in ("a:free", "b:free", "c:free")}
    assert [c["model_id"] for c in pick_cards(rows, scores, {}, {})] == ["c:free", "a:free", "b:free"]


def test_limit_four_and_no_padding():
    rows = [_row(f"m{i}:free", 1000 * i) for i in range(6)]
    scores = {r["model_id"]: {"score": 6, "max_score": 12} for r in rows}
    assert len(pick_cards(rows, scores, {}, {})) == 4


def test_review_link_carried_into_card():
    rows = [_row("a:free", 1000)]
    scores = {"a:free": {"score": 6, "max_score": 12}}
    cards = pick_cards(rows, scores, {"a:free": "12문항 중 9문항 정답"}, {"a:free": "https://x/posts/a"})
    assert cards[0]["review"] == "https://x/posts/a"
    assert cards[0]["verdict"] == "12문항 중 9문항 정답"
    assert cards[0]["spec"] == "컨텍스트 1,000 토큰"


def test_missing_context_is_stated_not_hidden():
    rows = [{"provider": "zen", "model_id": "z-free", "name": "Z", "pricing": None, "context_length": None}]
    scores = {"z-free": {"score": 6, "max_score": 12}}
    card = pick_cards(rows, scores, {}, {})[0]
    assert card["spec"] == "컨텍스트 길이 미공개"
    assert card["price"] == "가격 미공개"
    assert "OpenCode Zen" in card["usage"]