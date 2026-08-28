"""
tests/test_briefing_enricher.py
S3 브리핑 코멘트 어tenance 보강기 테스트

pytest -v tests/test_briefing_enricher.py
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from briefing_enricher import (
    select_candidates,
    select_hypotheses,
    _compose_prose,
    enrich_briefing,
)

# ── Fixture ──────────────────────────────────────────────
SAMPLE_ITEMS = json.loads(open(os.path.join(
    os.path.dirname(__file__), "fixtures", "briefing_sample_6.json"
), encoding="utf-8").read())

SAMPLE_ITEMS_WITH_COMMENT = [
    {**item, "comment": f"기존 코멘트 {item['id']}"}
    for item in SAMPLE_ITEMS
]

SAMPLE_CANDIDATES = [
    {
        "type": "A",
        "source_item_ids": ["1", "2"],
        "quote_1": "OpenAI는 오늘 GPT-5의 출시 일정을 공식 발표했다",
        "quote_2": "Google은 Gemini 3.5를 공개하며 AI 시장 경쟁을 한층 가속화했다",
        "gap_summary": "OpenAI와 Google이 동시에 신규 모델을 발표하며 AI 경쟁이 격화되고 있다.",
        "verification_path": "두 기업의 모델 비교 벤치마크 발표"
    },
    {
        "type": "B",
        "source_item_ids": ["3"],
        "quote_1": "유럽연합의 새로운 AI 규제가 시행되면서 유럽 내 AI 투자가 위축되고 있다",
        "quote_2": "AI 투자는 지속적으로 폭발적 증가세를 보일 것이다",
        "gap_summary": "유럽의 AI 규제 강화가 투자 위축을 초래하고 있다.",
        "verification_path": "유럽 AI 투자 데이터"
    },
    {
        "type": "A",
        "source_item_ids": ["4", "5"],
        "quote_1": "삼성전자가 AI 반도체 분야에 200억 달러 규모의 투자를 발표했다",
        "quote_2": "중국 정부가 AI 산업 규제를 대폭 완화하겠다고 발표했다",
        "gap_summary": "한국과 중국이 동시에 AI 반도체 투자를 확대하고 있다.",
        "verification_path": "양국 투자 집행 현황"
    },
]

SAMPLE_HYPOTHESES = [
    {
        "perspective": "시장 과열",
        "one_line": "두 기업의 동시 발표는 실제로는 시장 선점 경쟁에 불과하다",
        "falsifiable_news": "GPT-5 출시 후 실제 성능이 기대에 못 미치는 벤치마크 결과 발표",
        "confidence": "상",
    },
    {
        "perspective": "경쟁 구도",
        "one_line": "Gemini 3.5는 GPT-5에 대응하기 위한 급조된 발표일 수 있다",
        "falsifiable_news": "Google 내부 직원의 Gemini 3.5 완성도 불만 폭로",
        "confidence": "중",
    },
    {
        "perspective": "시간차",
        "one_line": "실제 출시까지 수개월이 남아 있어 현재 발표는 마케팅에 가깝다",
        "falsifiable_news": "GPT-5 출시 일정 연기 공지",
        "confidence": "하",
    },
]


# ── select_candidates ──────────────────────────────────────
class TestSelectCandidates:
    """후보 선별 테스트"""

    def test_different_types_selected(self):
        """type이 서로 다른 후보 우선 선택"""
        result = select_candidates(SAMPLE_CANDIDATES, max_n=2)
        assert len(result) == 2
        types = [c["type"] for c in result]
        assert types[0] == "A"
        assert types[1] == "B"

    def test_same_type_only_one(self):
        """같은 type 3개 입력 시 1개만 선택"""
        same_type = [
            {"type": "A", "source_item_ids": ["1"], "quote_1": "q1",
             "quote_2": "q2", "gap_summary": "g1", "verification_path": "v1"},
            {"type": "A", "source_item_ids": ["2"], "quote_1": "q3",
             "quote_2": "q4", "gap_summary": "g2", "verification_path": "v2"},
            {"type": "A", "source_item_ids": ["3"], "quote_1": "q5",
             "quote_2": "q6", "gap_summary": "g3", "verification_path": "v3"},
        ]
        result = select_candidates(same_type, max_n=2)
        assert len(result) == 1
        assert result[0]["type"] == "A"

    def test_order_preserved(self):
        """등장 순서 유지"""
        mixed = [
            {"type": "C", "source_item_ids": ["1"]},
            {"type": "A", "source_item_ids": ["2"]},
            {"type": "B", "source_item_ids": ["3"]},
        ]
        result = select_candidates(mixed, max_n=3)
        assert [c["type"] for c in result] == ["C", "A", "B"]

    def test_empty_input(self):
        """빈 입력"""
        assert select_candidates([]) == []


# ── select_hypotheses ──────────────────────────────────────
class TestSelectHypotheses:
    """가설 선별 테스트"""

    def test_confidence_sorting(self):
        """신뢰도 상 > 중 > 하 순 정렬"""
        result = select_hypotheses(SAMPLE_HYPOTHESES, max_n=3)
        assert len(result) == 3
        assert result[0]["confidence"] == "상"
        assert result[1]["confidence"] == "중"
        assert result[2]["confidence"] == "하"

    def test_high_med_sufficient(self):
        """상/중이 3개 이상이면 하 제외"""
        high_med_only = [
            {"confidence": "상", "one_line": "a"},
            {"confidence": "중", "one_line": "b"},
            {"confidence": "상", "one_line": "c"},
            {"confidence": "하", "one_line": "d"},
        ]
        result = select_hypotheses(high_med_only, max_n=3)
        assert len(result) == 3
        assert all(h["confidence"] in ("상", "중") for h in result)
        assert not any(h["one_line"] == "d" for h in result)

    def test_max_n_respected(self):
        """상한 max_n"""
        result = select_hypotheses(SAMPLE_HYPOTHESES, max_n=2)
        assert len(result) == 2

    def test_empty_input(self):
        """빈 입력"""
        assert select_hypotheses([]) == []


# ── _compose_prose ──────────────────────────────────────
class TestComposeProse:
    """산문 조립 테스트"""

    def test_no_newline(self):
        """출력에 줄바꿈 문자 없음"""
        prose = _compose_prose(SAMPLE_CANDIDATES[0], SAMPLE_HYPOTHESES[:3])
        assert "\n" not in prose
        assert "\r" not in prose

    def test_length_limit(self):
        """350자 상한"""
        # 긴 가설 생성
        long_hyps = [
            {"one_line": "매우 긴 가설 " * 20, "confidence": "상"},
            {"one_line": "또 다른 긴 가설 " * 20, "confidence": "중"},
        ]
        prose = _compose_prose(SAMPLE_CANDIDATES[0], long_hyps)
        assert len(prose) <= 350

    def test_single_hypothesis_connector(self):
        """가설 1개 → '한 가지로'"""
        prose = _compose_prose(SAMPLE_CANDIDATES[0], SAMPLE_HYPOTHESES[:1])
        assert "한 가지로" in prose

    def test_two_hypotheses_connector(self):
        """가설 2개 → '두 가지로'"""
        prose = _compose_prose(SAMPLE_CANDIDATES[0], SAMPLE_HYPOTHESES[:2])
        assert "두 가지로" in prose

    def test_three_hypotheses_connector(self):
        """가설 3개 → '몇 가지로'"""
        prose = _compose_prose(SAMPLE_CANDIDATES[0], SAMPLE_HYPOTHESES[:3])
        assert "몇 가지로" in prose

    def test_empty_gap(self):
        """gap_summary 없으면 빈 문자열"""
        assert _compose_prose({"gap_summary": ""}, SAMPLE_HYPOTHESES) == ""

    def test_empty_hypotheses(self):
        """가설 없으면 빈 문자열"""
        assert _compose_prose(SAMPLE_CANDIDATES[0], []) == ""

    def test_sentence_ends_with_period(self):
        """각 문장이 마침표로 끝남"""
        prose = _compose_prose(SAMPLE_CANDIDATES[0], SAMPLE_HYPOTHESES[:2])
        # 마지막 문장이 마침표로 끝나는지
        assert prose.rstrip().endswith(".")


# ── enrich_briefing ──────────────────────────────────────
class TestEnrichBriefing:
    """통합 테스트"""

    def test_s1_failure_preserves_original(self):
        """S1 실패 시 원본 comment 불변"""
        # find_abduction_candidates를 모의하여 빈 리스트 반환
        import briefing_enricher
        original = briefing_enricher.find_abduction_candidates
        briefing_enricher.find_abduction_candidates = lambda x: []
        try:
            result = enrich_briefing(SAMPLE_ITEMS_WITH_COMMENT, dry_run=True)
            for orig, res in zip(SAMPLE_ITEMS_WITH_COMMENT, result):
                assert orig["comment"] == res["comment"]
        finally:
            briefing_enricher.find_abduction_candidates = original

    def test_enrichment_appends(self):
        """정상 시 comment 뒤에 산문 부착"""
        import briefing_enricher
        original_find = briefing_enricher.find_abduction_candidates
        original_gen = briefing_enricher.generate_hypotheses
        briefing_enricher.find_abduction_candidates = lambda x: SAMPLE_CANDIDATES[:1]
        briefing_enricher.generate_hypotheses = lambda c, x: SAMPLE_HYPOTHESES[:2]
        try:
            result = enrich_briefing(SAMPLE_ITEMS_WITH_COMMENT, dry_run=True)
            target = next(r for r in result if r["id"] == 101)
            orig_comment = f"기존 코멘트 101"
            assert target["comment"].startswith(orig_comment)
            assert len(target["comment"]) > len(orig_comment)
        finally:
            briefing_enricher.find_abduction_candidates = original_find
            briefing_enricher.generate_hypotheses = original_gen

    def test_no_comment_field_handled(self):
        """comment 필드 없을 때도 동작"""
        import briefing_enricher
        items_no_comment = [{k: v for k, v in item.items() if k != "comment"}
                           for item in SAMPLE_ITEMS_WITH_COMMENT]
        original_find = briefing_enricher.find_abduction_candidates
        original_gen = briefing_enricher.generate_hypotheses
        briefing_enricher.find_abduction_candidates = lambda x: SAMPLE_CANDIDATES[:1]
        briefing_enricher.generate_hypotheses = lambda c, x: SAMPLE_HYPOTHESES[:2]
        try:
            result = enrich_briefing(items_no_comment, dry_run=True)
            target = next(r for r in result if r["id"] == 101)
            assert "이 지점은" in target.get("comment", "")
        finally:
            briefing_enricher.find_abduction_candidates = original_find
            briefing_enricher.generate_hypotheses = original_gen

    def test_empty_input(self):
        """빈 입력 → 빈 리스트"""
        assert enrich_briefing([], dry_run=True) == []

    def test_original_items_not_mutated(self):
        """원본 items 변경 없음"""
        import briefing_enricher
        original_find = briefing_enricher.find_abduction_candidates
        original_gen = briefing_enricher.generate_hypotheses
        briefing_enricher.find_abduction_candidates = lambda x: SAMPLE_CANDIDATES[:1]
        briefing_enricher.generate_hypotheses = lambda c, x: SAMPLE_HYPOTHESES[:2]
        orig_comments = {item["id"]: item.get("comment") for item in SAMPLE_ITEMS_WITH_COMMENT}
        try:
            _ = enrich_briefing(SAMPLE_ITEMS_WITH_COMMENT, dry_run=True)
            for item in SAMPLE_ITEMS_WITH_COMMENT:
                assert item.get("comment") == orig_comments[item["id"]]
        finally:
            briefing_enricher.find_abduction_candidates = original_find
            briefing_enricher.generate_hypotheses = original_gen
