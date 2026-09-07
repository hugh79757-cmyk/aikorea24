"""Tests for pipeline.threads.contrast.background_search — pool load + Python matching + fallback.

NOTE: 2026-09-07 rewrite — D1 LIKE per-keyword scan → 30-day pool 1-load + in-memory match.
Tests updated to new contract (pool SQL + Python matching). See CHANGES.md.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline.threads.contrast.background_search import (
    find_background,
    find_cross_articles,
    _match,
    _reset_pool_cache,
)

POOL_ROW = {"id": "2", "title": "AI 규제 뉴스", "description": "desc", "link": "http://a", "pub_date": "2026-08-20", "source": "src"}


@pytest.fixture(autouse=True)
def reset_pool():
    """모듈 풀 캐시 리셋 — 테스트 간 d1_query mock 격리."""
    _reset_pool_cache()
    yield
    _reset_pool_cache()


class TestMatch:
    def test_title_match_case_insensitive(self):
        assert _match({"title": "AI Regulation"}, "ai reg") is True

    def test_description_match(self):
        assert _match({"title": "x", "description": "신뢰 붕괴 발생"}, "신뢰 붕괴") is True

    def test_no_match(self):
        assert _match({"title": "foo", "description": "bar"}, "baz") is False


class TestFindBackground:
    def test_pool_sql_no_keyword_injection(self):
        """풀 SQL에 키워드 문자열이 들어가지 않음 — 7500 LIKE 에러 계열 소멸 검증."""
        captured = {}
        def capture(sql):
            captured["sql"] = sql
            return [POOL_ROW]
        with patch("pipeline.threads.contrast.background_search.d1_query", side_effect=capture):
            find_background(["O'Reilly"], "1")
            assert "O'Reilly" not in captured["sql"]
            assert "O''Reilly" not in captured["sql"]
            assert "LIKE" not in captured["sql"]

    def test_first_kw_hit(self):
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=[POOL_ROW]) as mock_q:
            result = find_background(["AI 규제", "다른 키워드"], "1")
            assert result["id"] == "2"
            # pool은 1회만 로드 — 키워드 수와 무관
            assert mock_q.call_count == 1

    def test_second_kw_fallback(self):
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=[
            {"id": "3", "title": "신뢰 붕괴 기사", "description": ""}
        ]):
            result = find_background(["AI 규제", "신뢰 붕괴"], "1")
            assert result["id"] == "3"

    def test_exclude_ids(self):
        rows = [
            {"id": "2", "title": "AI 규제 뉴스", "description": "", "pub_date": "2026-08-20"},
            {"id": "5", "title": "AI 규제 다른 기사", "description": "", "pub_date": "2026-08-19"},
        ]
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=rows):
            result = find_background(["AI 규제"], ["2"])  # list exclude
            assert result["id"] == "5"

    def test_zero_result_none(self):
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=[]):
            with patch.dict("sys.modules", {}):
                result = find_background(["없는키워드"], "1")
                assert result is None

    def test_pool_ttl_cached(self):
        """풀 캐시 — 두 번째 호출은 d1_query 재호출 없음."""
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=[POOL_ROW]) as mock_q:
            find_background(["AI 규제"], "1")
            find_background(["뉴스"], "9")
            assert mock_q.call_count == 1

    def test_empty_keywords(self):
        assert find_background([], "1") is None
        assert find_background([""], "1") is None


class TestFindCross:
    def test_limit_2(self):
        rows = [
            {"id": "2", "title": "t2", "source": "s1", "pub_date": "2026-08-20"},
            {"id": "3", "title": "t3", "source": "s2", "pub_date": "2026-08-19"},
            {"id": "4", "title": "t4", "source": "s3", "pub_date": "2026-08-18"},
        ]
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=rows):
            with patch("pipeline.threads.contrast.background_search._match", side_effect=lambda r, k: True):
                result = find_cross_articles("1", ["AI"], limit=2)
                assert len(result) == 2
                assert result[0]["id"] == "2"

    def test_exclude_seed(self):
        rows = [
            {"id": "1", "title": "seed", "source": "s1", "pub_date": "2026-08-20"},
            {"id": "2", "title": "other", "source": "s2", "pub_date": "2026-08-19"},
        ]
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=rows):
            with patch("pipeline.threads.contrast.background_search._match", side_effect=lambda r, k: True):
                result = find_cross_articles("1", ["AI"], limit=2)
                assert all(r["id"] != "1" for r in result)

    def test_distinct_sources(self):
        rows = [
            {"id": "2", "title": "a", "source": "s1", "pub_date": "2026-08-20"},
            {"id": "3", "title": "b", "source": "s1", "pub_date": "2026-08-19"},
            {"id": "4", "title": "c", "source": "s2", "pub_date": "2026-08-18"},
        ]
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=rows):
            with patch("pipeline.threads.contrast.background_search._match", side_effect=lambda r, k: True):
                result = find_cross_articles("1", ["AI"], limit=3)
                assert [r["id"] for r in result] == ["2", "4"]

    def test_no_keywords_empty(self):
        assert find_cross_articles("1", [], limit=2) == []
        assert find_cross_articles("1", ["AI"], limit=0) == []
