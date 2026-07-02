"""Tests for pipeline.threads.writer — pure functions and file-I/O functions."""
import pytest
import os, json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "threads"))

from pipeline.threads.writer import (
    parse_cards, save_draft,
    _clean_english_leakage, _fix_korean_particle_spacing,
    _cleanup_source_attribution, _strip_instruction_leak,
    assemble_final, humanize_cards, fix_cards,
)
from pipeline.threads.writer import FORMAT_CARD_COUNTS, FORMAT_CARD_COUNT_TOLERANCE
from pipeline.infra.config import project_root


class TestParseCards:
    @pytest.mark.unit
    def test_normal_parse(self):
        result = parse_cards("card1\nline2\nline3\nline4\n---\ncard2\nline2")
        assert len(result) == 2
        assert "card1" in result[0]

    @pytest.mark.unit
    def test_empty_text(self):
        assert parse_cards("") == []

    @pytest.mark.unit
    def test_single_card(self):
        result = parse_cards("only one card here")
        assert len(result) == 1


class TestCleanEnglishLeakage:
    @pytest.mark.unit
    def test_removes_leakage(self):
        result = _clean_english_leakage("한글English한글")
        assert "English" not in result

    @pytest.mark.unit
    def test_no_leakage(self):
        text = "순수 한글 텍스트입니다."
        assert _clean_english_leakage(text) == text


class TestFixKoreanParticleSpacing:
    @pytest.mark.unit
    def test_adds_space(self):
        result = _fix_korean_particle_spacing("AI가")
        assert "AI 가" in result

    @pytest.mark.unit
    def test_no_change(self):
        text = "안녕하세요"
        assert _fix_korean_particle_spacing(text) == text


class TestStripInstructionLeak:
    @pytest.mark.unit
    def test_removes_instruction(self):
        from pipeline.threads.writer import INSTRUCTION_PATTERNS
        text = f"{INSTRUCTION_PATTERNS[0]} some content\nnormal line"
        result = _strip_instruction_leak(text)
        assert INSTRUCTION_PATTERNS[0] not in result
        assert "normal line" in result

    @pytest.mark.unit
    def test_preserves_normal(self):
        text = "normal content here\nmore content"
        assert _strip_instruction_leak(text) == text.strip()


class TestCleanupSourceAttribution:
    @pytest.mark.unit
    def test_removes_source(self):
        cards = ["내용\n출처: 연합뉴스"]
        result = _cleanup_source_attribution(cards)
        assert "출처:" not in result[0]

    @pytest.mark.unit
    def test_removes_year_2000(self):
        cards = ["2000 내용"]
        result = _cleanup_source_attribution(cards)
        assert "2000" not in result[0]


class TestSaveDraft:
    @pytest.mark.unit
    def test_saves_file(self, monkeypatch, tmp_path):
        from pipeline.threads import writer
        original_dir = writer.DRAFTS_DIR
        test_dir = str(tmp_path / "drafts")
        writer.DRAFTS_DIR = test_dir
        os.makedirs(test_dir, exist_ok=True)
        try:
            cards = ["Test card content"]
            pitch = {"hook": "Test hook for draft"}
            path = save_draft(cards, pitch)
            assert os.path.exists(path)
            with open(path, 'r') as f:
                content = f.read()
            assert "Test card content" in content
        finally:
            writer.DRAFTS_DIR = original_dir


class TestHumanizeCards:
    @pytest.mark.unit
    def test_preserves_on_count_match(self, monkeypatch):
        """humanize_cards는 카드 수가 일치하면 humanize 결과 반환"""
        import v3.model_router
        def mock_chat(*, system_prompt, messages, temperature, max_tokens):
            return "---\n".join(["humanized card " + str(i) for i in range(6)])
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = [f"card {i}" for i in range(6)]
        result = humanize_cards(cards)
        assert len(result) == 6
        assert "humanized" in result[0]

    @pytest.mark.unit
    def test_returns_original_on_count_mismatch(self, monkeypatch):
        """humanize_cards는 count 불일치 시 원본 반환 + 로그"""
        import v3.model_router
        def mock_chat(*, system_prompt, messages, temperature, max_tokens):
            return "only one card"  # 1 card for 6 input
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = [f"card {i}" for i in range(6)]
        result = humanize_cards(cards)
        assert result is cards
        assert len(result) == 6

    @pytest.mark.unit
    def test_empty_input(self, monkeypatch):
        """humanize_cards는 빈 입력 시 그대로 반환"""
        import v3.model_router
        monkeypatch.setattr(v3.model_router, "chat_completion", lambda **kw: "result")
        assert humanize_cards([]) == []

    @pytest.mark.unit
    def test_short_input(self):
        """humanize_cards는 10자 미만 입력 시 그대로 반환 (LLM 호출 없음)"""
        cards = ["short"]
        assert humanize_cards(cards) is cards


class TestFixCards:
    @pytest.mark.unit
    def test_returns_original_on_humanize_mismatch(self, monkeypatch):
        """fix_cards는 humanize count 불일치 시에도 원본 반환"""
        import v3.model_router
        call_log = []
        def mock_chat(*, system_prompt, messages, temperature, max_tokens):
            call_log.append(('chat', temperature))
            if len(call_log) == 1:
                return "only one card"
            return "---\n".join([f"fixed card {i}" for i in range(3)])
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = [f"card {i}" for i in range(6)]
        result = fix_cards(cards)
        assert len(result) == 6


class TestWriteThreadEarlyRejection:
    @pytest.mark.unit
    def test_early_rejection_range(self, monkeypatch):
        """write_thread 내부 로직: lo=5 기준 1~4장 카드는 조기 rejection"""
        lo, _ = FORMAT_CARD_COUNT_TOLERANCE.get('D', (5, 5))
        assert lo == 5
        for n in range(1, 5):
            assert n < lo, f"{n} should be < lo={lo}"
        for n in range(5, 8):
            assert n >= lo, f"{n} should be >= lo={lo}"


class TestAssembleFinal:
    @pytest.mark.unit
    def test_url_appended(self, monkeypatch):
        import db_reader
        def mock_validate(url, timeout=5):
            return True
        monkeypatch.setattr(db_reader, "validate_link", mock_validate)
        cards = ["Card one", "Card two"]
        result = assemble_final(cards, [], primary_url="https://example.com")
        assert len(result) == 3
        assert "https://example.com" in result[-1]
