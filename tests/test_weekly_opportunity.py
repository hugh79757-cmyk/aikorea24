"""tests/test_weekly_opportunity.py

AIK24-PIPE-03 §작업7 — 주간 무료 기회 선별 규칙 테스트.

핵심 규칙: ① access='unverified' 는 INSERT 하지 않는다 ② expires 가 지난 항목은 넣지 않는다
③ 접근성 표기를 description 끝에 자동 부착한다 ((b)를 (a)처럼 표현하지 않는다).
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import weekly_opportunity as wo  # noqa: E402

TODAY = datetime.now(wo.KST).strftime("%Y-%m-%d")


def _e(**kw):
    base = {"title": "t", "description": "d", "link": "https://x", "category": "event_promo",
            "access": "direct", "expires": "2999-12-31"}
    base.update(kw)
    return base


def test_unverified_excluded():
    direct, unver = _e(title="검증됨"), _e(title="미검증", access="unverified")
    picked, skipped = wo.select_entries([direct, unver], today=TODAY)
    assert [e["title"] for e in picked] == ["검증됨"]
    assert any("unverified" in why for _, why in skipped)


def test_expired_excluded():
    live, dead = _e(title="진행중"), _e(title="끝남", expires="2000-01-01")
    picked, skipped = wo.select_entries([live, dead], today=TODAY)
    assert [e["title"] for e in picked] == ["진행중"]
    assert any("만료" in why for _, why in skipped)


def test_access_labels_attached():
    entries = [_e(title="a", access="direct"), _e(title="b", access="custom"), _e(title="c", access="local")]
    picked, _ = wo.select_entries(entries, today=TODAY)
    out = {e["title"]: wo.describe(e) for e in picked}
    assert "(a) OpenCode에서 바로 선택 가능" in out["a"]
    assert "(b) 커스텀 프로바이더 설정 후 연결 가능" in out["b"]
    assert "로컬 브리지(Ollama 등) 필요" in out["c"]
    assert "(a)" not in out["b"] and "(a)" not in out["c"]


def test_insert_fixed_values():
    """고정값: v2_tag='free-opportunity', v2_pass=1, category='benefit', source='무료 기회'."""
    sql = wo.build_inserts([_e(title="기회 '인용부호'", access="custom")])[0]
    assert "'free-opportunity'" in sql and ",1," in sql
    assert "'benefit'" in sql and "'무료 기회'" in sql
    assert "인용부호" in sql and "''" in sql  # 작은따옴표 이스케이프


# ─────────────────────────────────────────────────────────────────────────────
# 2026-10-16 — 링크 충돌(fail-silent) 재발 방지 테스트.
# 배경: news.link 는 UNIQUE. 다른 source 가 같은 링크를 점유하면 INSERT OR IGNORE 가
# 행을 소리 없이 버려 '8건 전송' 로그와 실제 7건이 어긋났다 (id=56069 사례).
# 아래 테스트는 D1 대신 스텁을 써서 main() 의 선별·검증 흐름만 검증한다.
# ─────────────────────────────────────────────────────────────────────────────
import json  # noqa: E402
import sys as _sys  # noqa: E402


class _StubCF:
    """cfnew 대역. sql() 호출 패턴만 해석한다 — 실제 D1 접근 없음."""

    A24_DB = "stub-db"

    def __init__(self, existing_titles=(), conflicts=(), landed=None):
        self.existing_titles = list(existing_titles)
        self.conflicts = list(conflicts)
        self.landed = landed
        self.insert_stmts = []
        self.queries = []

    def check_quota(self):
        return True

    def sql(self, q, database_id=None):  # noqa: ARG002
        self.queries.append(q)
        if "INSERT OR IGNORE INTO news" in q:
            self.insert_stmts.append(q)
            return []
        if "SELECT title FROM news WHERE source" in q:
            return [{"title": t} for t in self.existing_titles]
        if "SELECT id, title, source, link FROM news" in q:
            return list(self.conflicts)
        if "SELECT COUNT(*) AS c" in q:
            if self.landed is not None:
                return [{"c": self.landed}]
            n = sum(s.count("INSERT OR IGNORE INTO news") for s in self.insert_stmts)
            return [{"c": n}]
        raise AssertionError(f"예상 못한 쿼리: {q[:70]}")


def _run_main(tmp_path, monkeypatch, entries, stub):
    p = tmp_path / "weekly.json"
    p.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(wo, "cfnew", stub)
    monkeypatch.setattr(_sys, "argv", ["weekly_opportunity.py", "--path", str(p)])
    return wo.main()


def test_link_conflict_skipped_explicitly(tmp_path, monkeypatch, capsys):
    """점유된 링크는 건너뛰고, 로그에 기존 id 를 남긴다 (조용히 사라지지 않는다)."""
    dup, ok = _e(title="충돌 항목", link="https://x/dup"), _e(title="정상 항목", link="https://x/ok")
    stub = _StubCF(conflicts=[{"id": 56069, "title": "기존 점유", "source": "OpenRouter Free Models",
                              "link": "https://x/dup"}])
    rc = _run_main(tmp_path, monkeypatch, [dup, ok], stub)
    out = capsys.readouterr().out
    assert rc == 0
    assert "링크 충돌" in out and "56069" in out
    joined = "\n".join(stub.insert_stmts)
    assert "정상 항목" in joined and "충돌 항목" not in joined
    assert "확인: 1건 반영됨" in out


def test_landed_mismatch_reports_failure(tmp_path, monkeypatch, capsys):
    """전송 수 ≠ 반영 수면 exit 1 + 로그 (fail-silent 금지)."""
    stub = _StubCF(landed=0)
    rc = _run_main(tmp_path, monkeypatch, [_e(title="A", link="https://x/a")], stub)
    out = capsys.readouterr().out
    assert rc == 1
    assert "불일치" in out and "전송 1 / 확인 0" in out


def test_happy_path_reports_landed(tmp_path, monkeypatch, capsys):
    stub = _StubCF()
    rc = _run_main(tmp_path, monkeypatch, [_e(title="A", link="https://x/a")], stub)
    out = capsys.readouterr().out
    assert rc == 0
    assert "확인: 1건 반영됨" in out


def test_dry_run_does_not_touch_d1(tmp_path, monkeypatch):
    """--dry-run 은 D1 을 한 번도 호출하지 않는다 (sql() 호출 시 AssertionError)."""
    p = tmp_path / "weekly.json"
    p.write_text(json.dumps([_e(title="A")], ensure_ascii=False), encoding="utf-8")

    class _NoD1:
        A24_DB = "stub-db"

        def check_quota(self):
            raise AssertionError("dry-run 에서 check_quota 호출")

        def sql(self, q, database_id=None):  # noqa: ARG002
            raise AssertionError(f"dry-run 에서 D1 호출: {q[:40]}")

    monkeypatch.setattr(wo, "cfnew", _NoD1())
    monkeypatch.setattr(_sys, "argv", ["weekly_opportunity.py", "--path", str(p), "--dry-run"])
    assert wo.main() == 0


def test_link_list_escapes_quotes():
    assert wo._link_list([_e(link="https://x/a'b")]) == "'https://x/a''b'"
    assert wo._link_list([_e(link="https://x/a"), _e(link="https://x/a")]).count(",") == 0  # 중복 제거

