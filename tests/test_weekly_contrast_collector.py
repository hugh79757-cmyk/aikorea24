#!/usr/bin/env python3
"""Tests for weekly_contrast_collector.py"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)


class TestCollectWeeklyArticles:
    """D1 쿼리 빌드 및 결과 파싱 테스트."""

    @patch("scripts.weekly_contrast_collector.d1_query")
    def test_returns_articles_with_required_fields(self, mock_d1):
        """D1 결과에서 id, title, description, source, pub_date, link 포함."""
        mock_d1.return_value = [
            {"id": 1, "title": "AI 규제 강화", "description": "EU 규제", "source": "Reuters",
             "category": "AI", "pub_date": "2026-08-25", "link": "https://example.com/1"},
            {"id": 2, "title": "AI 투자 확대", "description": "구글 투자", "source": "TechCrunch",
             "category": "AI", "pub_date": "2026-08-24", "link": "https://example.com/2"},
        ]
        from scripts.weekly_contrast_collector import collect_weekly_articles
        articles = collect_weekly_articles(days=7)

        assert len(articles) == 2
        assert articles[0]["id"] == 1
        assert articles[0]["title"] == "AI 규제 강화"
        assert articles[0]["link"] == "https://example.com/1"

    @patch("scripts.weekly_contrast_collector.d1_query")
    def test_returns_empty_on_no_results(self, mock_d1):
        """D1이 빈 결과를 반환하면 빈 리스트."""
        mock_d1.return_value = []
        from scripts.weekly_contrast_collector import collect_weekly_articles
        articles = collect_weekly_articles(days=7)
        assert articles == []

    @patch("scripts.weekly_contrast_collector.d1_query")
    def test_handles_missing_fields(self, mock_d1):
        """D1 결과에 필드가 없어도 에러 없이 처리."""
        mock_d1.return_value = [{"id": 1}]  # title, description 등 없음
        from scripts.weekly_contrast_collector import collect_weekly_articles
        articles = collect_weekly_articles(days=7)
        assert len(articles) == 1
        assert articles[0]["title"] == ""
        assert articles[0]["description"] == ""

    @patch("scripts.weekly_contrast_collector.d1_query")
    def test_sql_includes_date_filter(self, mock_d1):
        """SQL에 briefing 날짜 필터가 포함됨."""
        mock_d1.return_value = []
        from scripts.weekly_contrast_collector import collect_weekly_articles
        collect_weekly_articles(days=7)
        called_sql = mock_d1.call_args[0][0]
        assert "b.date >=" in called_sql
        assert "FROM briefing_items" in called_sql


class TestCosineSimilarity:
    """코사인 유사도 계산 테스트."""

    def test_identical_vectors(self):
        """동일 벡터는 유사도 1.0."""
        from scripts.weekly_contrast_collector import _cosine_similarity
        assert _cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """직교 벡터는 유사도 0.0."""
        from scripts.weekly_contrast_collector import _cosine_similarity
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_empty_vectors(self):
        """빈 벡터는 유사도 0.0."""
        from scripts.weekly_contrast_collector import _cosine_similarity
        assert _cosine_similarity([], []) == 0.0

    def test_different_lengths(self):
        """길이 다른 벡터는 유사도 0.0."""
        from scripts.weekly_contrast_collector import _cosine_similarity
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


class TestDescriptionReliability:
    """description 신뢰도 검증 테스트."""

    @patch("pipeline.infra.vectorize_client.get_embedding")
    def test_reliable_when_high_similarity(self, mock_emb):
        """유사도가 높으면 description_reliable = True."""
        from scripts.weekly_contrast_collector import _check_description_reliability
        # 동일한 방향 벡터 → 유사도 1.0
        mock_emb.return_value = [1.0, 0.0, 0.0]
        art = {"id": 1, "title": "EU AI 규제 강화", "description": "EU가 AI 규제를 강화한다"}
        result = _check_description_reliability(art)
        assert result["description_reliable"] is True
        assert result["description_similarity"] == pytest.approx(1.0)

    @patch("pipeline.infra.vectorize_client.get_embedding")
    def test_unreliable_when_low_similarity(self, mock_emb):
        """유사도가 낮으면 description_reliable = False."""
        from scripts.weekly_contrast_collector import _check_description_reliability
        # 서로 다른 방향 벡터 → 유사도 0.0
        mock_emb.side_effect = lambda t: [1.0, 0.0] if "EU" in t else [0.0, 1.0]
        art = {"id": 1, "title": "EU AI 규제", "description": "일본 경제 성장"}
        result = _check_description_reliability(art)
        assert result["description_reliable"] is False

    def test_no_description_returns_none(self):
        """description이 없으면 reliable = None."""
        from scripts.weekly_contrast_collector import _check_description_reliability
        art = {"id": 1, "title": "제목", "description": ""}
        result = _check_description_reliability(art)
        assert result["description_reliable"] is None

    def test_no_title_returns_none(self):
        """title이 없으면 reliable = None."""
        from scripts.weekly_contrast_collector import _check_description_reliability
        art = {"id": 1, "title": "", "description": "설명"}
        result = _check_description_reliability(art)
        assert result["description_reliable"] is None

    @patch("pipeline.infra.vectorize_client.get_embedding")
    def test_embedding_failure_returns_none(self, mock_emb):
        """임베딩 호출 실패 시 reliable = None."""
        from scripts.weekly_contrast_collector import _check_description_reliability
        mock_emb.return_value = None
        art = {"id": 1, "title": "제목", "description": "설명"}
        result = _check_description_reliability(art)
        assert result["description_reliable"] is None

    @patch("pipeline.infra.vectorize_client.get_embedding")
    def test_embedding_exception_returns_none(self, mock_emb):
        """임베딩 예외 발생 시 reliable = None."""
        from scripts.weekly_contrast_collector import _check_description_reliability
        mock_emb.side_effect = RuntimeError("API down")
        art = {"id": 1, "title": "제목", "description": "설명"}
        result = _check_description_reliability(art)
        assert result["description_reliable"] is None
