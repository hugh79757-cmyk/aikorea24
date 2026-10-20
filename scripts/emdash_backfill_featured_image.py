#!/usr/bin/env python3
"""AIK24-PIPE-06 Phase A-3 — published 글의 featured_image 공란 백필.

배경
----
2026-10-19·10-20 발행된 글 5건이 featured_image 공란이다. 원인은
`blog_draft_generator.py` 5b 의 썸네일 게이트가 "전체 실패"면 5c(EmDash 발행)
**이전에** return 하던 결함이다(Phase A 에서 수정). 그 결함으로
① 10-20 minimax 초안은 발행 단계에 도달하지 못해 유실됐고
② 10-19·10-20 발행분 5건은 썸네일 없이(또는 placeholder) 공개됐다.

방법
----
1) 대상 글마다 Pexels 썸네일을 새로 만들어 `public/images/<emdash-slug>/thumbnail.webp` 에 둔다.
2) `ec_posts.featured_image` 를 정상 글과 동일한 형태로 채운다
   ({"provider":"external","id":"","src":"https://aikorea24.kr/images/<dir>/thumbnail.webp"}).
3) placeholder 사본이 나온 글은 featured_image 를 세우지 않는다 — 이미지 없는 공개를 재현하지 않기 위해.

사용:
    python3 scripts/emdash_backfill_featured_image.py           # 조사만 (D1 쓰기 없음)
    python3 scripts/emdash_backfill_featured_image.py --apply   # 썸네일 생성 + D1 반영
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cfnew  # noqa: E402
from emdash02_measure import query as d1_query  # noqa: E402
from emdash06_direct import lit  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = PROJECT_DIR / "public" / "images"
ORIGIN = "https://aikorea24.kr"
CHUNK = 50


def featured_image_json(src):
    """정상 글과 동일한 형태 (emdash10_images.py 규약)."""
    return json.dumps({"provider": "external", "id": "", "src": src}, ensure_ascii=False)


def target_rows():
    """published 이지만 featured_image 이 비어 있는 글."""
    res = d1_query(
        "SELECT id, slug, title, status, published_at FROM ec_posts "
        "WHERE status = 'published' AND deleted_at IS NULL "
        "AND (featured_image IS NULL OR featured_image = '') "
        "ORDER BY published_at DESC"
    )
    return res.get("result", [{}])[0].get("results", []) if "result" in res else []


def make_thumbnails(rows, dry=True):
    """각 글의 썸네일을 만든다. 반환: [(row, rel_path|None, 사유)]

    이미 유효한(placeholder 가 아닌) 썸네일이 로컬에 있으면 재사용한다 — 재실행 시
    불필요한 Pexels 호출과 사진 교체(글마다 다른 사진이 붙는 것)를 막는다.
    """
    import auto_thumbnail as at

    out = []
    for r in rows:
        slug = r["slug"]
        if not slug:
            out.append((r, None, "slug 없음"))
            continue
        existing = IMAGES_DIR / slug / "thumbnail.webp"
        if existing.exists() and not at.is_placeholder_copy(str(existing)):
            out.append((r, "/images/%s/thumbnail.webp" % slug,
                        "기존 썸네일 재사용 (%s bytes)" % format(existing.stat().st_size, ",")))
            continue
        if dry:
            out.append((r, None, "[dry-run] 생성 예정: /images/%s/thumbnail.webp" % slug))
            continue
        url = "https://models.dev/"
        rel = at.process_thumbnail(url, slug, title=r.get("title") or "", description=r.get("title") or "")
        if not rel:
            out.append((r, None, "썸네일 생성 실패"))
            continue
        full = IMAGES_DIR / rel.replace("/images/", "").split("/")[-2] / "thumbnail.webp"
        if at.is_placeholder_copy(str(full)):
            out.append((r, None, "placeholder 사본 — featured_image 세우지 않음"))
            continue
        out.append((r, rel, "생성 완료 (%s bytes)" % format(full.stat().st_size, ",")))
    return out


def main():
    apply = "--apply" in sys.argv
    rows = target_rows()
    print("featured_image 공란 published 글: %d건" % len(rows))
    for r in rows:
        print("   %s  %s" % (str(r.get("published_at"))[:19], (r.get("slug") or "")[:70]))
    if not rows:
        return

    made = make_thumbnails(rows, dry=not apply)
    plan = []
    for r, rel, why in made:
        print("   · %s → %s" % ((r.get("slug") or "")[:52], why))
        if rel:
            plan.append((r, ORIGIN + rel))

    if not apply:
        print("\n[dry-run] D1 쓰기 없음. --apply 로 실제 반영.")
        return
    if len(plan) != len(rows):
        print("\n[!] 생성 실패/placeholder 가 %d건 있어 --apply 를 중단한다."
              % (len(rows) - len(plan)))
        return

    stmts = [
        "UPDATE ec_posts SET featured_image=%s WHERE id=%s;"
        % (lit(featured_image_json(src)), lit(r["id"]))
        for r, src in plan
    ]
    done = 0
    for i in range(0, len(stmts), CHUNK):
        res = d1_query("\n".join(stmts[i:i + CHUNK]))
        ok = all(s.get("success", True) for s in res.get("result", []))
        if not ok:
            print("   ⚠️ 청크 %d 반영 실패" % (i // CHUNK + 1))
            continue
        done += len(stmts[i:i + CHUNK])
    print("\nD1 반영: %d/%d건" % (done, len(stmts)))


if __name__ == "__main__":
    main()
