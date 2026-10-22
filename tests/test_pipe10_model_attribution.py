"""AIK24-PIPE-10 — 자동 생성 글의 주제 오인(모델 귀속) 재발 방지.

지시서: 2026-10-22-1125-AIK24-PIPE-10-자동글-주제오인-재발방지.md
사고: 2026-10-22 브리핑 1번 항목(news 56082)의 실체는 특정 모델 recursive/flint-v1.0:free 인데,
      연결된 블로그 글은 ":free 태그 활용 가이드" 일반론으로 생성됐고,
      실측 섹션에 다른 모델(google/gemini-2.0-flash-exp:free)의 출처 미확인 수치가 들어 있었다.

여기서는 3규칙을 각각 재현한다.
  규칙 1. 원본 항목이 특정 모델이면 제목·본문에 그 모델 ID 가 있어야 한다 (없으면 hold)
  규칙 2. 정량 실측 수치는 실행 기록(model_eval 캐시·리더보드·실행 로그)이 있을 때만
  규칙 3. 생성 시 사용한 모델 ID 와 원본 항목의 모델 ID 가 같아야 한다
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import model_attribution as ma  # noqa: E402


# ── 픽스처 ────────────────────────────────────────────────────────────────
# 사고 항목(news 56082): v2_tag 가 free-opportunity 이라 extract_model_id 조차 호출되지 않았던 건
ART_56082 = {
    "id": 56082,
    "title": "OpenRouter 무료 모델 (:free 태그)",
    "original_title": "OpenRouter 무료 모델 (:free 태그)",
    "v2_tag": "free-opportunity",
    "link": "https://openrouter.ai/models?max_price=0&order=newest",
    "description": ":free 태그가 붙은 모델을 무료로 호출 — 별도 크레딧 없이 API 키만으로 사용.",
}

# 사고 글의 원본 본문 일부 (emdash revisions 01M5GGA6KWGXBX7VQA6Z4F96JG, 2026-10-22 00:31:26 UTC)
INCIDENT_BODY = (
    "## 5. ai.kr.24 실측 결과 — 신뢰도 검증\n"
    "2026년 10월 16일 기준, ai.kr.24 팀은 OpenRouter 무료 모델 "
    "`google/gemini-2.0-flash-exp:free` 에 대해 100회 연속 호출 테스트를 수행했습니다. "
    "검증 방법은 Python requests 입니다.\n"
)

# 실제 모델 항목(news 56721) — 모델 심층 경로 대상
ART_MODEL = {
    "id": 56721,
    "title": "[무료 LLM] flint-40b-free — OpenCode Zen 무료 티어",
    "original_title": "[무료 LLM] flint-40b-free — OpenCode Zen 무료 티어",
    "v2_tag": "free-llm",
    "link": "https://openrouter.ai/flint-40b-free",
}

# 일반 뉴스 항목 — 귀속 규칙 적용 대상이 아니다
ART_NEWS = {
    "id": 1,
    "source": "TechCrunch AI",
    "title": "구글, 유료 구독자에 비해 픽셀 등 무료 AI Pro 체험 사용자의 기능",
    "original_title": "구글, 유료 구독자에 비해 픽셀 등 무료 AI Pro 체험 사용자의 기능",
    "v2_tag": "news",
    "link": "https://blog.google/",
    "description": "무료 체험",
}


class TestRule2MeasurementWithoutRecord:
    """규칙 2 — 실측 기록이 없는 수치는 금지."""

    def test_incident_case_is_blocked(self):
        """오늘 사고 케이스: 원본 56082 + 허위 실측 → hold 사유가 나와야 한다."""
        issues = ma.check_attribution(
            "OpenRouter 무료 모델 (:free 태그) 활용 가이드", INCIDENT_BODY, ART_56082
        )
        assert issues, "사고 케이스가 검출되지 않았다"
        assert any("미실측 수치" in i for i in issues), issues
        assert any("google/gemini-2.0-flash-exp:free" in i for i in issues), issues

    def test_fabricated_model_has_no_record(self):
        """규칙 2 의 근거: 사고 글의 모델은 실행 기록이 없다."""
        assert ma.normalize_model_key("google/gemini-2.0-flash-exp:free") not in ma.evaluated_model_ids()

    def test_one_off_eval_artifact_counts_as_record(self):
        """1회성 평가 산출물(정본 미반영)도 '실행 기록'으로 인정한다.

        2026-10-22: Recursive Flint 12문항 실측이 `flint_eval_result.json` 에만 있고
        정본 3종(캐시·리더보드·runs)에는 아직 없다. 기록이 존재하므로
        그 수치가 든 글을 규칙 2 가 막으면 안 된다.
        """
        import pathlib

        artifact = pathlib.Path(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "scripts", "logs", "flint_eval_result.json",
            )
        )
        if not artifact.exists():
            return  # 산출물이 없으면 판정 대상이 아니므로 통과로 둔다
        assert "recursive/flint-v1.0:free" in ma.evaluated_model_ids()

    def test_general_news_with_number_passes(self):
        """모델을 언급하지 않으면 정량 수치가 있어도 귀속 위반이 아니다(일반 뉴스)."""
        body = "## 도입\n2024년 10월 기준 기능이 3개 개선됐습니다.\n"
        assert ma.check_attribution("구글 픽셀 AI Pro 무료 체험", body, ART_NEWS) == []


class TestRule1ModelIdMandatory:
    """규칙 1 — 원본 항목이 특정 모델이면 그 ID 가 제목·본문에 있어야 한다."""

    def test_missing_model_id_is_blocked(self):
        issues = ma.check_attribution("무료 LLM 활용법", "## 도입\n본문\n", ART_MODEL)
        assert issues, "모델 ID 누락이 검출되지 않았다"
        assert any("모델 귀속 누락" in i and "flint-40b-free" in i for i in issues), issues

    def test_present_model_id_passes(self):
        body = "## 도입\n`flint-40b-free` 는 OpenCode Zen 무료 티어에서 쓸 수 있습니다.\n"
        assert ma.check_attribution("무료 LLM flint-40b-free 활용법", body, ART_MODEL) == []

    def test_source_model_id_extraction(self):
        assert ma.source_model_id(ART_MODEL) == "flint-40b-free"
        # 사고 항목은 특정 모델 ID 가 없다 → 규칙 1·3 은 발동하지 않는다
        assert ma.source_model_id(ART_56082) is None
        assert ma.source_model_id(ART_NEWS) is None

    def test_original_title_is_priority(self):
        art = {"title": "다른 제목", "original_title": "[무료 LLM] recursive/flint-v1.0:free — 설명"}
        assert ma.source_model_id(art) == "recursive/flint-v1.0:free"
        # 접두사·접미사가 붙어도 같은 모델로 판정된다
        assert ma.same_model(ma.source_model_id(art), "recursive/flint-v1.0")


class TestRule3ModelNameMatch:
    """규칙 3 — 생성 시 사용한 모델과 원본 항목의 모델이 같아야 한다."""

    def test_mismatch_is_blocked(self):
        issues = ma.check_attribution(
            "무료 LLM 활용법", "## 도입\n`flint-40b-free` 소개\n", ART_MODEL,
            used_model_id="recursive/flint-v1.0:free",
        )
        assert issues, "모델명 불일치가 검출되지 않았다"
        assert any("모델명 불일치" in i for i in issues), issues

    def test_match_passes(self):
        body = "## 도입\n`flint-40b-free` 소개\n"
        assert ma.check_attribution("무료 LLM 활용법", body, ART_MODEL,
                                    used_model_id="flint-40b-free") == []

    def test_normalization_is_provider_and_suffix_insensitive(self):
        """PIPE-05 정규화 재사용: 접두사·접미사가 달라도 같은 모델로 본다.

        단일 정규화 키는 비대칭이라(``opencode/flint-40b-free``→``flint-40b`` vs
        ``flint-40b-free``→``flint-40b-free``) 비교는 **키 집합의 교집합**으로 한다.
        """
        assert ma.same_model("opencode/flint-40b-free", "flint-40b-free")
        assert ma.same_model("opencode/flint-40b-free:free", "flint-40b-free")
        assert ma.same_model("kilo/minimax/minimax-m3.1-flash:free", "minimax/minimax-m3.1-flash")
        assert not ma.same_model("flint-40b-free", "recursive/flint-v1.0:free")
        assert not ma.same_model("beam-free", "big-pickle")


class TestNoRegression:
    """회귀 없음 — 정상 모델 글·일반 뉴스 글은 기존대로 통과."""

    def test_normal_model_post_passes(self):
        body = (
            "## 도입\n`flint-40b-free` 는 OpenCode Zen 무료 티어에서 쓸 수 있습니다. "
            "12문항 중 8문항 정답입니다. 표와 링크로 정리했습니다.\n"
        )
        assert ma.check_attribution("무료 LLM flint-40b-free 활용법", body, ART_MODEL) == []

    def test_plain_news_passes(self):
        body = "## 도입\n무료 체험 기능을 정리했습니다. 표 1개, 링크 3개.\n"
        assert ma.check_attribution("구글 픽셀 AI Pro 무료 체험", body, ART_NEWS) == []

    def test_mentioned_ids_use_backticks_only(self):
        """링크·경로(techcrunch.com/2026, application/json)를 모델 ID 로 오인하지 않는다."""
        text = "`recursive/flint-v1.0:free` 와 https://techcrunch.com/2026/10/21/x 및 application/json"
        ids = ma.mentioned_model_ids(text)
        assert ids == ["recursive/flint-v1.0:free"], ids


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))


class TestGateIntegration:
    """발행 게이트 통합 — _gate_and_fix 안에서 귀속 검사가 실제로 hold 를 만드는지."""

    def test_gate_helper_flags_incident(self):
        import blog_draft_generator as b

        fp = "/tmp/pipe10-fixture.md"
        b._EMDASH_PENDING[fp] = {
            "md": "---\ntitle: x\n---\n\n" + INCIDENT_BODY,
            "links": [],
            "model_id": None,
        }
        try:
            issues = b._attribution_issues(
                "OpenRouter 무료 모델 (:free 태그) 활용 가이드", ART_56082, fp
            )
            assert issues, "게이트 헬퍼가 사고 케이스를 잡지 못했다"
            assert any("미실측 수치" in i for i in issues), issues
        finally:
            b._EMDASH_PENDING.pop(fp, None)

    def test_gate_helper_passes_normal_model_post(self):
        import blog_draft_generator as b

        fp = "/tmp/pipe10-fixture2.md"
        b._EMDASH_PENDING[fp] = {
            "md": "---\ntitle: x\n---\n\n## 도입\n`flint-40b-free` 는 OpenCode Zen 무료 티어에서 쓸 수 있습니다.\n",
            "links": [],
            "model_id": "flint-40b-free",
        }
        try:
            assert b._attribution_issues("무료 LLM flint-40b-free 활용법", ART_MODEL, fp) == []
        finally:
            b._EMDASH_PENDING.pop(fp, None)

    def test_gate_helper_never_raises(self):
        """검사기가 예외를 내도 게이트를 죽이지 않는다(항상 리스트를 돌린다)."""
        import blog_draft_generator as b

        out = b._attribution_issues("t", ART_MODEL, "/tmp/없는파일.md")
        assert isinstance(out, list)


class TestPromptInjection:
    """규칙 1 전반부 — 생성 입력에 모델 ID 가 명시적으로 들어가는지."""

    def test_news_path_prompt_contains_model_id(self, monkeypatch):
        import blog_draft_generator as b

        art = {
            "id": 999,
            "title": "[무료 모델] recursive/flint-v1.0:free — Recursive 새 코딩 모델",
            "original_title": "[무료 모델] recursive/flint-v1.0:free — Recursive 새 코딩 모델",
            "v2_tag": "free-opportunity",   # 모델 심층 경로가 아닌 뉴스 경로
            "link": "https://openrouter.ai/recursive/flint-v1.0:free",
            "description": "Recursive 가 공개한 코딩 모델",
            "source": "TechCrunch AI",
        }
        captured = {}

        def fake_chat(messages, **kw):
            captured["prompt"] = messages[0]["content"]
            return "TITLE: stub\n---\n## 마무리 — stub\n본문"

        monkeypatch.setattr(b, "chat_completion", fake_chat)
        monkeypatch.setattr(b, "save_draft", lambda *a, **k: ("/tmp/stub.md", "stub"))
        b.generate_draft("[무료 모델] recursive/flint-v1.0:free — Recursive 새 코딩 모델",
                         [art], "A", link_hint=False)
        assert "recursive/flint-v1.0:free" in captured["prompt"], \
            "생성 입력에 모델 ID 가 명시되지 않았다"
        assert "이 글의 대상 모델은" in captured["prompt"]

    def test_general_news_prompt_has_no_model_hint(self, monkeypatch):
        import blog_draft_generator as b

        captured = {}

        def fake_chat(messages, **kw):
            captured["prompt"] = messages[0]["content"]
            return "TITLE: stub\n---\n## 마무리 — stub\n본문"

        monkeypatch.setattr(b, "chat_completion", fake_chat)
        monkeypatch.setattr(b, "save_draft", lambda *a, **k: ("/tmp/stub.md", "stub"))
        b.generate_draft("구글 픽셀 AI Pro 무료 체험", [ART_NEWS], "A", link_hint=False)
        assert "이 글의 대상 모델은" not in captured["prompt"]
