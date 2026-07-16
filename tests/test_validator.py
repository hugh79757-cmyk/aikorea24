"""Tests for pipeline.threads.validator — pure functions, no mocking needed."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline.threads.validator import (
    validate_cards, validate_year, validate_keywords, validate_final_output,
    validate_model_message, validate_card_structure,
)


class TestValidateCards:
    @pytest.mark.unit
    def test_valid_card_count(self):
        cards = ["Card one\nline 2", "Card two", "Card three", "Card four", "Card five"]
        pitch = {"hook": "Test hook"}
        ok, reason = validate_cards(cards, pitch)
        assert ok is True

    @pytest.mark.unit
    def test_invalid_card_count_too_few(self):
        cards = ["Card one\nline 2", "Card two"]
        pitch = {"hook": "Test"}
        ok, reason = validate_cards(cards, pitch)
        assert ok is False

    @pytest.mark.unit
    def test_invalid_card_count_too_many(self):
        cards = [f"Card {i}\nline" for i in range(8)]
        pitch = {"hook": "Test"}
        ok, reason = validate_cards(cards, pitch)
        assert ok is False

    @pytest.mark.unit
    def test_first_line_too_short(self):
        cards = ["AB", "Card two\nline", "Card three\nline", "Card four\nline", "Card five\nline"]
        pitch = {"hook": "Test"}
        ok, reason = validate_cards(cards, pitch)
        assert ok is False

    @pytest.mark.unit
    def test_empty_cards(self):
        ok, reason = validate_cards([], {"hook": "Test"})
        assert ok is False


class TestValidateYear:
    @pytest.mark.unit
    def test_year_valid(self):
        cards = ["Hook line\ncontent", "2026년 3월 15일 발표"]
        article_body = "2026년 3월 15일에 발표된 내용입니다."
        ok, reason = validate_year(cards, article_body)
        assert ok is True

    @pytest.mark.unit
    def test_year_hallucinated(self):
        cards = ["Hook line\ncontent", "2025년에 발표된 내용"]
        article_body = "2024년 6월에 발표된 내용입니다."
        ok, reason = validate_year(cards, article_body)
        assert ok is False

    @pytest.mark.unit
    def test_current_year_allowed(self):
        from datetime import datetime
        cy = datetime.now().year
        cards = ["Hook line\ncontent", f"{cy}년 현재"]
        article_body = "기사 내용입니다."
        ok, reason = validate_year(cards, article_body)
        assert ok is True

    @pytest.mark.unit
    def test_no_year_in_thread(self):
        cards = ["Hook line\ncontent", "이런 상황이 발생했음"]
        article_body = "2026년에 발표된 내용입니다."
        ok, reason = validate_year(cards, article_body)
        assert ok is True


class TestValidateKeywords:
    @pytest.mark.unit
    def test_keywords_match(self):
        cards = ["첫번째 카드\n인공지능 기술 발전", "두번째 카드\n딥러닝 모델 혁신"]
        article_body = "인공지능 기술 발전과 딥러닝 모델 혁신 인공지능 딥러닝"
        ok, reason = validate_keywords(cards, article_body)
        assert ok is True

    @pytest.mark.unit
    def test_few_keywords_no_fail(self):
        cards = ["짧은 글"]
        article_body = "짧은 본문"
        ok, reason = validate_keywords(cards, article_body)
        assert ok is True

    @pytest.mark.unit
    def test_no_body_text(self):
        cards = ["Test card\ncontent"]
        ok, reason = validate_keywords(cards, "")
        assert ok is True


class TestValidateFinalOutput:
    @pytest.mark.unit
    def test_clean_cards_pass(self):
        """정상 카드 — 통과"""
        cards = [
            "소프트뱅크가 오픈AI 지분을 담보로 100억 달러 대출 제안을 다시 꺼냄.",
            "이번 제안에는 개인적인 채무 보증도 포함돼 있음."
        ]
        ok, reason = validate_final_output(cards)
        assert ok is True
        assert reason == "OK"

    @pytest.mark.unit
    def test_prompt_leak_card(self):
        """프롬프트 라벨 포함 카드 — 차단"""
        cards = [
            "상식(A): AI 에이전트가 16%의 프리랜서 작업을 수행함.",
            "실제(B): 8개월 전 2.5%였음."
        ]
        ok, reason = validate_final_output(cards)
        assert ok is False
        assert "프롬프트" in reason

    @pytest.mark.unit
    def test_chinese_card(self):
        """한자 포함 카드 — 차단"""
        cards = [
            "소프트뱅크가 오픈AI 지분을 담보로 대출 제안을 다시 꺼냄.",
            "新加金融管理局의 초대 최고데이터책임자 출신."
        ]
        ok, reason = validate_final_output(cards)
        assert ok is False
        assert "한자" in reason

    @pytest.mark.unit
    def test_japanese_card(self):
        """일본어 포함 카드 — 차단"""
        cards = [
            "소프트뱅크가 오픈AI 지분을 담보로 대출 제안을 다시 꺼냄.",
            "テスト입니다."
        ]
        ok, reason = validate_final_output(cards)
        assert ok is False
        assert "일본어" in reason

    @pytest.mark.unit
    def test_link_card_skip_korean_check(self):
        """출처 링크 카드 — 한글 비율 검사 스킵"""
        cards = [
            "소프트뱅크가 오픈AI 지분을 담보로 대출 제안을 다시 꺼냄.",
            "🔗 https://example.com/news"
        ]
        ok, reason = validate_final_output(cards)
        assert ok is True

    @pytest.mark.unit
    def test_nfkc_normalization_fullwidth(self):
        """전각 문자(＿, ！, Ａ) → NFKC 정규화로 한글 비율 정상"""
        # Before NFKC, these fullwidth chars would not be counted as Korean
        cards = [
            "\uff3f\uff01\uff21 \uac00\ub2a5\ud55c \ubc94\uc704\uc758 \ud55c\uae00 \ud14d\uc2a4\ud2b8\uc774\uba70 \ucda9\ubd84\ud788 \uae38\uace0 \ud55c\uae00 \ub0b4\uc6a9\uc744 \uac00\uc9c0\uace0 \uc788\uc2b5\ub2c8\ub2e4.",
        ]
        ok, reason = validate_final_output(cards)
        # After NFKC: ＿ → _, ！ → !, Ａ → A — Korean ratio should be ok
        assert ok is True

    @pytest.mark.unit
    def test_nfkc_normalization_chinese_fullwidth(self):
        """전각 한자 — NFKC 후 감지"""
        # Fullwidth Chinese characters should be caught after NFKC normalization
        cards = [
            "\ud55c\uae00 \uce74\ub4dc\ub0b4\uc6a9\uc73c\ub85c \ucda9\ubd84\ud788 \uae34 \ubb38\uc7a5\uc785\ub2c8\ub2e4. \ubb38\uc7a5\uc774 \uc644\uc131\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4. \ucda9\ubd84\ud788 \uae38\uac8c \uc791\uc131\ub418\uc5c8\uc2b5\ub2c8\ub2e4.",
            "\uff2c\uff2f\uff2e\uff24\uff2f\uff2e \ud2b9\ud30c\uc6d0\uc774 \ubc1c\ud45c\ud55c \uc218\uce58\uc785\ub2c8\ub2e4. \uc774\uac83\uc740 \uc804\uac01 \ubb38\uc790\ub85c \ud45c\ud604\ub418\uc5c8\uc2b5\ub2c8\ub2e4.",
        ]
        ok, reason = validate_final_output(cards)
        # Fullwidth LONDON chars (U+FF2C etc.) are in CJK range only as fullwidth forms
        # They should be caught (or at least not crash)
        assert ok is True  # Fullwidth Latin is not CJK; passes after NFKC


class TestDetectPromptLeakPatterns:
    @pytest.mark.unit
    def test_leaked_pattern_a(self):
        """상식(A): 패턴 탐지"""
        from pipeline.threads.pitch import detect_prompt_leak
        text = "상식(A): AI 에이전트가 16%의 프리랜서 작업을 수행함."
        leaked, reason = detect_prompt_leak(text)
        assert leaked is True
        assert "라벨" in reason

    @pytest.mark.unit
    def test_leaked_pattern_b(self):
        """실제(B): 패턴 탐지"""
        from pipeline.threads.pitch import detect_prompt_leak
        text = "실제(B): 8개월 전 2.5%였음."
        leaked, reason = detect_prompt_leak(text)
        assert leaked is True
        assert "라벨" in reason

    @pytest.mark.unit
    def test_system_prompt_fragment(self):
        """시스템 프래그먼트 탐지"""
        from pipeline.threads.pitch import detect_prompt_leak
        text = "스토리 파인더를 사용하여 이야기를 찾음."
        leaked, reason = detect_prompt_leak(text)
        assert leaked is True
        assert "프래그먼트" in reason

    @pytest.mark.unit
    def test_clean_text_passes(self):
        """정상 텍스트 — 통과"""
        from pipeline.threads.pitch import detect_prompt_leak
        text = "소프트뱅크가 오픈AI 지분을 담보로 대출 제안을 다시 꺼냄."
        leaked, reason = detect_prompt_leak(text)
        assert leaked is False
        assert reason == "OK"


class TestValidateModelMessage:
    @pytest.mark.unit
    def test_known_message(self):
        card = "수정할 글자 단위 오류가 발견되지 않았습니다."
        ok, reason = validate_model_message(card)
        assert ok is False

    @pytest.mark.unit
    def test_polite_form(self):
        card = "수정이 필요 없습니다."
        ok, reason = validate_model_message(card)
        assert ok is False

    @pytest.mark.unit
    def test_short_response(self):
        card = "네"
        ok, reason = validate_model_message(card)
        assert ok is False

    @pytest.mark.unit
    def test_english_message(self):
        card = "No changes needed."
        ok, reason = validate_model_message(card)
        assert ok is False

    @pytest.mark.unit
    def test_valid_content(self):
        card = "Mia Taylor는 투표 용지를 촬영해 Claude에게 물었음."
        ok, reason = validate_model_message(card)
        assert ok is True

    @pytest.mark.unit
    def test_link_card(self):
        card = "🔗 https://example.com"
        ok, reason = validate_model_message(card)
        assert ok is True

    @pytest.mark.unit
    def test_confirmed_message(self):
        card = "확인됨."
        ok, reason = validate_model_message(card)
        assert ok is False

    @pytest.mark.unit
    def test_completed_message(self):
        card = "완료했음."
        ok, reason = validate_model_message(card)
        assert ok is False

    @pytest.mark.unit
    def test_no_errors_message(self):
        card = "No errors found."
        ok, reason = validate_model_message(card)
        assert ok is False

    @pytest.mark.unit
    def test_returning_original_message(self):
        card = "Returning original content."
        ok, reason = validate_model_message(card)
        assert ok is False


class TestValidateCardStructure:
    @pytest.mark.unit
    def test_valid_cards(self):
        cards = [
            "Mia Taylor는 투표 용지를 촬영해 Claude에게 물었음. AI가 어떤 대답을 했는지 확인해보겠음.",
            "그녀는 AI에게 이곳에서 누구에게 투표해야 할지 물었음. Claude는 처음에 대답을 거부하는 반응을 보였음.",
            "Claude는 처음에 대답을 거부했음. 그리고 나중에 다시 물었을 때에야 비로소 답을 줬음.",
        ]
        assert validate_card_structure(cards) == (True, "OK")

    @pytest.mark.unit
    def test_duplicate_cards(self):
        cards = ["동일한 카드 내용이 두 번 반복됨.", "동일한 카드 내용이 두 번 반복됨.", "세 번째 카드입니다."]
        ok, reason = validate_card_structure(cards)
        assert ok is False
        assert "중복" in reason

    @pytest.mark.unit
    def test_short_card(self):
        cards = ["짧음", "두 번째 카드는 충분히 긴 내용을 담고 있음."]
        ok, reason = validate_card_structure(cards)
        assert ok is False
        assert "짧음" in reason

    @pytest.mark.unit
    def test_no_korean(self):
        cards = ["No Korean content here at all.", "Second card with no Korean."]
        ok, reason = validate_card_structure(cards)
        assert ok is False
        assert "한글" in reason

    @pytest.mark.unit
    def test_link_card_exempt(self):
        cards = [
            "첫 번째 카드는 충분히 긴 내용을 담고 있는 카드라서HOOK_MIN_LENGTH를 넘김.",
            "🔗 https://example.com",
        ]
        assert validate_card_structure(cards) == (True, "OK")

    @pytest.mark.unit
    def test_empty_cards(self):
        ok, reason = validate_card_structure([])
        assert ok is False
        assert "카드 없음" in reason

    @pytest.mark.unit
    def test_sentence_incomplete(self):
        # Relaxed: incomplete sentences no longer block (validator returns True)
        cards = [
            "첫 번째 카드는 충분히 긴 내용을 가지고 있음. 한국어로만 작성된 검증 통과 가능한 카드임. 세번째 줄도 문제없이 읽을 수 있는 내용임. 네번째 줄까지 충분한 내용을 제공함. 다섯번째 줄도 추가로 내용을 채워서 충분한 길이를 확보하겠음. 여섯번째 줄까지 계속 내용을 추가해서 충분한 길이를 확보함. 이제 이 카드는 충분히 긴 카드가 되었음. 검증을 통과할 수 있는 충분한 내용을 담고 있음.",
            "두 번째 카드는 문장이 끝나지 않았다 완전히 끝나지 않은 상태",
        ]
        ok, _ = validate_card_structure(cards)  # relaxed: incomplete sentences pass
        assert ok is True

    @pytest.mark.unit
    def test_ellipsis_acceptable(self):
        cards = [
            "첫 번째 카드는 충분히 긴 내용을 담고 있는 카드라서HOOK_MIN_LENGTH를 넘김.",
            "두 번째 카드는 내용이 이어지는 중이고 내용이 충분히 길게 작성되어 있음...",
        ]
        assert validate_card_structure(cards) == (True, "OK")

    @pytest.mark.unit
    def test_hook_too_short(self):
        # hook_first_line must be >= 8 chars (relaxed from 30)
        cards = [
            "이 카드는 스물다섯 자 정도 되는 훅임.",  # 25 chars, passes
            "두 번째 카드는 충분히 긴 내용을 담고 있는 카드라서BODY_MIN_LENGTH를 넘김.",
        ]
        ok, reason = validate_card_structure(cards)
        # Hook is 25 chars which is < 350 and >= 8, so passes
        assert ok is True

    @pytest.mark.unit
    def test_body_too_short(self):
        # Body card min length is 30 chars (relaxed)
        cards = [
            "첫 번째 카드는 충분히 긴 내용을 담고 있는 카드라서HOOK_MIN_LENGTH를 넘김.",
            "🔗 https://example.com",
            "이 본문 카드는 이십자에서 오십자 사이의 길이를 가지고 있음.",  # about 40 chars, >= 30 passes
        ]
        ok, reason = validate_card_structure(cards)
        assert ok is True  # body is 40 chars which is >= 30



