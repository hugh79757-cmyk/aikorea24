"""tests/test_pipe13_openweight_runnable.py

AIK24-PIPE-13 회귀 테스트 — "오픈 웨이트 = 쓸 수 있다" 전제 제거.

- 파라미터 규모 추출 (extract_param_scale_b): 1T/1조/671B/70B/7B 등
- 실행 가능성 판정 (is_runnable_scale): 컷오프 32B
- free_usability 점수 조건부 부여: 실행 불가 오픈 웨이트는 open-weight
  키워드 점수 0
- launch_soft 제외 규칙: 실행 불가 오픈 웨이트에는 free_hits가 있어도 적용
- v2_filter.classify 회귀: Le Chonk(1T) 제외, 7B~32B 정상 통과
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import briefing_scorer as bs  # noqa: E402
import v2_filter  # noqa: E402

import json
from pathlib import Path as _P

@pytest.fixture
def real_weights():
    wpath = _P(__file__).resolve().parent.parent / "config" / "impact_weights.json"
    with open(wpath, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- 추출

class TestExtractParamScale:
    @pytest.mark.parametrize("text, expected", [
        ("Mistral Large 4 has 1.2 trillion parameters", 1200.0),
        ("Model with 671B parameters", 671.0),
        ("70B model released", 70.0),
        ("7B open weights", 7.0),
        ("1T parameters", 1000.0),
        ("Mistral Large 4는 약 1조 파라미터 모델", 1000.0),
        ("6710억 파라미터", 671.0),
        ("model size: 32B", 32.0),
        ("no scale mentioned here", None),
        ("", None),
        (None, None),
    ])
    def test_extract(self, text, expected):
        got = bs.extract_param_scale_b(text)
        if expected is None:
            assert got is None
        else:
            assert got == pytest.approx(expected, rel=1e-9)


class TestIsOpenWeight:
    def test_open_weights(self):
        assert bs.is_open_weight("This is open weights model")
    def test_huggingface(self):
        assert bs.is_open_weight("Available on HuggingFace")
    def test_ollama(self):
        assert bs.is_open_weight("run with ollama")
    def test_none(self):
        assert not bs.is_open_weight("No open weight keywords")
    def test_none_input(self):
        assert not bs.is_open_weight(None)


class TestIsRunnableScale:
    def test_small(self):
        assert bs.is_runnable_scale(7.0, 32)
    def test_boundary(self):
        assert bs.is_runnable_scale(32.0, 32)
    def test_large(self):
        assert not bs.is_runnable_scale(1000.0, 32)
    def test_none_defaults_runnable(self):
        assert bs.is_runnable_scale(None, 32)


# --------------------------------------------------------------------------- free_usability 조건부

class TestFreeUsabilityConditional:
    def test_runnable_openweight_keeps_score(self, real_weights):
        text = "Mistral open weights huggingface 7B model, 무료 티어 제공"
        score, hits = bs._score_free_usability(text, real_weights)
        # open-weight keywords should be counted (runnable)
        assert "open weights" in hits
        assert "huggingface" in hits
        assert score > 0

    def test_nonrunnable_openweight_zeros_openweight_keywords(self, real_weights):
        text = "Mistral open weights huggingface 1T parameters, 무료 티어 제공"
        score, hits = bs._score_free_usability(text, real_weights)
        # open-weight keywords should NOT be counted (non-runnable)
        assert "open weights" not in hits
        assert "huggingface" not in hits
        # but other free keywords still count
        assert "무료 티어" in hits

    def test_nonrunnable_no_scale_keeps_behavior(self, real_weights):
        # no scale mentioned → runnable=True (default) → open-weight keywords count
        text = "Mistral open weights huggingface model, 무료 티어 제공"
        score, hits = bs._score_free_usability(text, real_weights)
        assert "open weights" in hits
        assert "huggingface" in hits

    def test_non_openweight_unaffected(self, real_weights):
        text = "Some tool with 무료 티어 1T parameters"
        score, hits = bs._score_free_usability(text, real_weights)
        # not open-weight → scale irrelevant, free keywords count
        assert "무료 티어" in hits


# --------------------------------------------------------------------------- launch_soft 제외

class TestLaunchSoftConditional:
    def test_nonrunnable_openweight_applies_launch_soft(self, real_weights):
        text = "Mistral open weights huggingface 1T parameters 출시했습니다"
        penalty, matched = bs._penalty_excluded_topic(text, real_weights, ["open weights", "huggingface"])
        # non-runnable open-weight → launch_soft applies even with free_hits
        assert penalty == -100
        assert "출시했습니다" in matched or len(matched) > 0

    def test_runnable_openweight_exempt_launch_soft(self, real_weights):
        text = "Mistral open weights huggingface 7B 출시했습니다"
        penalty, matched = bs._penalty_excluded_topic(text, real_weights, ["open weights", "huggingface"])
        # runnable → free_hits exempts launch_soft
        assert penalty == 0

    def test_non_openweight_launch_soft_with_free_hits_exempt(self, real_weights):
        # non-open-weight article with free_hits → launch_soft exempted (existing behavior)
        text = "Some tool 출시했습니다 with 무료 티어"
        penalty, matched = bs._penalty_excluded_topic(text, real_weights, ["무료 티어"])
        assert penalty == 0


# --------------------------------------------------------------------------- score_article integration

class TestLeChonkExcluded:
    def test_le_chonk_excluded(self, real_weights):
        article = {
            "title": "르 춍크(Le Chonk)를 환영합니다: 허깅페이스의 Mistral Large 4 모델 특징과 활용법",
            "description": "Mistral Large 4는 약 1조 파라미터 오픈 웨이트 모델. HuggingFace에서 공개.",
            "body": "Mistral Large 4 open weights huggingface 1T parameters 출시했습니다",
            "source": "HuggingFace Trending",
            "pub_date": "2026-10-31 10:00:00",
            "cluster": "product-launch",
        }
        result = bs.score_article(article, real_weights, {}, mode="full")
        # Le Chonk (1T) should be excluded via launch_soft penalty
        assert result["breakdown"]["penalty_excluded_topic"] == -100
        assert result["total"] == 0

    def test_small_openweight_passes(self, real_weights):
        article = {
            "title": "HuggingFace releases new 7B open weights model",
            "description": "A 7B open weights model on HuggingFace with free tier.",
            "body": "open weights huggingface 7B model, 무료 티어 제공, 출시했습니다",
            "source": "HuggingFace Trending",
            "pub_date": "2026-10-31 10:00:00",
            "cluster": "product-launch",
        }
        result = bs.score_article(article, real_weights, {}, mode="full")
        # 7B runnable → launch_soft exempted, free_usability counts open-weight
        assert result["breakdown"]["penalty_excluded_topic"] == 0
        assert result["breakdown"]["free_usability"] > 0


# --------------------------------------------------------------------------- v2_filter

class TestV2FilterPipe13:
    def test_le_chonk_excluded(self):
        title = "르 춍크(Le Chonk)를 환영합니다: 허깅페이스의 Mistral Large 4 모델 특징과 활용법"
        desc = "Mistral Large 4 open weights huggingface 1T parameters 출시했습니다"
        passed, tag = v2_filter.classify(title, desc, "HuggingFace Trending")
        assert passed is False
        assert tag is None

    def test_small_openweight_passes(self):
        title = "HuggingFace releases new 7B open weights model"
        desc = "open weights huggingface 7B model, 무료 티어 제공, 출시했습니다"
        passed, tag = v2_filter.classify(title, desc, "HuggingFace Trending")
        assert passed is True
        assert tag in ("opensource", "free-llm", "tool")

    def test_32b_boundary_passes(self):
        title = "HuggingFace 32B open weights model"
        desc = "open weights huggingface 32B 출시했습니다"
        passed, tag = v2_filter.classify(title, desc, "HuggingFace Trending")
        assert passed is True


# --------------------------------------------------------------------------- cli_free_block

class TestCliFreeBlockConditional:
    def test_nonrunnable_returns_reference_only(self):
        import auto_briefing as ab
        art = {
            "title": "Mistral Large 4 open weights 1T",
            "body": "open weights huggingface 1T parameters",
            "description": "1T model",
            "source": "HuggingFace Trending",
            "original_title": "mistral-large-4",
            "link": "https://huggingface.co/mistralai/Mistral-Large-4",
        }
        block = ab.cli_free_block(art)
        assert "구독자 환경에서 실행 불가" in block
        assert "Ollama" not in block or "참고용" in block

    def test_runnable_returns_ollama_block(self):
        import auto_briefing as ab
        art = {
            "title": "Small 7B open weights model",
            "body": "open weights huggingface 7B",
            "description": "7B model",
            "source": "HuggingFace Trending",
            "original_title": "small-7b",
            "link": "https://huggingface.co/small-7b",
        }
        block = ab.cli_free_block(art)
        assert "Ollama" in block or "로컬 브리지" in block

# ---------------------------------------------------------------------------
# AIK24-PIPE-16 (2026-11-07) — 한글 오픈 웨이트 사각지대
#
# 사고: 수집기가 제목·설명을 한글로 번역 저장하는데 _OPEN_WEIGHT_KEYWORDS 가 영문만
# 알아서, 65B 실행 불가 오픈 웨이트(리플-65B)가 v2 필터를 통과해 11-07 브리핑에 실렸다.
# (규모 추출은 한글도 되는데 오픈 웨이트 판정만 영문이었다.)
# ---------------------------------------------------------------------------

RIPPLE_TITLE = "리플-65B(Ripple-65B) 프리뷰, 아파치 2.0 기반의 강력한 코딩 에이전트 성능 입증"
RIPPLE_DESC = ("미국 스타트업이 650억 파라미터 규모의 오픈 웨이트 모델 리플-65B를 공개했습니다. "
               "아파치 2.0 라이선스로 배포됩니다.")


class TestKoreanOpenWeightPipe16:
    def test_korean_65b_classify_blocked(self):
        """A2안(한글 저장본) — 실행 불가 오픈 웨이트는 제외된다."""
        assert v2_filter.classify(RIPPLE_TITLE, RIPPLE_DESC, "The Decoder") == (False, None)

    def test_korean_65b_score_penalty(self, real_weights):
        """한글 65B — score_article 도 launch_soft 페널티로 제외한다."""
        article = {"title": RIPPLE_TITLE, "description": RIPPLE_DESC,
                   "body": RIPPLE_TITLE + "\n" + RIPPLE_DESC,
                   "source": "The Decoder", "pub_date": "2026-11-07 10:00:00"}
        result = bs.score_article(article, real_weights, {}, mode="full")
        assert result["breakdown"]["penalty_excluded_topic"] == -100
        assert result["breakdown"]["free_usability"] == 0

    def test_korean_7b_passes(self):
        """C안 — 실행 가능 규모(7B)는 기존대로 통과(회귀 기준)."""
        # '무료' 신호가 있으면 태그가 free-llm 으로 승격된다(그게 정상). 여기서는
        # 오픈 웨이트 판정만 보기 위해 설명에 무료 키워드를 넣지 않는다.
        assert v2_filter.classify("70억 파라미터 규모의 오픈 웨이트 모델 공개",
                                  "아파치 2.0 라이선스로 배포됩니다", "The Decoder") == (True, "opensource")

    def test_korean_32b_boundary_passes(self):
        """32B 경계값은 통과(컷오프 이내)."""
        assert v2_filter.classify("320억 파라미터 오픈 웨이트 모델 공개",
                                  "아파치 2.0 라이선스", "The Decoder") == (True, "opensource")

    def test_korean_openweight_keywords_detected(self):
        """한글 키워드도 is_open_weight 가 인식한다."""
        for t in ("오픈 웨이트", "오픈웨이트", "오픈소스", "오픈 소스", "가중치 공개"):
            assert bs.is_open_weight(t) is True, t

    def test_fallback_usable_excludes_korean_65b(self):
        """폴백 진입로(v2_filter 미경유)도 실행 불가 오픈 웨이트를 제외한다."""
        import auto_news_selector as sel
        assert sel._is_nonrunnable_open_weight(
            {"title": RIPPLE_TITLE, "description": RIPPLE_DESC}) is True

    def test_fallback_usable_keeps_korean_7b(self):
        """7B 한글은 폴백에서 제외되지 않는다(오탐 방지)."""
        import auto_news_selector as sel
        assert sel._is_nonrunnable_open_weight(
            {"title": "70억 파라미터 오픈 웨이트 모델 공개",
             "description": "무료 배포"}) is False

    def test_fallback_usable_keeps_unknown_scale(self):
        """규모 미상이면 기존 동작 유지(제외하지 않음)."""
        import auto_news_selector as sel
        assert sel._is_nonrunnable_open_weight(
            {"title": "오픈소스 모델 공개", "description": "규모 미공개"}) is False


def test_fallback_fill_excludes_korean_65b(monkeypatch):
    """지시서 §4 폴백 시뮬레이션 — 65B 한글 기사를 폴백 풀에 넣으면 채택되지 않는다.

    폴백 풀(v2_tag IS NULL)은 v2_filter 를 거치지 않는 두 번째 진입로다.
    """
    import briefing_dedup
    import auto_news_selector as sel

    pool = [
        {"id": "1", "title": RIPPLE_TITLE, "original_title": "", "description": RIPPLE_DESC,
         "link": "https://x/1", "source": "The Decoder", "pub_date": "2026-11-07 10:00:00",
         "v2_tag": None, "v2_pass": None, "_score": 9},
        {"id": "2", "title": "70억 파라미터 오픈 웨이트 모델 공개", "original_title": "",
         "description": "아파치 2.0 라이선스로 배포됩니다", "link": "https://x/2",
         "source": "AI타임스", "pub_date": "2026-11-07 09:00:00",
         "v2_tag": None, "v2_pass": None, "_score": 8},
    ]
    monkeypatch.setattr(sel, "get_general_fallback_news",
                        lambda *a, **k: [dict(x) for x in pool])
    monkeypatch.setattr(sel.time, "sleep", lambda *_: None)
    monkeypatch.setattr(briefing_dedup, "get_history_articles", lambda q: [])
    monkeypatch.setattr(briefing_dedup, "is_duplicate_article", lambda a, h: (False, None))
    monkeypatch.setattr(briefing_dedup, "is_duplicate_article_strict", lambda a, h: (False, None))

    picked = sel.fallback_fill_general(2, set(), set(), set(), lambda sql: [], lambda a: 0)
    ids = [a["id"] for a in picked]
    assert "1" not in ids, ids          # 65B 한글 = 실행 불가 → 폴백에서도 제외
    assert "2" in ids, ids              # 7B 한글 = 통과 (회귀)
