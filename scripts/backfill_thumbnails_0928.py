#!/usr/bin/env python3
"""2026-09-28 12건 누락 썸네일 백필 — 기존 MD 대상, 콘텐츠 재생성 없음.

대상: src/content/blog/2026-09-28-*.md 중 `^image:` frontmatter가 없는 파일만.
`^image:`가 이미 있는 파일은 절대 수정하지 않는다.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_thumbnail import process_thumbnail
from blog_draft_generator import _add_image_to_frontmatter

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_GLOB = os.path.join(PROJECT_DIR, "src", "content", "blog", "2026-09-28-*.md")


def has_image_frontmatter(content):
    return re.search(r"^image:", content, re.MULTILINE) is not None


def extract_title_desc(content):
    """frontmatter 파싱 없이 본문에서 title/description 추출."""
    parts = content.split("---", 2)
    body = parts[2] if len(parts) > 2 else content
    body = body.strip()
    title = ""
    for line in body.splitlines():
        line = line.strip().lstrip("#").strip()
        if len(line) >= 10:
            title = line
            break
    if not title:
        title = body[:80]
    return title, body[:400]


def main():
    candidates = sorted(glob.glob(TARGET_GLOB))
    targets, skipped = [], []
    for fp in candidates:
        with open(fp, encoding="utf-8") as f:
            content = f.read()
        if has_image_frontmatter(content):
            skipped.append(os.path.basename(fp))
        else:
            targets.append(fp)

    print(f"대상(check): {len(candidates)}건 중 image: 보유 {len(skipped)}건 skip, 백필 {len(targets)}건")
    for s in skipped:
        print(f"  SKIP (image: 보유): {s}")

    results = []  # (slug, status, detail)
    for fp in targets:
        slug = os.path.basename(fp).replace(".md", "").lower()
        try:
            with open(fp, encoding="utf-8") as f:
                content = f.read()
            if has_image_frontmatter(content):
                # 이중 가드: 루프 중 image: 생겼으면 수정 금지
                results.append((slug, "skip", "image: already present"))
                continue
            title, desc = extract_title_desc(content)
            thumb_rel = process_thumbnail("", slug, title=title, description=desc)
            if not thumb_rel:
                results.append((slug, "실패", "process_thumbnail returned None"))
                continue
            _add_image_to_frontmatter(fp, thumb_rel)
            with open(fp, encoding="utf-8") as f:
                injected = has_image_frontmatter(f.read())
            if injected:
                results.append((slug, "성공(주입됨)", thumb_rel))
            else:
                results.append((slug, "placeholder-skip", thumb_rel))
        except Exception as e:
            results.append((slug, "실패", str(e)[:200]))

    print("\n=== per-slug 결과 ===")
    for slug, status, detail in results:
        print(f"  [{status}] {slug} :: {detail}")
    ok = sum(1 for _, s, _ in results if s.startswith("성공"))
    ph = sum(1 for _, s, _ in results if s == "placeholder-skip")
    fail = [s for s, st, _ in results if st == "실패"]
    print(f"\n합계: 성공 {ok} / placeholder-skip {ph} / 실패 {len(fail)}")
    if fail:
        print("실패 slug:")
        for s in fail:
            print(f"  - {s}")


if __name__ == "__main__":
    main()
