"""AIK24-PIPE-03 작업 2 — 카탈로그 diff → news 테이블 기록 테스트.

cfnew(D1) 는 sys.modules 가짜 객체로 대체한다 (라이브 쓰기 없음).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import model_catalog  # noqa: E402


class _FakeCfnew:
    A24_DB = "fake-db"

    def __init__(self, existing_titles=()):
        self.existing = [{"title": t} for t in existing_titles]
        self.quota_calls = 0
        self.statements = []

    def check_quota(self, *a, **kw):
        self.quota_calls += 1

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
        "removed": [{"provider": "kilo", "model_id": "old-model-free", "reason": "단종/제거"}],
        "changed": [],
    }


def test_added_and_removed_become_free_llm_rows(monkeypatch):
    fake = _install(monkeypatch, _FakeCfnew())
    assert model_catalog.record_diff_to_news("2026-10-16", _diff()) == 2

    assert fake.quota_calls == 1, "쓰기 전 check_quota 가드 필수"
    sql = fake.statements[-1]
    assert "[신규 무료] new-model-free — OpenCode Zen 무료 목록에 추가" in sql
    assert "[제외] old-model-free — Kilo Free Models 무료 목록에서 제외" in sql
    assert "'free-llm'" in sql
    assert "12문항 평가 전 — 판단 보류" in sql
    assert sql.count("INSERT OR IGNORE INTO news") == 2


def test_same_day_duplicate_skipped(monkeypatch):
    fake = _install(monkeypatch, _FakeCfnew(
        existing_titles=["[신규 무료] new-model-free — OpenCode Zen 무료 목록에 추가"]))
    assert model_catalog.record_diff_to_news("2026-10-16", _diff()) == 1
    sql = fake.statements[-1]
    assert "new-model-free" not in sql
    assert "old-model-free" in sql


def test_unknown_provider_and_empty_diff_write_nothing(monkeypatch):
    fake = _install(monkeypatch, _FakeCfnew())
    d = {"added": [{"provider": "huggingface", "model_id": "x"}], "removed": [], "changed": []}
    assert model_catalog.record_diff_to_news("2026-10-16", d) == 0
    assert fake.statements == [], "대상 0건이면 D1 조회/쓰기 자체를 하지 않는다"


def test_quotes_escaped_in_titles(monkeypatch):
    fake = _install(monkeypatch, _FakeCfnew())
    d = {"added": [{"provider": "openrouter", "model_id": "a'b:free"}], "removed": [], "changed": []}
    model_catalog.record_diff_to_news("2026-10-16", d)
    assert "a''b:free" in fake.statements[-1]


def test_same_provider_rows_get_unique_links(monkeypatch):
    """news.link 는 UNIQUE — 같은 프로바이더 행은 링크가 겹치면 INSERT OR IGNORE 로 유실된다."""
    fake = _install(monkeypatch, _FakeCfnew())
    d = {"added": [{"provider": "kilo", "model_id": "new-free"}],
         "removed": [{"provider": "kilo", "model_id": "old-free", "reason": "단종/제거"}], "changed": []}
    assert model_catalog.record_diff_to_news("2026-10-16", d) == 2

    sql = fake.statements[-1]
    rows = [s for s in sql.split("INSERT OR IGNORE INTO news") if s.strip()]
    links = [s.split("VALUES (")[1].split(",")[1] for s in rows]
    assert len(links) == 2
    assert links[0] != links[1], links
    assert links[0].startswith("'https://api.kilo.ai/api/gateway/models#")


def test_origin_link_for_added_and_removed(monkeypatch):
    """AIK24-PIPE-07: 추가는 제공사 모델 페이지, 제외는 404 위험이 없도록 목록 페이지."""
    fake = _install(monkeypatch, _FakeCfnew())
    assert model_catalog.record_diff_to_news("2026-10-16", _diff()) == 2

    sql = fake.statements[-1]
    # zen added → OpenCode Zen 모델 표
    assert "'https://opencode.ai/v2/docs/console/models/'" in sql
    # kilo removed → per-model 대신 목록 페이지
    assert "'https://kilo.ai/models'" in sql
    assert "https://kilo.ai/models/old-model-free" not in sql.replace("'", "")

