"""Tests for contrast_writer 7→5 + validator gates + orchestrator E2E (Plan 37-03)."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline.threads.validator import validate_final_output, validate_card_structure

# helper: build 5 valid cards (350-450 target, 500 hard, card5 ends ?)
def _make_valid_cards(hook_entity="OpenAI"):
    # each ~50-80 chars, include hook entity in at least one body card to pass _validate_hook_body_entity_consistency
    c1 = f"{hook_entity}가 100억 투자를 유치했음\n\n시장 반응은 뜨거웠음\n\n반전은 따로 있었음"
    c2 = f"배경은 규제 강화였음\n\n{hook_entity} 전개는 논란 확산\n\n하지만 사실은 다른 그림이었음"
    c3 = f"예상밖 반응이 터졌음\n\n핵심 인물은 등장했음\n\n증거 A가 드러났음"
    c4 = f"논지 심화가 이어졌음\n\n허점이 드러났음\n\n구체적 수치 42%가 제시됐음"
    c5 = f"결국 무엇이 달라질까?\n\n이 선택이 다음 질문을 남기지 않을까?"
    return [c1, c2, c3, c4, c5]

def _valid_af():
    return {
        "A": {"사건명": "테스트 사건"},
        "B": [{"value_text": "100억", "metric": "투자액", "condition": "시리즈A", "evidence_sentence": "100억 투자"}, {"value_text": "42%", "metric": "점유율", "condition": "국내", "evidence_sentence": "42% 점유"}, {"value_text": "3명", "metric": "창업자", "condition": "공동", "evidence_sentence": "3명 창업"}],
        "C": [{"text": "We did it", "text_translated": "해냈다", "speakers": ["홍길동"], "speaker_type": "solo", "source_topic_tag": "테스트 주제", "speaker": "홍길동", "speaker_title": "대표", "paragraph_hint": "1"}, {"text": "Great", "text_translated": "훌륭하다", "speakers": ["김철수"], "speaker_type": "solo", "source_topic_tag": "테스트 주제", "speaker": "김철수", "speaker_title": "교수", "paragraph_hint": "2"}],
        "D": "상위 주제 테스트 문장 충분히 길게",
        "E": ["AI 규제", "신뢰", "투자"],
        "F": ["질문1"],
    }

def _bundle(background=None, cross=None):
    seed = {"id": "1", "title": "테스트 제목", "description": "본문 테스트 " * 20, "link": "http://example.com/1", "pub_date": "2026-08-26", "source": "테스트"}
    return {"seed_article": seed, "af": _valid_af(), "background": background, "cross_articles": cross or []}


class TestContrastWriterValid:
    def test_5card_count_ok(self):
        from pipeline.threads.contrast.contrast_writer import write_contrast_thread
        cards = _make_valid_cards()
        payload = json.dumps({"cards": cards}, ensure_ascii=False)
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=payload):
            result = write_contrast_thread(_bundle(), [])
            assert result is not None
            assert 3 <= len(result["cards"]) <= 8
            assert all(len(c) <= 500 for c in result["cards"])
            # card5 ends with ? or open ending
            last = result["cards"][-1].strip()
            assert last.endswith("?") or last.endswith("까") or "까?" in last or last.endswith("인데")

    def test_over500_drop(self):
        from pipeline.threads.contrast.contrast_writer import write_contrast_thread
        cards = _make_valid_cards()
        cards[1] = "가" * 501  # >500 forces validate_card_structure fail
        payload = json.dumps({"cards": cards}, ensure_ascii=False)
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=payload):
            result = write_contrast_thread(_bundle(), [])
            assert result is None

    def test_hanja_hiragana_fail(self):
        from pipeline.threads.contrast.contrast_writer import write_contrast_thread
        cards = _make_valid_cards()
        cards[2] = cards[2] + " 漢字"  # hanja
        payload = json.dumps({"cards": cards}, ensure_ascii=False)
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=payload):
            result = write_contrast_thread(_bundle(), [])
            assert result is None
        # also direct validator
        cards_jp = _make_valid_cards()
        cards_jp[1] = "あいうえお 테스트" + cards_jp[1]
        ok, _ = validate_final_output(cards_jp)
        assert ok is False

    def test_background_none_graceful(self):
        from pipeline.threads.contrast.contrast_writer import write_contrast_thread
        cards = _make_valid_cards()
        payload = json.dumps({"cards": cards}, ensure_ascii=False)
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=payload):
            result = write_contrast_thread(_bundle(background=None, cross=[]), [])
            assert result is not None
            assert 3 <= len(result["cards"]) <= 8

    def test_leak_fail(self):
        from pipeline.threads.contrast.contrast_writer import write_contrast_thread
        cards = _make_valid_cards()
        cards[0] = "상위 주제: AI 폭발 " + cards[0]
        payload = json.dumps({"cards": cards}, ensure_ascii=False)
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=payload):
            result = write_contrast_thread(_bundle(), [])
            assert result is None
        # direct leak
        from pipeline.threads.pitch import detect_prompt_leak
        leaked, _ = detect_prompt_leak("상위 주제: 테스트")
        assert leaked is True

    def test_hook_entity_missing_fail(self):
        # hook has entity OpenAI but body cards have no OpenAI -> _validate_hook_body_entity_consistency fail
        cards = _make_valid_cards(hook_entity="OpenAI")
        # replace body cards to remove entity
        cards[1] = "배경은 규제였음\n\n전개는 논란이었음"
        cards[2] = "예상밖 반응이었음\n\n증거 A였음"
        cards[3] = "논지 심화였음\n\n허점이었음"
        # ensure hook (c1) has OpenAI, body none -> fail
        ok, reason = validate_final_output(cards)
        assert ok is False
        assert "Hook 고유명사" in reason or "본문" in reason

    def test_json_brace_fallback(self):
        from pipeline.threads.contrast.contrast_writer import write_contrast_thread
        cards = _make_valid_cards()
        payload = json.dumps({"cards": cards}, ensure_ascii=False)
        # wrap with code fence + extra text
        wrapped = "```json\n" + payload + "\n```"
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=wrapped):
            result = write_contrast_thread(_bundle(), [])
            assert result is not None
            assert 3 <= len(result["cards"]) <= 8
        # also brace stack without fence
        wrapped2 = "쓰레드 시작\n" + payload + "\n쓰레드 끝"
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=wrapped2):
            result2 = write_contrast_thread(_bundle(), [])
            assert result2 is not None


class TestOrchestratorE2E:
    def test_orchestrator_mocked_e2e(self):
        from pipeline.threads.contrast.orchestrator import run_contrast_thread
        seed = {"id": "1", "title": "테스트", "link": "http://example.com/1", "description": "본문 " * 50, "source": "테스트", "crawled_body": "본문 크롤링 테스트 " * 50}
        af = _valid_af()
        cards = _make_valid_cards()
        mock_result = {"cards": cards, "link": "http://example.com/1"}
        with patch("pipeline.threads.contrast.extractor.extract_af", return_value=af):
            with patch("pipeline.threads.contrast.background_search.find_background", return_value=None):
                with patch("pipeline.threads.contrast.background_search.find_cross_articles", return_value=[]):
                    with patch("pipeline.threads.contrast.contrast_writer.write_contrast_thread", return_value=mock_result) as mock_writer:
                        with patch("pipeline.threads.writer.save_draft", return_value="/tmp/draft.txt") as mock_save:
                            result = run_contrast_thread(seed, [seed])
                            assert result is not None
                            assert result["cards"] == cards
                            mock_writer.assert_called_once()
                            mock_save.assert_called_once()
                            # pitch_stub should have seed id only
                            args, _ = mock_save.call_args
                            assert args[1]["article_ids"] == ["1"]
