"""AIK24-PIPE-03 작업 4 — verdict_block 검증.

지시서: "평가 결과가 없으면 '12문항 평가 전 — 판단 보류'".
2026-10-16 실측 사고: 캐시 미스에서 eval_model_cached 를 부르면 12문항 라이브 평가가
돌아간다(이미 제외된 모델에 48초 낭비) → 캐시 전용 조회여야 한다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auto_briefing as ab  # noqa: E402
import model_eval  # noqa: E402


def test_cache_miss_returns_hold_without_live_eval(monkeypatch):
    monkeypatch.setattr(model_eval, "cache_get", lambda mid: None)

    def _boom(*a, **k):
        raise AssertionError("캐시 미스에서 라이브 평가를 호출하면 안 된다")

    monkeypatch.setattr(model_eval, "eval_model_cached", _boom)
    assert ab.verdict_block("gone-free", "OpenCode Zen") == "12문항 평가 전 — 판단 보류"


def test_cache_hit_renders_score_and_top3_comparison(monkeypatch):
    monkeypatch.setattr(model_eval, "cache_get",
                        lambda mid: {"score": 10, "max_score": 12, "label": "12문항 중 10문항 정답"})
    monkeypatch.setattr(ab, "_top3_avg", lambda: 9.0)
    out = ab.verdict_block("good-free", "OpenCode Zen")
    assert out.splitlines()[0] == "12문항 평가: 10/12 — 12문항 중 10문항 정답"
    assert out.splitlines()[1] == "현재 추천 Top 3 대비: 추천 모델과 동급"


def test_cache_hit_below_top3_states_the_gap(monkeypatch):
    monkeypatch.setattr(model_eval, "cache_get",
                        lambda mid: {"score": 7, "max_score": 12, "label": "12문항 중 7문항 정답"})
    monkeypatch.setattr(ab, "_top3_avg", lambda: 9.5)
    assert "현재 추천 모델 대비 2.5점 낮음" in ab.verdict_block("meh-free")
