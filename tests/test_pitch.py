"""Tests for pipeline.threads.pitch — parsing, dedup, history."""
import pytest
import json
import os
import sys
from pathlib import Path

_scripts = str(Path(__file__).resolve().parent.parent / "scripts")
_threads = str(Path(__file__).resolve().parent.parent / "scripts" / "threads")
if _threads not in sys.path:
    sys.path.insert(0, _threads)
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

from pipeline.threads.pitch import (
    parse_pitches_from_text, is_duplicate_pitch,
    load_pitch_history, fill_article_ids,
    clean_leaked_prompt,
)


class TestCleanLeakedPrompt:
    @pytest.mark.unit
    def test_removes_leaked_상식A_label(self):
        result = clean_leaked_prompt("상식(A): AI는 생산성을 높인다")
        assert "상식(A):" not in result
        assert "AI는 생산성을 높인다" in result

    @pytest.mark.unit
    def test_removes_leaked_실제B_label(self):
        result = clean_leaked_prompt("실제(B): AI는 일자리를 줄인다")
        assert "실제(B):" not in result

    @pytest.mark.unit
    def test_removes_vs_separator(self):
        result = clean_leaked_prompt("상식(A): A\nvs\n실제(B): B")
        assert "vs" not in result

    @pytest.mark.unit
    def test_handles_various_delimiters(self):
        cases = [
            "상식（A）：텍스트",
            "상식 (A) : 텍스트",
            "실제(B):텍스트",
            "text\nVS\nmore",
            "text\nversus\nmore",
        ]
        for c in cases:
            result = clean_leaked_prompt(c)
            assert result, f"빈 결과 반환: {c!r}"

    @pytest.mark.unit
    def test_clean_text_unchanged(self):
        text = "Nvidia가 새로운 칩을 출시했다."
        assert clean_leaked_prompt(text) == text

    @pytest.mark.unit
    def test_the_entire_narrative_with_leak(self):
        text = "상식(A): AI는 생산성을 높일 것이다 — 실제(B): AI 사용 중 예상치 못한 문제가 발생"
        result = clean_leaked_prompt(text)
        assert "상식(A):" not in result
        assert "실제(B):" not in result
        assert "AI는 생산성을" in result or "AI 사용 중" in result


class TestParsePitchesFromText:
    @pytest.mark.unit
    def test_standard_schema(self):
        text = 'Some text {"hook": "Test hook", "narrative": "Test narrative", "twist": "Test twist", "emotion": "놀람", "article_ids": [1]} more text'
        pitches = parse_pitches_from_text(text)
        assert len(pitches) == 1
        assert pitches[0]["hook"] == "Test hook"
        assert pitches[0]["article_ids"] == [1]

    @pytest.mark.unit
    def test_diffusiongemma_schema(self):
        text = '{"title": "AI Breakthrough", "summary": "This is a summary", "tags": ["ai"]}'
        pitches = parse_pitches_from_text(text)
        assert len(pitches) == 1
        assert "AI Breakthrough" in pitches[0]["hook"]

    @pytest.mark.unit
    def test_pitch_id_schema(self):
        text = '{"pitch_id": 1, "title": "Pitch Title", "summary": "Summary text"}'
        pitches = parse_pitches_from_text(text)
        assert len(pitches) == 1
        assert pitches[0]["hook"] == "Pitch Title"

    @pytest.mark.unit
    def test_invalid_json(self):
        text = "This is not valid JSON at all"
        pitches = parse_pitches_from_text(text)
        assert pitches == []


class TestIsDuplicatePitch:
    @pytest.mark.unit
    def test_exact_hook_duplicate(self):
        pitch = {"hook": "Nvidia unveils new chip", "narrative": "Test", "article_ids": [1]}
        history = [{"hook": "Nvidia unveils new chip", "narrative": "Old", "article_ids": [2]}]
        assert is_duplicate_pitch(pitch, history) is True

    @pytest.mark.unit
    def test_no_match(self):
        pitch = {"hook": "Completely different", "narrative": "New story", "article_ids": [5]}
        history = [{"hook": "Something else", "narrative": "Old story", "article_ids": [1]}]
        assert is_duplicate_pitch(pitch, history) is False

    @pytest.mark.unit
    def test_article_id_overlap(self):
        pitch = {"hook": "New hook", "narrative": "New", "article_ids": [1, 2, 3]}
        history = [{"hook": "Old", "narrative": "Old", "article_ids": [1, 2, 4]}]
        assert is_duplicate_pitch(pitch, history) is True

    @pytest.mark.unit
    def test_no_article_ids(self):
        pitch = {"hook": "Hook", "narrative": "Narrative", "article_ids": []}
        history = [{"hook": "Other", "narrative": "Other", "article_ids": []}]
        assert is_duplicate_pitch(pitch, history) is False


class TestFillArticleIds:
    @pytest.mark.unit
    def test_skips_if_already_has_ids(self):
        pitch = {"hook": "Test", "narrative": "Test", "article_ids": [42]}
        result = fill_article_ids(pitch, [])
        assert result["article_ids"] == [42]

    @pytest.mark.unit
    def test_matches_by_keyword(self):
        pitch = {"hook": "OpenAI launches", "narrative": "New model released", "article_ids": []}
        articles_text = [
            "기사 #1:\n제목: OpenAI launches new model\n본문: OpenAI released today"
        ]
        result = fill_article_ids(pitch, articles_text)
        assert len(result["article_ids"]) > 0


class TestLoadPitchHistory:
    @pytest.mark.unit
    def test_returns_empty_when_no_file(self, tmp_path, monkeypatch):
        import pipeline.threads.pitch as pitch_mod
        def mock_load(*args, **kwargs):
            return []
        monkeypatch.setattr(pitch_mod, "load_pitch_history", mock_load)
        result = pitch_mod.load_pitch_history()
        assert result == []
