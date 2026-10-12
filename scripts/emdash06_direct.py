#!/usr/bin/env python3
"""AIK24-EMDASH-06 — D1 직접 SQL 경로로 잔여 blog 글 적재 (Worker CPU 10ms 우회).

scripts/emdash04_migrate.py 의 md_to_pt / load_posts 를 재사용.
사용: LIMIT=500 python3 scripts/emdash06_direct.py [--dry]
"""
import datetime
import json
import os
import random
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emdash02_measure as M  # noqa: E402
from emdash04_migrate import load_posts, md_to_pt  # noqa: E402

LIMIT = int(os.environ.get("LIMIT", "500"))
BATCH = int(os.environ.get("BATCH", "50"))
BATCH_SLEEP = float(os.environ.get("BATCH_SLEEP", "5"))
UTC = datetime.timezone.utc

CROCK = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_last = [0, 0]


def ulid():
    ms = int(time.time() * 1000)
    if ms != _last[0]:
        _last[0], _last[1] = ms, random.randrange(1 << 16)
    else:
        _last[1] = (_last[1] + 1) % (1 << 16)
    bits = [(ms >> (i * 5)) & 31 for i in range(9, -1, -1)] + \
           [(_last[1] >> (i * 5)) & 31 for i in range(15, -1, -1)]
    return "".join(CROCK[b] for b in bits)


def js_slugify(title):
    """node_modules/@emdash-cms/admin/dist/slugify.js 재현 (근사)."""
    import unicodedata
    s = unicodedata.normalize("NFKC", str(title or "")).lower()
    s = re.sub(r"[\s_]+", "-", s, flags=re.U)
    out = []
    for c in s:
        if c == "-" or c.isalpha() or c.isdigit() or unicodedata.category(c) in ("Mn", "Mc", "Me"):
            out.append(c)
    s = re.sub(r"-+", "-", "".join(out)).strip("-")
    return s[:80] or ("untitled-%s" % ulid()[-7:].lower())


def q(sql):
    r = M.query(sql)
    if not isinstance(r, dict) or "result" not in r:
        raise RuntimeError("SQL 실패: %s" % json.dumps(r, ensure_ascii=False)[:400])
    res = r["result"]
    for st in res:
        if not st.get("success", True):
            raise RuntimeError("SQL 실패: %s" % json.dumps(st, ensure_ascii=False)[:400])
    return res


def lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def now_iso():
    return datetime.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (
        datetime.datetime.now(UTC).microsecond // 1000)


def rows_written(res):
    return sum(s.get("meta", {}).get("rows_written", 0) or 0 for s in res)


def main():
    posts = load_posts()[:LIMIT]
    print("소스 %d건 (최신 %s ~ %s)" % (len(posts), posts[0]["date"].isoformat(), posts[-1]["date"].isoformat()))
    if "--dry" in sys.argv:
        print("dry: %d건 변환 예정" % len(posts))
        return

    existing = {}
    for r in q("SELECT id,title,status,published_at,live_revision_id FROM ec_posts")[0]["results"]:
        existing[r["title"]] = r
    print("기존 %d건 (published %d / draft %d)" % (
        len(existing),
        sum(1 for v in existing.values() if v["status"] == "published"),
        sum(1 for v in existing.values() if v["status"] != "published")))

    tax = {}
    for r in q("SELECT id,label FROM taxonomies WHERE name IN ('category','tag')")[0]["results"]:
        tax[r["label"]] = r["id"]
    author = q("SELECT id FROM users LIMIT 1")[0]["results"][0]["id"]
    print("author=%s taxonomy=%s" % (author, {k: v for k, v in tax.items() if k in ("뉴스", "심층분석")}))

    todo = [p for p in posts if p["meta"].get("title") not in existing or
            existing[p["meta"]["title"]]["status"] != "published"]
    todo = todo[:int(os.environ.get("MAXOPS", "99999"))]
    print("작업 대상 %d건 (기존 %d건 중 미발행 포함)" % (len(todo), len(existing)))

    total_written = 0
    done = {"publish": 0, "insert": 0}
    errors = []
    slugs = set(r["slug"] for r in q("SELECT slug FROM ec_posts")[0]["results"] if r.get("slug"))

    for i, p in enumerate(todo, 1):
        m = p["meta"]
        title = m.get("title")
        pt = json.dumps(md_to_pt(p["body"]), ensure_ascii=False)
        excerpt = m.get("description")
        img = m.get("image")
        pub = p["date"].strftime("%Y-%m-%dT%H:%M:%S+00:00")
        rev = ulid()
        rev_data = json.dumps({"title": title, "excerpt": excerpt, "content": json.loads(pt),
                               **({"featured_image": str(img)} if img else {})}, ensure_ascii=False)
        cat = m.get("category")
        tid = tax.get(str(cat)) if cat else None
        is_draft = title in existing and existing[title]["status"] != "published"
        if is_draft:
            pid = existing[title]["id"]
            kind = "publish"
        else:
            pid = ulid()
            kind = "insert"
            slug = js_slugify(title)
            base, n = slug, 2
            while slug in slugs:
                slug = "%s-%d" % (base[:77], n)
                n += 1
            slugs.add(slug)
        stmts = ["INSERT INTO revisions (id,collection,entry_id,data,created_at) VALUES "
                 "(%s,'posts',%s,%s,datetime('now'))" % (lit(rev), lit(pid), lit(rev_data))]
        if kind == "publish":
            stmts.append("UPDATE ec_posts SET status='published', published_at=%s, updated_at=%s, "
                         "version=2, live_revision_id=%s WHERE id=%s" % (lit(pub), lit(now_iso()), lit(rev), lit(pid)))
        else:
            stmts.append(
                "INSERT INTO ec_posts (id,slug,status,author_id,created_at,updated_at,published_at,version,"
                "live_revision_id,locale,title,excerpt,content,featured_image) VALUES "
                "(%s,%s,'published',%s,%s,%s,%s,2,%s,'en',%s,%s,%s,%s)"
                % (lit(pid), lit(slug), lit(author), lit(now_iso()), lit(now_iso()), lit(pub), lit(rev),
                   lit(title), lit(excerpt), lit(pt), lit(str(img)) if img else "NULL"))
        if tid:
            stmts.append("INSERT OR REPLACE INTO content_taxonomies (collection,entry_id,taxonomy_id) "
                         "VALUES ('posts',%s,%s)" % (lit(pid), lit(tid)))
        try:
            res = q(";\n".join(stmts))
            total_written += rows_written(res)
            done[kind] += 1
        except Exception as e:
            errors.append((p["path"], kind, str(e)[:200]))
            if len(errors) > 5:
                break
        if i % 10 == 0:
            print("  [%d/%d] publish=%d insert=%d rowsWritten=%d" % (i, len(todo), done["publish"], done["insert"], total_written), flush=True)
        if i % BATCH == 0 and i != len(todo):
            time.sleep(BATCH_SLEEP)

    print("=== publish=%d insert=%d 실패=%d 누적 rowsWritten=%d ===" % (
        done["publish"], done["insert"], len(errors), total_written))
    for e in errors:
        print("ERR", e)


if __name__ == "__main__":
    main()