"""Tests for pipeline.threads.contrast.extractor — A-F JSON guard."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline.threads.contrast.extractor import _validate_af, extract_af


VALID_AF = {
    "A": {"사건명": "테스트 사건", "시점": "2026-08-26", "장소": "서울", "행위자": "홍길동", "계기": "발표"},
    "B": ["매출 100억", "2026년 3월"],
    "C": ["홍길동 발언: 좋다"],
    "D": "인공지능 규제라는 상위 주제에서 표면 문제는 과장 광고, 근본은 신뢰 붕괴",
    "E": ["AI 규제", "신뢰 붕괴", "과장 광고"],
    "F": ["왜 규제 실패했나?", "다음 단계는?"],
}


class TestValidateAf:
    def test_valid(self):
        assert _validate_af(VALID_AF) is True

    def test_b_zero(self):
        d = {**VALID_AF, "B": []}
        assert _validate_af(d) is False

    def test_c_zero(self):
        d = {**VALID_AF, "C": []}
        assert _validate_af(d) is False

    def test_e_len_2(self):
        d = {**VALID_AF, "E": ["a", "b"]}
        assert _validate_af(d) is False

    def test_e_len_4(self):
        d = {**VALID_AF, "E": ["a", "b", "c", "d"]}
        assert _validate_af(d) is False

    def test_empty_d(self):
        d = {**VALID_AF, "D": ""}
        assert _validate_af(d) is False

    def test_d_short(self):
        d = {**VALID_AF, "D": "짧음"}
        assert _validate_af(d) is False


class TestExtractAf:
    def test_valid_parse(self):
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=json.dumps(VALID_AF)):
            result = extract_af("본문 내용 " * 100, "제목")
            assert result is not None
            assert result["E"] == ["AI 규제", "신뢰 붕괴", "과장 광고"]

    def test_json_garbage_none(self):
        with patch("scripts.threads.v3.model_router.chat_completion", return_value="not json at all"):
            assert extract_af("본문", "제목") is None

    def test_none_response_none(self):
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=None):
            assert extract_af("본문", "제목") is None

    def test_b_zero_returns_none(self):
        bad = {**VALID_AF, "B": []}
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=json.dumps(bad)):
            assert extract_af("본문", "제목") is None

    def test_c_zero_returns_none(self):
        bad = {**VALID_AF, "C": []}
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=json.dumps(bad)):
            assert extract_af("본문", "제목") is None

    def test_e_2_returns_none(self):
        bad = {**VALID_AF, "E": ["a", "b"]}
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=json.dumps(bad)):
            assert extract_af("본문", "제목") is None

    def test_empty_d_returns_none(self):
        bad = {**VALID_AF, "D": ""}
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=json.dumps(bad)):
            assert extract_af("본문", "제목") is None

    def test_quote_in_keyword_not_crash(self):
        af = {**VALID_AF, "E": ["AI's 규제", "O'Reilly", "test"]}
        # still valid E len 3, guard passes
        assert _validate_af(af) is True
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=json.dumps(af)):
            result = extract_af("본문", "제목")
            assert result is not None
            assert "AI's 규제" in result["E"]

    def test_empty_body_none(self):
        assert extract_af("", "제목") is None
        assert extract_af("   ", "제목") is None

    def test_code_fence_json(self):
        wrapped = "```json\n" + json.dumps(VALID_AF) + "\n```"
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=wrapped):
            result = extract_af("본문", "제목")
            assert result is not None

    def test_leak_not_triggered_on_clean(self):
        from pipeline.threads.pitch import detect_prompt_leak
        clean = "AI가 100억 투자를 유치했음. 시장 반응은 뜨거웠음."
        leaked, _ = detect_prompt_leak(clean)
        assert leaked is False

    def test_leak_triggered_on_contrast_label(self):
        from pipeline.threads.pitch import detect_prompt_leak
        leaked, _ = detect_prompt_leak("상위 주제: AI 폭발")
        assert leaked is True
        leaked2, _ = detect_prompt_leak("근본 문제: 신뢰 붕괴")
        assert leaked2 is True
        leaked3, _ = detect_prompt_leak("대비 논지: 표면은 해결")
        assert leaked3 is True

    def test_condition_null_allowed(self):
        """Wave5: condition/evidence_sentence may be null and still valid."""
        d = {
            "A": {"사건명": "x", "시점": "2026-08-26", "장소": "서울", "행위자": "y", "계기": "z"},
            "B": [{"value_text": "20%", "metric": "무게 감소", "condition": None, "evidence_sentence": None}],
            "C": [{"text": "a", "text_translated": "a", "speaker": "s", "speaker_title": "", "speakers": ["s"], "speaker_type": "solo", "source_topic_tag": "t", "paragraph_hint": "p"}],
            "D": "상위 주제 문장 테스트 충분 길이",
            "E": ["k1","k2","k3"],
            "F": ["q1"],
        }
        assert _validate_af(d) is True

    def test_b_extraction_not_capped_at_three(self):
        """Wave5: B 6개까지 추출되어야 하며 3개 상한 아님."""
        # mock LLM returning 6 B
        fake_data = {
            "A": {"사건명": "x", "시점": "2026-08-26", "장소": "서울", "행위자": "y", "계기": "z"},
            "B": [{"value_text": f"{i}%", "metric": f"m{i}", "condition": f"c{i}", "evidence_sentence": f"e{i}"} for i in range(6)],
            "C": [
                {"text": "a", "text_translated": "a", "speaker": "s", "speaker_title": "t", "speakers": ["s"], "speaker_type": "solo", "source_topic_tag": "t", "paragraph_hint": "p"},
                {"text": "b", "text_translated": "b", "speaker": "s2", "speaker_title": "t2", "speakers": ["s2"], "speaker_type": "solo", "source_topic_tag": "t2", "paragraph_hint": "p2"},
            ],
            "D": "상위 주제 문장 테스트 충분 길이 확보 테스트",
            "E": ["k1","k2","k3"],
            "F": ["q1"],
        }
        with patch("scripts.threads.v3.model_router.chat_completion", return_value=json.dumps(fake_data, ensure_ascii=False)):
            af = extract_af("dummy body for test that is long enough " + "x"*200, "title", pub_date="2026-08-26")
            assert af is not None
            assert len(af["B"]) == 6
            assert len(af["C"]) == 2
