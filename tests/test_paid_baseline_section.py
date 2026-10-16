"""B안(유료 대비) 섹션 테스트 — 공식 발표 수치만 인용하는지, 미확인 값을 숨기지 않는지.

설계 (2026-10-16 대표님 결정: "비용 없이 공식 자료 인용 방식"):
- 유료 기준선 수치는 벤더 공식 자료에서만 온다. 우리가 유료 API 를 결제해 돌린 값이 아니다.
- 그래서 페이지에는 **같은 잣대가 아니라는 경고**와 **출처 URL·확인일**이 반드시 함께 나가야 한다.
- 없는 항목은 빈 칸으로 두지 않고 '미확인'이라고 적는다(추측 금지).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)

from free_models_page import load_paid_baseline, render_eval06, render_paid_baseline  # noqa: E402

DATA = {
    "fetchedAt": "2026-10-16",
    "baseline": {
        "name": "Claude Sonnet 5.5",
        "vendor": "Anthropic",
        "announced": "2026-09-28",
        "price": {"input_per_mtok_usd": 2, "output_per_mtok_usd": 10},
        "context_tokens": 1000000,
        "max_output_tokens": 128000,
        "training_cutoff": "2026-06",
        "official_benchmark": {"name": "Terminal-Bench 4.0", "score": "70.6%"},
        "sources": ["https://www.anthropic.com/news/claude-sonnet-5-5"],
    },
}


def _models():
    return [{"model_id": "a-free", "provider": "zen", "context_length": 1000000,
             "retention_percent": None, "kilobench_completion": None,
             "zen_data_policy": None, "zen_trains_on_prompts": None}]


def test_section_carries_official_numbers_and_sources():
    md = "\n".join(render_paid_baseline(DATA, _models()))
    assert "## 유료 모델과 비교 (공식 발표 기준)" in md
    assert "Claude Sonnet 5.5" in md and "Anthropic" in md
    assert "$2 입력 / $10 출력" in md
    assert "1,000,000 토큰" in md and "최대 출력 128,000" in md
    assert "Terminal-Bench 4.0 70.6%" in md
    assert "2026-06" in md  # 학습 컷오프
    assert "https://www.anthropic.com/news/claude-sonnet-5-5" in md
    assert "2026-10-16 확인" in md


def test_section_warns_that_axes_differ():
    """우리 실측과 벤더 발표값을 같은 잣대로 읽지 않게 하는 문장이 반드시 있어야 한다."""
    md = "\n".join(render_paid_baseline(DATA, _models()))
    assert "같은 잣대가 아닙니다" in md
    assert "단정하지 않" in md


def test_missing_fields_are_stated_not_hidden():
    thin = {"baseline": {"name": "X", "sources": []}}
    md = "\n".join(render_paid_baseline(thin, _models()))
    assert md.count("미확인") >= 3  # 가격·컨텍스트·공식 수치·컷오프 중 비어 있는 항목
    assert "출처" not in md  # 출처가 없으면 출처 목록 자체를 만들지 않는다


def test_section_skipped_when_no_baseline_data():
    """데이터가 없으면 섹션이 통째로 빠진다 — 페이지 렌더가 깨지지 않는다."""
    md = render_eval06("2026-10-16", _models(),
                       {"total": 0, "rows": [], "added": [], "removed": [], "changed": []},
                       [], {"verified_at": None, "fail": []}, baseline={})
    assert "## 유료 모델과 비교" not in md
    assert "## 제외된 모델" in md  # 나머지 섹션은 그대로


def test_section_rendered_in_full_page_when_baseline_given():
    md = render_eval06("2026-10-16", _models(),
                       {"total": 0, "rows": [], "added": [], "removed": [], "changed": []},
                       [], {"verified_at": None, "fail": []}, baseline=DATA)
    assert "## 유료 모델과 비교 (공식 발표 기준)" in md
    # 무료 목록 표 뒤, 제외된 모델 앞에 온다 (표 판독 순서 유지)
    assert md.index("## 전체 리스트") < md.index("## 유료 모델과 비교") < md.index("## 제외된 모델")
    # 12문항 실측과 벤더 발표값을 구분해 표기
    assert "자체 12문항 평가" in md and "벤더 공식 발표" in md


def test_shipped_json_has_official_shape():
    """배포된 데이터 파일이 스키마를 지키는지 (가격·출처·확인일 누락 방지)."""
    path = os.path.join(ROOT, "scripts", "logs", "paid_baseline.json")
    data = json.load(open(path, encoding="utf-8"))
    b = data["baseline"]
    assert data["fetchedAt"]
    assert b["name"] and b["vendor"]
    assert isinstance(b["price"]["input_per_mtok_usd"], (int, float))
    assert isinstance(b["price"]["output_per_mtok_usd"], (int, float))
    assert b["sources"] and all(u.startswith("http") for u in b["sources"])
    assert load_paid_baseline()["baseline"]["name"] == b["name"]
