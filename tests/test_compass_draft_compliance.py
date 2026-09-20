"""Tests for pipeline.threads.compass — draft tone compliance and leak detection."""
import pytest
import json
import re
import sys
from pathlib import Path

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


FORMAL_CARDS = [
    "AI 공감 능력 평가의 새로운 방법론이 발표되었습니다. 100만 건의 대화 데이터를 분석하여 89% 정확도를 기록했습니다.\n\n기존 벤치마크는 72%에 그쳤지만 새 시스템은 크게 발전했습니다.\n\n이번 연구는 AI 업계에 새로운 기준을 제시했습니다.",
    "새 시스템은 문맥과 대화 흐름을 종합적으로 분석하여 더 정확한 결과를 도출했습니다.\n\n기존 시스템은 표면적 신호에 의존했지만 이번 연구는 근본적 변화를 가져왔습니다.\n\n연구팀은 추가 연구를 통해 정확도를 더 높일 계획이라고 발표했습니다.",
    "이 발견은 고객 서비스, 정신 건강, 교육 등 다양한 분야에서 활용될 수 있습니다.\n\n시장 조사 기관은 5조 원 규모의 시장을 형성할 것으로 전망했습니다.\n\n여러 글로벌 기업들이 이 기술에 주목하고 있습니다.",
    "결국 AI가 진정한 공감을 갖추려면 수치를 넘어 사람의 말과 행동을 이해하는 능력이 필요합니다.\n\n연구팀은 추가 연구를 통해 이 기술의 정확도를 더 높일 계획이라고 밝혔습니다.\n\nAI 감정 이해 기술의 미래가 기대되는 이유입니다.",
    "이 연구의 핵심은 AI가 인간의 감정을 단순히 감지하는 수준을 넘어 이해할 수 있다는 점입니다.\n\n이 기술이 상용화되면 AI 산업의 패러다임이 바뀔 것입니다.\n\n앞으로 AI가 정말 인간의 감정을 이해하는 시대가 올 수 있을까요?",
]

LEAKED_CARDS = [
    "AI 공감 능력 평가의 새로운 방법론이 발표되었습니다. slot1_fact: 핵심 사실입니다.\n\n기존 벤치마크는 72%에 그쳤지만 새 시스템은 크게 발전했습니다.\n\n이번 연구는 AI 업계에 새로운 기준을 제시했습니다.",
    "새 시스템은 문맥과 대화 흐름을 종합적으로 분석하여 더 정확한 결과를 도출했습니다.\n\n기존 시스템은 표면적 신호에 의존했지만 이번 연구는 근본적 변화를 가져왔습니다.\n\n연구팀은 추가 연구를 통해 정확도를 더 높일 계획이라고 발표했습니다.",
    "이 발견은 고객 서비스, 정신 건강, 교육 등 다양한 분야에서 활용될 수 있습니다.\n\n시장 조사 기관은 5조 원 규모의 시장을 형성할 것으로 전망했습니다.\n\n여러 글로벌 기업들이 이 기술에 주목하고 있습니다.",
    "결국 AI가 진정한 공감을 갖추려면 수치를 넘어 사람의 말과 행동을 이해하는 능력이 필요합니다.\n\n연구팀은 추가 연구를 통해 이 기술의 정확도를 더 높일 계획이라고 밝혔습니다.\n\nAI 감정 이해 기술의 미래가 기대되는 이유입니다.",
    "이 연구의 핵심은 AI가 인간의 감정을 단순히 감지하는 수준을 넘어 이해할 수 있다는 점입니다.\n\n이 기술이 상용화되면 AI 산업의 패러다임이 바뀔 것입니다.\n\n앞으로 AI가 정말 인간의 감정을 이해하는 시대가 올 수 있을까요?",
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


def _make_mock_chat(cards_json):
    call_log = []

    def mock_chat(*, system_prompt, messages, temperature, max_tokens, response_format=None, **kwargs):
        call_log.append(1)
        user_msg = messages[0]["content"] if messages else ""
        if "=== 피치 ===" in user_msg or "=== 관련 기사 ===" in user_msg:
            return json.dumps(VALID_COMPASS, ensure_ascii=False)
        if "[컴퍼스]" in user_msg:
            return cards_json
        if "팩트체크" in (system_prompt or ""):
            return json.dumps({"verdict": "PASS", "reason": "출처 기반 주장"})
        return None

    return mock_chat, call_log


class TestToneFormal:
    """Draft must use formal tone (~습니다/~합니다)."""

    @pytest.mark.unit
    def test_formal_endings_present(self, sample_pitch, sample_articles, monkeypatch):
        import v3.model_router
        from pipeline.threads.compass import write_compass_article

        cards_json = json.dumps({"cards": FORMAL_CARDS}, ensure_ascii=False)
        mock_chat, _ = _make_mock_chat(cards_json)
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)

        result = write_compass_article(sample_pitch, sample_articles)
        assert result is not None
        _, output = result
        all_text = " ".join(output["cards"])
        # At least 3 cards should end with formal ~습니다/~합니다/~입니다/~입니다/~でした/~ㅂ니다
        formal_endings = re.findall(r'[가-힣]+(?:습니다|합니다|입니다|였습니다|하겠습니다|ㅂ니다)', all_text)
        assert len(formal_endings) >= 3, f"공식 종결어미 부족: {len(formal_endings)}개"


class TestNoLeak:
    """Draft must not contain compass field labels."""

    @pytest.mark.unit
    def test_no_compass_labels_in_draft(self, sample_pitch, sample_articles, monkeypatch):
        import v3.model_router
        from pipeline.threads.compass import write_compass_article

        cards_json = json.dumps({"cards": FORMAL_CARDS}, ensure_ascii=False)
        mock_chat, _ = _make_mock_chat(cards_json)
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)

        result = write_compass_article(sample_pitch, sample_articles)
        assert result is not None
        _, output = result
        all_text = " ".join(output["cards"])
        compass_labels = [
            "slot1_fact", "slot2_compare", "slot3_context",
            "slot4_outlook", "intro_style", "h2_flow",
        ]
        for label in compass_labels:
            assert not re.search(rf'{label}\s*[:：]', all_text), (
                f"compass 레이블 '{label}'이 카드에 누출됨"
            )

    @pytest.mark.unit
    def test_leaked_cards_rejected(self, sample_pitch, sample_articles, monkeypatch):
        """Cards with compass labels should be rejected by write_compass_article."""
        import v3.model_router
        from pipeline.threads.compass import write_compass_article

        cards_json = json.dumps({"cards": LEAKED_CARDS}, ensure_ascii=False)
        mock_chat, _ = _make_mock_chat(cards_json)
        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat)

        result = write_compass_article(sample_pitch, sample_articles)
        assert result is None, "누출된 카드가 통과하면 안 됨"
