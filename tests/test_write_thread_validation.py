"""Tests for pipeline.threads.writer — E2E validation chain (retry, pattern detection, link cards)."""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "threads"))

from pipeline.threads.writer import write_thread


@pytest.fixture
def sample_pitch():
    """Minimal valid pitch for validation chain testing."""
    return {
        "hook": "AI \uacf5\uac10 \ub2a5\ub825 \uc774\uc0c1 \uac10\uc9c0 — \uc548\ubcf4\uc774\ub294 \uc0ac\ub791",
        "narrative": "\ud55c\uad6d\uc5b4\ub85c \uc791\uc131\ub41c \ub0b4\ub7ec\ud2f0\ube0c\uc774\uba70 \ucda9\ubd84\ud55c \uae38\uc774\uc640 \uad6c\uc870\ub97c \uac16\ucd98\ub2e4.",
        "twist": "\uc608\uc0c1\ubc16\uc758 \uacb0\uacfc",
        "emotion": "\ub180\ub77c\uc6c0",
        "article_ids": [1],
        "crawled_body": (
            "2026\ub144 7\uc6d4 5\uc77c, AI \uacf5\uac10 \ub2a5\ub825 \ud3c9\uac00 \uc0c8 \ubc29\ubc95\ub860\uc774 \ubc1c\ud45c\ub418\uc5c8\uc2b5\ub2c8\ub2e4." +
            " \uae30\uc874 \ubc29\ubc95\ub860\uc740 \uc131\ub2a5 \uce21\uc815\uc5d0\ub9cc \uc758\uc874\ud588\uc9c0\ub9cc," +
            " \uc0c8\ub85c\uc6b4 \uc5f0\uad6c\ub294 100\ub9cc \uac74\uc758 \ub300\ud654 \ub370\uc774\ud130\ub97c \ubd84\uc11d\ud558\uc5ec" +
            " \uac10\uc815\uc801 \ubc18\uc751\uc758 \uc2e4\uc81c \ubcf5\uc7a1\uc131\uc744 \ub4dc\ub7ec\ub0c8\uc2b5\ub2c8\ub2e4." +
            " \uae30\uc874 \ubca4\uce58\ub9c8\ud06c\ub294 72% \uc815\ud655\ub3c4\uc5d0 \uadf8\uce58\uba74\uc11c" +
            " \uc778\uac04 \ud3c9\uac00\uc790\uc758 89%\uc5d0 \ud06c\uac8c \ubabb \ubbf8\ucce4\uc2b5\ub2c8\ub2e4." +
            " \uc0c8 \uc2dc\uc2a4\ud15c\uc740 AI\uac00 \uac10\uc815\uc744 '\uac10\uc9c0\ud558\ub294' \uac83\uc774 \uc544\ub2cc" +
            " '\uc774\ud574\ud558\ub294' \uac83\uc784\uc744 \uac15\uc870\ud569\ub2c8\ub2e4."
        ),
        "crawled_url": "https://example.com/ai-sentiment",
    }


@pytest.fixture
def sample_articles():
    """Minimal article data for write_thread."""
    return [
        {
            "id": 1,
            "title": "AI \uacf5\uac10 \ub2a5\ub825 \uc774\uc0c1 \uac10\uc9c0 \uc0c8 \uc5f0\uacb5\uacb0",
            "link": "https://example.com/ai-sentiment",
            "source": "\ud14c\uc2a4\ud2b8\uc0ac",
            "pub_date": "2026-07-05",
        },
    ]


def _make_response(text):
    """Helper: create a chat_completion-like response string."""
    return text


VALID_CARDS = [
    "AI가 공감을 이해하는 것이 아니라 감지하는 것으로 밝혀졌음.\n이 연구는 100만 건의 대화 데이터를 분석했음.\n기존 벤치마크는 72% 정확도였지만 새 시스템은 더 발전했음.\n이것은 AI 감정 인식의 새로운 지평을 열었음.",
    "그런데 새 시스템은 AI가 감정을 감지하는 것이 아닌 이해하는 것임을 입증했음. 감정 공감 능력의 큰 변화임.",
    "이 발견은 고객 서비스, 정신 건강, 교육 등 다양한 분야에서 실제로 적용될 수 있는 중요한 전환점임.",
    "결국 AI가 진정한 공감을 갖추려면 수치를 넘어 사람의 말과 행동을 이해하는 능력이 필요함.",
    "이 연구의 핵심은 AI가 인간의 감정을 단순히 감지하는 수준을 넘어 이해할 수 있다는 점임.",
    "🔗 https://example.com/ai-sentiment",
]

VALID_CARD_COUNT = 6


def _extract_card_between(user_msg, start_marker, end_markers):
    """Extract text between start_marker and the first end_marker found."""
    start_idx = user_msg.find(start_marker)
    if start_idx == -1:
        return None
    start_idx += len(start_marker)
    end_idx = len(user_msg)
    for em in end_markers:
        ei = user_msg.find(em, start_idx)
        if ei != -1 and ei < end_idx:
            end_idx = ei
    return user_msg[start_idx:end_idx].strip()


def _make_mock(generate_cards=None):
    """Create a mock_chat that handles the new per-card pipeline.

    Uses message content inspection (not call count) to distinguish:
    - Generate call (contains '=== 피치 ===' or '=== 관련 기사 ===')
    - Per-card humanize call (contains '다음 카드의 AI 말투')
    - Per-card MiMo call (contains '--- 카드 시작 ---')

    Returns card content unchanged (per-card processing preserves content).
    """
    call_log = []
    gen_cards = generate_cards or VALID_CARDS

    def mock_chat(*, system_prompt, messages, temperature, max_tokens, **kwargs):
        call_log.append(1)
        user_msg = messages[0]['content'] if messages else ''

        if '=== 피치 ===' in user_msg or '=== 관련 기사 ===' in user_msg:
            return '\n---\n'.join(gen_cards)

        if '--- 카드 시작 ---' in user_msg:
            return _extract_card_between(user_msg, '--- 카드 시작 ---\n', ['\n--- 카드 끝 ---'])

        if '다음 카드의 AI 말투' in user_msg:
            return _extract_card_between(user_msg, '[카드 내용]\n', ['\n\n[', '\n\n===苏', '\n\n---'])

        return None

    return mock_chat, call_log


class TestWriteThreadValidationChain:
    """E2E validation chain for per-card pipeline: rejection on issues, success on valid."""

    @pytest.mark.integration
    def test_chinese_char_rejected(self, sample_pitch, sample_articles, monkeypatch):
        """Chinese character in card → write_thread returns [] (validation catches it)."""
        import v3.model_router
        import db_reader

        monkeypatch.setattr(db_reader, "validate_link", lambda *a, **kw: True)

        bad_cards = [
            "첫번째 카드는 충분히 긴 내용을 가지고 있음.\n한국어로만 작성된 검증 통과 가능한 카드임.\n세번째 줄도 문제없이 읽을 수 있는 내용임.\n네번째 줄까지 충분한 내용을 제공함.",
            "一 중국어가 포함된 카드입니다. 이런 내용은 발행되면 안 됩니다. 검증 단계에서 걸러져야 합니다.",
            "세번째 카드도 충분히 길고 한글로만 구성되어야 합니다. 이 카드는 검증을 통과할 수 있습니다.",
            "네번째 카드는 문장이 완성되었습니다. 충분히 긴 내용을 가지고 있어 검증을 통과합니다.",
            "다섯번째 카드는 여운을 남기는 마무리입니다. 충분히 긴 내용을 가지고 있습니다.",
            "🔗 https://example.com/ai-sentiment",
        ]
        mock_chat, call_log = _make_mock(generate_cards=bad_cards)
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = write_thread(sample_pitch, sample_articles, format_choice="D")
        assert cards == []  # Rejected by validation

    @pytest.mark.integration
    def test_prompt_label_leak_rejected(self, sample_pitch, sample_articles, monkeypatch):
        """Prompt label leak ('상식(A):') → write_thread returns []."""
        import v3.model_router
        import db_reader

        monkeypatch.setattr(db_reader, "validate_link", lambda *a, **kw: True)

        bad_cards = [
            "상식(A): AI가 감정을 이해할 수 있다는 연구 결과가 나왔음.\n이 연구는 100만 건의 데이터를 분석했음.\n그러나 이 레이블은 검증에서 걸러져야 함.\n검증 단계가 이 내용을 차단할 것으로 기대함.",
            "두번째 카드는 충분히 길고 한글로만 구성되었습니다. 검증을 통과할 만한 길이를 가지고 있음. 모든 검증 조건을 충족합니다.",
            "세번째 카드도 길고 충분한 한글 카드입니다. 모든 검증을 통과할 수 있도록 작성되었음. 충분히 긴 내용을 포함하고 있음.",
            "네번째 카드도 문장이 완성되었습니다. 충분히 긴 내용을 담고 있음. 검증 조건을 모두 만족합니다.",
            "다섯번째 카드는 여운을 남기는 마무리입니다. 이 카드도 충분히 긴 내용을 담고 있음. 검증을 통과할 수 있습니다.",
            "🔗 https://example.com/ai-sentiment",
        ]
        mock_chat, call_log = _make_mock(generate_cards=bad_cards)
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = write_thread(sample_pitch, sample_articles, format_choice="D")
        assert cards == []  # Rejected by validation

    @pytest.mark.integration
    def test_success_valid_cards(self, sample_pitch, sample_articles, monkeypatch):
        """All 6 valid Korean cards → write_thread returns cards."""
        import v3.model_router
        import db_reader

        monkeypatch.setattr(db_reader, "validate_link", lambda *a, **kw: True)

        mock_chat, call_log = _make_mock()
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = write_thread(sample_pitch, sample_articles, format_choice="D")
        assert cards is not None
        assert len(cards) > 0
        assert len(call_log) >= 12  # 1 generate + 6 humanize + 5 MiMo (link card skipped)

    @pytest.mark.integration
    def test_link_card_stripped(self, sample_pitch, sample_articles, monkeypatch):
        """Link card with leading whitespace is still treated as link card."""
        import v3.model_router
        import db_reader

        monkeypatch.setattr(db_reader, "validate_link", lambda *a, **kw: True)

        spaced_cards = [
            "Hook 카드는 매우 길고 한글로 작성되었음.\n충분히 긴 내용을 가지고 있어야 하며 중요함.\n기사 원문의 중요한 정보를 모두 담았음.\n이 카드는 검증을 통과할 수 있는 길이임.",
            "두번째 카드도 비슷하게 충분히 긴 한글 카드입니다. 여기에도 많은 정보가 담겨 있으며 문장이 완성되어 있습니다.",
            "세번째 카드는 한글로 길게 작성되어 있고 문장 완성도 확인되었습니다. 이 카드는 본문의 정보를 충분히 담고 있습니다.",
            "네번째 카드, 이 카드도 역시 충분히 길고 한글로 구성되어 있습니다. 문장 완성도 확인하였고 검증을 통과할 수 있습니다.",
            "다섯번째 카드는 여운을 남기는 마무리입니다. 이 카드도 충분히 길게 작성되어 있으며 문장이 완성되어 있습니다.",
            "  🔗 https://example.com/ai-sentiment",
        ]
        mock_chat, call_log = _make_mock(generate_cards=spaced_cards)
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = write_thread(sample_pitch, sample_articles, format_choice="D")
        assert cards is not None
        assert len(cards) > 0