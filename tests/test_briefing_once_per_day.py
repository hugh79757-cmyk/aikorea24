"""tests/test_briefing_once_per_day.py

2026-10-16 정책 — 브리핑 하루 1회 발행.

실측 근거: 07:03 KST 자동 실행이 3건짜리 브리핑(id=354)을 만든 뒤, 12:07 재실행이
1건짜리(제외 통보 1건)를 '-2'(id=355)로 붙였다. API(src/pages/api/briefing/latest.ts)는
최신 1건만 서빙하므로 3건짜리가 화면에서 가려졌고, 파이프라인은 브리핑 생성과 무관하게
이메일을 보내 같은 브리핑이 2회 발송됐다.

여기서는 D1 대신 스텁으로 save_briefing / main 의 가드만 검증한다 (실제 D1 접근 없음).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import auto_briefing as ab  # noqa: E402


class _StubD1:
    """d1_query / d1_execute 대역 — 호출 패턴만 해석한다."""

    def __init__(self, same_date_rows=(), new_id=900):
        self.same_date_rows = list(same_date_rows)
        self.new_id = new_id
        self.queries = []
        self.executed = []

    def query(self, sql):
        self.queries.append(sql)
        if "status = 'published'" in sql:
            return [r for r in self.same_date_rows if r.get("status", "published") == "published"]
        if "ORDER BY date DESC" in sql:
            return list(self.same_date_rows)
        if "SELECT id FROM briefings WHERE date =" in sql:
            return [{"id": self.new_id}]
        raise AssertionError(f"예상 못한 쿼리: {sql[:70]}")

    def execute(self, sql):
        self.executed.append(sql)
        return True

    def statements(self, needle):
        return [s for s in self.executed if needle in s]


def _patch(monkeypatch, stub):
    monkeypatch.setattr(ab, "d1_query", stub.query)
    monkeypatch.setattr(ab, "d1_execute", stub.execute)
    monkeypatch.delenv("AIK24_BRIEFING_FORCE", raising=False)


def _data():
    return {"date": "2026-10-16", "intro": "i", "status": "published",
            "items": [{"news_id": 1, "sort_order": 1, "comment": "c"}]}


def test_same_day_rerun_is_skipped_without_any_write(monkeypatch, capsys):
    """같은 날 published 가 있으면 재실행은 저장하지 않는다 (INSERT/UPDATE 0건)."""
    stub = _StubD1(same_date_rows=[{"id": 354, "date": "2026-10-16-1", "status": "published"}])
    _patch(monkeypatch, stub)
    assert ab.save_briefing(_data()) is None
    out = capsys.readouterr().out
    assert "이미 오늘 브리핑이 published" in out and "id=354" in out
    assert stub.executed == [], f"쓰기가 발생했다: {stub.executed}"
    assert "AIK24_BRIEFING_FORCE=1" in out  # 강제 재발행 안내


def test_forced_rerun_supersedes_previous_and_creates_next_seq(monkeypatch, capsys):
    """force=True: 기존 published 를 superseded 로 내리고 새 seq 를 만든다."""
    stub = _StubD1(same_date_rows=[{"id": 354, "date": "2026-10-16-1", "status": "published"}])
    _patch(monkeypatch, stub)
    monkeypatch.setenv("AIK24_BRIEFING_FORCE", "1")
    assert ab._force_requested() is True

    bid = ab.save_briefing(_data())
    out = capsys.readouterr().out
    assert bid == 900
    sups = stub.statements("superseded")
    assert len(sups) == 1 and "id = 354" in sups[0]
    ins = stub.statements("INSERT INTO briefings")
    assert len(ins) == 1 and "2026-10-16-2" in ins[0]
    assert "superseded (id=354" in out


def test_first_briefing_of_day_keeps_seq_1(monkeypatch):
    """당일 첫 발행은 기존과 동일하게 '-1' (회귀 방지)."""
    stub = _StubD1(same_date_rows=[])
    _patch(monkeypatch, stub)
    bid = ab.save_briefing(_data())
    ins = stub.statements("INSERT INTO briefings")
    assert bid == 900 and len(ins) == 1 and "2026-10-16-1" in ins[0]
    assert stub.statements("superseded") == []


def test_main_exits_early_when_today_published(monkeypatch, capsys):
    """main() 은 LLM 작업 전에 조기 종료한다 (비용·중복 생성 방지)."""
    stub = _StubD1(same_date_rows=[{"id": 354, "date": "2026-10-16-1", "status": "published"}])
    _patch(monkeypatch, stub)
    assert ab.main() is None
    out = capsys.readouterr().out
    assert "이미 오늘 브리핑 발행됨" in out and "건너뜀" in out
    assert stub.executed == [], f"쓰기가 발생했다: {stub.executed}"
    # 조기 종료 경로에서는 브리핑 후보 조회(SELECT ... FROM news)까지 가지 않는다
    assert not any("FROM news" in q for q in stub.queries), stub.queries


def test_force_flag_only_env_1(monkeypatch):
    monkeypatch.delenv("AIK24_BRIEFING_FORCE", raising=False)
    assert ab._force_requested() is False
    monkeypatch.setenv("AIK24_BRIEFING_FORCE", "true")  # '1' 이 아니면 강제 아님
    assert ab._force_requested() is False
    monkeypatch.setenv("AIK24_BRIEFING_FORCE", "1")
    assert ab._force_requested() is True
