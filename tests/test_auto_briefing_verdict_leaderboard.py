"""tests/test_auto_briefing_verdict_leaderboard.py

2026-10-18 회귀 테스트 — verdict_block 의 리더보드 폴백(tier 2).

사고 실측(2026-10-18 09:00 KST): cat-jam-free 는 리더보드에 10/12 가 남아 있고
무료 모델 페이지도 그 점수를 보여 주는데, 브리핑은 캐시(model_eval_cache.json)가
만료(schema v3 / TTL 초과)됐다는 이유로 "12문항 평가 전 — 판단 보류" 를 출력했다.
그 문구가 그대로 자동 발행 글에 들어가 "평가 전이라 제외됐다"는 날조 문장의 전제가 됐다.

계약:
  1. 캐시가 비어도 리더보드에 점수가 있으면 점수 + 측정 시각을 쓴다.
  2. 문항 버전(qv)이 다르면 그 사실을 밝히고 Top 3 비교는 생략한다.
  3. 어디에도 점수가 없으면 기존 문구("12문항 평가 전 — 판단 보류") 그대로.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auto_briefing as ab  # noqa: E402
import model_eval  # noqa: E402

QV = model_eval.EVAL_QUESTIONS_VERSION


def _leaderboard(tmp_path, rows):
    path = tmp_path / "model_leaderboard.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def _no_cache(monkeypatch):
    monkeypatch.setattr(model_eval, "cache_get", lambda mid: None)


def test_expired_cache_uses_leaderboard_score(monkeypatch, tmp_path):
    """캐시 만료 → 리더보드 점수. 페이지·리더보드와 같은 숫자를 말해야 한다."""
    monkeypatch.setattr(ab, "LEADERBOARD_PATH", _leaderboard(tmp_path, [
        {"model_id": "opencode/cat-jam-free", "score": 10, "max_score": 12, "qv": QV,
         "ts": 1760700000.0},
    ]))
    _no_cache(monkeypatch)
    monkeypatch.setattr(ab, "_top3_avg", lambda: 9.0)

    lines = ab.verdict_block("cat-jam-free", "OpenCode Zen").splitlines()

    assert lines[0] == "12문항 평가: 10/12"
    assert lines[1] == "현재 추천 Top 3 대비: 추천 모델과 동급"
    assert lines[2].startswith("측정: "), lines


def test_provider_prefix_matches_same_model(monkeypatch, tmp_path):
    """프로바이더 표기가 달라도 같은 모델로 본다 (:free 접미사·경로 제거)."""
    monkeypatch.setattr(ab, "LEADERBOARD_PATH", _leaderboard(tmp_path, [
        {"model_id": "muse-spark-1.3-contributor-free", "score": 8, "max_score": 12, "qv": QV},
    ]))
    _no_cache(monkeypatch)

    assert ab.verdict_block("opencode/muse-spark-1.3-contributor-free").startswith("12문항 평가: 8/12")


def test_version_mismatch_is_labelled_and_skips_comparison(monkeypatch, tmp_path):
    """문항 버전이 다르면 기준을 밝히고 Top 3 비교는 하지 않는다(사과와 사과 비교 금지)."""
    monkeypatch.setattr(ab, "LEADERBOARD_PATH", _leaderboard(tmp_path, [
        {"model_id": "muse-spark-1.3-contributor-free", "score": 8, "max_score": 12,
         "qv": QV - 1},
    ]))
    _no_cache(monkeypatch)
    monkeypatch.setattr(ab, "_top3_avg", lambda: 9.0)

    lines = ab.verdict_block("muse-spark-1.3-contributor-free").splitlines()

    assert lines[0] == f"12문항 평가: 8/12 (문항 v{QV - 1} 기준 · 현재 v{QV})"
    assert all(not line.startswith("현재 추천 Top 3") for line in lines), lines


def test_zero_score_row_is_not_a_score(monkeypatch, tmp_path):
    """0/12 행은 '점수 있음'이 아니다 — 판단 보류로 남긴다."""
    monkeypatch.setattr(ab, "LEADERBOARD_PATH", _leaderboard(tmp_path, [
        {"model_id": "some-free", "score": 0, "max_score": 12, "qv": QV},
    ]))
    _no_cache(monkeypatch)
    monkeypatch.setattr(ab, "_verified_running", lambda: set())

    assert ab.verdict_block("some-free") == "12문항 평가 전 — 판단 보류"


def test_no_score_anywhere_stays_pending(monkeypatch, tmp_path):
    """리더보드에도 없으면 기존 문구 그대로 (기존 테스트의 계약 유지)."""
    monkeypatch.setattr(ab, "LEADERBOARD_PATH", _leaderboard(tmp_path, []))
    _no_cache(monkeypatch)
    monkeypatch.setattr(ab, "_verified_running", lambda: set())

    assert ab.verdict_block("gone-free") == "12문항 평가 전 — 판단 보류"


def test_missing_leaderboard_file_does_not_break(monkeypatch, tmp_path):
    """리더보드 파일이 없어도 브리핑을 막지 않는다."""
    monkeypatch.setattr(ab, "LEADERBOARD_PATH", tmp_path / "nope.json")
    _no_cache(monkeypatch)
    monkeypatch.setattr(ab, "_verified_running", lambda: set())

    assert ab.verdict_block("gone-free") == "12문항 평가 전 — 판단 보류"


def test_highest_score_wins_when_multiple_runs(monkeypatch, tmp_path):
    """같은 모델이 여러 번 평가됐으면 최고 점수를 쓴다."""
    monkeypatch.setattr(ab, "LEADERBOARD_PATH", _leaderboard(tmp_path, [
        {"model_id": "cat-jam-free", "score": 10, "max_score": 12, "qv": QV},
        {"model_id": "cat-jam-free", "score": 7, "max_score": 12, "qv": QV},
    ]))
    _no_cache(monkeypatch)

    assert ab.verdict_block("cat-jam-free").startswith("12문항 평가: 10/12")
