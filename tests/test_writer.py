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
    assemble_final,
)
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
