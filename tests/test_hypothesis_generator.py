#!/usr/bin/env python3
"""tests/test_hypothesis_generator.py — S2 가설 생성기 테스트"""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from hypothesis_generator import (
    _build_prompt,
    _parse_hypotheses,
    _dedupe,
    generate_hypotheses,
    PERSPECTIVES,
)


SAMPLE_CANDIDATE = {
    "type": "A",
    "source_item_ids": ["1", "2"],
    "quote_1": "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다.",
    "quote_2": "구글은 Gemini 2.0이 GPT-5와 대등한 성능을 보인다고 발표했다.",
    "gap_summary": "OpenAI는 GPT-5가 압도적 우위를 점한다고 주장하는 반면, 구글은 대등하다고 발표한다.",
    "verification_path": "양사 모델의 벤치마크 비교 결과가 나오면 검증 가능",
}

SAMPLE_ITEMS = [
    {"id": "1", "title": "OpenAI, GPT-5 출시 발표",
     "body": "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다. 새 모델은 추론 능력에서 큰 폭의 향상을 보이며, 기존 GPT-4 대비 코딩 능력이 40% 향상되었다고 밝혔다. 샘 알트만 CEO는 이번 모델은 AGI를 향한 결정적 한 걸음이 될 것이라고 말했다. 출시는 올해 4분기로 예정되어 있으며, 기업용 API가 먼저 제공될 전망이다.",
     "source": "TechCrunch"},
    {"id": "2", "title": "구글, Gemini 2.0으로 GPT-5에 대응",
     "body": "구글은 Gemini 2.0을 공개하며 AI 시장 경쟁을 한층 가속화했다. Gemini 2.0은 멀티모달 처리에서 GPT-4를 크게 앞선다고 구글은 주장했다. 특히 비디오 이해와 실시간 번역 기능이 주목받고 있다. 구글 클라우드 CEO는 AI 경쟁은 이제 막 시작이라며 기업 고객 유치에 나섰다.",
     "source": "The Verge"},
    {"id": "3", "title": "유럽 AI 규제 강화", "body": "유럽연합이 AI 모델에 대한 엄격한 규제안을 발표했다.", "source": "Reuters"},
    {"id": "4", "title": "AI 일자리 대체 우려", "body": "최근 연구에서 AI가 향후 5년 내 사무직의 30%를 대체할 수 있다고 발표했다.", "source": "Bloomberg"},
    {"id": "5", "title": "AI 스타트업 투자 감소", "body": "2분기 AI 스타트업 투자가 전 분기 대비 40% 감소했다.", "source": "Crunchbase"},
    {"id": "6", "title": "AI 에너지 소비 증가", "body": "대규모 AI 모델 학습에 사용되는 전력이 연간 2배로 증가했다는 보고가 나왔다.", "source": "Nature"},
]


# 원문(SAMPLE_ITEMS 1,2)에 근거하는 one_line — evidence_checker 통과 용도
_UNIQUE_LINES = [
    "GPT-5의 성능 대폭 향상 주장이 실제 벤치마크에서 검증될지 주목된다",
    "구글 Gemini 2.0의 대등성 주장이 실제 사용 환경에서 확인될지 미지수다",
    "OpenAI의 GPT-5 공개가 AI 시장 경쟁을 더욱 가속화할 것으로 보인다",
    "GPT-5와 Gemini 2.0의 멀티모달 성능 비교가 관심사로 떠올랐다",
    "성능 대폭 향상이라는 OpenAI의 표현이 실제 검증과 다를 수 있다",
    "OpenAI와 구글의 AI 경쟁이 시작 단계에 불과하다는 관측이 나온다",
    "GPT-5의 기업용 API 먼저 제공 전략이 시장에 미치는 영향이 주목된다",
    "구글의 Gemini 2.0 비디오 이해 기능이 실제 어떤 성능을 보일지 궁금하다",
    "GPT-5 추론 능력의 큰 폭 향상이 AGI에 얼마나 기여할지 불확실하다",
    "OpenAI와 구글의 경쟁 가속화가 소비자에게 어떤 변화를 가져올지 지켜볼 일이다",
]

_NEWS_LINES = [
    "독립 벤치마크에서 GPT-5 점수가 공개될 전망",
    "구글 I/O에서 Gemini 실사용 데모가 공개된다",
    "OpenAI 성능 주장과 실제 벤치마크 결과의 차이가 보도된다",
    "GPT-5와 Gemini 2.0 사용자 비교 리뷰가 공개된다",
    "AI 업계 전문가들의 성능 과장 비판 기사가 나온다",
    "OpenAI-구글 모델 직접 비교 테스트 결과가 나온다",
    "GPT-5 출시 시기를 둘러싼 업계 분석이 보도된다",
    "구글 Gemini 2.0 비디오 이해 기능 테스트 결과가 공개된다",
    "GPT-5의 AGI 기여도에 대한 학계 분석이 나온다",
    "AI 경쟁 가속화가 소비자 시장에 미치는 영향에 대한 조사가 발표된다",
]


def _make_hypotheses(count=10):
    """테스트용 가설 리스트 생성. 각 one_line은 원문에 근거."""
    h = []
    for i in range(min(count, len(PERSPECTIVES))):
        h.append({
            "perspective": PERSPECTIVES[i],
            "one_line": _UNIQUE_LINES[i],
            "falsifiable_news": _NEWS_LINES[i],
            "confidence": ["상", "중", "하"][i % 3],
        })
    return h


class TestParseHypotheses:
    def test_valid_json(self):
        data = {"hypotheses": _make_hypotheses(3)}
        result = _parse_hypotheses(json.dumps(data, ensure_ascii=False))
        assert len(result) == 3
        assert result[0]["perspective"] == "기술적 한계"

    def test_markdown_wrapped(self):
        data = {"hypotheses": _make_hypotheses(2)}
        raw = f"```json\n{json.dumps(data, ensure_ascii=False)}\n```"
        result = _parse_hypotheses(raw)
        assert len(result) == 2

    def test_bad_json(self):
        assert _parse_hypotheses("not json at all") == []

    def test_missing_key(self):
        assert _parse_hypotheses('{"wrong_key": []}') == []


class TestDedupe:
    def test_no_duplicates(self):
        hyps = _make_hypotheses(10)
        result = _dedupe(hyps)
        assert len(result) == 10

    def test_near_duplicates_removed(self):
        hyps = [
            {"perspective": "기술적 한계", "one_line": "GPT-5 성능 과장 가능성", "falsifiable_news": "x", "confidence": "상"},
            {"perspective": "미디어 과장", "one_line": "GPT-5 성능 과장 가능성이 높음", "falsifiable_news": "y", "confidence": "중"},
            {"perspective": "시장 과열", "one_line": "AI 투자 거품 신호", "falsifiable_news": "z", "confidence": "하"},
        ]
        result = _dedupe(hyps)
        assert len(result) == 2
        assert result[0]["perspective"] == "기술적 한계"
        assert result[1]["perspective"] == "시장 과열"


class TestGenerateHypotheses:
    def test_normal_10(self, monkeypatch):
        hyps = _make_hypotheses(10)
        raw = json.dumps({"hypotheses": hyps}, ensure_ascii=False)
        monkeypatch.setattr("hypothesis_generator.chat_completion", lambda **kw: raw)
        result = generate_hypotheses(SAMPLE_CANDIDATE, SAMPLE_ITEMS)
        assert len(result) >= 5
        perspectives = [h["perspective"] for h in result]
        assert len(perspectives) == len(set(perspectives))

    def test_below_minimum(self, monkeypatch):
        hyps = _make_hypotheses(3)
        raw = json.dumps({"hypotheses": hyps}, ensure_ascii=False)
        monkeypatch.setattr("hypothesis_generator.chat_completion", lambda **kw: raw)
        result = generate_hypotheses(SAMPLE_CANDIDATE, SAMPLE_ITEMS)
        assert result == []

    def test_dedupe_action(self, monkeypatch):
        hyps = [
            {"perspective": "기술적 한계", "one_line": "GPT-5의 성능 대폭 향상이 검증되지 않았다",
             "falsifiable_news": "x", "confidence": "상"},
            {"perspective": "미디어 과장", "one_line": "GPT-5의 성능 대폭 향상이 검증되지 않고 있다",
             "falsifiable_news": "y", "confidence": "중"},
            {"perspective": "시장 과열", "one_line": "AI 모델 경쟁이 치열해지고 있다",
             "falsifiable_news": "z", "confidence": "하"},
            {"perspective": "규제/정치", "one_line": "AI 시장 경쟁이 가속화되고 있다",
             "falsifiable_news": "a", "confidence": "상"},
            {"perspective": "시간차", "one_line": "과거 예측과 현재 현실의 괴리가 크다",
             "falsifiable_news": "b", "confidence": "중"},
        ]
        raw = json.dumps({"hypotheses": hyps}, ensure_ascii=False)
        monkeypatch.setattr("hypothesis_generator.chat_completion", lambda **kw: raw)
        result = generate_hypotheses(SAMPLE_CANDIDATE, SAMPLE_ITEMS)
        assert result == []

    def test_llm_failure(self, monkeypatch):
        monkeypatch.setattr("hypothesis_generator.chat_completion", lambda **kw: None)
        result = generate_hypotheses(SAMPLE_CANDIDATE, SAMPLE_ITEMS)
        assert result == []

    def test_llm_exception(self, monkeypatch):
        def raise_error(**kw):
            raise RuntimeError("LLM unavailable")
        monkeypatch.setattr("hypothesis_generator.chat_completion", raise_error)
        result = generate_hypotheses(SAMPLE_CANDIDATE, SAMPLE_ITEMS)
        assert result == []

    def test_empty_candidate(self):
        result = generate_hypotheses({}, SAMPLE_ITEMS)
        assert result == []

    def test_empty_items(self):
        result = generate_hypotheses(SAMPLE_CANDIDATE, [])
        assert result == []


class TestEvidenceVerification:
    """S2 근거 검증: 원문에 없는 내용이 포함된 가설이 폐기되는지 확인"""

    def test_unsupported_one_line_dropped(self, monkeypatch):
        """one_line에 원문에 없는 '수백 건의 보안 사고'가 포함되면 폐기"""
        hyps = [
            {"perspective": "기술적 한계", "one_line": "수백 건의 자율형 AI 에이전트 보안 사고가 발생하고 있다",
             "falsifiable_news": "x", "confidence": "상"},
            {"perspective": "미디어 과장", "one_line": "GPT-5와 Gemini 2.0의 성능 격차가 과장되고 있다",
             "falsifiable_news": "y", "confidence": "상"},
            {"perspective": "시장 과열", "one_line": "AI 모델 성능 경쟁이 치열해지고 있다",
             "falsifiable_news": "z", "confidence": "중"},
            {"perspective": "규제/정치", "one_line": "OpenAI와 구글의 경쟁이 시장에 미치는 영향이 크다",
             "falsifiable_news": "a", "confidence": "상"},
            {"perspective": "시간차", "one_line": "AI 기술 발전 속도가 예측을 뛰어넘고 있다",
             "falsifiable_news": "b", "confidence": "중"},
            {"perspective": "사용자 행동", "one_line": "사용자들이 GPT-5와 Gemini를 비교하고 있다",
             "falsifiable_news": "c", "confidence": "하"},
            {"perspective": "경쟁 구도", "one_line": "OpenAI와 구글이 치열하게 경쟁하고 있다",
             "falsifiable_news": "d", "confidence": "상"},
            {"perspective": "한국 시장 특수성", "one_line": "한국에서 GPT-5 도입이 확산되고 있다",
             "falsifiable_news": "e", "confidence": "중"},
            {"perspective": "이해관계자 충돌", "one_line": "투자자와 개발자의 이해관계가 엇갈리고 있다",
             "falsifiable_news": "f", "confidence": "하"},
            {"perspective": "정의의 문제", "one_line": "AI 성능 경쟁의 편중이 문제로 대두되고 있다",
             "falsifiable_news": "g", "confidence": "하"},
        ]
        raw = json.dumps({"hypotheses": hyps}, ensure_ascii=False)
        monkeypatch.setattr("hypothesis_generator.chat_completion", lambda **kw: raw)
        result = generate_hypotheses(SAMPLE_CANDIDATE, SAMPLE_ITEMS)
        one_lines = [h["one_line"] for h in result]
        assert not any("보안 사고" in ol for ol in one_lines), \
            f"Unsupported hypothesis should be dropped, got: {one_lines}"

    def test_supported_one_line_kept(self, monkeypatch):
        """one_line이 원문에 근거 있으면 유지"""
        hyps = [
            {"perspective": "기술적 한계", "one_line": "GPT-5의 성능 향상이 실제 벤치마크에서 검증되고 있다",
             "falsifiable_news": "x", "confidence": "상"},
            {"perspective": "미디어 과장", "one_line": "Gemini 2.0의 대등성 주장이 과장일 수 있다",
             "falsifiable_news": "y", "confidence": "상"},
            {"perspective": "시장 과열", "one_line": "AI 모델 성능 경쟁이 치열해지고 있다",
             "falsifiable_news": "z", "confidence": "중"},
            {"perspective": "규제/정치", "one_line": "OpenAI와 구글의 경쟁이 가속화되고 있다",
             "falsifiable_news": "a", "confidence": "상"},
            {"perspective": "시간차", "one_line": "GPT-5의 추론 능력 향상이 실제 검증과 다를 수 있다",
             "falsifiable_news": "b", "confidence": "중"},
            {"perspective": "사용자 행동", "one_line": "사용자들이 GPT-5와 Gemini를 비교하고 있다",
             "falsifiable_news": "c", "confidence": "하"},
            {"perspective": "경쟁 구도", "one_line": "OpenAI와 구글이 치열하게 경쟁하고 있다",
             "falsifiable_news": "d", "confidence": "상"},
            {"perspective": "한국 시장 특수성", "one_line": "한국에서 GPT-5 도입이 확산되고 있다",
             "falsifiable_news": "e", "confidence": "중"},
            {"perspective": "이해관계자 충돌", "one_line": "투자자와 개발자의 이해관계가 엇갈리고 있다",
             "falsifiable_news": "f", "confidence": "하"},
            {"perspective": "정의의 문제", "one_line": "AI 성능 경쟁의 편중이 문제로 대두되고 있다",
             "falsifiable_news": "g", "confidence": "하"},
        ]
        raw = json.dumps({"hypotheses": hyps}, ensure_ascii=False)
        monkeypatch.setattr("hypothesis_generator.chat_completion", lambda **kw: raw)
        result = generate_hypotheses(SAMPLE_CANDIDATE, SAMPLE_ITEMS)
        assert len(result) >= 5

    def test_specific_number_rejected(self, monkeypatch):
        """원문에 없는 구체적 수치 '2년' 포함 가설 → 폐기"""
        hyps = [
            {"perspective": "규제/정치", "one_line": "OpenAI가 규제를 2년간 유예하는 방안을 추진한다",
             "falsifiable_news": "x", "confidence": "상"},
            {"perspective": "미디어 과장", "one_line": "OpenAI와 구글의 경쟁이 가속화되고 있다",
             "falsifiable_news": "y", "confidence": "상"},
            {"perspective": "시장 과열", "one_line": "AI 모델 성능 경쟁이 치열해지고 있다",
             "falsifiable_news": "z", "confidence": "중"},
            {"perspective": "기술적 한계", "one_line": "GPT-5의 추론 능력 향상이 실제 검증과 다를 수 있다",
             "falsifiable_news": "a", "confidence": "중"},
            {"perspective": "시간차", "one_line": "Gemini 2.0의 대등성 주장이 실제 검증될지 미지수다",
             "falsifiable_news": "b", "confidence": "중"},
            {"perspective": "경쟁 구도", "one_line": "OpenAI와 구글이 치열하게 경쟁하고 있다",
             "falsifiable_news": "c", "confidence": "상"},
            {"perspective": "사용자 행동", "one_line": "사용자들이 GPT-5와 Gemini를 비교하고 있다",
             "falsifiable_news": "d", "confidence": "하"},
            {"perspective": "한국 시장 특수성", "one_line": "한국에서 GPT-5 도입이 확산되고 있다",
             "falsifiable_news": "e", "confidence": "중"},
            {"perspective": "이해관계자 충돌", "one_line": "투자자와 개발자의 이해관계가 엇갈리고 있다",
             "falsifiable_news": "f", "confidence": "하"},
            {"perspective": "정의의 문제", "one_line": "AI 성능 경쟁의 편중이 문제로 대두되고 있다",
             "falsifiable_news": "g", "confidence": "하"},
        ]
        raw = json.dumps({"hypotheses": hyps}, ensure_ascii=False)
        monkeypatch.setattr("hypothesis_generator.chat_completion", lambda **kw: raw)
        result = generate_hypotheses(SAMPLE_CANDIDATE, SAMPLE_ITEMS)
        one_lines = [h["one_line"] for h in result]
        assert not any("2년" in ol for ol in one_lines), \
            f"Hypothesis with hallucinated number should be dropped, got: {one_lines}"

    def test_missing_entity_rejected(self, monkeypatch):
        """원문에 없는 '남반구 시장' 포함 가설 → 폐기"""
        hyps = [
            {"perspective": "경쟁 구도", "one_line": "중국 기업들이 남반구 시장에서 점유율을 확대하고 있다",
             "falsifiable_news": "x", "confidence": "상"},
            {"perspective": "미디어 과장", "one_line": "OpenAI와 구글의 경쟁이 가속화되고 있다",
             "falsifiable_news": "y", "confidence": "상"},
            {"perspective": "시장 과열", "one_line": "AI 모델 성능 경쟁이 치열해지고 있다",
             "falsifiable_news": "z", "confidence": "중"},
            {"perspective": "기술적 한계", "one_line": "GPT-5의 추론 능력 향상이 실제 검증과 다를 수 있다",
             "falsifiable_news": "a", "confidence": "중"},
            {"perspective": "시간차", "one_line": "Gemini 2.0의 대등성 주장이 실제 검증될지 미지수다",
             "falsifiable_news": "b", "confidence": "중"},
            {"perspective": "규제/정치", "one_line": "OpenAI와 구글의 경쟁이 시장에 미치는 영향이 크다",
             "falsifiable_news": "c", "confidence": "상"},
            {"perspective": "사용자 행동", "one_line": "사용자들이 GPT-5와 Gemini를 비교하고 있다",
             "falsifiable_news": "d", "confidence": "하"},
            {"perspective": "한국 시장 특수성", "one_line": "한국에서 GPT-5 도입이 확산되고 있다",
             "falsifiable_news": "e", "confidence": "중"},
            {"perspective": "이해관계자 충돌", "one_line": "투자자와 개발자의 이해관계가 엇갈리고 있다",
             "falsifiable_news": "f", "confidence": "하"},
            {"perspective": "정의의 문제", "one_line": "AI 성능 경쟁의 편중이 문제로 대두되고 있다",
             "falsifiable_news": "g", "confidence": "하"},
        ]
        raw = json.dumps({"hypotheses": hyps}, ensure_ascii=False)
        monkeypatch.setattr("hypothesis_generator.chat_completion", lambda **kw: raw)
        result = generate_hypotheses(SAMPLE_CANDIDATE, SAMPLE_ITEMS)
        one_lines = [h["one_line"] for h in result]
        assert not any("남반구" in ol for ol in one_lines), \
            f"Hypothesis with hallucinated entity should be dropped, got: {one_lines}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
