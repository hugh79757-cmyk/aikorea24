#!/usr/bin/env python3
"""Tests for contrast_cluster_finder.py"""

import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)


SAMPLE_ARTICLES = [
    {"id": 1, "title": "EU, AI 규제법 시행 선언", "description": "EU가 AI 규제를 강화한다", "source": "Reuters", "pub_date": "2026-08-25", "link": "https://a.com/1"},
    {"id": 2, "title": "중국, AI 산업 규제 완화 발표", "description": "중국이 AI 규제를 완화한다", "source": "SCMP", "pub_date": "2026-08-24", "link": "https://a.com/2"},
    {"id": 3, "title": "삼성, AI 반도체 투자 50조원 발표", "description": "삼성이 AI 반도체에 투자", "source": "매일경제", "pub_date": "2026-08-23", "link": "https://a.com/3"},
    {"id": 4, "title": "구글, AI 모델 성능 2배 향상 발표", "description": "구글 Gemini 성능 개선", "source": "TechCrunch", "pub_date": "2026-08-22", "link": "https://a.com/4"},
    {"id": 5, "title": "일본, AI 로봇 도입 확대", "description": "일본 기업들의 AI 로봇 도입", "source": "Nikkei", "pub_date": "2026-08-21", "link": "https://a.com/5"},
    {"id": 6, "title": "美 의회, AI 규제 청문회 개최", "description": "미국 의회의 AI 규제 논의", "source": "Washington Post", "pub_date": "2026-08-20", "link": "https://a.com/6"},
]


class TestParseClusters:
    """LLM 출력 파싱 테스트."""

    def test_valid_json(self):
        """정상 JSON 파싱."""
        from scripts.contrast_cluster_finder import _parse_clusters
        raw = json.dumps({
            "groups": [
                {"topic": "규제", "article_ids": [1, 2], "contrast_frame": "강화 vs 완화", "why_contrast": "상반된 규제 접근"},
                {"topic": "투자", "article_ids": [3, 4], "contrast_frame": "하드웨어 vs 소프트웨어", "why_contrast": "투자 영역 차이"},
            ]
        })
        result = _parse_clusters(raw)
        assert len(result) == 2
        assert result[0]["topic"] == "규제"
        assert result[1]["article_ids"] == [3, 4]

    def test_markdown_wrapped_json(self):
        """```json 래핑된 JSON 파싱."""
        from scripts.contrast_cluster_finder import _parse_clusters
        raw = '```json\n{"groups": [{"topic": "test", "article_ids": [1, 2], "contrast_frame": "A vs B", "why_contrast": "reason"}]}\n```'
        result = _parse_clusters(raw)
        assert len(result) == 1
        assert result[0]["topic"] == "test"

    def test_bad_json_returns_empty(self):
        """잘못된 JSON은 빈 리스트 반환."""
        from scripts.contrast_cluster_finder import _parse_clusters
        assert _parse_clusters("not json at all") == []
        assert _parse_clusters("") == []

    def test_missing_groups_key(self):
        """groups 키 없으면 빈 리스트."""
        from scripts.contrast_cluster_finder import _parse_clusters
        raw = json.dumps({"items": []})
        assert _parse_clusters(raw) == []

    def test_filters_invalid_groups(self):
        """topic이나 article_indices 없는 그룹 필터링."""
        from scripts.contrast_cluster_finder import _parse_clusters
        raw = json.dumps({
            "groups": [
                {"topic": "valid", "article_indices": [1, 2], "contrast_frame": "A vs B", "why_contrast": "ok"},
                {"topic": "", "article_indices": [1], "contrast_frame": "", "why_contrast": ""},  # invalid
                {"article_indices": [3, 4]},  # no topic
            ]
        })
        result = _parse_clusters(raw)
        assert len(result) == 1


class TestParseEvidence:
    """근거 문장 파싱 테스트."""

    def test_valid_evidence(self):
        """정상 근거 문장 파싱."""
        from scripts.contrast_cluster_finder import _parse_evidence
        raw = json.dumps({
            "contrast_pairs": [
                {
                    "type": "A",
                    "article_1_index": 1,
                    "article_2_index": 2,
                    "quote_1": "EU가 AI 규제를 강화한다",
                    "quote_2": "중국이 AI 규제를 완화한다",
                    "gap_summary": "상반된 규제 접근이 나타나고 있다",
                    "reading_angle": "지정학적 경쟁 관점",
                }
            ]
        })
        result = _parse_evidence(raw)
        assert len(result) == 1
        assert result[0]["type"] == "A"
        assert result[0]["quote_1"] == "EU가 AI 규제를 강화한다"

    def test_invalid_type_filtered(self):
        """type이 A/B/C가 아닌 것 필터링."""
        from scripts.contrast_cluster_finder import _parse_evidence
        raw = json.dumps({
            "contrast_pairs": [
                {"type": "D", "quote_1": "q1", "gap_summary": "g"},  # invalid type
                {"type": "B", "quote_1": "q1", "gap_summary": "g"},  # valid
            ]
        })
        result = _parse_evidence(raw)
        assert len(result) == 1
        assert result[0]["type"] == "B"

    def test_missing_quote_filtered(self):
        """quote_1이나 gap_summary 없으면 필터링."""
        from scripts.contrast_cluster_finder import _parse_evidence
        raw = json.dumps({
            "contrast_pairs": [
                {"type": "A", "quote_1": "", "gap_summary": "g"},  # empty quote
                {"type": "A", "quote_1": "q1"},  # no gap_summary
            ]
        })
        result = _parse_evidence(raw)
        assert len(result) == 0


class TestBuildClusterPrompt:
    """프롬프트 빌드 테스트."""

    def test_includes_all_articles(self):
        """프롬프트에 모든 기사 제목이 포함됨."""
        from scripts.contrast_cluster_finder import _build_cluster_prompt
        prompt = _build_cluster_prompt(SAMPLE_ARTICLES)
        assert "EU, AI 규제법 시행 선언" in prompt
        assert "삼성, AI 반도체 투자" in prompt
        assert "일본, AI 로봇 도입" in prompt

    def test_includes_index_numbers(self):
        """프롬프트에 [ID:1], [ID:6] 등 ID 포함."""
        from scripts.contrast_cluster_finder import _build_cluster_prompt
        prompt = _build_cluster_prompt(SAMPLE_ARTICLES)
        assert "[ID:1]" in prompt
        assert "[ID:6]" in prompt

    def test_empty_articles(self):
        """빈 기사 목록 처리."""
        from scripts.contrast_cluster_finder import _build_cluster_prompt
        prompt = _build_cluster_prompt([])
        assert "뉴스 목록" in prompt


class TestFindClusters:
    """find_clusters 통합 테스트 (LLM mock)."""

    @patch("scripts.contrast_cluster_finder.chat_completion")
    def test_normal_clustering(self, mock_llm):
        """정상 클러스터링 결과."""
        mock_llm.return_value = json.dumps({
            "groups": [
                {"topic": "EU 규제", "article_ids": [1, 2], "contrast_frame": "강화 vs 완화", "why_contrast": "ok", "category": "규제"},
            ]
        })
        from scripts.contrast_cluster_finder import find_clusters
        clusters = find_clusters(SAMPLE_ARTICLES)
        assert len(clusters) == 1
        assert clusters[0]["topic"] == "EU 규제"

    @patch("scripts.contrast_cluster_finder.chat_completion")
    def test_llm_failure_returns_empty(self, mock_llm):
        """LLM 실패 시 빈 리스트."""
        mock_llm.return_value = None
        from scripts.contrast_cluster_finder import find_clusters
        assert find_clusters(SAMPLE_ARTICLES) == []

    def test_too_few_articles_returns_empty(self):
        """기사 1개 이하면 빈 리스트."""
        from scripts.contrast_cluster_finder import find_clusters
        assert find_clusters([{"id": 1, "title": "a"}]) == []


class TestDiversityFilter:
    """주제 중복 방지 필터 테스트."""

    def test_no_overlap_keeps_all(self):
        """서로 다른 주제는 모두 유지."""
        from scripts.contrast_cluster_finder import _diversity_filter
        candidates = [
            {"topic": "EU AI 규제법 시행 vs 중국 규제 완화", "contrast_frame": "강화 vs 완화"},
            {"topic": "삼성 AI 반도체 투자 vs SK하이닉스 경쟁", "contrast_frame": "투자 vs 경쟁"},
            {"topic": "일본 AI 로봇 도입 vs 미국 로봇 규제", "contrast_frame": "도입 vs 규제"},
        ]
        result = _diversity_filter(candidates)
        assert len(result) == 3

    def test_high_overlap_drops_duplicates(self):
        """같은 주제가 반복되면 제외."""
        from scripts.contrast_cluster_finder import _diversity_filter
        candidates = [
            {"topic": "EU AI 규제 강화 vs 중국 AI 규제 완화", "contrast_frame": "강화 vs 완화"},
            {"topic": "EU 규제 강화 vs 미국 규제 완화", "contrast_frame": "강화 vs 완화"},  # 겹침
            {"topic": "삼성 AI 반도체 투자 확대", "contrast_frame": "투자 vs 경쟁"},
        ]
        result = _diversity_filter(candidates, max_overlap_ratio=0.4)
        # 첫 번째와 세 번째는 유지, 두 번째는 겹침으로 제외
        assert len(result) == 2
        assert result[0]["topic"] == "EU AI 규제 강화 vs 중국 AI 규제 완화"
        assert result[1]["topic"] == "삼성 AI 반도체 투자 확대"

    def test_empty_candidates(self):
        """빈 리스트 처리."""
        from scripts.contrast_cluster_finder import _diversity_filter
        assert _diversity_filter([]) == []

    def test_single_candidate(self):
        """후보 1개는 그대로 반환."""
        from scripts.contrast_cluster_finder import _diversity_filter
        candidates = [{"topic": "EU 규제", "contrast_frame": "A vs B"}]
        result = _diversity_filter(candidates)
        assert len(result) == 1


class TestExtractTopicTokens:
    """주제 토큰 추출 테스트."""

    def test_korean_tokens(self):
        """한국어 토큰 추출."""
        from scripts.contrast_cluster_finder import _extract_topic_tokens
        tokens = _extract_topic_tokens("EU AI 규제 vs 중국 규제 완화")
        assert "규제" in tokens
        assert "중국" in tokens
        assert "EU" in tokens

    def test_stopwords_removed(self):
        """불용어 제거."""
        from scripts.contrast_cluster_finder import _extract_topic_tokens
        tokens = _extract_topic_tokens("EU vs 중국으로")
        assert "으로" not in tokens
