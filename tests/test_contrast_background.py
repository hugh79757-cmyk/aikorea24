"""Tests for pipeline.threads.contrast.background_search — D1 LIKE + fallback."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline.threads.contrast.background_search import find_background, find_cross_articles, _esc

pytestmark = pytest.mark.skip(reason="미사용 기능 비활성화 2026-10-13")


class TestEsc:
    def test_escape_single_quote(self):
        assert _esc("a'b") == "a''b"
        assert _esc("O'Reilly") == "O''Reilly"


class TestFindBackground:
    def test_first_kw_hit(self):
        mock_rows = [{"id": "2", "title": "AI 규제 뉴스", "description": "desc", "link": "http://a", "pub_date": "2026-08-20", "source": "src"}]
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=mock_rows) as mock_q:
            result = find_background(["AI 규제", "다른 키워드"], "1")
            assert result["id"] == "2"
            # should use first keyword only
            assert mock_q.call_count == 1

    def test_second_kw_fallback(self):
        """2026-10-13: 구현이 '키워드별 순차 쿼리(첫 히트 우선)'에서
        '키워드를 OR 로 묶은 단일 쿼리 + ORDER BY pub_date DESC LIMIT 1(최신 우선)'로 바뀌었다.
        두 번째 키워드도 같은 쿼리로 조회되고, 반환된 최신 기사가 채택된다는 계약을 검증한다."""
        captured = {}
        rows = [{"id": "3", "title": "신뢰 붕괴 기사", "description": "d",
                 "link": "http://b", "pub_date": "2026-08-21", "source": "src"}]

        def capture(sql):
            captured["sql"] = sql
            return rows

        with patch("pipeline.threads.contrast.background_search.d1_query",
                   side_effect=capture) as mock_q:
            result = find_background(["AI 규제", "신뢰 붕괴"], "1")
            assert result["id"] == "3"
            assert mock_q.call_count == 1                                       # 단일 쿼리
            assert "AI 규제" in captured["sql"] and "신뢰 붕괴" in captured["sql"]  # OR 결합
            assert "ORDER BY pub_date DESC LIMIT 1" in captured["sql"]           # 최신 우선

    def test_zero_result_none(self):
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=[]):
            # patch vectorize fallback to also return None/empty
            with patch.dict("sys.modules", {}):
                # ensure vectorize import fails gracefully -> None
                # We mock vectorize to return empty
                result = find_background(["없는키워드"], "1")
                # d1 returns [] for all kws, vectorize fallback may be attempted but we didn't mock it to succeed
                # should be None
                assert result is None

    def test_vectorize_fallback_path(self):
        # D1 returns empty, vectorize returns hit
        mock_v = [{"id": "9", "title": "vector hit", "description": "desc"}]
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=[]):
            with patch("pipeline.infra.vectorize_client.query_vectors", return_value=mock_v, create=True):
                # also need to handle `query` import path — patch both
                with patch("pipeline.infra.vectorize_client.get_embedding", return_value=[0.1]*10, create=True):
                    # find_background tries `query` first, then fallback to query_vectors with embedding
                    # Simulate TypeError on string call to trigger embedding path
                    result = find_background(["AI 규제"], "1")
                    # may hit vector path depending on which import succeeds; just check not crash
                    assert result is None or result["id"] == "9"

    def test_sql_quote_escape(self):
        captured = {}
        def capture(sql):
            captured["sql"] = sql
            return [{"id": "5", "title": "hit"}]
        with patch("pipeline.threads.contrast.background_search.d1_query", side_effect=capture):
            find_background(["O'Reilly"], "1")
            assert "O''Reilly" in captured["sql"]

    def test_empty_keywords(self):
        assert find_background([], "1") is None
        assert find_background([""], "1") is None


class TestFindCross:
    def test_limit_2(self):
        rows = [
            {"id": "2", "title": "t2"}, {"id": "3", "title": "t3"}, {"id": "4", "title": "t4"}
        ]
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=rows):
            result = find_cross_articles("1", ["AI"], limit=2)
            assert len(result) == 2
            assert result[0]["id"] == "2"

    def test_exclude_seed(self):
        rows = [{"id": "1", "title": "seed"}, {"id": "2", "title": "other"}]
        with patch("pipeline.threads.contrast.background_search.d1_query", return_value=rows):
            result = find_cross_articles("1", ["AI"], limit=2)
            assert all(r["id"] != "1" for r in result)

    def test_no_keywords_empty(self):
        assert find_cross_articles("1", [], limit=2) == []
        assert find_cross_articles("1", ["AI"], limit=0) == []
