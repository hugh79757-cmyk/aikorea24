#!/usr/bin/env python3
"""Tests for deep_dive_writer.py"""

import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)


SAMPLE_CANDIDATE = {
    "topic": "EU 규제 vs 중국 규제 완화",
    "contrast_frame": "강화 vs 완화",
    "type": "A",
    "source_articles": [
        {"id": 1, "title": "EU AI 규제법 시행", "source": "Reuters", "pub_date": "2026-08-25", "link": "https://a.com/1"},
        {"id": 2, "title": "중국 AI 규제 완화", "source": "SCMP", "pub_date": "2026-08-24", "link": "https://a.com/2"},
    ],
    "quote_1": "EU가 AI 규제를 강화한다",
    "quote_2": "중국이 AI 규제를 완화한다",
    "gap_summary": "상반된 규제 접근이 나타나고 있다",
    "reading_angle": "지정학적 경쟁 관점",
}


class TestParseDeepDive:
    """LLM 출력 파싱 테스트."""

    def test_valid_output(self):
        """정상 출력 파싱."""
        from scripts.deep_dive_writer import _parse_deep_dive
        raw = """TITLE: EU vs 중국 AI 규제의 향방

---

## 대비의 발견
EU와 중국이 정반대 방향으로 규제 접근을 취하고 있다.

## A측: EU의 강화 접근
EU는 AI 규제법을 시행하며 강력한 규제를 도입했다.

## B측: 중국의 완화 접근
중국은 AI 산업 활성화를 위해 규제를 완화하고 있다.

## 분석: 왜 이런 대비가 발생했는가
지정학적 경쟁이 이런 차이를 만들어낼 수 있다.

## 전망: 앞으로 어떤 뉴스가 나올지
양측 간의 규제 조화 시도가 나타날 수 있다.

https://example.com/1
https://example.com/2"""
        result = _parse_deep_dive(raw)
        assert result is not None
        assert result["title"] == "EU vs 중국 AI 규제의 향방"
        assert "대비의 발견" in result["body"]
        assert len(result["source_links"]) == 2

    def test_no_title_extracts_from_h2(self):
        """TITLE 없으면 첫 번째 H2를 제목으로."""
        from scripts.deep_dive_writer import _parse_deep_dive
        long_body = "A" * 200  # 100자 이상이어야 파싱 성공
        raw = f"""## 규제 대비 분석

{long_body}

## 본문 내용
더 많은 내용이 여기에 들어갑니다. 충분한 길이를 위해 추가 텍스트를 넣습니다."""
        result = _parse_deep_dive(raw)
        assert result is not None
        assert result["title"] == "규제 대비 분석"

    def test_empty_returns_none(self):
        """빈 입력은 None."""
        from scripts.deep_dive_writer import _parse_deep_dive
        assert _parse_deep_dive("") is None
        assert _parse_deep_dive(None) is None

    def test_too_short_body_returns_none(self):
        """본문이 너무 짧으면 None."""
        from scripts.deep_dive_writer import _parse_deep_dive
        raw = "TITLE: 제목\n---\n짧은 본문."
        result = _parse_deep_dive(raw)
        assert result is None


class TestBuildWritingPrompt:
    """프롬프트 빌드 테스트."""

    def test_includes_articles_and_evidence(self):
        """프롬프트에 기사 본문과 근거 문장 포함."""
        from scripts.deep_dive_writer import _build_writing_prompt
        articles = [
            {"id": 1, "title": "EU AI 규제", "body": "EU 규제 본문 내용", "source": "Reuters", "pub_date": "2026-08-25", "link": "https://a.com/1"},
            {"id": 2, "title": "중국 AI 완화", "body": "중국 완화 본문 내용", "source": "SCMP", "pub_date": "2026-08-24", "link": "https://a.com/2"},
        ]
        prompt = _build_writing_prompt(SAMPLE_CANDIDATE, articles)
        assert "EU 규제 본문 내용" in prompt
        assert "중국 완화 본문 내용" in prompt
        assert SAMPLE_CANDIDATE["quote_1"] in prompt
        assert "5단락" in prompt

    def test_body_truncated_to_3000(self):
        """기사 본문 3000자로 잘림."""
        from scripts.deep_dive_writer import _build_writing_prompt
        long_body = "A" * 5000
        articles = [
            {"id": 1, "title": "t1", "body": long_body, "source": "s", "pub_date": "d", "link": "l"},
            {"id": 2, "title": "t2", "body": "normal body", "source": "s", "pub_date": "d", "link": "l"},
        ]
        prompt = _build_writing_prompt(SAMPLE_CANDIDATE, articles)
        assert "A" * 3001 not in prompt  # truncated


class TestVerifyQuoteMultiSource:
    """verify_quote 다중 소스 검증 테스트."""

    def test_verify_with_korean_description(self):
        """한국어 description과 정확히 일치하면 검증 통과."""
        from scripts.abductive_finder import verify_quote
        quote = "고객들이 브로커 앱을 거치지 않고도 AI 비서를 통해 포트폴리오를 분석하고 거래할 수 있게 했습니다."
        description = "스케일러블 캐피털은 자사 투자 플랫폼을 챗GPT와 클로드에 개방하여, 고객들이 브로커 앱을 거치지 않고도 AI 비서를 통해 포트폴리오를 분석하고 거래할 수 있게 했습니다."
        # description에 quote가 포함되어 있으므로 통과
        assert verify_quote(quote, description)

    def test_verify_fails_on_unrelated_text(self):
        """관련 없는 텍스트에서는 실패."""
        from scripts.abductive_finder import verify_quote
        quote = "원문에 존재하지 않는 완전한 환각 문장입니다"
        source = "이것은 전혀 다른 내용의 기사입니다"
        assert not verify_quote(quote, source)


class TestWriteDeepDive:
    """write_deep_dive 통합 테스트 (LLM mock)."""

    @patch("scripts.deep_dive_writer.chat_completion")
    def test_normal_writing(self, mock_llm):
        """정상 심층 분석 작성."""
        mock_llm.return_value = """TITLE: EU vs 중국 AI 규제

---

## 대비의 발견
EU와 중국이 정반대 방향으로 규제 접근을 취하고 있다.

## A측: EU의 강화 접근
EU는 AI 규제법을 시행하며 강력한 규제를 도입했다.

## B측: 중국의 완화 접근
중국은 AI 산업 활성화를 위해 규제를 완화하고 있다.

## 분석: 왜 이런 대비가 발생했는가
지정학적 경쟁이 이런 차이를 만들어낼 수 있다.

## 전망: 앞으로 어떤 뉴스가 나올지
양측 간의 규제 조화 시도가 나타날 수 있다.

https://example.com/1
https://example.com/2"""

        from scripts.deep_dive_writer import write_deep_dive
        candidate = dict(SAMPLE_CANDIDATE)
        candidate["source_articles"] = [
            {"id": 1, "title": "EU 규제", "body": "EU 규제 본문", "source": "Reuters", "pub_date": "2026-08-25", "link": "https://a.com/1"},
            {"id": 2, "title": "중국 완화", "body": "중국 완화 본문", "source": "SCMP", "pub_date": "2026-08-24", "link": "https://a.com/2"},
        ]
        result = write_deep_dive(candidate)
        assert result is not None
        assert result["title"] == "EU vs 중국 AI 규제"
        assert len(result["body"]) > 100

    @patch("scripts.deep_dive_writer.chat_completion")
    def test_llm_failure_returns_none(self, mock_llm):
        """LLM 실패 시 None."""
        mock_llm.return_value = None
        from scripts.deep_dive_writer import write_deep_dive
        candidate = dict(SAMPLE_CANDIDATE)
        candidate["source_articles"] = [
            {"id": 1, "title": "EU 규제", "body": "EU 본문", "source": "Reuters", "pub_date": "d", "link": "l"},
            {"id": 2, "title": "중국 완화", "body": "중국 본문", "source": "SCMP", "pub_date": "d", "link": "l"},
        ]
        assert write_deep_dive(candidate) is None

    @patch("scripts.deep_dive_writer.chat_completion")
    def test_insufficient_bodies_uses_fallback(self, mock_llm):
        """body가 없으면 title+source로 fallback."""
        mock_llm.return_value = None  # LLM 실패
        from scripts.deep_dive_writer import write_deep_dive
        candidate = dict(SAMPLE_CANDIDATE)
        candidate["source_articles"] = [
            {"id": 1, "title": "EU 규제", "body": "", "source": "Reuters", "pub_date": "d", "link": "https://a.com/1"},
            {"id": 2, "title": "중국 완화", "body": "", "source": "SCMP", "pub_date": "d", "link": "https://a.com/2"},
        ]
        with patch("scripts.deep_dive_writer._crawl_article_body", return_value=""):
            result = write_deep_dive(candidate)
            # fallback으로 body가 채워지지만 LLM이 실패하므로 None
            assert result is None

    @patch("scripts.deep_dive_writer.chat_completion")
    def test_source_links_from_candidate(self, mock_llm):
        """source_links가 candidate.source_articles에서 추출됨."""
        mock_llm.return_value = """TITLE: EU vs 중국 규제

---

## 대비의 발견
EU와 중국이 정반대 규제 접근을 취하고 있다.

## A측: EU 강화
EU는 AI 규제법을 시행했다.

## B측: 중국 완화
중국은 AI 산업 규제를 완화했다.

## 분석: 대비 원인
지정학적 경쟁 때문이다.

## 전망: 향후
규제 조화 시도가 나타날 수 있다.

https://example.com/1
https://example.com/2"""

        from scripts.deep_dive_writer import write_deep_dive
        candidate = dict(SAMPLE_CANDIDATE)
        candidate["source_articles"] = [
            {"id": 1, "title": "EU 규제", "body": "EU 본문", "source": "Reuters", "pub_date": "d", "link": "https://a.com/1"},
            {"id": 2, "title": "중국 완화", "body": "중국 본문", "source": "SCMP", "pub_date": "d", "link": "https://a.com/2"},
        ]
        result = write_deep_dive(candidate)
        assert result is not None
        # candidate.source_articles의 link가 source_links로 사용됨
        assert "https://a.com/1" in result["source_links"]
        assert "https://a.com/2" in result["source_links"]

    @patch("scripts.deep_dive_writer.chat_completion")
    def test_quality_judgment_in_output(self, mock_llm):
        """품질 판단이 결과에 포함됨."""
        mock_llm.return_value = """TITLE: EU vs 중국 규제

---

## 대비의 발견
EU와 중국이 정반대 규제 접근을 취하고 있다.

## A측: EU 강화
EU는 "AI 규제법을 시행하며 강력한 규제를 도입했다".

## B측: 중국 완화
중국은 AI 산업 규제를 완화하고 있다.

## 분석: 대비 원인
지정학적 경쟁 때문이다.

## 전망: 향후
규제 조화 시도가 나타날 수 있다."""

        from scripts.deep_dive_writer import write_deep_dive
        candidate = dict(SAMPLE_CANDIDATE)
        candidate["source_articles"] = [
            {"id": 1, "title": "EU 규제", "body": 'EU는 AI 규제법을 시행하며 강력한 규제를 도입했다. EU AI 규제법이 시행되었다.', "source": "Reuters", "pub_date": "d", "link": "https://a.com/1"},
            {"id": 2, "title": "중국 완화", "body": "중국은 AI 산업 규제를 완화하고 있다. 중국 AI 완화.", "source": "SCMP", "pub_date": "d", "link": "https://a.com/2"},
        ]
        result = write_deep_dive(candidate)
        assert result is not None
        assert "quality_judgment" in result
        q = result["quality_judgment"]
        assert "verdict" in q
        assert q["verdict"] in ("추천", "보류", "폐기")
        assert "issues" in q
        assert "verified_quotes" in q

    @patch("scripts.deep_dive_writer.chat_completion")
    def test_generic_topic_gets_poor_judgment(self, mock_llm):
        """뻔한 주제('혁신 vs 위협')는 폐기 판단."""
        mock_llm.return_value = """TITLE: AI의 두 얼굴

---

## 대비의 발견
AI는 혁신이자 위협이다.

## A측: 혁신
AI가 의료 혁신을 이끈다.

## B측: 위협
AI가 실업을 유발한다.

## 분석
기술의 양면성 때문이다.

## 전망
규제 논의가 본격화될 것이다."""

        from scripts.deep_dive_writer import write_deep_dive
        candidate = {
            "topic": "AI의 혁신 vs 위협",
            "contrast_frame": "긍정 vs 부정",
            "type": "A",
            "source_articles": [
                {"id": 1, "title": "AI 혁신", "body": "AI 혁신 본문", "source": "R", "pub_date": "d", "link": "https://a.com/1"},
                {"id": 2, "title": "AI 위협", "body": "AI 위협 본문", "source": "S", "pub_date": "d", "link": "https://a.com/2"},
            ],
            "quote_1": "AI 혁신",
            "quote_2": "AI 위협",
            "gap_summary": "대비",
            "reading_angle": "분석",
        }
        result = write_deep_dive(candidate)
        assert result is not None
        q = result["quality_judgment"]
        assert q["verdict"] == "폐기"
        assert any("일반적" in issue for issue in q["issues"])

    @patch("scripts.deep_dive_writer.chat_completion")
    def test_hallucinated_quote_rejects_deep_dive(self, mock_llm):
        """환각 인용(원문에 없는 따옴표 문장)은 전체 폐기."""
        mock_llm.return_value = """TITLE: 테스트 기사

---

## 대비의 발견
이 대비는 중요하다.

## A측
"원문에 존재하지 않는 완전한 환각 문장입니다 이것은 허구입니다"

## B측
이것은 두 번째 입장이다.

## 분석
이 대비는 복잡하다.

## 전망
향후 변화가 예상된다."""

        from scripts.deep_dive_writer import write_deep_dive
        candidate = {
            "topic": "A vs B 구체적 대비",
            "contrast_frame": "구체적 대비",
            "type": "A",
            "source_articles": [
                {"id": 1, "title": "기사 A", "body": "원문 본문에는 이런 내용이 없다.", "description": "설명also 없음",
                 "source": "R", "pub_date": "d", "link": "https://a.com/1"},
                {"id": 2, "title": "기사 B", "body": "두 번째 기사 본문.", "description": "두 번째 설명",
                 "source": "S", "pub_date": "d", "link": "https://a.com/2"},
            ],
            "quote_1": "원문 A 문장",
            "quote_2": "원문 B 문장",
            "gap_summary": "대비가 존재한다",
            "reading_angle": "분석",
        }
        result = write_deep_dive(candidate)
        assert result is not None
        q = result["quality_judgment"]
        assert q["verdict"] == "폐기"
        assert q["hallucinated_quotes"] > 0
        assert any("환각" in issue for issue in q["issues"])

    @patch("scripts.deep_dive_writer.chat_completion")
    def test_inference_only_gets_hold_judgment(self, mock_llm):
        """인용 없이 추론만으로 구성된 기사는 '보류' 판단."""
        mock_llm.return_value = """TITLE: AI 규제 대비 분석

---

## 대비의 발견
EU와 중국의 규제 접근이 상반된다.

## A측: EU의 강화
EU는 AI 규제를 강화하는 방향으로 움직이고 있다.

## B측: 중국의 완화
중국은 AI 산업 활성화를 위해 규제를 완화하고 있다.

## 분석: 왜 이런 대비가 발생했는가
지정학적 경쟁이 이런 차이를 만들어낼 수 있다.

## 전망: 앞으로 어떤 뉴스가 나올지
규제 조화 시도가 나타날 수 있다."""

        from scripts.deep_dive_writer import write_deep_dive
        candidate = {
            "topic": "EU AI 규제 vs 중국 규제 완화",
            "contrast_frame": "강화 vs 완화",
            "type": "A",
            "source_articles": [
                {"id": 1, "title": "EU 규제", "body": "EU 규제 본문", "source": "Reuters", "pub_date": "d", "link": "https://a.com/1"},
                {"id": 2, "title": "중국 완화", "body": "중국 완화 본문", "source": "SCMP", "pub_date": "d", "link": "https://a.com/2"},
            ],
            "quote_1": "EU가 AI 규제를 강화한다",
            "quote_2": "중국이 AI 규제를 완화한다",
            "gap_summary": "상반된 규제 접근",
            "reading_angle": "지정학적 경쟁",
        }
        result = write_deep_dive(candidate)
        assert result is not None
        q = result["quality_judgment"]
        # 인용 없는 추론 기사는 "보류" (사람 검토용)
        assert q["verdict"] == "보류"
        assert any("인용 없음" in issue for issue in q["issues"])
