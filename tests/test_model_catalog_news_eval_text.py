"""tests/test_model_catalog_news_eval_text.py

2026-10-18 회귀 테스트 — 무료 목록 변경 news 행의 description 문구.

사고 실측(2026-10-17 10:00 KST 생성 → 2026-10-18 09:00 브리핑 → 자동 발행):
  desc = "OpenCode Zen 무료 목록에 제외 · 12문항 평가 전 — 판단 보류"
cat-jam-free 는 이미 10/12 를 받은 모델인데도 "평가 전"으로 박혔고, 자동 발행 글이
그 문구를 전제로 "공식 공지에 따르면 정책 변경으로 제외" 같은 사유를 지어냈다.

계약:
  1. 리더보드에 점수가 있으면 점수를 적는다 ("직전 12문항 평가 10/12 (문항 v2)").
  2. 점수가 없을 때만 기존 문구("12문항 평가 전 — 판단 보류")를 쓴다 (기존 테스트 계약 유지).
  3. 제외 알림에는 "제외 사유는 제공사 미공지"를 붙인다 — 사유를 아는 척하지 않는다.
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import model_catalog  # noqa: E402


class _FakeCfnew:
    A24_DB = "fake-db"

    def __init__(self, existing_titles=()):
        self.existing = [{"title": t} for t in existing_titles]
        self.statements = []

    def check_quota(self, *a, **kw):
        pass

    def sql(self, statement, database_id=None, **kw):
        self.statements.append(statement)
        if statement.strip().upper().startswith("SELECT"):
            return self.existing
        return []


def _install(monkeypatch, fake):
    monkeypatch.setitem(sys.modules, "cfnew", fake)
    return fake


def _diff():
    return {
        "added": [{"provider": "zen", "model_id": "new-model-free", "name": "New"}],
        "removed": [
            {"provider": "zen", "model_id": "cat-jam-free", "reason": "단종/제거"},
            {"provider": "zen", "model_id": "never-evaluated-free", "reason": "단종/제거"},
        ],
        "changed": [],
    }


def _leaderboard(tmp_path, rows):
    path = tmp_path / "model_leaderboard.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def test_scored_model_gets_score_instead_of_judgement_pending(monkeypatch, tmp_path):
    """10/12 를 받은 모델에 '평가 전'을 쓰지 않는다 — 브리핑·자동 글의 날조 전제 차단."""
    monkeypatch.setattr(model_catalog, "LEADERBOARD_PATH", _leaderboard(tmp_path, [
        {"model_id": "opencode/cat-jam-free", "score": 10, "max_score": 12, "qv": 2},
    ]))
    fake = _install(monkeypatch, _FakeCfnew())

    assert model_catalog.record_diff_to_news("2026-10-18", _diff()) == 3
    sql = fake.statements[-1]

    assert "직전 12문항 평가 10/12 (문항 v2)" in sql
    # 점수 없는 모델은 기존 문구 유지 (기존 테스트 계약)
    assert "12문항 평가 전 — 판단 보류" in sql


def test_removed_row_states_provider_did_not_announce(monkeypatch, tmp_path):
    """제외 사유는 관측 범위만 — '공식 공지에 따르면' 같은 출처 날조를 막는 문구."""
    monkeypatch.setattr(model_catalog, "LEADERBOARD_PATH", _leaderboard(tmp_path, []))
    fake = _install(monkeypatch, _FakeCfnew())

    model_catalog.record_diff_to_news("2026-10-18", _diff())
    sql = fake.statements[-1]

    assert "제외 사유는 제공사 미공지(수집 스냅샷 비교)" in sql
    # 추가 행에는 제외 사유 문구가 붙지 않는다
    added = sql.split("[신규 무료]")[1].split("INSERT OR IGNORE INTO news")[0]
    assert "제외 사유" not in added


def test_missing_leaderboard_file_falls_back_to_old_text(monkeypatch, tmp_path):
    """리더보드가 없어도 수집을 막지 않고 기존 문구를 쓴다."""
    monkeypatch.setattr(model_catalog, "LEADERBOARD_PATH", tmp_path / "nope.json")
    fake = _install(monkeypatch, _FakeCfnew())

    model_catalog.record_diff_to_news("2026-10-18", _diff())
    sql = fake.statements[-1]

    assert "12문항 평가 전 — 판단 보류" in sql
    assert "직전 12문항 평가" not in sql


def test_core_model_name_normalization():
    """프로바이더 경로·접미사 차이를 넘어 같은 모델을 찾는다."""
    assert model_catalog._core_model_name("opencode/cat-jam-free") == "cat-jam"
    assert model_catalog._core_model_name("cat-jam-free") == "cat-jam"
    assert model_catalog._core_model_name("meta/llama-3:free") == "llama-3"
    assert model_catalog._core_model_name("") == ""
