#!/usr/bin/env python3
"""
S3: 주간 블로그 포스트 발행 — 심층 분석을 Astro 블로그 형식으로 저장.

출력: src/content/blog/weekly-contrast-{YYYYMMDD}-{num}.md
"""

import json
import os
import re
import sys
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)

from pipeline.infra.config import project_root
from pipeline.infra.logger import get_scrubbed_logger

logger = get_scrubbed_logger(__name__)

BLOG_DIR = os.path.join(str(project_root()), "src", "content", "blog")
DRAFTS_DIR = os.path.join(BLOG_DIR, "_drafts")


def _make_slug(title: str) -> str:
    """제목에서 SEO 친화적 slug 생성."""
    slug = re.sub(r'[^\w\s가-힣-]', '', title)
    slug = re.sub(r'\s+', '-', slug.strip())
    slug = slug.lower()[:80]
    return slug or "weekly-contrast"


def _next_file_number(date_str: str, target_dir: str = None) -> int:
    """해당 날짜의 다음 파일 번호 결정."""
    import glob
    if target_dir is None:
        target_dir = BLOG_DIR
    pattern = os.path.join(target_dir, f"weekly-contrast-{date_str}-*.md")
    existing = glob.glob(pattern)
    return len(existing) + 1


def publish_blog_post(deep_dive: dict) -> str:
    """
    심층 분석을 블로그 포스트로 발행.

    발행 게이트:
    - "추천" → src/content/blog/ (일반 발행)
    - "보류" → src/content/blog/_drafts/ (발행 금지)
    - "폐기" → 저장하지 않음

    Args:
        deep_dive: deep_dive_writer 출력 {title, body, tags, source_links, quality_judgment}

    Returns:
        str: 저장된 파일 경로 (폐기 시 빈 문자열)
    """
    quality = deep_dive.get("quality_judgment", {})
    verdict = quality.get("verdict", "추천")

    # 폐기: 저장하지 않음
    if verdict == "폐기":
        logger.info("blog_skipped_disposed: %s — %s",
                     deep_dive.get("title", ""), quality.get("issues", []))
        return ""

    # 보류: drafts 폴더에 저장
    if verdict == "보류":
        target_dir = DRAFTS_DIR
        logger.info("blog_saved_as_draft: %s", deep_dive.get("title", ""))
    else:
        target_dir = BLOG_DIR

    today = datetime.now().strftime("%Y%m%d")
    file_num = _next_file_number(today, target_dir)
    slug = _make_slug(deep_dive["title"])

    filename = f"weekly-contrast-{today}-{file_num:03d}-{slug}.md"
    filepath = os.path.join(target_dir, filename)

    # frontmatter
    tags_yaml = json.dumps(deep_dive.get("tags", ["weekly-analysis", "contrast"]), ensure_ascii=False)
    title_escaped = deep_dive["title"].replace('"', '\\"')

    # draft 플래그: 보류는 draft: true
    draft_flag = "true" if verdict == "보류" else "false"

    # 원문 링크를 본문 하단에 추가
    source_links = deep_dive.get("source_links", [])
    links_section = ""
    if source_links:
        links_section = "\n\n---\n\n### 참고 기사\n\n"
        for i, link in enumerate(source_links, 1):
            links_section += f"{i}. {link}\n"

    frontmatter = f"""---
title: "{title_escaped}"
description: "AI 뉴스 심층 분석 — 대비 구조를 통한 인사이트"
pubDatetime: {datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")}
author: "aikorea24"
tags: {tags_yaml}
category: "심층분석"
draft: {draft_flag}
---

"""

    content = frontmatter + deep_dive["body"] + links_section

    os.makedirs(target_dir, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("blog_published: %s (%d chars) [verdict: %s]", filepath, len(content), verdict)
    return filepath


def publish_all(deep_dives: list[dict]) -> list[str]:
    """
    여러 심층 분석을 블로그 포스트로 발행.

    Returns:
        list[str]: 저장된 파일 경로 목록 (추천+보류만, 폐기 제외)
    """
    paths = []
    disposed_count = 0
    for dive in deep_dives:
        quality = dive.get("quality_judgment", {})
        verdict = quality.get("verdict", "추천")

        if verdict == "폐기":
            disposed_count += 1
            logger.info("publish_disposed: %s", dive.get("title", ""))
            continue

        try:
            path = publish_blog_post(dive)
            if path:
                paths.append(path)
        except Exception as e:
            logger.error("publish_failed: %s — %s", dive.get("title", ""), e)

    # 추천 0건 확인
    recommend_count = sum(1 for d in deep_dives
                          if d.get("quality_judgment", {}).get("verdict") == "추천")
    if recommend_count == 0:
        logger.info("publish_skipped_no_recommend: "
                     "이번 주 추천 기준 통과 0건 — 강제 생성 안 함")

    logger.info("published_all: %d published, %d disposed, %d total",
                len(paths), disposed_count, len(deep_dives))
    return paths


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI: python3 scripts/weekly_blog_publisher.py [--from-json FILE]"""
    import argparse
    parser = argparse.ArgumentParser(description="주간 블로그 포스트 발행")
    parser.add_argument("--from-json", type=str, help="심층 분석 JSON 파일")
    args = parser.parse_args()

    if args.from_json:
        with open(args.from_json, "r", encoding="utf-8") as f:
            dives = json.load(f)
    else:
        print("Usage: weekly_blog_publisher.py --from-json <deep_dives.json>")
        return

    paths = publish_all(dives)

    print(f"\n발행 완료: {len(paths)}건")
    for p in paths:
        print(f"  → {p}")


if __name__ == "__main__":
    main()
