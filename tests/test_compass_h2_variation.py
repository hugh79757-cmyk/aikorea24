"""Tests for compass H2 variation — required/optional split + conditional rearrange."""
import re
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "threads"))

from pipeline.threads.compass import (
    H2_FLOW_PRESETS,
    H2_FLOW_REQUIRED,
    H2_FLOW_OPTIONAL,
    _rearrange_h2,
    _build_blog_pass2_user_prompt,
)

pytestmark = pytest.mark.unit


class TestH2RequiredOptional:
    """H2 split into required(3) + optional(2)."""

    def test_each_category_has_3_required(self):
        for cat, presets in H2_FLOW_PRESETS.items():
            required = H2_FLOW_REQUIRED[cat]
            assert len(required) == 3, (
                f"{cat}: required H2 수 이상, got {len(required)}"
            )
            assert required == presets[:3]

    def test_each_category_has_2_optional(self):
        for cat, presets in H2_FLOW_PRESETS.items():
            optional = H2_FLOW_OPTIONAL[cat]
            assert len(optional) == 2, (
                f"{cat}: optional H2 수 이상, got {len(optional)}"
            )
            assert optional == presets[3:]

    def test_required_plus_optional_equals_preset(self):
        for cat in H2_FLOW_PRESETS:
            combined = H2_FLOW_REQUIRED[cat] + H2_FLOW_OPTIONAL[cat]
            assert combined == H2_FLOW_PRESETS[cat]

    def test_h2_count_within_3_to_6(self):
        """All categories' presets have 5 items (3 required + 2 optional)."""
        for cat, presets in H2_FLOW_PRESETS.items():
            assert 3 <= len(presets) <= 6, (
                f"{cat}: H2 수 {len(presets)}가 3~6 범위 아님"
            )


class TestH2Rearrange:
    """Conditional rearrange rules."""

    def test_rearrange_pulls_compare_forward_with_competitor(self):
        compass = {
            "slot2_compare": "SK는 이미 운영 중이며 GS는 차별화됩니다",
            "slot4_outlook": "향후 전망입니다",
        }
        h2_flow = [
            "팩트: 핵심 사건과 수치",
            "비교: 경쟁사 대비 차별점",
            "맥락: 시장 트렌드와 배경",
            "전망: 향후 변수와 전망",
            "요약: 핵심 포인트 정리",
        ]
        result = _rearrange_h2(compass, h2_flow)
        # Compare section should move to front
        assert "비교" in result[0], (
            f"비교 섹션이 앞으로 당겨지지 않음: {result}"
        )

    def test_rearrange_no_change_without_conditions(self):
        compass = {
            "slot2_compare": "일반적 비교 내용입니다",
            "slot4_outlook": "안정적인 시장 환경이 예상됩니다",
        }
        h2_flow = [
            "팩트: 핵심 사건과 수치",
            "비교: 경쟁사 대비 차별점",
            "맥락: 시장 트렌드와 배경",
            "전망: 향후 변수와 전망",
            "요약: 핵심 포인트 정리",
        ]
        result = _rearrange_h2(compass, h2_flow)
        assert result == h2_flow, (
            f"조건 없음에도 변경됨: {result}"
        )

    def test_rearrange_does_not_exceed_original_length(self):
        compass = {
            "slot2_compare": "KT 대비 SK의 우위",
            "slot4_outlook": "불확실한 향후 전망",
        }
        h2_flow = [
            "팩트: 핵심 사건과 수치",
            "비교: 경쟁사 대비 차별점",
            "맥락: 시장 트렌드와 배경",
            "전망: 향후 변수와 전망",
            "요약: 핵심 포인트 정리",
        ]
        result = _rearrange_h2(compass, h2_flow)
        assert len(result) == len(h2_flow)

    def test_blog_prompt_contains_optional_h2_guideline(self):
        compass = {
            "category": "tech",
            "slot1_fact": "테스트",
            "slot2_compare": "비교",
            "slot3_context": "맥락",
            "slot4_outlook": "전망",
            "intro_style": "number_shock",
            "h2_flow": ["A", "B", "C"],
            "tone": "neutral_careful",
            "table_plan": None,
        }
        p = _build_blog_pass2_user_prompt(
            compass, "본문",
            h2_flow="현황과 주요 수치", intro_style="what_if", summary_format="bullet",
        )
        assert "slot1_fact" in p, "Compass JSON 필드 누락"
        assert "코드가 결정한 값" in p, "코드 결정 값 섹션 누락"


class TestH2BlogPromptFlexibility:
    """Blog prompt should allow H2 count 3~6."""

    def test_prompt_allows_3_h2s(self):
        """With only required H2s (3), prompt should still be valid."""
        compass = {
            "category": "tech",
            "slot1_fact": "테스트 사실",
            "slot2_compare": "비교 내용",
            "slot3_context": "맥락 설명",
            "slot4_outlook": "전망",
            "intro_style": "number_shock",
            "h2_flow": ["팩트", "비교", "맥락"],  # 3 only
            "tone": "neutral_careful",
            "table_plan": None,
        }
        p = _build_blog_pass2_user_prompt(
            compass, "본문",
            h2_flow="현황과 주요 수치", intro_style="what_if", summary_format="bullet",
        )
        assert "Compass JSON" in p
        assert "h2_flow" in p

    def test_prompt_with_full_5_h2s(self):
        compass = {
            "category": "tech",
            "slot1_fact": "테스트 사실",
            "slot2_compare": "비교 내용",
            "slot3_context": "맥락 설명",
            "slot4_outlook": "전망",
            "intro_style": "number_shock",
            "h2_flow": ["A", "B", "C", "D", "E"],
            "tone": "neutral_careful",
            "table_plan": None,
        }
        p = _build_blog_pass2_user_prompt(
            compass, "본문",
            h2_flow="현황과 주요 수치", intro_style="what_if", summary_format="bullet",
        )
        assert "slot1_fact" in p and "slot4_outlook" in p
