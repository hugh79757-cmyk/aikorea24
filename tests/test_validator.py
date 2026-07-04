"""Tests for pipeline.threads.validator — pure functions, no mocking needed."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline.threads.validator import (
    validate_cards, validate_year, validate_keywords, validate_final_output,
)


class TestValidateCards:
    @pytest.mark.unit
    def test_valid_card_count(self):
        cards = ["Card one\nline 2", "Card two", "Card three", "Card four", "Card five"]
        pitch = {"hook": "Test hook"}
        assert validate_cards(cards, pitch) is True

    @pytest.mark.unit
    def test_invalid_card_count_too_few(self):
        cards = ["Card one\nline 2", "Card two"]
        pitch = {"hook": "Test"}
        assert validate_cards(cards, pitch) is False

    @pytest.mark.unit
    def test_invalid_card_count_too_many(self):
        cards = [f"Card {i}\nline" for i in range(8)]
        pitch = {"hook": "Test"}
        assert validate_cards(cards, pitch) is False

    @pytest.mark.unit
    def test_first_line_too_short(self):
        cards = ["AB", "Card two\nline", "Card three\nline", "Card four\nline", "Card five\nline"]
        pitch = {"hook": "Test"}
        assert validate_cards(cards, pitch) is False

    @pytest.mark.unit
    def test_empty_cards(self):
        assert validate_cards([], {"hook": "Test"}) is False


class TestValidateYear:
    @pytest.mark.unit
    def test_year_valid(self):
        cards = ["Hook line\ncontent", "2026년 3월 15일 발표"]
        article_body = "2026년 3월 15일에 발표된 내용입니다."
        assert validate_year(cards, article_body) is True

    @pytest.mark.unit
    def test_year_hallucinated(self):
        cards = ["Hook line\ncontent", "2025년에 발표된 내용"]
        article_body = "2024년 6월에 발표된 내용입니다."
        assert validate_year(cards, article_body) is False

    @pytest.mark.unit
    def test_current_year_allowed(self):
        from datetime import datetime
        cy = datetime.now().year
        cards = ["Hook line\ncontent", f"{cy}년 현재"]
        article_body = "기사 내용입니다."
        assert validate_year(cards, article_body) is True

    @pytest.mark.unit
    def test_no_year_in_thread(self):
        cards = ["Hook line\ncontent", "이런 상황이 발생했음"]
        article_body = "2026년에 발표된 내용입니다."
        assert validate_year(cards, article_body) is True


class TestValidateKeywords:
    @pytest.mark.unit
    def test_keywords_match(self):
        cards = ["첫번째 카드\n인공지능 기술 발전", "두번째 카드\n딥러닝 모델 혁신"]
        article_body = "인공지능 기술 발전과 딥러닝 모델 혁신 인공지능 딥러닝"
        assert validate_keywords(cards, article_body) is True

    @pytest.mark.unit
    def test_few_keywords_no_fail(self):
        cards = ["짧은 글"]
        article_body = "짧은 본문"
        assert validate_keywords(cards, article_body) is True

    @pytest.mark.unit
    def test_no_body_text(self):
        cards = ["Test card\ncontent"]
        assert validate_keywords(cards, "") is True


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



