#!/usr/bin/env python3
"""EmDash 발행 글의 **보이는 텍스트만** 일괄 치환한다 (기본 dry-run).

배경 (2026-10-17 대표님 지시): 자사 표기를 축약형으로 쓰지 않는다 —
`ai.kr.24`(쓰레드 계정) 또는 `aikorea24.kr`(사이트)만 쓴다.
규칙 파일(`scripts/blog_writing_rules.md`)을 고쳐도, 그 전에 생성된 글은
이미 축약형을 달고 발행돼 있다. 이 도구가 그 잔존분을 정리한다.

안전장치
  1. 치환 범위는 Portable Text 의 문자열 키 `text` 뿐이다.
     `_key`(블록 식별자)·링크 URL·marks 는 건드리지 않는다 —
     `_key` 를 바꾸면 CMS 가 블록을 새 블록으로 보고 중복 렌더 위험이 있다.
  2. 기본이 dry-run 이다. 쓰려면 `--apply` 를 명시한다.
  3. `--apply` 는 쓰기 전 원본을 `scripts/logs/backup_text_replace_<ts>.json` 에 남긴다.
  4. **API(PUT+publish) 로만 쓴다.** D1 직접 UPDATE 는 revision 을 만들지 않아
     라이브에 반영되지 않는다(AIK24-FREE-PIPE-01 실측).
  5. 쓴 뒤 재조회로 ① 대상 문자열 0건 ② slug 불변 ③ publishedAt 불변을 확인한다.

사용
  python3 scripts/emdash_text_replace.py --map 'AIK24 실측=ai.kr.24 실측'          # 미리보기
  python3 scripts/emdash_text_replace.py --map 'AIK24 실측=ai.kr.24 실측' --apply  # 실행
  python3 scripts/emdash_text_replace.py --slugs a,b --map 'X=Y' --apply           # 대상 지정
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cfnew  # noqa: E402  (D1 조회 + 읽기 예산 가드)
import emdash_publish as ep  # noqa: E402

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def text_nodes(obj, out):
    """Portable Text 안의 (부모dict, key, 문자열) 중 문자열 값이 'text' 인 것만 모은다."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "text" and isinstance(v, str):
                out.append((obj, k))
            else:
                text_nodes(v, out)
    elif isinstance(obj, list):
        for v in obj:
            text_nodes(v, out)
    return out


def visible_strings(content):
    """content(PT) 안의 보이는 문자열 목록."""
    return [n[0][n[1]] for n in text_nodes(content, [])]


def apply_maps(content, maps):
    """maps: [(find, repl)] 순서대로. 반환 (새 content, 변경 건수, 변경된 문맥 목록)."""
    nodes = text_nodes(content, [])
    n = 0
    ctx = []
    for d, k in nodes:
        s = d[k]
        orig = s
        for find, repl in maps:
            if find in s:
                n += s.count(find)
                s = s.replace(find, repl)
        if s != orig:
            ctx.append(orig[:80])
            d[k] = s
    return content, n, ctx


def target_slugs(find_list, limit=None):
    """D1 ec_posts 에서 대상 문자열을 가진 글의 slug 를 찾는다(deleted_at IS NULL)."""
    where = " OR ".join("content LIKE '%%%s%%'" % f.replace("'", "''") for f in find_list)
    sql = ("SELECT slug, status, published_at FROM ec_posts "
           "WHERE deleted_at IS NULL AND (%s) ORDER BY published_at DESC" % where)
    rows = cfnew.sql(sql)
    if isinstance(rows, dict):
        raise SystemExit("D1 조회 실패: %s" % json.dumps(rows, ensure_ascii=False)[:300])
    slugs = [r["slug"] for r in rows if r.get("slug")]
    return slugs[:limit] if limit else slugs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", action="append", default=[], metavar="FIND=REPL",
                    help="치환 쌍. 여러 번 지정하면 **지정 순서대로** 적용한다(긴 문구를 먼저).")
    ap.add_argument("--slugs", default="", help="쉼표 구분 대상 slug. 없으면 D1 에서 검색한다.")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다(기본은 dry-run).")
    a = ap.parse_args(argv)

    maps = []
    for m in a.map:
        if "=" not in m:
            raise SystemExit("--map 형식은 FIND=REPL 입니다: %r" % m)
        f, r = m.split("=", 1)
        maps.append((f, r))
    if not maps:
        raise SystemExit("--map 이 최소 1개 필요합니다.")

    if a.slugs:
        slugs = [s.strip() for s in a.slugs.split(",") if s.strip()]
    else:
        slugs = target_slugs([f for f, _ in maps], a.limit)
    print("대상 %d건: %s" % (len(slugs), ", ".join(slugs[:6]) + (" …" if len(slugs) > 6 else "")))
    print("치환: %s" % " / ".join("%s→%s" % m for m in maps))
    print("모드: %s" % ("APPLY" if a.apply else "DRY-RUN"))
    print()

    backup = {}
    ok, fail = 0, []
    for slug in slugs:
        it = ep.get_post(slug) or {}
        item = it.get("item") or {}
        data = item.get("data") or {}
        content = data.get("content")
        if content is None:
            print("  ! %s — 본문 조회 실패, 건너뜀" % slug[:50])
            fail.append((slug, "조회 실패"))
            continue

        before = sum(len(re.findall(re.escape(f), "\n".join(visible_strings(content)))) for f, _ in maps)
        new_content, n, ctx = apply_maps(content, maps)
        print("  · %s" % slug[:60])
        print("      가시 텍스트 일치 %d건 → 변경 %d건" % (before, n))
        for c in ctx[:6]:
            print("        … %s …" % c)
        if n == 0:
            continue

        if not a.apply:
            continue

        backup[slug] = {"id": item.get("id"), "slug": item.get("slug"),
                        "published_at": item.get("publishedAt"), "data": data}
        new_data = dict(data)
        new_data["content"] = new_content
        from emdash04_migrate import api
        st, d = api("/_emdash/api/content/posts/%s" % (item.get("id") or slug), "PUT",
                    {"collection": "posts", "id": item.get("id") or slug,
                     "data": new_data, "_rev": it.get("_rev")})
        if st not in (200, 201):
            print("      ! PUT 실패 http=%s %s" % (st, json.dumps(d, ensure_ascii=False)[:160]))
            fail.append((slug, "PUT http=%s" % st))
            continue
        st2, d2 = api("/_emdash/api/content/posts/%s/publish" % (item.get("id") or slug), "POST", {})
        if st2 not in (200, 201):
            print("      ! publish 실패 http=%s %s" % (st2, json.dumps(d2, ensure_ascii=False)[:160]))
            fail.append((slug, "publish http=%s" % st2))
            continue

        it3 = ep.get_post(slug) or {}
        item3 = it3.get("item") or {}
        after = sum(len(re.findall(re.escape(f), "\n".join(visible_strings((item3.get("data") or {}).get("content") or []))))
                    for f, _ in maps)
        same_slug = (item3.get("slug") == item.get("slug"))
        same_pub = (item3.get("publishedAt") == item.get("publishedAt"))
        verdict = "OK" if (after == 0 and same_slug and same_pub) else "확인 필요"
        print("      PUT+publish 완료 — 잔존 %d건, slug 보존 %s, 발행시각 보존 %s → %s"
              % (after, same_slug, same_pub, verdict))
        if verdict != "OK":
            fail.append((slug, "검증 불일치"))
        else:
            ok += 1

    if a.apply and backup:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        path = os.path.join(BACKUP_DIR, "backup_text_replace_%s.json" % dt.datetime.now().strftime("%Y%m%d_%H%M"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(backup, f, ensure_ascii=False, indent=1)
        print("\n백업: %s (%d건, %d bytes)" % (path, len(backup), os.path.getsize(path)))

    print("\n요약: 성공 %d / 실패 %d" % (ok, len(fail)))
    for s, r in fail:
        print("   ! %s — %s" % (s[:60], r))
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
