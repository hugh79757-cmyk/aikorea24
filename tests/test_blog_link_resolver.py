#!/usr/bin/env python3
"""AIK24-PIPE-05 — blog_link_resolver 단위 테스트 (오프라인 · D1/EmDash 호출 0회)

검증 대상: scripts/blog_link_resolver.py 의 순수 함수
  · normalize_model_key / model_key_variants  — 모델 키 정규화
  · match_post                                — EmDash 글 매칭 + 우선순위

사용: pytest tests/test_blog_link_resolver.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from blog_link_resolver import (  # noqa: E402
    match_post,
    model_key_variants,
    normalize_model_key,
)


# ----------------------------------------------------------------------
# 정규화
# ----------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.parametrize("raw,expected", [
    # 지시서 §3-2 예시
    ("opencode/minimax-m3.1-flash-free", "minimax-m3.1-flash"),
    ("minimax/minimax-m3.1-flash:free", "minimax/minimax-m3.1-flash"),
    ("kilo/minimax/minimax-m3.1-flash:free", "minimax/minimax-m3.1-flash"),
    ("openrouter/free", "openrouter/free"),
    # opencode 모델명은 자체가 -free 로 끝난다 → 접미사 제거 후 짧아진다
    ("beam-free", "beam"),
    ("ll-alpha-free", "ll-alpha"),
    ("cat-jam-free", "cat-jam"),
    # org 접두사는 남긴다 (모델 동일성 판별 근거)
    ("cohere/north-mini-code:free", "cohere/north-mini-code"),
    ("nvidia/nemotron-3.5-super-vl-120b-a12b", "nemotron-3.5-super-vl-120b-a12b"),
])
def test_normalize_model_key(raw, expected):
    assert normalize_model_key(raw) == expected


@pytest.mark.unit
def test_provider_prefix_not_stripped_when_remainder_is_one_token():
    """openrouter/free → free 로 떼면 '무료 모델 목록' 페이지와 오인된다."""
    assert normalize_model_key("openrouter/free") == "openrouter/free"


@pytest.mark.unit
def test_variants_prefer_exact_id_before_loose():
    v = model_key_variants("opencode/minimax-m3.1-flash-free")
    specs = [(seq, spec) for seq, _org, spec, _rank in v]
    # 구체도 2 의 정확 시퀀스가 먼저, 느슨한 후보는 최소 3토큰
    assert (("minimax", "m3", "1", "flash", "free"), None, 2, 0) in v
    loose = [x for x in v if x[2] == 1]
    assert loose and all(len(x[0]) >= 3 for x in loose)


@pytest.mark.unit
def test_variants_keep_org_requirement_for_tail_sequence():
    v = model_key_variants("minimax/minimax-m3.1-flash")
    tail = [x for x in v if x[0] == ("minimax", "m3", "1", "flash")]
    assert tail, "org 를 뗀 꼬리 시퀀스가 있어야 한다"
    assert tail[0][1] == ("minimax",), "org 토큰 요구가 붙어야 한다"


# ----------------------------------------------------------------------
# 매칭
# ----------------------------------------------------------------------
def _post(slug, title, published_at="2026-10-20T00:00:00.000Z"):
    """load_posts() 가 만든 dict 와 같은 형태의 테스트 픽스처."""
    from blog_link_resolver import (_compact, _has_free_marker, _has_removal_marker,
                                    _title_core_tokens, _tokens)
    return {
        "slug": slug,
        "title": title,
        "status": "published",
        "published_at": published_at,
        "title_tokens": _tokens(title),
        "slug_tokens": _tokens(slug),
        "core_tokens": _title_core_tokens(title),
        "free_ctx": _has_free_marker(title, slug),
        "removal_ctx": _has_removal_marker(title),
        "compact_title": _compact(title),
        "compact_slug": _compact(slug),
    }


@pytest.mark.unit
def test_match_post_by_exact_title():
    posts = [_post("무료-llm-beam-free-분석", "무료 LLM beam-free — OpenCode Zen 무료 티어 분석")]
    hit = match_post(posts, "beam-free")
    assert hit is not None
    assert hit["slug"] == "무료-llm-beam-free-분석"


@pytest.mark.unit
def test_match_post_prefers_subject_post_over_removal_notice():
    """'목록에서 제외된 …' 알림글보다 모델 자체를 다룬 글을 고른다."""
    removal = _post("opencode-zen-무료-목록-제외-cat-jam-free",
                    "OpenCode Zen 무료 목록 제외 cat-jam-free 모델 현황과 대처 방법",
                    published_at="2026-10-18T00:00:00.000Z")
    subject = _post("무료-llm-cat-jam-free",
                    "무료 LLM cat-jam-free — 오픈코드 젠 무료 티어 성능과 특징 분석",
                    published_at="2026-10-13T00:00:00.000Z")
    hit = match_post([removal, subject], "cat-jam-free")
    assert hit is not None and hit["slug"] == "무료-llm-cat-jam-free"


@pytest.mark.unit
def test_match_post_skips_free_models_collection_page():
    """'무료 모델 목록' 페이지는 모델 글이 아니다."""
    posts = [_post("free-models", "무료로 쓸 수 있는 AI 모델 목록")]
    assert match_post(posts, "openrouter/free") is None


@pytest.mark.unit
def test_match_post_loose_match_requires_free_marker():
    """느슨한 후보는 무료 모델 글에만 매칭된다 (일반 뉴스글 배제)."""
    news_post = _post("알리바바-qwen36-plus-출시", "알리바바 Qwen3.6 Plus 출시와 중국 AI 오픈소스 전환")
    free_post = _post("무료-qwen36-plus", "무료 Qwen3.6 Plus 무료 티어 사용법")
    assert match_post([news_post], "qwen3.6-plus-free") is None
    hit = match_post([news_post, free_post], "qwen3.6-plus-free")
    assert hit is not None and hit["slug"] == "무료-qwen36-plus"


@pytest.mark.unit
def test_match_post_short_key_does_not_match_longer_model():
    """glm-5 가 glm-5.3-flash 글에 매칭되면 안 된다."""
    post = _post("무료-glm-53-flash-free-12문항-실측",
                 "무료 GLM-5.3-Flash Free 12문항 실측 — OpenCode Zen 무료 티어의 상한과 함정")
    assert match_post([post], "glm-5-free") is None


@pytest.mark.unit
def test_match_post_cross_provider_same_model_one_post():
    """opencode / kilo / openrouter 의 같은 모델이 1개 글로 매칭된다."""
    post = _post("무료-llm-minimax-m31-flash",
                 "무료 LLM minimax-m3.1-flash-free — 오픈코드 젠 무료 티어")
    for raw in ("opencode/minimax-m3.1-flash-free",
                "kilo/minimax/minimax-m3.1-flash:free",
                "minimax/minimax-m3.1-flash:free"):
        hit = match_post([post], raw)
        assert hit is not None, raw
        assert hit["slug"] == "무료-llm-minimax-m31-flash"


@pytest.mark.unit
def test_match_post_returns_none_when_no_candidate():
    posts = [_post("다른-글", "무료 LLM 다른 모델 — 무료 티어 안내")]
    assert match_post(posts, "minimax-m3.1-flash-free") is None


@pytest.mark.unit
def test_match_post_handles_dot_in_model_id():
    """`lfm-2.5-2.6b` 와 제목의 `LFM2.5-2.6B` — 점 표기 차이를 건너뛴다."""
    post = _post("free-model-liquid-lfm-2-5",
                 "LFM2.5-2.6B: 2.6B 파라미터로 폰에서 AI 에이전트를 돌리는 Liquid AI의 온디바이스 야심")
    hit = match_post([post], "liquid/lfm-2.5-2.6b:free")
    assert hit is not None and hit["slug"] == "free-model-liquid-lfm-2-5"


@pytest.mark.unit
def test_match_post_handles_org_prefix_with_dot():
    """`dots-studio/dots-3-note-preview` — org 접두사·점·가운뎃점을 모두 건너뛴다."""
    post = _post("free-model-dots-3-note-preview",
                 "Dots3-Note Preview — 샤오홍슈가 만든 280B 오픈웨이트 멀티모달 모델")
    hit = match_post([post], "dots-studio/dots-3-note-preview:free")
    assert hit is not None and hit["slug"] == "free-model-dots-3-note-preview"


@pytest.mark.unit
def test_free_marker_also_reads_slug():
    """제목에 '무료'가 없어도 슬러그가 free-model-… 면 무료 모델 글이다."""
    from blog_link_resolver import _has_free_marker
    assert _has_free_marker("Dots3-Note Preview — 멀티모달 모델", "free-model-dots-3-note-preview")
    assert not _has_free_marker("Dots3-Note Preview — 멀티모달 모델", "dots3-note-preview")
