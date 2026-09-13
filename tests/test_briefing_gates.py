"""3중 방어 게이트 테스트 — auto_briefing (생성 직후 / 저장 직전 / 저장 후 read-back)

각 층위별 독립 검증 + 오탐 방지(한국어 + 영어 제품명 케이스).
production code 수정 없이 통과해야 함.
"""
from unittest.mock import patch

import pytest

import auto_briefing


# ============================================================
# 순수 검증기 — validate_briefing_comment / looks_korean
# ============================================================

class TestValidateBriefingComment:
    def test_pure_korean_passes(self):
        ok, reason = auto_briefing.validate_briefing_comment(
            "오픈AI가 새 모델을 공개하며 시장 경쟁이 한층 치열해졌다."
        )
        assert ok, reason

    def test_korean_with_english_product_names_passes(self):
        """오탐 방지 핵심 케이스 — 제품명 영어 포함 한국어 코멘트는 통과해야 함"""
        ok, reason = auto_briefing.validate_briefing_comment(
            "OpenAI가 GPT-6를 공개했다. 업계는 Google Gemini와의 경쟁이 더 치열해질 것으로 전망한다."
        )
        assert ok, reason

    def test_english_comment_fails(self):
        ok, reason = auto_briefing.validate_briefing_comment(
            "Sure, here is a comment about AI datacenters and their impact."
        )
        assert not ok

    def test_prompt_template_mirroring_fails(self):
        ok, reason = auto_briefing.validate_briefing_comment(
            "제목: 오픈AI 발표\n출처: TechCrunch\n내용: GPT-6 공개\n코멘트:"
        )
        assert not ok

    def test_empty_fails(self):
        ok, _ = auto_briefing.validate_briefing_comment("")
        assert not ok


class TestLooksKorean:
    def test_korean_true(self):
        assert auto_briefing.looks_korean("GPT-6 공개 임박")

    def test_english_false(self):
        assert not auto_briefing.looks_korean("GPT-6 launch imminent")

    def test_empty_false(self):
        assert not auto_briefing.looks_korean("")


# ============================================================
# 1차 게이트 — generate_comment 재생성 루프
# ============================================================

class TestGate1GenerateComment:
    def test_english_then_korean_returns_korean(self):
        """영어 2회 → 한국어 순 반환 시 최종 한국어 코멘트 반환"""
        responses = iter([
            "Sure, here is a comment about the news.",
            "This is another English response from the model.",
            "오픈AI가 GPT-6를 공개하며 시장 경쟁이 치열해졌다.",
        ])
        with patch.object(auto_briefing, "chat_completion", side_effect=lambda **kw: next(responses)):
            result = auto_briefing.generate_comment(
                {"title": "OpenAI GPT-6", "description": "desc", "source": "TechCrunch"}
            )
        assert result is not None
        assert "오픈AI" in result

    def test_english_only_returns_none(self):
        """영어만 3회 반환 시 None (comment='')"""
        with patch.object(
            auto_briefing, "chat_completion",
            side_effect=lambda **kw: "Sure, here is an English comment.",
        ):
            result = auto_briefing.generate_comment(
                {"title": "AI news", "description": "desc", "source": "TechCrunch"}
            )
        assert result is None


# ============================================================
# 2차 게이트 — save_briefing INSERT 직전 릭 스킵
# ============================================================

class TestGate2SaveBriefing:
    def _make_data(self, comment):
        return {
            "date": "2026-09-13",
            "intro": "오늘의 브리핑",
            "status": "published",
            "items": [
                {"news_id": 1, "sort_order": 1, "comment": comment},
            ],
        }

    def test_leaking_comment_skipped(self):
        """릭 코멘트 아이템은 INSERT 스킵 (d1_execute 미호출)"""
        executed = []
        with patch.object(auto_briefing, "d1_query", side_effect=[
            [],  # existing briefings
            [{"id": 77}],  # briefing id lookup
        ]), patch.object(
            auto_briefing, "d1_execute", side_effect=lambda sql: executed.append(sql) or True,
        ):
            auto_briefing.save_briefing(self._make_data("제목: 테스트\n코멘트:"))
        item_inserts = [s for s in executed if "briefing_items" in s]
        assert item_inserts == []

    def test_clean_comment_inserted(self):
        """정상 한국어 코멘트는 INSERT 수행"""
        executed = []
        with patch.object(auto_briefing, "d1_query", side_effect=[
            [],
            [{"id": 77}],
        ]), patch.object(
            auto_briefing, "d1_execute", side_effect=lambda sql: executed.append(sql) or True,
        ):
            auto_briefing.save_briefing(
                self._make_data("오픈AI가 새 모델을 공개하며 경쟁이 치열해졌다.")
            )
        item_inserts = [s for s in executed if "briefing_items" in s]
        assert len(item_inserts) == 1


# ============================================================
# 3차 게이트 — verify_briefing_items read-back 검증
# ============================================================

class TestGate3VerifyBriefingItems:
    def test_leaking_row_detected_and_cleared(self):
        """릭 row 1건 포함 D1 조회 → 감지 1, UPDATE 1"""
        rows = [
            {"id": 101, "comment": "오픈AI가 GPT-6를 공개하며 시장이 주목하고 있다."},
            {"id": 102, "comment": "제목: 테스트\n출처: TechCrunch\n코멘트:"},
        ]
        executed = []
        with patch.object(auto_briefing, "d1_query", return_value=rows), patch.object(
            auto_briefing, "d1_execute", side_effect=lambda sql: executed.append(sql) or True,
        ):
            count = auto_briefing.verify_briefing_items(50)
        assert count == 1
        updates = [s for s in executed if "UPDATE" in s and "comment=''" in s]
        assert len(updates) == 1
        assert "id=102" in updates[0]

    def test_all_clean_returns_zero(self):
        rows = [
            {"id": 201, "comment": "구글이 새 AI 칩을 발표했다."},
            {"id": 202, "comment": "엔비디아 주가가 급등하며 시장이 반응하고 있다."},
        ]
        executed = []
        with patch.object(auto_briefing, "d1_query", return_value=rows), patch.object(
            auto_briefing, "d1_execute", side_effect=lambda sql: executed.append(sql) or True,
        ):
            count = auto_briefing.verify_briefing_items(51)
        assert count == 0
        assert executed == []

    def test_d1_exception_returns_zero(self):
        """D1 예외 시 0 반환 — 저장 흐름 영향 없음"""
        with patch.object(auto_briefing, "d1_query", side_effect=Exception("D1 down")):
            count = auto_briefing.verify_briefing_items(52)
        assert count == 0


# ============================================================
# 제목 언어 게이트 (4b) — ensure_korean_title
# ============================================================

class TestEnsureKoreanTitle:
    def test_korean_title_untouched(self):
        """한글 제목은 LLM/D1 호출 없이 통과"""
        art = {"id": 1, "title": "오픈AI, GPT-6 공개 예고"}
        with patch.object(auto_briefing, "chat_completion") as mc, patch.object(
            auto_briefing, "d1_execute"
        ) as me:
            result = auto_briefing.ensure_korean_title(art)
        assert result == "오픈AI, GPT-6 공개 예고"
        mc.assert_not_called()
        me.assert_not_called()

    def test_english_title_translated_and_d1_updated(self):
        """영어 제목 → 번역 적용 + D1 UPDATE"""
        art = {"id": 50155, "title": "Steve Jones on the pros and cons of AI datacentres"}
        executed = []
        with patch.object(
            auto_briefing, "chat_completion",
            return_value="스티브 존스가 본 AI 데이터센터의 장단점",
        ), patch.object(
            auto_briefing, "d1_execute", side_effect=lambda sql: executed.append(sql) or True,
        ):
            result = auto_briefing.ensure_korean_title(art)
        assert result == "스티브 존스가 본 AI 데이터센터의 장단점"
        assert art["title"] == result
        assert len(executed) == 1
        assert "UPDATE news" in executed[0]
        assert "original_title" in executed[0]

    def test_translation_failure_keeps_original(self):
        """번역 실패(한글 없는 응답) 시 원문 유지, D1 UPDATE 없음"""
        art = {"id": 50235, "title": "GPT-6 Astra appears to show a step change"}
        with patch.object(
            auto_briefing, "chat_completion", return_value="still English response"
        ), patch.object(auto_briefing, "d1_execute") as me:
            result = auto_briefing.ensure_korean_title(art)
        assert result == "GPT-6 Astra appears to show a step change"
        me.assert_not_called()

    def test_translation_exception_keeps_original(self):
        """LLM 예외 시 원문 유지 — 파이프라인 중단 없음"""
        art = {"id": 50269, "title": "Conversations that AIs are having in the office"}
        with patch.object(
            auto_briefing, "chat_completion", side_effect=Exception("LLM down")
        ), patch.object(auto_briefing, "d1_execute") as me:
            result = auto_briefing.ensure_korean_title(art)
        assert result == "Conversations that AIs are having in the office"
        me.assert_not_called()
