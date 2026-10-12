#!/usr/bin/env python3
"""AIK24-THUMB-BACKFILL-01: placeholder로 떨어진 건만 large2x로 재시도.

auto_thumbnail은 Pexels src.large(1200px)를 쓰는데, 일부 사진은 800x800 WebP
품질 게이트(15KB)를 통과하지 못해 공용 placeholder로 폴백한다. 같은 검색 결과의
src.large2x(2x 해상도)를 쓰면 게이트를 통과한다.

사용: python3 scripts/emdash12_thumb_retry.py <slug|slug::query> [<slug|query> ...]
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_thumbnail import (  # noqa: E402
    PUBLIC_IMAGES_DIR, create_thumbnail, download_image,
    validate_thumbnail_quality, search_pexels, _load_used_ids, _save_used_id,
)
from emdash02_measure import query as d1_query  # noqa: E402

QUERIES = ["abstract technology", "artificial intelligence", "data center",
           "machine learning", "technology abstract", "semiconductor"]


def main():
    targets = []
    for a in sys.argv[1:]:
        if "::" in a:  # slug::query — 육안 검수에서 부적합 판정된 건의 검색어 지정
            s, q = a.split("::", 1)
            targets.append((s, [q]))
        else:
            targets.append((a, QUERIES))
    if not targets:
        print("slug 1개 이상 필요")
        sys.exit(2)
    slugs = [s for s, _ in targets]
    qmap = dict(targets)

    inlist = ",".join("'" + s.replace("'", "''") + "'" for s in slugs)
    rows = d1_query("SELECT slug, title, excerpt FROM ec_posts WHERE slug IN (%s)" % inlist)["result"][0]["results"]
    meta = {r["slug"]: r for r in rows}
    used = _load_used_ids()

    failed = []
    for slug in slugs:
        out = PUBLIC_IMAGES_DIR / slug / "thumbnail.webp"
        r = meta.get(slug, {})
        print(f"\n=== {slug[:60]}")
        done = False
        for q in qmap[slug]:
            photos = [p for p in search_pexels(q, max_pages=2) if p.get("id") not in used]
            for p in photos[:6]:
                src = p.get("src", {})
                url = src.get("large2x") or src.get("large") or src.get("medium")
                if not url:
                    continue
                data = download_image(url)
                if not data:
                    continue
                create_thumbnail(data, str(out))
                valid, why = validate_thumbnail_quality(out)
                if valid:
                    _save_used_id(p["id"])
                    used.add(p["id"])  # 같은 이미지 재사용 방지 (파일만 쓰면 메모리는 그대로)
                    print(f"  OK query={q!r} id={p['id']} {os.path.getsize(out):,}B")
                    done = True
                    break
                print(f"  .. {q!r} id={p['id']} ({src.get('large2x') and 'large2x' or 'large'}) {why}")
            if done:
                break
        if not done:
            print("  ! 실패 — placeholder 유지")
            failed.append(slug)

    print(f"\n성공 {len(slugs)-len(failed)} / 실패 {len(failed)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()