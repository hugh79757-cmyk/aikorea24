#!/usr/bin/env python3
"""AIK24-PIPE-07 — 수집기 INSERT 의 origin_link 기록 테스트 (D1 호출 0회)

검증 대상: scripts/news_collector_v2.save()
  · 무료 모델 행은 origin_link(제공사 페이지)를 기록한다
  · origin_link 가 없는 비무료 행은 '' 가 아니라 NULL 을 기록한다
    ('' 는 SQLite COALESCE 에서 NULL 로 취급되지 않아 링크가 빈 값이 된다)

사용: pytest tests/test_news_collector_origin_link.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import news_collector_v2  # noqa: E402


class _FakeCfnew:
    A24_DB = "fake-db"

    def __init__(self):
        self.statements = []

    def sql(self, statement, database_id=None, **kw):
        self.statements.append(statement)
        return []  # SELECT link → 비어 있음(신규), INSERT → 무시


def _row(**over):
    row = {
        "title": "[무료 LLM] minimax-m3.1-flash-free — OpenCode Zen 무료 티어",
        "link": "https://models.dev/opencode/minimax-m3.1-flash-free",
        "origin_link": "https://opencode.ai/v2/docs/console/models/",
        "description": "desc",
        "source": "OpenCode Zen",
        "category": "AI",
        "pub_date": "2026-10-20 00:00:00",
        "source_url": "https://models.dev/api.json",
        "original_title": "minimax-m3.1-flash-free",
        "country": "us",
    }
    row.update(over)
    return row


def _insert_values(sql):
    """단일 INSERT 의 VALUES 튜플을 필드 목록으로 (테스트 값에는 쉼표가 없다)."""
    body = sql.split("VALUES (")[1].split(");")[0]
    return [p.strip() for p in body.split(",")]


def test_free_model_inserts_origin_link(monkeypatch):
    fake = _FakeCfnew()
    monkeypatch.setattr(news_collector_v2, "cfnew", fake)

    assert news_collector_v2.save([_row()]) == 1
    sql = fake.statements[-1]
    assert "origin_link" in sql
    vals = _insert_values(sql)
    assert vals[2] == "'https://opencode.ai/v2/docs/console/models/'"


def test_non_free_row_without_origin_link_inserts_null(monkeypatch):
    fake = _FakeCfnew()
    monkeypatch.setattr(news_collector_v2, "cfnew", fake)

    row = _row(
        title="AI 뉴스 제목",
        link="https://example.com/news/1",
        source="TechCrunch AI",
        source_url="https://example.com/feed",
        original_title="News",
    )
    row.pop("origin_link")
    assert news_collector_v2.save([row]) == 1

    vals = _insert_values(fake.statements[-1])
    assert vals[2] == "NULL", "빈 문자열은 COALESCE 폴백을 막는다"
