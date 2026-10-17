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

def test_eval06_table_is_five_columns_with_short_names():
    """EVAL-08: 전체 리스트 표는 5컬럼(모델명·프로바이더·컨텍스트·지표·상태), 모델명은 접미사 제거."""
    from free_models_page import render_eval06  # noqa: E402
    models = [
        {"model_id": "nvidia/nemotron-3.5-lightning:free", "cli_id": "kilo/x",
         "provider": "kilo", "context_length": 1000000,
         "retention_percent": None, "kilobench_completion": None,
         "zen_data_policy": None, "zen_trains_on_prompts": None},
        {"model_id": "mimo-v2.6-flash-free", "cli_id": "opencode/y",
         "provider": "zen", "context_length": None,
         "retention_percent": 80.3, "kilobench_completion": None,
         "zen_data_policy": "제로-retention · 프롬프트 학습 미사용(기본 정책)",
         "zen_trains_on_prompts": False},
    ]
    md = render_eval06("2026-10-15", models,
                       {"total": 0, "rows": [], "added": [], "removed": [],
                        "changed": []}, [], {"verified_at": None, "fail": []})
    table = [ln for ln in md.splitlines() if ln.startswith("|")]
    assert table[0] == "| 모델명 | 프로바이더 | 컨텍스트 길이 | 지표 | 상태 |"
    assert "`nvidia/nemotron-3.5-lightning`" in table[2]  # org prefix 유지(동명 구분)
    assert ":free" not in md.split("## 제외된 모델")[0].split("## 전체 리스트")[1]
    assert "재사용 80.3%" in table[3]
    assert "현재 무료 · 제로-retention" in table[3]


def test_render_works_when_catalog_model_has_leaderboard_score(monkeypatch):
    """회귀(2026-10-18): 리더보드 점수를 가진 모델이 카탈로그에 들어오면 페이지 생성이 죽던 결함.

    원인: 판관 폐지 커밋에서 지역 변수 `judged` 가 `graded` 로 개명됐으나 조건문 두 곳이
    옛 이름을 그대로 참조했다. 점수 없는 모델만 카탈로그에 있던 동안에는 if 조건이
    단락평가로 넘어가 잠복했고, 첫 점수 보유 모델(`glm-5.3-flash-free`)이 등록되며
    `NameError: name 'judged' is not defined` 로 발현했다.
    """
    import free_models_page as fmp  # noqa: E402

    monkeypatch.setattr(
        fmp, "leaderboard_scores",
        lambda qv: {"glm-5.3-flash-free": {"score": 6, "max_score": 12, "graded_n": 12}},
    )
    models = [
        {"model_id": "glm-5.3-flash-free", "cli_id": "opencode/glm-5.3-flash-free",
         "provider": "zen", "context_length": 200000,
         "retention_percent": None, "kilobench_completion": None,
         "zen_data_policy": None, "zen_trains_on_prompts": None},
    ]
    md = fmp.render_eval06("2026-10-18", models,
                           {"total": 0, "rows": [], "added": [], "removed": [], "changed": []},
                           [], {"verified_at": None, "fail": []})
    assert "glm-5.3-flash-free" in md
    assert "CLI 평가 6/12문항" in md
