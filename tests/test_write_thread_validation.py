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


def _valid_6cards():
    """Return valid 6-card Korean response."""
    return "\n---\n".join([
        "AI가 \uacf5\uac10\uc744 \uc774\ud574\ud558\ub294 \uac83\uc774 \uc544\ub2c8\ub77c \uac10\uc9c0\ud558\ub294 \uac83\uc73c\ub85c \ubc1d\ud600\uc84c\uc74c.",
        "\uc774 \uc5f0\uad6c\ub294 100\ub9cc \uac74\uc758 \ub300\ud654 \ub370\uc774\ud130\ub97c \ubd84\uc11d\ud588\uc74c. \uae30\uc874 \ubca4\uce58\ub9c8\ud06c\ub294 72%\uc758 \uc815\ud655\ub3c4\uc5d0 \uadf8\uce58\uba74\uc11c \uc0ac\ub78c\uc758 89%\uc5d0 \ud06c\uac8c \ubabb \ubbf8\uce58\uace0 \uc788\uc5c8\uc74c. \uc774\uac83\uc740 \uc131\ub2a5 \uce21\uc815\ub9cc\uc73c\ub85c\ub294 \ucda9\ubd84\ud558\uc9c0 \uc54a\ub2e4\ub294 \uc99d\uac70\uc784.",
        "\uadf8\ub7f0\ub370 \uc0c8 \uc2dc\uc2a4\ud15c\uc740 AI\uac00 \uac10\uc815\uc744 \uac10\uc9c0\ud558\ub294 \uac83\uc774 \uc544\ub2cc \uc774\ud574\ud558\ub294 \uac83\uc784\uc744 \uc785\uc99d\ud588\uc74c. \uc774\uac83\uc740 \uac10\uc815 \uacf5\uac10 \ub2a5\ub825\uc758 \ud070 \ubcc0\ud654\ub97c \uc758\ubbf8\ud568.",
        "\uc774 \ubc1c\uacac\uc740 \uace0\uac1d \uc11c\ube44\uc2a4, \uc815\uc2e0 \uac74\uac15, \uad50\uc721 \ub4f1 \ub2e4\uc591\ud55c \ubd84\uc57c\uc5d0\uc11c \uc2e4\uc81c\ub85c \uc801\uc6a9\ub420 \uc218 \uc788\ub294 \uc911\uc694\ud55c \uc804\ud658\uc810\uc784.",
        "\uacb0\uad6d AI\uac00 \uc9c4\uc815\ud55c \uacf5\uac10\uc744 \uac16\ucd94\ub824\uba74 \uc218\uce58\ub97c \ub118\uc5b4 \uc0ac\ub78c\uc758 \ub9d0\uacfc \ud589\ub3d9\uc744 \uc774\ud574\ud558\ub294 \ub2a5\ub825\uc774 \ud544\uc694\ud568.",
        "\U0001f517 https://example.com/ai-sentiment",
    ])


class TestWriteThreadValidationChain:
    """E2E validation chain: retry on Chinese, courteous patterns, prompt leak, success."""

    @pytest.mark.integration
    def test_chinese_char_retry(self, sample_pitch, sample_articles, monkeypatch):
        """First response contains Chinese character → retry → second valid."""
        import v3.model_router
        import db_reader

        # Mock validate_link: always valid
        monkeypatch.setattr(db_reader, "validate_link", lambda *a, **kw: True)

        call_log = []
        def mock_chat(*, system_prompt, messages, temperature, max_tokens):
            call_log.append(1)
            if len(call_log) == 1:
                # First: card with Chinese character (一)
                return "\n---\n".join([
                    "\ud55c\uae00 \uce74\ub4dc\ub294 \ucda9\ubd84\ud788 \uae38\uace0",
                    "\u4e00 \uc911\uad6d\uc5b4\uac00 \ud3ec\ud568\ub41c \uce74\ub4dc\uc785\ub2c8\ub2e4. \uc774\ub7f0 \ub0b4\uc6a9\uc740 \ubc1c\ud589\ub418\uba74 \uc548 \ub429\ub2c8\ub2e4.",
                    "\uc138\ubc88\uc9f8 \uce74\ub4dc\ub3c4 \ucda9\ubd84\ud788 \uae38\uace0 \ud55c\uae00\ub85c\ub9cc \uad6c\uc131\ub418\uc5b4\uc57c \ud558\ub294\ub370",
                    "\ub124\ubc88\uc9f8 \uce74\ub4dc\ub294 \ubb38\uc7a5\uc774 \uc644\uc131\ub418\uc5c8\uc2b5\ub2c8\ub2e4.",
                    "\ub2e4\uc12f\ubc88\uc9f8 \uce74\ub4dc\ub294 \uc5ec\uc6b4\uc744 \ub0a8\uae30\ub294 \ub9c8\ubb34\ub9ac\uc785\ub2c8\ub2e4.",
                    "\U0001f517 https://example.com/ai-sentiment",
                ])
            else:
                return _valid_6cards()

        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = write_thread(sample_pitch, sample_articles, format_choice="D")
        assert cards is not None
        assert len(cards) > 0
        assert len(call_log) >= 2

    @pytest.mark.integration
    def test_polite_additional_retry(self, sample_pitch, sample_articles, monkeypatch):
        """First response contains polite ADDITIONAL pattern ('네') → retry → second valid."""
        import v3.model_router
        import db_reader

        monkeypatch.setattr(db_reader, "validate_link", lambda *a, **kw: True)

        call_log = []
        def mock_chat(*, system_prompt, messages, temperature, max_tokens):
            call_log.append(1)
            if len(call_log) == 1:
                return "네\n---\n" + "\n---\n".join([
                    "\ud55c\uae00 \uce74\ub4dc \ud558\ub098\uc774\ub2e4. \uadf8\ub807\uc9c0\ub9cc \ucda9\ubd84\ud788 \uae34 \ub0b4\uc6a9\uc774 \uc544\ub2c8\ub2e4.",
                    "\ub450\ubc88\uc9f8 \uce74\ub4dc\ub3c4 \ud55c\uae00\uc73c\ub85c \uae34 \ub0b4\uc6a9\uc744 \uac00\uc84c\uc74c.",
                    "\uc138\ubc88\uc9f8 \uce74\ub4dc, \ubb38\uc7a5 \uc644\uc131\ub3c4 \uc0dd\uac01\ud574\uc57c \ud568.",
                    "\ub124\ubc88\uc9f8 \uce74\ub4dc, \uad6c\uc870\ub3c4 \ucda9\ubd84\ud788 \uac16\ucd94\uc5b4\uc57c \ud568.",
                    "\ub2e4\uc12f\ubc88\uc9f8 \uce74\ub4dc\ub294 \uc5ec\uc6b4\uc744 \ub0a8\uae41\ub2c8\ub2e4.",
                    "\U0001f517 https://example.com/ai-sentiment",
                ])
            else:
                return _valid_6cards()

        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = write_thread(sample_pitch, sample_articles, format_choice="D")
        assert cards is not None
        assert len(cards) > 0
        assert len(call_log) >= 2

    @pytest.mark.integration
    def test_prompt_label_leak_retry(self, sample_pitch, sample_articles, monkeypatch):
        """First response contains prompt label leak ('상식(A):') → retry → second valid."""
        import v3.model_router
        import db_reader

        monkeypatch.setattr(db_reader, "validate_link", lambda *a, **kw: True)

        call_log = []
        def mock_chat(*, system_prompt, messages, temperature, max_tokens):
            call_log.append(1)
            if len(call_log) == 1:
                return "\n---\n".join([
                    "\uc0c1\uc2dd(A): AI\uac00 \uac10\uc815\uc744 \uc774\ud574\ud560 \uc218 \uc788\ub2e4.",
                    "\ub450\ubc88\uc9f8 \uce74\ub4dc\ub294 \ucda9\ubd84\ud788 \uae38\uace0 \ud55c\uae00\ub85c\ub9cc \uad6c\uc131\ub418\uc5c8\uc2b5\ub2c8\ub2e4.",
                    "\uc138\ubc88\uc9f8 \uce74\ub4dc\ub3c4 \uae38\uace0 \ucda9\ubd84\ud55c \ud55c\uae00 \uce74\ub4dc\uc785\ub2c8\ub2e4.",
                    "\ub124\ubc88\uc9f8 \uce74\ub4dc\ub3c4 \ubb38\uc7a5\uc774 \uc644\uc131\ub418\uc5c8\uc2b5\ub2c8\ub2e4.",
                    "\ub2e4\uc12f\ubc88\uc9f8 \uce74\ub4dc\ub294 \uc5ec\uc6b4\uc744 \ub0a8\uae41\ub2c8\ub2e4.",
                    "\U0001f517 https://example.com/ai-sentiment",
                ])
            else:
                return _valid_6cards()

        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = write_thread(sample_pitch, sample_articles, format_choice="D")
        assert cards is not None
        assert len(cards) > 0
        assert len(call_log) >= 2

    @pytest.mark.integration
    def test_success_on_second_attempt(self, sample_pitch, sample_articles, monkeypatch):
        """Retry mechanism: first fails validation, second succeeds."""
        import v3.model_router
        import db_reader

        monkeypatch.setattr(db_reader, "validate_link", lambda *a, **kw: True)

        call_log = []
        def mock_chat(*, system_prompt, messages, temperature, max_tokens):
            call_log.append(1)
            if len(call_log) == 1:
                # Too short — will fail validation
                return "\n---\n".join([
                    "\uc9e7\uc740 \ud6c5 \ubb38\uc7a5\uc784.",
                    "\ub450\ubc88\uc9f8 \uce74\ub4dc\ub294 \uae38\ucc98\ub7fc \ubcf4\uc774\uc9c0\ub9cc \uc62c\ubc14\ub978 \uac80\uc99d\uc744 \ud1b5\uacfc\ud558\uc9c0 \ubabb\ud568.",
                    "\uc138\ubc88\uc9f8 \uce74\ub4dc\uc758 \ub0b4\uc6a9\uc740 \ub9e4\uc6b0 \uc9e7\uc2b5\ub2c8\ub2e4.",
                    "\ub124\ubc88\uc9f8 \uce74\ub4dc\ub3c4 \uc5ed\uc2dc \uc9e7\uac8c \uc791\uc131\ub418\uc5c8\uc2b5\ub2c8\ub2e4.",
                    "\ub2e4\uc12f\ubc88\uc9f8 \uce74\ub4dc\ub294 \uc5ec\uc6b4\uc744 \ub0a8\uae41\ub2c8\ub2e4.",
                    "\U0001f517 https://example.com/ai-sentiment",
                ])
            else:
                return _valid_6cards()

        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = write_thread(sample_pitch, sample_articles, format_choice="D")
        assert cards is not None
        assert len(cards) > 0
        assert len(call_log) >= 2

    @pytest.mark.integration
    def test_success_without_issues(self, sample_pitch, sample_articles, monkeypatch):
        """All checks pass on first attempt — no retry needed."""
        import v3.model_router
        import db_reader

        monkeypatch.setattr(db_reader, "validate_link", lambda *a, **kw: True)

        call_log = []
        def mock_chat(*, system_prompt, messages, temperature, max_tokens):
            call_log.append(1)
            return _valid_6cards()

        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = write_thread(sample_pitch, sample_articles, format_choice="D")
        assert cards is not None
        assert len(cards) > 0
        assert len(call_log) >= 1  # At least one attempt (main + humanize + fix)

    @pytest.mark.integration
    def test_link_card_stripped(self, sample_pitch, sample_articles, monkeypatch):
        """Link card with leading whitespace is still treated as link card."""
        import v3.model_router
        import db_reader

        monkeypatch.setattr(db_reader, "validate_link", lambda *a, **kw: True)

        call_log = []
        def mock_chat(*, system_prompt, messages, temperature, max_tokens):
            call_log.append(1)
            # Link card with leading whitespace — all body cards must be long enough (50+ chars min)
            return "\n---\n".join([
                "\ud6c5 \uce74\ub4dc\ub294 \ub9e4\uc6b0 \uae38\uace0 \ud55c\uae00\ub85c \uc791\uc131\ub418\uc5c8\uc2b5\ub2c8\ub2e4. \ucda9\ubd84\ud788 500\uc790 \uc774\uc0c1\uc758 \ub0b4\uc6a9\uc744 \uac16\ucd94\uace0 \uc788\uc5b4\uc57c \ud569\ub2c8\ub2e4. \uae30\uc0ac \uc6d0\ubb38\uc758 \uc911\uc694\ud55c \uc815\ubcf4\ub97c \ud6c5\uc5d0 \ub2f4\uc558\uc2b5\ub2c8\ub2e4.",
                "\ub450\ubc88\uc9f8 \uce74\ub4dc\ub3c4 \ube44\uc2b7\ud558\uac8c \ucda9\ubd84\ud788 \uae34 \ud55c\uae00 \uce74\ub4dc\uc785\ub2c8\ub2e4. \uc5ec\uae30\uc5d0\ub3c4 \ub9ce\uc740 \uc815\ubcf4\uac00 \ub2f4\uaca8 \uc788\uc73c\uba70 \ubb38\uc7a5\uc774 \uc644\uc131\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4. \uac80\uc99d\uc744 \ud1b5\uacfc\ud560 \uc218 \uc788\ub294 \ucda9\ubd84\ud55c \uae38\uc774\uc784.",
                "\uc138\ubc88\uc9f8 \uce74\ub4dc\ub294 \ud55c\uae00\ub85c \uae38\uac8c \uc791\uc131\ub418\uc5b4 \uc788\uace0 \ubb38\uc7a5 \uc644\uc131\ub3c4 \uba4b\uc9c0\uac8c \ud655\uc778\ub418\uc5c8\uc2b5\ub2c8\ub2e4. \uc774 \uce74\ub4dc\ub294 \ubcf8\ubb38\uc758 \uc815\ubcf4\ub97c \ucda9\ubd84\ud788 \ub2f4\uace0 \uc788\uc73c\uba70 \uc544\ubb34 \ubb38\uc81c\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.",
                "\ub124\ubc88\uc9f8 \uce74\ub4dc, \uc774 \uce74\ub4dc\ub3c4 \uc5ed\uc2dc \ucda9\ubd84\ud788 \uae38\uace0 \ud55c\uae00\ub85c \uad6c\uc131\ub418\uc5b4 \uc788\uc2b5\ub2c8\ub2e4. \ubb38\uc7a5 \uc644\uc131\ub3c4 \ud655\uc778\ud558\uc600\uace0 \ubaa8\ub4e0 \uac80\uc99d\uc744 \ubb38\uc81c\uc5c6\uc774 \ud1b5\uacfc\ud560 \uc218 \uc788\uc744 \uac83\uc785\ub2c8\ub2e4.",
                "\ub2e4\uc12f\ubc88\uc9f8 \uce74\ub4dc\ub294 \uc5ec\uc6b4\uc744 \ub0a8\uae30\ub294 \ub9c8\ubb34\ub9ac\uc785\ub2c8\ub2e4. \uc774 \uce74\ub4dc\ub3c4 \ucda9\ubd84\ud788 \uae38\uac8c \uc791\uc131\ub418\uc5b4 \uc788\uc73c\uba70 \ubb38\uc7a5 \ub610\ud55c \uc644\uc131\ub418\uc5b4 \uc788\uc5b4 \uac80\uc99d\uc744 \ud1b5\uacfc\ud568.",
                "  \U0001f517 https://example.com/ai-sentiment",
            ])

        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        cards = write_thread(sample_pitch, sample_articles, format_choice="D")
        assert cards is not None
        assert len(cards) > 0