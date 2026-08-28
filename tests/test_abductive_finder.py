#!/usr/bin/env python3
"""abductive_finder 테스트"""

import json
from unittest.mock import patch

import pytest

import abductive_finder as af


# ── 샘플 입력 ──
SAMPLE_ITEMS = [
    {"id": "1", "title": "OpenAI GPT-5 발표", "body": "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다. 벤치마크에서 기존 모델을 크게 앞질렀다고 밝혔다.", "source": "TechCrunch", "url": "https://example.com/1"},
    {"id": "2", "title": "구글 Gemini 2.0", "body": "구글은 Gemini 2.0이 GPT-5와 대등한 성능을 보인다고 발표했다. 오픈소스 모델로는 최초라고 설명했다.", "source": "The Verge", "url": "https://example.com/2"},
    {"id": "3", "title": "EU AI 규제", "body": "유럽연합이 AI 모델에 대한 엄격한 규제안을 발표했다. 기업들은 규제가 혁신을 저해한다고 반발했다.", "source": "Reuters", "url": "https://example.com/3"},
    {"id": "4", "title": "AI 일자리 대체", "body": "최근 연구에서 AI가 향후 5년 내 사무직의 30%를 대체할 수 있다고 발표했다. 반면 새로운 일자리도同等히 창출될 것이라고 분석했다.", "source": "Bloomberg", "url": "https://example.com/4"},
    {"id": "5", "title": "AI 투자 감소", "body": "2분기 AI 스타트업 투자가 전 분기 대비 40% 감소했다. 투자자들은 수익성 불확실성을 이유로 들었다.", "source": "Crunchbase", "url": "https://example.com/5"},
    {"id": "6", "title": "AI 에너지 소비", "body": "대규모 AI 모델 학습에 사용되는 전력이 연간 2배로 증가했다. 환경단체들은 지속가능성을 우려하고 있다.", "source": "Nature", "url": "https://example.com/6"},
]


# ── verify_quote 단위 테스트 ──

class TestVerifyQuote:
    def test_exact_match(self):
        assert af.verify_quote("OpenAI가 GPT-5를 공개", SAMPLE_ITEMS[0]["body"])

    def test_whitespace_normalized(self):
        assert af.verify_quote("OpenAI가   GPT-5를 공개", SAMPLE_ITEMS[0]["body"])

    def test_not_found(self):
        assert not af.verify_quote("삼성전자가 반도체를 출시", SAMPLE_ITEMS[0]["body"])

    def test_empty_quote(self):
        assert af.verify_quote("", "anything")


# ── _parse_candidates 단위 테스트 ──

class TestParseCandidates:
    def test_valid_json(self):
        raw = json.dumps({"candidates": [{"type": "A", "source_item_ids": ["1"]}]})
        result = af._parse_candidates(raw)
        assert len(result) == 1
        assert result[0]["type"] == "A"

    def test_markdown_wrapped(self):
        raw = '```json\n{"candidates": [{"type": "B", "source_item_ids": ["2"]}]}\n```'
        result = af._parse_candidates(raw)
        assert len(result) == 1

    def test_bad_json(self):
        result = af._parse_candidates("이것은 JSON이 아니다")
        assert result == []

    def test_missing_candidates_key(self):
        result = af._parse_candidates('{"not_candidates": []}')
        assert result == []


# ── find_abduction_candidates 통합 구조 테스트 (모의 LLM) ──

MOCK_LLM_RESPONSE = json.dumps({
    "candidates": [
        {
            "type": "A",
            "source_item_ids": ["1", "2"],
            "quote_1": "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다",
            "quote_2": "구글은 Gemini 2.0이 GPT-5와 대등한 성능을 보인다고 발표했다",
            "gap_summary": "OpenAI와 구글이 동시에 같은 모델과 대등하다고 주장하여 양사의 주장을 동시에 수용하기 어렵다.",
            "verification_path": "양사 모델의 독립 벤치마크 비교 결과가 나오면 검증 가능"
        },
        {
            "type": "B",
            "source_item_ids": ["5"],
            "quote_1": "2분기 AI 스타트업 투자가 전 분기 대비 40% 감소했다",
            "quote_2": "AI는 모든 산업을 혁신할 것이다",
            "gap_summary": "AI 투자가 급감하는 현실과 AI 혁신 낙관론이 충돌한다.",
            "verification_path": "3분기 투자 데이터가 나오면 추세 지속 여부 검증"
        },
        {
            "type": "C",
            "source_item_ids": ["4"],
            "quote_1": "AI가 향후 5년 내 사무직의 30%를 대체할 수 있다고 발표했다",
            "quote_2": "지난해 전문가들은 10년 이상 걸릴 것으로 예측했다",
            "gap_summary": "대체 예상 시점이 빨라지고 있어 기존 예측과 괴리가 있다.",
            "verification_path": "실제 자동화 도입 속도 데이터로 검증 가능"
        }
    ]
})


class TestFindAbductionCandidates:
    @patch("abductive_finder.chat_completion", return_value=MOCK_LLM_RESPONSE)
    def test_normal_input_returns_candidates(self, mock_llm):
        results = af.find_abduction_candidates(SAMPLE_ITEMS)
        assert len(results) >= 1
        assert all(c["type"] in ("A", "B", "C") for c in results)
        mock_llm.assert_called_once()

    @patch("abductive_finder.chat_completion", return_value=None)
    def test_llm_failure_returns_empty(self, mock_llm):
        results = af.find_abduction_candidates(SAMPLE_ITEMS)
        assert results == []

    @patch("abductive_finder.chat_completion", return_value="not json at all")
    def test_bad_json_returns_empty(self, mock_llm):
        results = af.find_abduction_candidates(SAMPLE_ITEMS)
        assert results == []

    @patch("abductive_finder.chat_completion")
    def test_quote_mismatch_drops_candidate(self, mock_llm):
        bad_quote = json.dumps({
            "candidates": [{
                "type": "A",
                "source_item_ids": ["1"],
                "quote_1": "이 문장은 본문에 존재하지 않는 허구적인 인용문이다",
                "quote_2": "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다",
                "gap_summary": "테스트용 어긋남",
                "verification_path": "테스트"
            }]
        })
        mock_llm.return_value = bad_quote
        results = af.find_abduction_candidates(SAMPLE_ITEMS)
        assert results == []

    @patch("abductive_finder.chat_completion", return_value=MOCK_LLM_RESPONSE)
    def test_body_fallback_to_summary(self, mock_llm):
        items_no_body = [
            {"id": "1", "title": "제목1", "summary": "요약 텍스트가 여기 있다", "source": "S1", "url": "https://example.com/1"},
        ]
        af.find_abduction_candidates(items_no_body)
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args[1]
        prompt = call_kwargs["messages"][0]["content"]
        assert "요약 텍스트가 여기 있다" in prompt


# ── 빈 입력 테스트 ──

class TestEdgeCases:
    def test_empty_input_returns_empty(self):
        assert af.find_abduction_candidates([]) == []

    @patch("abductive_finder.chat_completion", return_value=json.dumps({"candidates": []}))
    def test_empty_candidates(self, mock_llm):
        results = af.find_abduction_candidates(SAMPLE_ITEMS)
        assert results == []


# ── gap_summary 충성도 검증 테스트 ──

class TestGapSummaryFidelity:
    """gap_summary가 인용문+원문 범위를 벗어나는지 확인"""

    @patch("abductive_finder.chat_completion")
    def test_gap_summary超出_source_drops(self, mock_llm):
        """gap_summary에 원문에 없는 '수백 건의 보안 사고'가 포함된 경우 폐기"""
        hallucinated = json.dumps({
            "candidates": [{
                "type": "A",
                "source_item_ids": ["1", "2"],
                "quote_1": "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다",
                "quote_2": "구글은 Gemini 2.0이 GPT-5와 대등한 성능을 보인다고 발표했다",
                "gap_summary": "실제 현장에서는 수백 건의 자율형 AI 에이전트 보안 사고가 발생하고 있으며 통제 불능 상태다",
                "verification_path": "테스트"
            }]
        })
        mock_llm.return_value = hallucinated
        results = af.find_abduction_candidates(SAMPLE_ITEMS)
        # gap_summary의 "수백 건의 보안 사고"는 원문에 없으므로 폐기
        assert results == []

    @patch("abductive_finder.chat_completion")
    def test_gap_summary忠实_source_kept(self, mock_llm):
        """gap_summary가 인용문과 원문 범위 내에 있으면 통과"""
        faithful = json.dumps({
            "candidates": [{
                "type": "A",
                "source_item_ids": ["1", "2"],
                "quote_1": "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다",
                "quote_2": "구글은 Gemini 2.0이 GPT-5와 대등한 성능을 보인다고 발표했다",
                "gap_summary": "OpenAI와 구글이 동시에 같은 모델과 대등하다고 주장하여 양사의 주장을 동시에 수용하기 어렵다",
                "verification_path": "양사 모델의 독립 벤치마크 비교 결과가 나오면 검증 가능"
            }]
        })
        mock_llm.return_value = faithful
        results = af.find_abduction_candidates(SAMPLE_ITEMS)
        assert len(results) == 1
