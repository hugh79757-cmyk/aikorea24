"""AIK24-EVAL-ZEN-01 — Zen 모델 오차단 방지 + context_length null 정렬 규칙.

지시서 작업 3(규칙 3개)·작업 4(Zen 이 mark_failed 로 차단되지 않음)의 회귀 방지.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from free_models_page import ctx_key, pick_cards, split_zen  # noqa: E402


def row(mid, ctx=None):
    return {"provider": "zen", "model_id": mid, "name": mid, "pricing": None, "context_length": ctx}


# ---------- EVAL-ZEN-01 작업 4 + EVAL-CLI-01 작업 4 + AGENT-EVAL-01 ----------
# 계약이 또 바뀌었다 (2026-10-14 대표님 결정 "모든 평가는 OpenCode CLI 기준"):
# 판정 기준은 **provider 가 아니라 CLI 호출 경로의 존재 여부**다.
# resolve_cli_model() 이 id 를 찾으면 평가 대상, 못 찾으면( zen·kilo·openrouter·구형 포맷
# 전부 무관 ) 대기. 예전처럼 "zen 만 제외하고 나머지는 OpenRouter 직접 호출로 평가"는
# 대표님 결정 위반이므로 더 이상 성립하지 않는다.


def test_split_zen_excludes_every_model_without_cli_route():
    """CLI 경로가 없는 모델은 provider 와 무관하게 대기 — zen 예외 규칙은 폐기됐다."""
    added = [row("jev-1.13-free"), {"provider": "openrouter", "model_id": "a/b:free"}]
    rest, unresolved = split_zen(added)
    assert sorted(unresolved) == ["a/b:free", "jev-1.13-free"]
    assert rest == []


def test_split_zen_routes_cli_registered_zen_to_evaluation():
    """CLI_MODEL_MAP 에 있는 Zen 은 평가 대상으로 낸다 — 경로가 생겼으니 대기는 무의미."""
    import model_eval

    mid = next(m for m in model_eval.CLI_MODEL_MAP)
    rest, zen_ids = split_zen([row(mid), row("jev-1.13-free")])
    assert [t["model_id"] for t in rest] == [mid]
    assert zen_ids == ["jev-1.13-free"]


def test_split_zen_all_zen_without_cli_route_gives_empty_eval_targets():
    rest, zen_ids = split_zen([row("jev-1.13-free")])
    assert rest == []
    assert zen_ids == ["jev-1.13-free"]


def test_split_zen_keeps_model_registered_in_cli_catalog():
    """CLI 카탈로그(free_models_cli.json)에 있으면 provider 표기 없이도 평가 대상이다."""
    rest, unresolved = split_zen([{"model_id": "cohere/north-mini-code:free"}])
    assert [t["model_id"] for t in rest] == ["cohere/north-mini-code:free"]
    assert unresolved == []


def test_split_zen_excludes_legacy_entry_without_cli_route():
    """provider 가 없는 구 포맷 항목도 CLI 경로가 없으면 대기(옛 '무조건 평가' 동작 폐기)."""
    rest, unresolved = split_zen([{"model_id": "legacy/no-provider"}])
    assert unresolved == ["legacy/no-provider"]
    assert rest == []


def test_split_zen_does_not_touch_failed_list():
    """CLI 경로가 없는 Zen 은 mark_failed 가 아니라 zen_pending 로 가야 한다."""
    added = [row("jev-1.13-free")]
    rest, zen_ids = split_zen(added)
    assert rest == []          # 평가 시도 대상에 없음 → mark_failed 로 향할 수 없다
    assert zen_ids == ["jev-1.13-free"]  # zen_pending 경로로만 감


def test_provider_label_no_longer_decides():
    """provider 문자열 판정은 사라졌다 — 'zenfree' 같은 오인 위험 자체가 없게 됐다."""
    rest, unresolved = split_zen([{"provider": "zenfree", "model_id": "x"}])
    assert unresolved == ["x"] and rest == []


# ---------- 작업 3 — context_length null 정렬 ----------


def test_ctx_key_treats_null_and_missing_as_zero():
    assert ctx_key({"context_length": None}) == 0
    assert ctx_key({}) == 0
    assert ctx_key({"context_length": 0}) == 0


def test_ctx_key_keeps_value():
    assert ctx_key({"context_length": 262144}) == 262144


def test_null_context_model_sorts_after_number_under_equal_score():
    rows = [row("zz-model", 128000), row("aa-model", None)]
    scores = {"zz-model": {"score": 8}, "aa-model": {"score": 8}}
    cards = pick_cards(rows, scores, {}, {}, limit=4)
    # 점수 동점 → 컨텍스트 있는 쪽이 앞, 모델 ID 알파벳은 그 다음 기준
    assert [c["model_id"] for c in cards] == ["zz-model", "aa-model"]


def test_null_vs_null_tie_breaks_on_model_id():
    rows = [row("zz-model"), row("aa-model")]
    scores = {"zz-model": {"score": 8}, "aa-model": {"score": 8}}
    cards = pick_cards(rows, scores, {}, {}, limit=4)
    assert [c["model_id"] for c in cards] == ["aa-model", "zz-model"]


def test_score_outranks_context_length():
    rows = [row("small", 8), row("big", 262144)]
    scores = {"small": {"score": 9}, "big": {"score": 8}}
    cards = pick_cards(rows, scores, {}, {}, limit=4)
    assert [c["model_id"] for c in cards] == ["small", "big"]


@pytest.mark.parametrize("mid", ["cat-jam-free", "jev-1.13-free"])
def test_zen_models_display_unpublished_context(mid):
    """Zen 카드의 스펙 문자열에 컨텍스트가 '미공개'로 적혀야 한다 (카드 키는 spec)."""
    cards = pick_cards([row(mid)], {mid: {"score": 8}}, {}, {}, limit=4)
    assert cards[0]["spec"] == "컨텍스트 길이 미공개"
    assert cards[0]["price"] == "가격 미공개"