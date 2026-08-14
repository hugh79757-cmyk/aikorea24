"""Tests for pipeline integration — validate_final_output + detect_prompt_leak + writer chain."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "threads"))

from pipeline.threads.validator import validate_final_output, validate_no_foreign_language
from pipeline.threads.pitch import detect_prompt_leak, clean_leaked_prompt


class TestValidateFinalOutputIntegration:
    @pytest.mark.unit
    def test_real_cards_sample_1(self):
        """실제 카드 샘플 — 통과 (FORMAT_D: 5 콘텐츠 카드, 링크 별도)"""
        cards = [
            "소프트뱅크가 오픈AI 지분을 담보로 100억 달러 대출 제안을 다시 꺼냄.",
            "이번 제안에는 개인적인 채무 보증도 포함돼 있음.",
            "소프트뱅크는 2024년 오픈AI에 5억 달러를 투자했음.",
            "지분 담보 대출은 기업 가치가 높을 때 자금을 끌어쓰는 전략임.",
            "소프트뱅크가 AI 기업에 다시 베팅하는 신호로 해석됨.",
        ]
        ok, reason = validate_final_output(cards)
        assert ok is True
        assert reason == "OK"

    @pytest.mark.unit
    def test_real_cards_sample_2_chinese_detected(self):
        """실제 카드 샘플 — 한자 포함"""
        cards = [
            "소프트뱅크가 오픈AI 지분을 담보로 대출 제안을 다시 꺼냄.",
            "新加金融管理局의 초대 최고데이터책임자 출신임."
        ]
        ok, reason = validate_final_output(cards)
        assert ok is False
        assert "한자" in reason

    @pytest.mark.unit
    def test_real_cards_sample_3_prompt_leak(self):
        """실제 카드 샘플 — 프롬프트 노출"""
        cards = [
            "상식(A): AI 에이전트가 16%의 프리랜서 작업을 수행함.",
            "실제(B): 8개월 전 2.5%였음."
        ]
        ok, reason = validate_final_output(cards)
        assert ok is False
        assert "프롬프트" in reason


class TestDetectAndCleanPipeline:
    @pytest.mark.unit
    def test_detect_then_clean(self):
        """프롬프트 탐지 →삭제 파이프라인"""
        text = "상식(A): AI 에이전트가 16%의 프리랜서 작업을 수행함."
        leaked, reason = detect_prompt_leak(text)
        assert leaked is True
        cleaned = clean_leaked_prompt(text)
        leaked2, reason2 = detect_prompt_leak(cleaned)
        assert leaked2 is False

    @pytest.mark.unit
    def test_multiple_leaks_cleaned(self):
        """여러 프롬프트 라벨 동시 탐지 →삭제"""
        text = "상식(A): 첫 번째 문장.\nvs\n실제(B): 두 번째 문장."
        leaked, _ = detect_prompt_leak(text)
        assert leaked is True
        cleaned = clean_leaked_prompt(text)
        assert "상식(A):" not in cleaned
        assert "실제(B):" not in cleaned
        assert "vs" not in cleaned

    @pytest.mark.unit
    def test_clean_text_passes_through(self):
        """정상 텍스트 — 그대로 통과"""
        text = "소프트뱅크가 오픈AI 지분을 담보로 대출 제안을 다시 꺼냄."
        leaked, _ = detect_prompt_leak(text)
        assert leaked is False
        cleaned = clean_leaked_prompt(text)
        assert cleaned == text


class TestMultipleDefenseLayers:
    @pytest.mark.unit
    def test_layer_1_detect_prompt_leak(self):
        """1차 방어: detect_prompt_leak"""
        text = "스토리 파인더를 사용하여 이야기를 찾음."
        leaked, reason = detect_prompt_leak(text)
        assert leaked is True
        assert "프래그먼트" in reason

    @pytest.mark.unit
    def test_layer_2_validate_no_foreign_language(self):
        """2차 방어: validate_no_foreign_language"""
        cards = ["카드 한글만 있음."]
        ok, reason = validate_no_foreign_language(cards)
        assert ok is True

    @pytest.mark.unit
    def test_layer_3_validate_final_output(self):
        """3차 방어: validate_final_output"""
        cards = [
            "소프트뱅크가 오픈AI 지분을 담보로 대출 제안을 다시 꺼냄.",
            "이번 제안에는 개인적인 채무 보증도 포함돼 있음."
        ]
        ok, reason = validate_final_output(cards)
        assert ok is True

    @pytest.mark.unit
    def test_all_layers_block_bad_input(self):
        """모든 방어 레이어가 악성 입력 차단"""
        bad_card = "상식(A): AI 에이전트가 16%의 프리랜서 작업을 수행함."
        # 1차 방어
        leaked, _ = detect_prompt_leak(bad_card)
        assert leaked is True
        # 3차 방어
        ok, reason = validate_final_output([bad_card])
        assert ok is False
        assert "프롬프트" in reason
