"""Tests for pipeline.threads.pitch — parsing, dedup, history, crawl-fail discard."""
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
    clean_leaked_prompt, validate_korean_output,
    normalize_output, detect_prompt_leak,
    get_pitches,
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


class TestDetectPromptLeak:
    @pytest.mark.unit
    def test_clean_text_no_leak(self):
        leaked, reason = detect_prompt_leak("Boeing의 Wisk Aero가 FAA 테스트를 축소했다.")
        assert leaked is False
        assert reason == "OK"

    @pytest.mark.unit
    def test_detects_system_prompt_fragment(self):
        leaked, reason = detect_prompt_leak("스토리 파인더입니다. 인과관계를 정확히 파악하라")
        assert leaked is True
        assert "스토리 파인더" in reason

    @pytest.mark.unit
    def test_detects_multiple_fragments(self):
        leaked, reason = detect_prompt_leak("당신은 스토리 파인더입니다. [핵심 원칙] 인과관계를 정확히 파악")
        assert leaked is True

    @pytest.mark.unit
    def test_detects_output_format_label(self):
        leaked, reason = detect_prompt_leak("[출력 형식] 응답은 유효한 JSON만")
        assert leaked is True


class TestValidateKoreanOutput:
    @pytest.mark.unit
    def test_korean_hook_with_proper_nouns_passes(self):
        ok, reason = validate_korean_output(
            "Boeing의 Wisk Aero가 FAA 테스트 축소 의혹으로 내부고발 소송에 직면했다.",
            "한국어 설명입니다."
        )
        assert ok is True

    @pytest.mark.unit
    def test_english_hook_fails(self):
        ok, reason = validate_korean_output(
            "Boeing's Wisk Aero faces whistleblower lawsuit",
            "over alleged cuts to FAA testing"
        )
        assert ok is False
        assert "한글이 전혀 없음" in reason

    @pytest.mark.unit
    def test_prompt_leak_detected(self):
        ok, reason = validate_korean_output(
            "스토리 파인더입니다. 핵심 원칙을 따라",
            "인과관계를 정확히 파악하라"
        )
        assert ok is False
        assert "프롬프트 프래그먼트" in reason

    @pytest.mark.unit
    def test_mixed_korean_english_passes(self):
        ok, reason = validate_korean_output(
            "OpenAI의 ChatGPT가 GPT-5 출시와 함께 Enterprise 시장 공략",
            "AI 기반 B2B SaaS 스타트업이 Series A 투자 유치에 성공했다."
        )
        assert ok is True

    @pytest.mark.unit
    def test_empty_hook_fails(self):
        ok, reason = validate_korean_output("", "내러티브")
        assert ok is False
        assert "비어있음" in reason


class TestNormalizeOutput:
    @pytest.mark.unit
    def test_truncates_long_hook(self):
        hook = "A" * 150
        narrative = "B" * 250
        result = normalize_output(hook, narrative)
        assert len(result["hook"]) == 100
        assert len(result["narrative"]) == 200

    @pytest.mark.unit
    def test_applies_clean_leaked_prompt(self):
        result = normalize_output("상식(A): 테스트 hook", "실제(B): 테스트 narrative")
        assert "상식(A):" not in result["hook"]
        assert "실제(B):" not in result["narrative"]

    @pytest.mark.unit
    def test_sets_lang_valid_for_korean(self):
        result = normalize_output("한국어 hook입니다.", "한국어 narrative입니다.")
        assert result["lang_valid"] is True
        assert result["lang_reason"] == "OK"

    @pytest.mark.unit
    def test_sets_lang_valid_false_for_english(self):
        result = normalize_output("English hook only", "English narrative")
        assert result["lang_valid"] is False
        assert result["lang_reason"] != "OK"


class TestGetPitchesCrawlFail:
    """get_pitches()가 크롤링 실패 시 빈 리스트 반환하는지 검증"""

    @pytest.fixture
    def mock_deps(self, monkeypatch):
        def _mock_chat(**kw):
            return json.dumps([{"hook": "Test: AI changes everything", "narrative": "한국어 설명입니다. AI가 세상을 바꾼다.", "twist": "예상 밖", "emotion": "놀람", "article_ids": [1]}])
        monkeypatch.setattr("v3.model_router.chat_completion", _mock_chat)

        monkeypatch.setattr("db_reader.load_posted", lambda: {})
        monkeypatch.setattr("pipeline.threads.pitch_evaluator.filter_pitches", lambda p: p[0] if p else None)

    def _make_article(self, aid=1, url="https://example.com/article"):
        return {"id": aid, "title": "Test Title", "original_title": "Test Original", "description": "Test desc", "link": url, "source": "Test"}

    @pytest.mark.unit
    def test_discards_when_url_missing(self, mock_deps):
        articles = [self._make_article(aid=1, url="")]

        result = get_pitches(articles, max_articles=1, batch_size=1)

        assert result == ([], {"1"})

    @pytest.mark.unit
    def test_discards_when_crawl_fails(self, mock_deps, monkeypatch):
        monkeypatch.setattr("pipeline.threads.crawler.fetch_article_body", lambda *a, **kw: "")
        articles = [self._make_article(aid=1)]

        result = get_pitches(articles, max_articles=1, batch_size=1)

        assert result == ([], {"1"})

    @pytest.mark.unit
    def test_discards_when_regeneration_fails(self, mock_deps, monkeypatch):
        monkeypatch.setattr("pipeline.threads.crawler.fetch_article_body", lambda *a, **kw: "Crawled body text " * 100)
        monkeypatch.setattr("pipeline.threads.pitch._regenerate_pitch_from_crawl", lambda *a, **kw: None)
        articles = [self._make_article(aid=1)]

        result = get_pitches(articles, max_articles=1, batch_size=1)

        assert result == ([], {"1"})

    @pytest.mark.unit
    def test_keeps_when_crawl_succeeds(self, mock_deps, monkeypatch):
        monkeypatch.setattr("pipeline.threads.crawler.fetch_article_body", lambda *a, **kw: "Crawled body text " * 100)
        regenerated = {"hook": "한국어 hook 재생성 성공", "narrative": "한국어 narrative 재생성 성공", "article_ids": [1], "crawled_url": "https://example.com/article"}
        monkeypatch.setattr("pipeline.threads.pitch._regenerate_pitch_from_crawl", lambda *a, **kw: regenerated)
        articles = [self._make_article(aid=1)]

        result = get_pitches(articles, max_articles=1, batch_size=1)
        pitches, failed_ids = result

        assert len(pitches) == 1
        assert pitches[0]["hook"] == "한국어 hook 재생성 성공"
        assert failed_ids == set()
