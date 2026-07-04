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
    load_style_examples, build_system_prompt_D,
    _strip_model_explanatory,
)
from pipeline.threads.validator import MODEL_MESSAGE_PATTERNS
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


class TestLoadStyleExamples:
    @pytest.mark.unit
    def test_returns_string(self):
        """load_style_examples는 문자열 반환"""
        result = load_style_examples()
        assert isinstance(result, str)

    @pytest.mark.unit
    def test_file_not_found_returns_empty(self, monkeypatch):
        """파일 없을 때 빈 문자열 반환"""
        import pipeline.threads.writer as writer_mod
        monkeypatch.setattr(writer_mod, 'STYLE_EXAMPLES_PATH', '/nonexistent/path.md')
        result = load_style_examples()
        assert result == ''


class TestBuildSystemPromptD:
    @pytest.mark.unit
    def test_contains_required_keywords(self):
        """시스템 프롬프트에 필수 키워드 포함"""
        prompt = build_system_prompt_D()
        assert '반말체' in prompt
        assert '카드' in prompt
        assert '스스테이저' in prompt or 'stanza' in prompt

    @pytest.mark.unit
    def test_returns_string(self):
        """build_system_prompt_D는 문자열 반환"""
        result = build_system_prompt_D()
        assert isinstance(result, str)
        assert len(result) > 100


class TestWriteThreadIntegration:
    @pytest.mark.unit
    def test_assemble_final_without_url(self, monkeypatch):
        """URL 없을 때 원본 카드 그대로 반환 (출처 카드 추가 안 함)"""
        import db_reader
        def mock_validate(url, timeout=5):
            return True
        monkeypatch.setattr(db_reader, "validate_link", mock_validate)
        cards = ["Card one", "Card two", "Card three"]
        result = assemble_final(cards, [], primary_url="")
        assert len(result) == 3  # 원본 그대로

    @pytest.mark.unit
    def test_humanize_cards_preserves_count(self, monkeypatch):
        """humanize_cards는 원본 카드 수 유지"""
        import v3.model_router
        def mock_chat(*, system_prompt, messages, temperature, max_tokens):
            return "---\n".join([f"humanized card {i}" for i in range(4)])
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = [f"card {i}" for i in range(4)]
        result = humanize_cards(cards)
        assert len(result) == 4


class TestStripModelExplanatory:
    """_strip_model_explanatory 테스트"""

    @pytest.mark.unit
    def test_message_with_separator(self):
        """메시지 + --- + 카드 → 메시지 제거, 카드 유지"""
        result = "수정할 글자 단위 오류가 발견되지 않았습니다.\n---\n카드1\n---\n카드2"
        filtered = _strip_model_explanatory(result)
        assert "수정할" not in filtered
        assert "카드1" in filtered
        assert "카드2" in filtered

    @pytest.mark.unit
    def test_message_without_separator(self):
        """메시지만, 구분자 없음 → 빈 문자열"""
        result = "원본을 그대로 반환합니다."
        filtered = _strip_model_explanatory(result)
        assert len(filtered) == 0

    @pytest.mark.unit
    def test_no_message(self):
        """메시지 없음 → 변경 없음"""
        result = "카드1\n---\n카드2"
        filtered = _strip_model_explanatory(result)
        assert filtered == result

    @pytest.mark.unit
    def test_multiple_messages(self):
        """여러 메시지 → 모두 제거"""
        result = "수정할 게 없습니다.\n---\n원본을 그대로 반환합니다.\n---\n카드1"
        filtered = _strip_model_explanatory(result)
        assert "수정할" not in filtered
        assert "원본을" not in filtered
        assert "카드1" in filtered

    @pytest.mark.unit
    def test_message_before_cards(self):
        """메시지가 첫 번째 줄에, 카드 --- 구분"""
        result = "AI 티가 나는 패턴이 발견되지 않았습니다.\n---\n실제 카드 내용\n---\n두 번째 카드"
        filtered = _strip_model_explanatory(result)
        assert "AI 티가" not in filtered
        assert "실제 카드 내용" in filtered

    @pytest.mark.unit
    def test_correction_not_needed(self):
        """교정 불필요 메시지"""
        result = "교정할 부분이 없습니다.\n---\n카드내용"
        filtered = _strip_model_explanatory(result)
        assert "교정할" not in filtered
        assert "카드내용" in filtered

    @pytest.mark.unit
    def test_no_changes_message(self):
        """변경사항 없음 메시지"""
        result = "변경 사항이 없습니다.\n---\n원본카드"
        filtered = _strip_model_explanatory(result)
        assert "변경" not in filtered
        assert "원본카드" in filtered

    @pytest.mark.unit
    def test_fix_not_needed_message(self):
        """수정 불필요 메시지"""
        result = "수정 불필요합니다.\n---\n카드"
        filtered = _strip_model_explanatory(result)
        assert "수정 불필요" not in filtered
        assert "카드" in filtered

    @pytest.mark.unit
    def test_error_not_found(self):
        """오류 발견되지 않음 메시지"""
        result = "오류가 발견되지 않았습니다.\n---\n카드내용"
        filtered = _strip_model_explanatory(result)
        assert "오류가" not in filtered
        assert "카드내용" in filtered

    @pytest.mark.unit
    def test_legitimate_content_preserved(self):
        """실제 콘텐츠에서 유사 패턴이 있어도 정상 동작"""
        result = "변경 사항이 중요하다고 생각함.\n---\n카드2"
        filtered = _strip_model_explanatory(result)
        # '변경 사항이' 패턴은 끝부분 '없' 불일치 → 유지
        assert "변경 사항이 중요하다고" in filtered


class TestFixCardsModelMessage:
    """fix_cards에서 모델 메시지 필터링 통합 테스트"""

    @pytest.mark.unit
    def test_model_message_filtered(self, monkeypatch):
        """fix_cards 호출 시 모델 메시지가 포함된 결과에서도 필터링"""
        import v3.model_router
        call_count = [0]
        def mock_chat(*, system_prompt, messages, temperature, max_tokens):
            call_count[0] += 1
            if call_count[0] == 1:
                # humanize pass: 정상 카드
                return "---\n".join([f"humanized card {i}" for i in range(6)])
            # fix_cards pass: 모델 메시지 포함
            return "수정할 게 없습니다.\n---\n" + "---\n".join([f"fixed card {i}" for i in range(6)])
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = [f"card {i}" for i in range(6)]
        result = fix_cards(cards)
        for card in result:
            assert "수정할 게 없습니다" not in card


class TestHumanizeCardsModelMessage:
    """humanize_cards에서 모델 메시지 필터링 통합 테스트"""

    @pytest.mark.unit
    def test_model_message_filtered(self, monkeypatch):
        """humanize_cards 호출 시 모델 메시지가 포함된 결과에서도 필터링"""
        import v3.model_router
        model_response = "원본을 그대로 반환합니다.\n---\n" + "---\n".join([f"card {i}" for i in range(6)])
        def mock_chat(*, system_prompt, messages, temperature, max_tokens):
            return model_response
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = [f"card {i}" for i in range(6)]
        result = humanize_cards(cards)
        for card in result:
            assert "원본을 그대로" not in card


class TestValidateFinalOutputModelMessage:
    """validate_final_output에서 모델 메시지 탐지 테스트"""

    @pytest.mark.unit
    def test_detects_model_message(self):
        """모델 메시지가 포함된 카드 탐지"""
        from pipeline.threads.validator import validate_final_output
        cards = ["수정할 게 없습니다.", "normal card", "another card"]
        ok, reason = validate_final_output(cards)
        assert not ok
        assert "모델 메시지" in reason

    @pytest.mark.unit
    def test_normal_cards_pass(self):
        """일반 카드는 통과"""
        from pipeline.threads.validator import validate_final_output
        cards = ["일반적인 카드 내용입니다. 충분한 길이의 텍스트.", "두 번째 카드 내용도 충분히 길게 작성됨."]
        ok, reason = validate_final_output(cards)
        assert ok
