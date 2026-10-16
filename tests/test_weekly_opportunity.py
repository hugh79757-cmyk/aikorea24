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
