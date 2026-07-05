"""Tests for pipeline.threads.writer — E2E validation chain (retry, pattern detection, link cards)."""
import pytest
import json
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
    "AI 공감 능력 평가의 새로운 방법론이 발표되었음. 기존 방법론은 성능 측정에만 의존했지만, 새로운 연구는 100만 건의 대화 데이터를 분석했음.\n기존 벤치마크는 72% 정확도에 그쳤지만 새 시스템은 더 발전된 정확도를 보였음.\n새 시스템은 AI가 감정을 이해하는 수준에 도달했으며, 이 연구는 AI 감정 이해의 새로운 지평을 열었음.\n감정적 반응의 실제 복잡성을 드러냈고, 여러 기업들이 이 기술 도입에 관심을 보이고 있음.\nAI 감정 이해 기술의 미래는 매우 밝으며 계속 발전할 것임.",
    "그런데 새 시스템은 AI가 감정을 감지하는 것이 아닌 이해하는 것임을 입증했음. 감정 공감 능력의 큰 변화임. 이는 단순한 패턴 인식을 넘어, 실제로 인간의 감정 상태를 이해하는 수준에 도달했음을 의미함. 연구팀은 100만 건의 대화 데이터를 학습시켜 이 결과를 얻었음. 기존 AI 감정 분석 시스템은 표정이나 목소리 톤 같은 표면적 신호에 의존했음. 하지만 새 시스템은 문맥과 대화 흐름을 종합적으로 분석해 더 정확한 결과를 도출함. 이번 연구는 AI 업계에 큰 반향을 일으켰으며, 앞으로 이 기술이 어떻게 발전할지 주목됨. AI 감정 이해 기술이 상용화되면 산업 전반에 큰 변화가 일어날 것임.",
    "이 발견은 고객 서비스, 정신 건강, 교육 등 다양한 분야에서 실제로 적용될 수 있는 중요한 전환점임. 특히 정신 건강 분야에서는 AI가 환자의 감정 상태를 실시간으로 모니터링하는 데 활용될 수 있음. 교육 분야에서는 학생의 집중도와 이해도를 파악하는 데 도움이 될 것임. 고객 서비스에서는 상담사의 감정 상태를 분석해 더 나은 서비스를 제공할 수 있음. 시장 조사 기관은 이 기술이 5조 원 규모의 시장을 형성할 것으로 전망했음. 이는 AI 산업의 새로운 패러다임을 제시할 중요한 발전임. 연구팀의 발표 이후, 여러 글로벌 기업들이 이 기술에 주목하고 있음.",
    "결국 AI가 진정한 공감을 갖추려면 수치를 넘어 사람의 말과 행동을 이해하는 능력이 필요함. 단순한 데이터 분석을 넘어, 인간의 복잡한 감정 세계를 이해하는 것이 AI의 다음 과제임. 연구팀의 발표 이후, 여러 글로벌 기업들이 이 기술에 주목하고 있음. 특히 마이크로소프트와 구글은 자사의 AI 어시스턴트에 이 기술을 적용하는 방안을 검토 중임. 이는 AI 산업의 새로운 패러다임을 제시할 중요한 발전임. 앞으로 AI가 인간의 감정을 이해하는 수준에 도달할 수 있을지 귀추가 주목됨. AI 감정 이해 기술의 미래가 기대되는 이유임.",
    "이 연구의 핵심은 AI가 인간의 감정을 단순히 감지하는 수준을 넘어 이해할 수 있다는 점임. 이는 AI와 인간의 상호작용 방식을 근본적으로 변화시킬 잠재력을 가지고 있음. 앞으로 AI는 단순한 도구를 넘어, 인간의 감정적 니즈를 이해하고 대응할 수 있는 동반자로 진화할 것임. 연구팀은 추가 연구를 통해 이 기술의 정확도를 더 높일 계획이라고 밝혔음. AI 감정 이해 기술의 미래가 기대되는 이유임. 이 기술이 상용화되면 AI 산업의 패러다임이 완전히 바뀔 것임. AI가 인간의 감정을 이해하는 시대가 곧 도래할 것임.",
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
            return json.dumps({"cards": gen_cards})

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
            "첫번째 카드는 충분히 긴 내용을 가지고 있음. 한국어로만 작성된 검증 통과 가능한 카드임. 세번째 줄도 문제없이 읽을 수 있는 내용임. 네번째 줄까지 충분한 내용을 제공함. 다섯번째 줄도 추가로 내용을 채워서 400자 이상을 만들겠음. 여섯번째 줄까지 계속 내용을 추가해서 충분한 길이를 확보함. 이제 이 카드는 충분히 긴 카드가 되었음. 검증을 통과할 수 있는 충분한 내용을 담고 있음.",
            "一 중국어가 포함된 카드입니다. 이런 내용은 발행되면 안 됩니다. 검증 단계에서 걸러져야 합니다. 하지만 충분한 길이를 확보하기 위해 추가 내용을 더 채워넣겠음. 이 카드는 검증 단계에서 걸러질 예정이므로 내용이 길든 짧든 상관없지만, 400자 제한을 통과하기 위해 길게 작성함.",
            "세번째 카드도 충분히 길고 한글로만 구성되어야 합니다. 이 카드는 검증을 통과할 수 있습니다. 추가 내용을 더 넣어서 충분한 길이를 확보하겠음. 실제 기사에서도 이 정도 길이의 카드는 충분히 나올 수 있음. 계속해서 내용을 추가해 400자를 넘기도록 하겠음.",
            "네번째 카드는 문장이 완성되었습니다. 충분히 긴 내용을 가지고 있어 검증을 통과합니다. 추가로 더 많은 내용을 넣어서 카드 길이를 충분히 확보하겠음. 이렇게 길게 작성하면 검증을 통과할 수 있음.",
            "다섯번째 카드는 여운을 남기는 마무리입니다. 충분히 긴 내용을 가지고 있습니다. 추가로 내용을 더 채워서 400자 이상을 만들겠음. 계속해서 문장을 추가해 충분한 길이를 확보함.",
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
            "Hook 카드는 매우 길고 한글로 작성되었음. 충분히 긴 내용을 가지고 있어야 하며 중요함. 기사 원문의 중요한 정보를 모두 담았음. 이 카드는 검증을 통과할 수 있는 길이임. 추가로 더 많은 내용을 넣어서 충분한 길이를 확보하겠음. 계속해서 문장을 추가해서 긴 카드를 만들겠음.",
            "두번째 카드도 비슷하게 충분히 긴 한글 카드입니다. 여기에도 많은 정보가 담겨 있으며 문장이 완성되어 있습니다. 추가로 내용을 더 채워서 더 긴 카드를 만들겠음. 계속해서 문장을 추가해 충분한 길이를 확보함. 이렇게 길게 작성하면 검증을 통과할 수 있음.",
            "세번째 카드는 한글로 길게 작성되어 있고 문장 완성도 확인되었습니다. 이 카드는 본문의 정보를 충분히 담고 있습니다. 추가로 더 많은 내용을 넣어서 카드 길이를 충분히 확보하겠음. 계속해서 문장을 추가해서 긴 카드를 만들겠음.",
            "네번째 카드는 역시 충분히 길고 한글로 구성되어 있습니다. 문장 완성도 확인하였고 검증을 통과할 수 있습니다. 추가로 내용을 더 채워서 더 긴 카드를 만들겠음. 계속해서 문장을 추가해 충분한 길이를 확보함. 이제 이 카드는 충분히 긴 카드가 되었음.",
            "다섯번째 카드는 여운을 남기는 마무리입니다. 이 카드도 충분히 길게 작성되어 있으며 문장이 완성되어 있습니다. 추가로 더 많은 내용을 넣어서 충분한 길이를 확보하겠음. 계속해서 문장을 추가해서 긴 카드를 만들겠음.",
            "  🔗 https://example.com/ai-sentiment",
        ]
        mock_chat, call_log = _make_mock(generate_cards=spaced_cards)
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = write_thread(sample_pitch, sample_articles, format_choice="D")
        assert cards is not None
        assert len(cards) > 0