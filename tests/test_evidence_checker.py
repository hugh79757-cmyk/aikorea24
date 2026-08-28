#!/usr/bin/env python3
"""evidence_checker 단위 테스트"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from evidence_checker import (
    _extract_words, check_evidence, check_gap_fidelity,
    _check_specific_numbers, _check_entities, _check_absolute_expressions,
)


class TestExtractWords:
    def test_korean_words(self):
        words = _extract_words("OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다")
        assert "OpenAI" in words
        assert "공개" in words or "공개하며" in words

    def test_english_words(self):
        words = _extract_words("The quick brown fox")
        assert "The" in words
        assert "quick" in words

    def test_numbers(self):
        words = _extract_words("GPT-5와 40% 감소")
        assert "GPT" in words or "GPT-5" in words
        assert "40" in words

    def test_empty(self):
        assert _extract_words("") == []

    def test_stopwords_removed(self):
        words = _extract_words("것이다 그리고 또한 통해")
        # 불용어가 제거되어야 함
        for sw in ["것이다", "그리고", "통해"]:
            assert sw not in words


class TestCheckSpecificNumbers:
    def test_matching_number(self):
        claim = "삼성의 200억 달러 투자"
        source = "삼성전자가 200억 달러 규모의 투자를 발표했다."
        assert _check_specific_numbers(claim, source) == []

    def test_missing_number(self):
        claim = "2년간의 유예 기간"
        source = "유럽에서 AI 규제를 강화했다."
        missing = _check_specific_numbers(claim, source)
        assert "2년" in missing

    def test_no_numbers(self):
        assert _check_specific_numbers("삼성의 투자", "삼성의 투자") == []

    def test_partial_number_match(self):
        # "200억" is in "200억 달러" — should match
        claim = "200억 규모"
        source = "200억 달러 규모의 투자"
        assert _check_specific_numbers(claim, source) == []


class TestCheckEntities:
    def test_matching_entity(self):
        claim = "유럽에서 규제를 강화했다"
        source = "유럽연합이 새로운 AI 규제를 발표했다."
        assert _check_entities(claim, source) == []

    def test_missing_entity(self):
        claim = "남반구 시장에서 성장했다"
        source = "유럽에서 규제를 강화했다."
        missing = _check_entities(claim, source)
        assert "남반구" in missing

    def test_entity_in_source(self):
        claim = "중국 정부가 규제를 완화했다"
        source = "중국 정부가 AI 산업 규제를 대폭 완화하겠다고 발표했다."
        assert _check_entities(claim, source) == []

    def test_no_entities(self):
        assert _check_entities("투자가 위축되고 있다", "투자가 위축되고 있다.") == []


class TestCheckAbsoluteExpressions:
    def test_absolute_in_claim_not_source(self):
        missing = _check_absolute_expressions(
            "표준을 완전히 장악할 것이다",
            "표준을 장악할 것이다"
        )
        assert "완전히" in missing

    def test_absolute_in_both(self):
        missing = _check_absolute_expressions(
            "표준을 완전히 장악할 것이다",
            "이 기업은 완전히 독점을 이루었다"
        )
        assert "완전히" not in missing

    def test_no_absolute(self):
        missing = _check_absolute_expressions(
            "투자가 위축되고 있다",
            "투자가 위축되고 있다."
        )
        assert missing == []


class TestCheckEvidence:
    def test_supported(self):
        claim = "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다"
        source = "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다. 벤치마크에서 기존 모델을 크게 앞질렀다고 밝혔다."
        assert check_evidence(claim, source) is True

    def test_unsupported(self):
        claim = "수백 건의 자율형 AI 에이전트 보안 사고가 발생하고 있다"
        source = "오픈AI와 구글 등은 AI 보안을 위해 공공과 민간의 협력을 촉구하고 있다"
        assert check_evidence(claim, source) is False

    def test_morphological_variant(self):
        claim = "OpenAI가 GPT-5를 공개하며 성능을 주장했다"
        source = "OpenAI가 GPT-5를 공개했다. 성능을 주장한다."
        assert check_evidence(claim, source) is True

    def test_empty_claim(self):
        assert check_evidence("", "source text") is False

    def test_empty_source(self):
        assert check_evidence("claim text", "") is False

    def test_partial_hallucination_rejected(self):
        """삼성의 투자로 수백 개의 신규 일자리가 창출될 것이다 → 폐기"""
        claim = "삼성의 투자로 수백 개의 신규 일자리가 창출될 것이다"
        source = "삼성전자가 AI 반도체 분야에 200억 달러 규모의 투자를 발표했다. HBM4 및 차세대 GPU용 메모리 개발에 집중할 예정이며, 2027년까지 제조 역량을 2배로 확대할 계획이다."
        # "수백 개" — 원문에 없는 수치 패턴 → 폐기
        assert check_evidence(claim, source) is False

    def test_specific_number_rejected(self):
        """원문에 없는 '2년 유예' 포함 가설 → 폐기"""
        claim = "유럽연합이 AI 법의 핵심 조항 집행을 2년 유예하는 수정안을 통과시킨다"
        source = "유럽연합의 새로운 AI 규제가 시행되면서 유럽 내 AI 투자가 위축되고 있다."
        assert check_evidence(claim, source) is False

    def test_missing_entity_rejected(self):
        """원문에 없는 '남반구 시장' 포함 가설 → 폐기"""
        claim = "토종 AI 모델들이 남반구 시장에서 점유율을 대체한다"
        source = "중국 정부가 AI 산업 규제를 대폭 완화하겠다고 발표했다."
        assert check_evidence(claim, source) is False

    def test_inference_without_marker_still_checked(self):
        """추론 표현 유무와 무관하게 근거 검증은 동일하게 적용"""
        claim = "유럽연합의 AI 규제가 유럽 내 투자에 영향을 미치고 중국은 규제를 완화한다"
        source = "유럽연합의 새로운 AI 규제가 시행되면서 유럽 내 AI 투자가 위축되고 있다. 중국 정부가 AI 산업 규제를 대폭 완화하겠다고 발표했다."
        assert check_evidence(claim, source) is True

    def test_threshold_enforced(self):
        """threshold=0.4, min_matched=3 적용 — 부분 환각은 여전히 폐기"""
        claim = "삼성의 투자로 수백 개의 신규 일자리가 창출될 것이다"
        source = "삼성전자가 AI 반도체 분야에 200억 달러 규모의 투자를 발표했다. HBM4 및 차세대 GPU용 메모리 개발에 집중할 예정이며, 2027년까지 제조 역량을 2배로 확대할 계획이다."
        # "수백", "개의" 등 원문에 없는 수치 → 폐기
        assert check_evidence(claim, source, threshold=0.4, min_matched=3) is False

    def test_min_matched_enforced(self):
        """범용 단어 2개만 매칭 → min_matched=3 미달로 폐기"""
        claim = "삼성의 투자로 일자리가 창출될 것이다"
        source = "삼성전자가 AI 반도체 분야에 투자를 발표했다."
        # "삼성", "투자" 매칭 = 2 < min_matched=3
        assert check_evidence(claim, source, threshold=0.4, min_matched=3) is False


class TestCheckGapFidelity:
    def test_faithful_gap(self):
        gap = "OpenAI와 구글이 대등하다고 주장하여 양사의 주장을 동시에 수용하기 어렵다"
        q1 = "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다"
        q2 = "구글은 Gemini 2.0이 GPT-5와 대등한 성능을 보인다고 발표했다"
        source = "OpenAI가 GPT-5를 공개했다. 구글은 Gemini 2.0이 대등하다고 발표했다."
        assert check_gap_fidelity(gap, q1, q2, source) is True

    def test_hallucinated_gap(self):
        gap = "실제 현장에서는 수백 건의 보안 사고가 발생하고 있다"
        q1 = "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다"
        q2 = "구글은 Gemini 2.0이 GPT-5와 대등한 성능을 보인다고 발표했다"
        source = "AI 보안을 위해 공공과 민간의 협력을 촉구하고 있다"
        assert check_gap_fidelity(gap, q1, q2, source) is False

    def test_empty_gap(self):
        assert check_gap_fidelity("", "q1", "q2", "source") is True

    def test_gap_only_from_quotes(self):
        gap = "OpenAI는 성능 대폭 향상을 주장한다"
        q1 = "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다"
        q2 = ""
        source = ""
        assert check_gap_fidelity(gap, q1, q2, source) is True

    def test_gap_with_source_support(self):
        gap = "유럽연합의 AI 모델 규제안이 발표되었다"
        q1 = "유럽연합이 AI 모델에 대한 엄격한 규제안을 발표했다"
        q2 = ""
        source = "유럽연합이 AI 모델에 대한 엄격한 규제안을 발표했다. 기업들은 규제가 혁신을 저해한다고 반발했다."
        assert check_gap_fidelity(gap, q1, q2, source) is True

    def test_gap_with_specific_number_missing(self):
        """gap_summary에 원문에 없는 '450억' 수치 포함 → 폐기"""
        gap = "유럽의 AI 투자가 450억 달러 감소했다"
        q1 = "유럽에서 AI 규제가 강화되어 투자가 위축되고 있다."
        q2 = ""
        source = "유럽에서 AI 규제가 강화되어 투자가 위축되고 있다."
        assert check_gap_fidelity(gap, q1, q2, source) is False

    def test_gap_with_entity_missing(self):
        """gap_summary에 원문에 없는 '남반구' 포함 → 폐기"""
        gap = "남반구 시장에서 AI 규제가 완화되고 있다"
        q1 = "AI 산업 규제를 완화하겠다고 발표했다."
        q2 = ""
        source = "AI 산업 규제를 완화하겠다고 발표했다."
        assert check_gap_fidelity(gap, q1, q2, source) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
