#!/usr/bin/env python3
"""AIK24-PIPE-07 — origin_link_resolver 단위 테스트 (오프라인 · D1/HTTP 호출 0회)

검증 대상: scripts/origin_link_resolver.py 의 순수 함수
  · resolve_origin_link  — 무료 모델 4종의 제공사 모델 페이지 결정
  · strip_free_suffix / slugify_model — 표기 정규화

사용: pytest tests/test_origin_link_resolver.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

from origin_link_resolver import (  # noqa: E402
    PROVIDER_LIST_PAGE,
    provider_for_source,
    resolve_origin_link,
    slugify_model,
    strip_free_suffix,
)


# ----------------------------------------------------------------------
# 제공사 매핑
# ----------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.parametrize("source,expected", [
    ("OpenCode Zen", "zen"),
    ("OpenRouter Free Models", "openrouter"),
    ("Kilo Free Models", "kilo"),
    ("NVIDIA NIM Free", "nvidia"),
])
def test_provider_for_source_free_models(source, expected):
    assert provider_for_source(source) == expected


@pytest.mark.unit
@pytest.mark.parametrize("source", ["TechCrunch AI", "HuggingFace Blog", "", None])
def test_provider_for_source_non_free(source):
    assert provider_for_source(source) is None


# ----------------------------------------------------------------------
# 표기 정규화
# ----------------------------------------------------------------------
@pytest.mark.unit
@pytest.mark.parametrize("raw,expected", [
    ("minimax/minimax-m3.1-flash:free", "minimax/minimax-m3.1-flash"),
    ("minimax-m3.1-flash-free", "minimax-m3.1-flash"),
    ("z-ai/glm-5.3-flash", "z-ai/glm-5.3-flash"),
    ("", ""),
])
def test_strip_free_suffix(raw, expected):
    assert strip_free_suffix(raw) == expected


@pytest.mark.unit
@pytest.mark.parametrize("raw,expected", [
    # Kilo 실제 페이지 URL — 2026-10-20 HTTP 200 확인
    ("minimax/minimax-m3.1-flash:free", "minimax-minimax-m3-1-flash-free"),
    ("cohere/north-mini-code:free", "cohere-north-mini-code-free"),
    ("OPENROUTER/Auto", "openrouter-auto"),
    ("", ""),
])
def test_slugify_model(raw, expected):
    assert slugify_model(raw) == expected


# ----------------------------------------------------------------------
# 제공사별 목적지
# ----------------------------------------------------------------------
@pytest.mark.unit
def test_opencode_zen_has_no_per_model_page():
    """OpenCode Zen 은 모델별 페이지가 없다 → 공식 모델 표(docs)로."""
    assert resolve_origin_link("OpenCode Zen", "minimax-m3.1-flash-free") == (
        "https://opencode.ai/v2/docs/console/models/"
    )


@pytest.mark.unit
def test_openrouter_uses_per_model_page():
    assert resolve_origin_link(
        "OpenRouter Free Models", "minimax/minimax-m3.1-flash:free"
    ) == "https://openrouter.ai/minimax/minimax-m3.1-flash"


@pytest.mark.unit
def test_openrouter_single_token_falls_back_to_list():
    """openrouter/free 처럼 org 가 없는 id 는 모델 페이지가 아니다."""
    assert resolve_origin_link("OpenRouter Free Models", "free") == (
        PROVIDER_LIST_PAGE["openrouter"]
    )


@pytest.mark.unit
def test_kilo_uses_per_model_page():
    assert resolve_origin_link(
        "Kilo Free Models", "minimax/minimax-m3.1-flash:free"
    ) == "https://kilo.ai/models/minimax-minimax-m3-1-flash-free"


@pytest.mark.unit
def test_nvidia_uses_build_page():
    assert resolve_origin_link("NVIDIA NIM Free", "z-ai/glm-5.3-flash") == (
        "https://build.nvidia.com/z-ai/glm-5.3-flash"
    )


@pytest.mark.unit
@pytest.mark.parametrize("source", [
    "OpenCode Zen", "OpenRouter Free Models", "Kilo Free Models", "NVIDIA NIM Free",
])
def test_empty_model_id_falls_back_to_provider_list(source):
    assert resolve_origin_link(source, "") == PROVIDER_LIST_PAGE[provider_for_source(source)]


@pytest.mark.unit
@pytest.mark.parametrize("source", ["TechCrunch AI", "HuggingFace Blog", "", None])
def test_non_free_source_returns_none(source):
    """비무료 뉴스는 origin_link 가 NULL — 렌더링에서 기존 link(실제 원문)를 쓴다."""
    assert resolve_origin_link(source, "anything") is None


# ----------------------------------------------------------------------
# 회귀: 2026-10-20 브리핑 1번 카드(실측 데이터)
# ----------------------------------------------------------------------
@pytest.mark.unit
def test_regression_minimax_briefing_card():
    """브리핑 카드의 원문은 블로그가 아니라 OpenCode Zen 모델 표로 가야 한다."""
    url = resolve_origin_link("OpenCode Zen", "minimax-m3.1-flash-free")
    assert "emdash.aikorea24.kr" not in url
    assert "models.dev" not in url
    assert url == "https://opencode.ai/v2/docs/console/models/"
