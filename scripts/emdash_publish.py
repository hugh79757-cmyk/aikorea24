#!/usr/bin/env python3
"""AIK24-EMDASH-01 — EmDash 즉시 발행 헬퍼.

blog_draft_generator.py 가 생성한 마크다운 1건을 EmDash CMS 에 publish 한다.
전환 기간 이중 저장 정책에 따라 Astro 저장(src/content/blog/)은 그대로 둔다 —
여기서 실패해도 Astro 사본이 살아 있으므로 롤백할 게 없다.

PAT 는 코드에 기록하지 않는다(Secure Vault). 환경변수에서만 읽는다.
사용: EMDASH_AIKOREA24_API_TOKEN=... python3 -c "import emdash_publish"
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.environ.get("EMDASH_BASE", "https://emdash.aikorea24.kr").rstrip("/")
PAT_KEYS = ("EMDASH_AIKOREA24_API_TOKEN", "EMDASH_PAT")


def get_pat():
    """환경변수에서만 PAT 를 읽는다. 없으면 None."""
    for k in PAT_KEYS:
        v = os.environ.get(k)
        if v and v.strip():
            return v.strip().strip('"').strip("'")
    return None


def publish_post(title, body_md, excerpt=None, featured_image=None, published_at=None):
    """글 1건 생성 후 publish. 성공하면 공개 URL, 실패하면 None(호출측이 폴백)."""
    pat = get_pat()
    if not pat:
        print("  ! EmDash PAT 없음 (%s)" % "/".join(PAT_KEYS))
        return None
    os.environ["EMDASH_PAT"] = pat  # emdash04_migrate.api() 가 이 키를 읽는다
    from emdash04_migrate import md_to_pt, api

    data = {"title": title, "excerpt": excerpt or "", "content": md_to_pt(body_md)}
    if featured_image:
        data["featured_image"] = featured_image
    st, d = api("/_emdash/api/content/posts", "POST", {"data": data})
    if st != 201:
        print("  ! EmDash create 실패 http=%s %s" % (st, json.dumps(d, ensure_ascii=False)[:200]))
        return None
    item = (d.get("data") or {}).get("item") or {}
    payload = {}
    if published_at is not None:
        payload["publishedAt"] = (published_at.isoformat()
                                  if hasattr(published_at, "isoformat") else str(published_at))
    st2, d2 = api("/_emdash/api/content/posts/%s/publish" % item.get("id"), "POST", payload)
    if st2 not in (200, 201):
        print("  ! EmDash publish 실패 http=%s %s" % (st2, json.dumps(d2, ensure_ascii=False)[:200]))
        return None
    return "%s/posts/%s" % (BASE, item.get("slug") or item.get("id"))