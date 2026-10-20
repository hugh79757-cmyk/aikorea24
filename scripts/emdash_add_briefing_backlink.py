#!/usr/bin/env python3
"""AIK24-PIPE-06 Phase C — 발행된 모델 글에 브리핑 역링크 삽입 (관례 방식).

관례(기존 1,500개 글)
---------------------
글 도입부 직후(첫 문단 뒤)에 아래 블록을 넣는다.

    원문기사는 아래의 링크를 통해 확인할 수 있습니다. [기사원문보기]

링크는 `https://aikorea24.kr/briefing/<date>-<n>/#item-<번호>` 이고 <번호>는
그 모델이 실린 브리핑에서의 항목 번호다.

사용
----
    python3 scripts/emdash_add_briefing_backlink.py           # 조사만
    python3 scripts/emdash_add_briefing_backlink.py --apply   # 실제 삽입

수정 경로
---------
EmDash REST GET 은 `_rev` 토큰을 주지 않는다. PUT 은 `_rev` 가 필수라서
MCP `content_get` 로 토큰을 받아 PUT → publish 순으로 간다
(emdash13_repair.py 와 동일 경로). published 항목에 PUT 하면 draft revision 이
되므로 publish 를 빼먹으면 반영되지 않는다.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cfnew  # noqa: E402
import emdash13_repair as rep  # noqa: E402  (MCP content_get / rest 헬퍼 재사용)

FREE_SOURCES = ("OpenRouter Free Models", "OpenCode Zen", "Kilo Free Models", "NVIDIA NIM Free")
LEAD_TEXT = "원문기사는 아래의 링크를 통해 확인할 수 있습니다. "
LINK_TEXT = "기사원문보기"


def _block(url, i):
    """기존 글 관례와 같은 형태의 역링크 블록."""
    p = "kb%d" % i
    return {
        "_type": "block", "_key": p + "0", "style": "normal",
        "markDefs": [{"_key": p + "1", "_type": "link", "href": url}],
        "children": [
            {"_type": "span", "_key": p + "2", "text": LEAD_TEXT, "marks": []},
            {"_type": "span", "_key": p + "3", "text": LINK_TEXT, "marks": [p + "1"]},
        ],
    }


def targets():
    """역링크가 필요한 대상 목록."""
    rows = cfnew.sql(
        "SELECT bi.deep_dive_url, b.date, bi.sort_order, n.original_title, n.source "
        "FROM briefing_items bi JOIN briefings b ON b.id = bi.briefing_id "
        "JOIN news n ON bi.news_id = n.id "
        "WHERE bi.deep_dive_url IS NOT NULL AND bi.deep_dive_url <> '' "
        "AND n.source IN ('%s')" % "','".join(FREE_SOURCES),
        database_id=cfnew.A24_DB) or []
    em = {r["slug"]: r for r in (cfnew.sql(
        "SELECT slug, content FROM ec_posts WHERE status='published' AND deleted_at IS NULL",
        database_id=cfnew.EMDASH_DB) or [])}
    out = []
    seen = set()
    for r in rows:
        slug = (r.get("deep_dive_url") or "").rsplit("/", 1)[-1]
        if not slug or slug in seen:
            continue
        seen.add(slug)
        p = em.get(slug)
        if not p:
            continue
        if "aikorea24.kr/briefing" in (p.get("content") or ""):
            continue
        out.append({
            "slug": slug,
            "title": r.get("original_title"),
            "url": "https://aikorea24.kr/briefing/%s/#item-%s" % (r.get("date"), r.get("sort_order")),
            "briefing_date": r.get("date"),
            "sort_order": r.get("sort_order"),
        })
    return out


def apply_one(t):
    """글 1건에 역링크 삽입. 반환 (ok, message)"""
    pid = None
    # 한글 슬러그 → id 찾기
    from urllib.parse import quote
    st, d = rep.rest("GET", "/_emdash/api/content/posts/%s" % quote(t["slug"], safe=""))
    if st == 200:
        item = (d.get("data") or {}).get("item") or d.get("item") or {}
        pid = item.get("id")
    if not pid:
        return False, "id 조회 실패 (http=%s)" % st

    try:
        rev, data, status, has_draft = rep.get_item(pid)
    except Exception as e:  # noqa: BLE001
        return False, "content_get 실패: %s" % str(e)[:100]
    if not rev:
        return False, "_rev 토큰 없음"

    blocks = data.get("content") or []
    if not blocks:
        return False, "본문 블록 없음"
    if any("aikorea24.kr/briefing" in json.dumps(b, ensure_ascii=False) for b in blocks):
        return True, "이미 역링크 있음 (스킵)"

    if has_draft:
        rep.rest("POST", "/_emdash/api/content/posts/%s/publish" % pid, {})

    new_blocks = [blocks[0], _block(t["url"], 0)] + blocks[1:]
    new_data = dict(data)
    new_data["content"] = new_blocks
    st2, b2 = rep.rest("PUT", "/_emdash/api/content/posts/" + pid,
                        {"collection": "posts", "id": pid, "data": new_data, "_rev": rev})
    if st2 not in (200, 201):
        return False, "PUT 실패 http=%s %s" % (st2, str(b2)[:140])
    st3, b3 = rep.rest("POST", "/_emdash/api/content/posts/%s/publish" % pid, {})
    if st3 not in (200, 201):
        return False, "publish 실패 http=%s %s" % (st3, str(b3)[:140])

    # 검증 — 재조회해서 링크 존재·블록 수 확인
    time.sleep(1.0)
    st4, d4 = rep.rest("GET", "/_emdash/api/content/posts/%s" % pid)
    if st4 != 200:
        return False, "검증 조회 실패 http=%s" % st4
    item = (d4.get("data") or {}).get("item") or {}
    nb = (item.get("data") or {}).get("content") or []
    has = any("aikorea24.kr/briefing" in json.dumps(b, ensure_ascii=False) for b in nb)
    if not has:
        return False, "재조회에서 역링크 없음 (블록 %d)" % len(nb)
    if len(nb) != len(blocks) + 1:
        return False, "블록 수 이상 (%d → %d, 기대 %d)" % (len(blocks), len(nb), len(blocks) + 1)
    return True, "역링크 삽입 완료 (블록 %d → %d)" % (len(blocks), len(nb))


def main():
    apply = "--apply" in sys.argv
    os.environ.setdefault("EMDASH_PAT", "")
    import emdash_publish
    os.environ["EMDASH_PAT"] = emdash_publish.get_pat() or ""
    if not os.environ["EMDASH_PAT"]:
        print("  ! EmDash PAT 없음")
        return 2

    ts = targets()
    print("역링크 대상: %d건" % len(ts))
    for t in ts:
        print("   %s  →  %s" % (t["slug"][:56], t["url"]))
    if not apply:
        print("\n[dry-run] 실제 삽입 없음. --apply 로 실행.")
        return

    ok, fail = 0, 0
    for i, t in enumerate(ts, 1):
        try:
            good, msg = apply_one(t)
        except Exception as e:  # noqa: BLE001
            good, msg = False, "예외: %s: %s" % (type(e).__name__, str(e)[:120])
        print("  [%d/%d] %s — %s" % (i, len(ts), "✅" if good else "❌", msg), flush=True)
        ok += 1 if good else 0
        fail += 0 if good else 1
        time.sleep(1.5)
    print("\n역링크 삽입: 성공 %d / 실패 %d" % (ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
