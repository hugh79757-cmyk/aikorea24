"""Tests for compass summary block variation + tone branching."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "threads"))

from pipeline.threads.compass import (
    _build_summary_block,
    build_blog_system_prompt,
)

pytestmark = pytest.mark.unit


class TestSummaryBlockFormats:
    """_build_summary_block must produce 4 formats."""

    def test_bullet_format(self):
        result = _build_summary_block("핵심 포인트 정리", "bullet")
        assert "📌" in result
        assert "**요약**" in result
        assert "핵심 포인트 정리" in result

    def test_narrative_format(self):
        result = _build_summary_block("한 문단 요약입니다", "narrative")
        assert "📌 요약." in result
        assert "한 문단 요약입니다" in result

    def test_key_question_format(self):
        result = _build_summary_block("핵심 질문 내용", "key_question")
        assert "📌 핵심 질문." in result
        assert "핵심 질문 내용" in result

    def test_natural_close_format(self):
        result = _build_summary_block("마무리 내용", "natural_close")
        assert "📌 마무리." in result
        assert "마무리 내용" in result
        assert "댓글" in result

    def test_unknown_format_defaults_to_bullet(self):
        result = _build_summary_block("테스트", "unknown_format")
        assert "📌" in result
        assert "**요약**" in result

    def test_empty_summary_handled(self):
        for fmt in ["bullet", "narrative", "key_question", "natural_close"]:
            result = _build_summary_block("", fmt)
            assert "📌" in result


class TestToneBranches:
    """build_blog_system_prompt must have 3 tone branches."""

    def test_neutral_careful_tone(self):
        p = build_blog_system_prompt(tone="neutral_careful")
        assert "~습니다" in p or "~합니다" in p
        assert "공식" in p or "신중" in p

    def test_fan_friendly_tone(self):
        p = build_blog_system_prompt(tone="fan_friendly")
        assert "~요" in p or "~해요" in p
        assert "여러분" in p
        assert "비유" in p or "허용" in p

    def test_analytical_tone(self):
        p = build_blog_system_prompt(tone="analytical")
        assert "~이다" in p or "~다" in p
        assert "수치" in p or "인용" in p

    def test_default_tone_is_neutral_careful(self):
        p_default = build_blog_system_prompt()
        p_neutral = build_blog_system_prompt(tone="neutral_careful")
        assert p_default == p_neutral

    def test_tone_rules_differ(self):
        neutral = build_blog_system_prompt(tone="neutral_careful")
        friendly = build_blog_system_prompt(tone="fan_friendly")
        analytical = build_blog_system_prompt(tone="analytical")
        assert neutral != friendly
        assert friendly != analytical
        assert neutral != analytical

    def test_tone_in_system_prompt(self):
        """Each tone appears in the generated prompt."""
        p = build_blog_system_prompt(tone="neutral_careful")
        assert "톤:" in p


class TestToneSentenceLengthRanges:
    """Each tone has different sentence length guidance."""

    def test_neutral_has_length_range(self):
        p = build_blog_system_prompt(tone="neutral_careful")
        assert "문장 길이" in p or "30" in p

    def test_fan_friendly_shorter_sentences(self):
        p = build_blog_system_prompt(tone="fan_friendly")
        assert "70" in p

    def test_analytical_longer_allowed(self):
        p = build_blog_system_prompt(tone="analytical")
        assert "90" in p
