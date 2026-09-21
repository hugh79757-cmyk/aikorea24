"""Tests for pipeline.threads.compass — compass JSON generation and intro_style rotation."""
import pytest
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "threads"))


@pytest.fixture
def sample_pitch():
    return {
        "hook": "AI 공감 능력 평가 — 새로운 방법론",
        "narrative": "한국어로 작성된 내러티브로 충분한 길이와 구조를 갖춤.",
        "twist": "예상밖의 결과",
        "emotion": "놀람",
        "article_ids": [1],
        "crawled_body": (
            "2026년 7월 5일, AI 공감 능력 평가 새 방법론이 발표되었습니다. "
            "기존 방법론은 성능 측정에만 의존했지만, 새로운 연구는 100만 건의 "
            "대화 데이터를 분석했습니다. 기존 벤치마크는 72% 정확도에 그쳤지만 "
            "새 시스템은 89% 정확도를 기록했습니다."
        ),
        "crawled_url": "https://example.com/ai-sentiment",
    }


@pytest.fixture
def sample_articles():
    return [
        {
            "id": 1,
            "title": "AI 공감 능력 평가 새 연구결과",
            "link": "https://example.com/ai-sentiment",
            "source": "테스트사",
            "pub_date": "2026-07-05",
        },
    ]


VALID_COMPASS = {
    "category": "tech",
    "slot1_fact": "새 AI 평가 방법론이 100만 건 대화 데이터로 검증됨",
    "slot2_compare": "기존 72% vs 새 시스템 89% 정확도",
    "slot3_context": "기존 벤치마크는 72% 정확도에 그쳤지만 새 시스템은 89% 정확도를 기록했습니다",
    "slot4_outlook": "상용화 시 5조 원 시장 형성 전망",
    "intro_style": "number_shock",
    "h2_flow": ["기술적 배경", "핵심 수치", "적용 분야", "한계", "전망"],
    "tone": "neutral_careful",
    "table_plan": None,
}

VALID_CARDS = [
    "AI 공감 능력 평가의 새로운 방법론이 발표되었음. 100만 건의 대화 데이터를 분석해 89% 정확도를 기록했음.\n\n기존 벤치마크는 72%에 그쳤지만 새 시스템은 크게 발전함.\n\n이번 연구는 AI 업계에 새로운 기준을 제시했음.",
    "새 시스템은 문맥과 대화 흐름을 종합적으로 분석해 더 정확한 결과를 도출함.\n\n기존 시스템은 표면적 신호에 의존했지만 이번 연구는 근본적 변화를 가져옴.\n\n연구팀은 추가 연구를 통해 정확도를 더 높일 계획이라고 밝혔음.",
    "이 발견은 고객 서비스, 정신 건강, 교육 등 다양한 분야에서 활용될 수 있음.\n\n시장 조사 기관은 5조 원 규모의 시장을 형성할 것으로 전망했음.\n\n여러 글로벌 기업들이 이 기술에 주목하고 있음.",
    "결국 AI가 진정한 공감을 갖추려면 수치를 넘어 사람의 말과 행동을 이해하는 능력이 필요함.\n\n연구팀은 추가 연구를 통해 이 기술의 정확도를 더 높일 계획이라고 밝혔음.\n\nAI 감정 이해 기술의 미래가 기대되는 이유임.",
    "이 연구의 핵심은 AI가 인간의 감정을 단순히 감지하는 수준을 넘어 이해할 수 있다는 점임.\n\n이 기술이 상용화되면 AI 산업의 패러다임이 바뀔 것임.\n\n앞으로 AI가 정말 인간의 감정을 이해하는 시대가 올 수 있을까?",
]


def _make_mock_chat(compass_json=None, cards_json=None):
    """Create a mock_chat that dispatches Pass1/Pass2 by message content."""
    call_log = []
    compass_str = compass_json or json.dumps(VALID_COMPASS, ensure_ascii=False)
    cards_str = cards_json or json.dumps({"cards": VALID_CARDS}, ensure_ascii=False)

    def mock_chat(*, system_prompt, messages, temperature, max_tokens, response_format=None, **kwargs):
        call_log.append(1)
        user_msg = messages[0]["content"] if messages else ""
        # Pass 1: compass JSON generation
        if "=== 피치 ===" in user_msg or "=== 관련 기사 ===" in user_msg:
            return compass_str
        # Pass 2: body draft
        if "[컴퍼스]" in user_msg:
            return cards_str
        # fact-gate LLM call
        if "팩트체크" in (system_prompt or ""):
            return json.dumps({"verdict": "PASS", "reason": "출처 기반 주장"})
        return None

    return mock_chat, call_log


class TestCompassFields:
    """compass dict must contain all 9 required fields."""

    @pytest.mark.unit
    def test_compass_has_all_9_fields(self, sample_pitch, sample_articles, monkeypatch):
        import v3.model_router
        from pipeline.threads.compass import write_compass_article

        mock_chat, _ = _make_mock_chat()
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        monkeypatch.setattr(
            "pipeline.threads.compass._load_compass_rotation", lambda: 0
        )
        monkeypatch.setattr(
            "pipeline.threads.compass._save_compass_rotation", lambda c: None
        )

        result = write_compass_article(sample_pitch, sample_articles)
        assert result is not None
        compass, output = result
        assert isinstance(compass, dict)
        required = [
            "category", "slot1_fact", "slot2_compare", "slot3_context",
            "slot4_outlook", "intro_style", "h2_flow", "tone", "table_plan",
        ]
        for field in required:
            assert field in compass, f"누락 필드: {field}"

    @pytest.mark.unit
    def test_compass_returns_tuple_format(self, sample_pitch, sample_articles, monkeypatch):
        import v3.model_router
        from pipeline.threads.compass import write_compass_article

        mock_chat, _ = _make_mock_chat()
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)
        monkeypatch.setattr(
            "pipeline.threads.compass._load_compass_rotation", lambda: 0
        )
        monkeypatch.setattr(
            "pipeline.threads.compass._save_compass_rotation", lambda c: None
        )

        result = write_compass_article(sample_pitch, sample_articles)
        assert result is not None
        compass, output = result
        assert "cards" in output
        assert "link" in output
        assert isinstance(output["cards"], list)


class TestRotation:
    """intro_style must rotate across 5 distinct patterns via persistence."""

    @pytest.mark.unit
    def test_5_distinct_intro_styles(self, sample_pitch, sample_articles, monkeypatch):
        import v3.model_router
        from pipeline.threads.compass import write_compass_article, INTRO_STYLES

        saved_counters = []

        def mock_save(counter):
            saved_counters.append(counter)

        styles_seen = []
        for i in range(5):
            monkeypatch.setattr(
                "pipeline.threads.compass._load_intro_rotation", lambda i=i: i
            )
            monkeypatch.setattr(
                "pipeline.threads.compass._save_intro_rotation", mock_save
            )
            monkeypatch.setattr(
                "pipeline.threads.compass._compass_cache", {}
            )
            # Mock weighted_pick to return INTRO_STYLES[i % len] for determinism
            monkeypatch.setattr(
                "pipeline.threads.compass.weighted_pick",
                lambda items, recent, exclude_count=2, idx=[i]: items[idx[0] % len(items)],
            )

            mock_chat, _ = _make_mock_chat()
            monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)

            result = write_compass_article(sample_pitch, sample_articles)
            assert result is not None, f"rotation={i} 인 경우 실패"
            compass, _ = result
            styles_seen.append(compass["intro_style"])

        assert len(set(styles_seen)) >= 5, f"5개 고유 스타일 필요, got {set(styles_seen)}"
        assert styles_seen == list(INTRO_STYLES)[:5], (
            f"순서 불일치: {styles_seen} != {list(INTRO_STYLES)[:5]}"
        )

    @pytest.mark.unit
    def test_counter_persists_across_calls(self, sample_pitch, sample_articles, monkeypatch):
        import v3.model_router
        from pipeline.threads.compass import write_compass_article, INTRO_STYLES

        state = {"counter": 0}

        def mock_load():
            return state["counter"]

        def mock_save(counter):
            state["counter"] = counter

        monkeypatch.setattr(
            "pipeline.threads.compass._load_intro_rotation", mock_load
        )
        monkeypatch.setattr(
            "pipeline.threads.compass._save_intro_rotation", mock_save
        )
        monkeypatch.setattr(
            "pipeline.threads.compass._compass_cache", {}
        )
        monkeypatch.setattr(
            "pipeline.threads.compass.weighted_pick",
            lambda items, recent, exclude_count=2: items[0],
        )

        mock_chat, _ = _make_mock_chat()
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)

        # Run 3 times — counter should increment 0→1→2→3
        for expected_after in [1, 2, 3]:
            monkeypatch.setattr(
                "pipeline.threads.compass._compass_cache", {}
            )
            result = write_compass_article(sample_pitch, sample_articles)
            assert result is not None
            assert state["counter"] == expected_after

    @pytest.mark.unit
    def test_rotation_overrides_llm_intro_style(self, sample_pitch, sample_articles, monkeypatch):
        """Rotation counter overrides whatever intro_style the LLM returns."""
        import v3.model_router
        from pipeline.threads.compass import write_compass_article, INTRO_STYLES

        monkeypatch.setattr(
            "pipeline.threads.compass._load_intro_rotation", lambda: 3
        )
        monkeypatch.setattr(
            "pipeline.threads.compass._save_intro_rotation", lambda c: None
        )
        monkeypatch.setattr(
            "pipeline.threads.compass._compass_cache", {}
        )
        monkeypatch.setattr(
            "pipeline.threads.compass.weighted_pick",
            lambda items, recent, exclude_count=2: items[3],
        )

        # LLM returns "number_shock" but rotation 3 → weighted_pick returns INTRO_STYLES[3]
        compass_llm = {**VALID_COMPASS, "intro_style": "number_shock"}
        mock_chat, _ = _make_mock_chat(
            compass_json=json.dumps(compass_llm, ensure_ascii=False)
        )
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)

        result = write_compass_article(sample_pitch, sample_articles)
        assert result is not None
        compass, _ = result
        assert compass["intro_style"] == INTRO_STYLES[3]


class TestIntroStyleExamples:
    """INTRO_STYLE_EXAMPLES must define a concrete example for every pattern."""

    @pytest.mark.unit
    def test_intro_style_examples_defined(self):
        from pipeline.threads.compass import INTRO_STYLES, INTRO_STYLE_EXAMPLES

        assert len(INTRO_STYLES) == 5
        for style in INTRO_STYLES:
            assert style in INTRO_STYLE_EXAMPLES, f"예시 누락: {style}"
            assert INTRO_STYLE_EXAMPLES[style], f"빈 예시: {style}"


class TestNaverOutput:
    """output_target='naver' wraps cards in tag-whitelist HTML."""

    @pytest.mark.unit
    def test_naver_wraps_cards_in_p_tags(self, sample_pitch, sample_articles, monkeypatch):
        import v3.model_router
        from pipeline.threads.compass import write_compass_article

        monkeypatch.setattr(
            "pipeline.threads.compass._load_intro_rotation", lambda: 0
        )
        monkeypatch.setattr(
            "pipeline.threads.compass._save_intro_rotation", lambda c: None
        )
        monkeypatch.setattr(
            "pipeline.threads.compass._compass_cache", {}
        )
        monkeypatch.setattr(
            "pipeline.threads.compass.weighted_pick",
            lambda items, recent, exclude_count=2: items[0],
        )

        mock_chat, _ = _make_mock_chat()
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)

        result = write_compass_article(
            sample_pitch, sample_articles, output_target="naver"
        )
        assert result is not None
        _, output = result
        cards = output["cards"]
        assert len(cards) == 5
        for card in cards:
            # At least one <p> tag per card
            assert "<p>" in card, f"Naver HTML 누락: {card[:80]}"

    @pytest.mark.unit
    def test_threads_returns_plain_cards(self, sample_pitch, sample_articles, monkeypatch):
        import v3.model_router
        from pipeline.threads.compass import write_compass_article

        monkeypatch.setattr(
            "pipeline.threads.compass._load_intro_rotation", lambda: 0
        )
        monkeypatch.setattr(
            "pipeline.threads.compass._save_intro_rotation", lambda c: None
        )
        monkeypatch.setattr(
            "pipeline.threads.compass._compass_cache", {}
        )
        monkeypatch.setattr(
            "pipeline.threads.compass.weighted_pick",
            lambda items, recent, exclude_count=2: items[0],
        )

        mock_chat, _ = _make_mock_chat()
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)

        result = write_compass_article(
            sample_pitch, sample_articles, output_target="threads"
        )
        assert result is not None
        _, output = result
        cards = output["cards"]
        for card in cards:
            assert "<p>" not in card, f"threads 모드에서 HTML 태그 잔존: {card[:80]}"
