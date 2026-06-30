"""Tests for pipeline.threads.validator — pure functions, no mocking needed."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline.threads.validator import (
    validate_cards, validate_year, validate_keywords,
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



