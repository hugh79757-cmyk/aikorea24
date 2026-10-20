#!/usr/bin/env python3
"""AIK24-PIPE-07 — "원문 보기" / "더 깊이 읽기" 렌더 계약 회귀 테스트 (오프라인)

배경: PIPE-05 가 렌더 5곳을 COALESCE(n.blog_link, n.link) 로 바꾸면서
"원문 보기"와 "더 깊이 읽기"가 같은 AIK24 블로그로 가는 문제가 생겼다.
PIPE-07 은 원문을 COALESCE(n.origin_link, n.link) 로 되돌렸다.

이 테스트는 소스 계약을 고정한다:
  1) 표시 경로는 blog_link 를 원문 링크로 쓰지 않는다 (origin_link → link 폴백).
  2) 브리핑 상세의 두 버튼은 서로 다른 필드를 쓴다
     (원문 = item.link, 심층 = item.deep_dive_url).

D1·네트워크 호출 0회. 사용: pytest tests/test_origin_link_render_contract.py -q
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# "원문 보기"를 렌더하는 파일들 — 모두 origin_link 우선이어야 한다.
SOURCE_LINK_RENDERERS = [
    "src/pages/briefing/[date].astro",
    "src/pages/briefing/index.astro",
    "src/pages/news.astro",
    "src/pages/api/briefing/send-email.ts",
    "scripts/auto_email_sender.py",
]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_source_link_renderers_prefer_origin_link():
    for rel in SOURCE_LINK_RENDERERS:
        text = _read(rel)
        assert (
            "COALESCE(n.origin_link, n.link)" in text
            or "COALESCE(origin_link, link)" in text
        ), f"{rel}: origin_link 우선 렌더가 아니다"


def test_source_link_renderers_do_not_fall_back_to_blog_link():
    for rel in SOURCE_LINK_RENDERERS:
        text = _read(rel)
        assert "COALESCE(n.blog_link, n.link)" not in text, f"{rel}: PIPE-05 회귀"
        assert "COALESCE(blog_link, link)" not in text, f"{rel}: PIPE-05 회귀"


def test_briefing_detail_buttons_use_separate_fields():
    """원문(item.link)과 심층(item.deep_dive_url)이 같은 필드로 합쳐지면 안 된다."""
    text = _read("src/pages/briefing/[date].astro")
    assert 'href={item.link}' in text
    assert 'href={item.deep_dive_url}' in text
    # 두 버튼이 같은 href 를 쓰는 형태(회귀)가 없어야 한다.
    assert '<a href={item.link} class="deep-dive">' not in text
