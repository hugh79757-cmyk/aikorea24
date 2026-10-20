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
from urllib.parse import quote

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


def _get_post_raw(identifier):
    """조회 1회. 실패하면 None — 인코딩 재시도는 get_post 가 담당한다."""
    pat = get_pat()
    if not pat:
        return None
    os.environ["EMDASH_PAT"] = pat
    from emdash04_migrate import api

    st, d = api("/_emdash/api/content/posts/%s" % identifier, "GET")
    if st != 200:
        return None
    item = d.get("data") or d.get("item") or d
    if not isinstance(item, dict):
        return None
    item.setdefault("_rev", d.get("_rev"))
    return item


def get_post(identifier):
    """글 1건 조회. 없으면 None. id 또는 slug 를 받는다 (EmDash 가 둘 다 받는다).

    AIK24-BLOG-01(2026-10-17 실측): 한글 slug 는 인코딩 없이 요청하면 http=0(예외)로
    실패한다 — raw '무료-llm-beam-free-...' → http 0, percent-encoding → 200.
    이 실패를 그대로 두면 upsert_post 가 "글이 없다"로 판단해 같은 글을 하나 더 만든다
    (실측: 한글 slug 재작성 시도 → 미발행 중복 draft 1건 생성 → 수동 삭제). 그래서
      ① 조회 실패 시 percent-encoding 으로 1회 재시도하고
      ② 응답이 {"item": {...}} 로 중첩돼 오면 item 의 id 를 최상위로 올려
         호출측이 id 경로로 PUT 할 수 있게 한다 (slug 경로 PUT 도 한글에서는 http=0).
    """
    item = _get_post_raw(identifier)
    if item is None and isinstance(identifier, str):
        enc = quote(identifier, safe="")
        if enc != identifier:
            item = _get_post_raw(enc)
    if isinstance(item, dict):
        inner = item.get("item")
        if isinstance(inner, dict) and inner.get("id"):
            item.setdefault("id", inner["id"])
    return item


def _featured_image_data(src):
    """썸네일 src → EmDash featured_image 값.

    AIK24-EVAL-09: '/' 로 시작하는 상대경로는 emdash.aikorea24.kr 에서 404 난다
    (실측: 관련글 카드 2건이 404). 이미지는 aikorea24.kr/public 에 있으므로 절대 URL 로 만든다.
    dict 형식(featured_image 객체)이면 src 만 고쳐 다시 감싼다.
    """
    if not src:
        return None
    if isinstance(src, dict):
        inner = _featured_image_data(src.get("src"))
        return {**src, "src": inner} if inner else None
    s = str(src)
    if s.startswith("/"):
        return "https://aikorea24.kr" + s
    return s


def upsert_post(slug, title, body_md, excerpt=None, featured_image=None):
    """고정 슬러그 페이지 생성 또는 **본문만 교체**. slug 는 끝까지 그대로 유지된다.

    AIK24-FREE-PIPE-01 작업 3용. EmDash 는 published 항목에 PUT 하면 draft revision 으로
    스테이징되므로 publish 후행이 없으면 라이브에 반영되지 않는다
    (emdash13_repair.py 가 1,479건 수리에서 사용한 그 순서).
    AIK24-EVAL-09: featured_image 를 받는다 — 이전엔 없어서 free-models 페이지에
    썸네일이 설정될 경로가 아예 없었다.
    성공하면 공개 URL, 실패하면 None.
    """
    pat = get_pat()
    if not pat:
        print("  ! EmDash PAT 없음 (%s)" % "/".join(PAT_KEYS))
        return None
    os.environ["EMDASH_PAT"] = pat
    from emdash04_migrate import md_to_pt, api

    data = {"title": title, "excerpt": excerpt or "", "content": md_to_pt(body_md)}
    feat = _featured_image_data(featured_image)
    if feat:
        data["featured_image"] = feat
    existing = get_post(slug)
    if existing is None:
        # slug 필드는 posts 컬렉션에 없다(400 unknown field). EmDash 는 title 을 slugify 해
        # slug 를 만든다 — 고정 URL 을 만들려면 title 자체가 slug 가 되어야 한다.
        st, d = api("/_emdash/api/content/posts", "POST", {"data": data})
        item = (d.get("data") or {}).get("item") or {}
        if st in (200, 201) and item.get("slug") != slug:
            print("  ! 생성됐지만 slug 가 '%s' 가 아니다 (요청 %s) — 고정 URL 깨짐. "
                  "고아 글 id=%s (삭제 필요)"
                  % (item.get("slug"), slug, item.get("id")))
            return None
    else:
        st, d = api("/_emdash/api/content/posts/%s" % (existing.get("id") or slug), "PUT",
                    {"collection": "posts", "id": existing.get("id") or slug,
                     "data": data, "_rev": existing.get("_rev")})
        item = existing
    if st not in (200, 201):
        print("  ! EmDash upsert 실패 http=%s %s" % (st, json.dumps(d, ensure_ascii=False)[:200]))
        return None
    st2, d2 = api("/_emdash/api/content/posts/%s/publish" % (item.get("id") or slug), "POST", {})
    if st2 not in (200, 201):
        print("  ! EmDash publish 실패 http=%s %s" % (st2, json.dumps(d2, ensure_ascii=False)[:200]))
        return None
    return "%s/posts/%s" % (BASE, item.get("slug") or slug)


def publish_post(title, body_md, excerpt=None, featured_image=None, published_at=None):
    """글 1건 생성 후 publish. 성공하면 공개 URL, 실패하면 None(호출측이 폴백)."""
    pat = get_pat()
    if not pat:
        print("  ! EmDash PAT 없음 (%s)" % "/".join(PAT_KEYS))
        return None
    os.environ["EMDASH_PAT"] = pat  # emdash04_migrate.api() 가 이 키를 읽는다
    from emdash04_migrate import md_to_pt, api

    data = {"title": title, "excerpt": excerpt or "", "content": md_to_pt(body_md)}
    feat = _featured_image_data(featured_image)
    if feat:
        data["featured_image"] = feat
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


def create_draft_post(title, body_md, excerpt=None, featured_image=None):
    """글 1건을 **draft 상태로** 만든다. publish 하지 않는다.

    AIK24-PIPE-05 §3-3·§5 — 자동 작성 글은 검수 전까지 draft 로만 둔다.
    검수 주체(시니어 2 / 대표님)는 지시서 §5 에서 결정 대기다. 그래서 여기선
    publish 를 호출하지 않는다 — 호출하는 순간 "검수 없이 공개" 가 된다.
    반환값은 draft 로서의 URL (공개 전이므로 링크를 외부에 노출하지 않는다).
    """
    pat = get_pat()
    if not pat:
        print("  ! EmDash PAT 없음 (%s)" % "/".join(PAT_KEYS))
        return None
    os.environ["EMDASH_PAT"] = pat
    from emdash04_migrate import md_to_pt, api

    data = {"title": title, "excerpt": excerpt or "", "content": md_to_pt(body_md)}
    feat = _featured_image_data(featured_image)
    if feat:
        data["featured_image"] = feat
    st, d = api("/_emdash/api/content/posts", "POST", {"data": data})
    if st not in (200, 201):
        # CONTENT_CREATE_ERROR(500) 은 일시적 서버 오류가 있다 — 2026-10-20 14:11 실측
        # (Phase B 전수 배치에서 11건이 이 에러로 실패했다). 3회 재시도한다.
        import time as _time
        for attempt in range(1, 4):
            print("  ! EmDash draft create 실패 http=%s — %d초 후 재시도 (%d/3)"
                  % (st, attempt * 5, attempt))
            _time.sleep(attempt * 5)
            st, d = api("/_emdash/api/content/posts", "POST", {"data": data})
            if st in (200, 201):
                break
        else:
            print("  ! EmDash draft create 실패 http=%s %s" % (st, json.dumps(d, ensure_ascii=False)[:200]))
            return None
    item = (d.get("data") or {}).get("item") or {}
    if not item.get("id"):
        print("  ! EmDash draft create 응답에 id 없음")
        return None
    print("  📝 EmDash draft 생성(미발행): id=%s slug=%s" % (item.get("id"), item.get("slug")))
    return "%s/posts/%s" % (BASE, item.get("slug") or item.get("id"))