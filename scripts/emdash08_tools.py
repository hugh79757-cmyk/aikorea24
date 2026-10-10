#!/usr/bin/env python3
"""AIK24-EMDASH-08 Day2-2 — src/content/tools 362건 -> emDash ec_tools (D1 직접 SQL).

scripts/emdash06_direct.py 의 헬퍼 재사용.
사용: python3 -u scripts/emdash08_tools.py [--dry]
"""
import glob
import json
import os
import sys
import time

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emdash04_migrate import md_to_pt  # noqa: E402
from emdash06_direct import js_slugify, lit, now_iso, q, rows_written, ulid  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "content", "tools")
LIMIT = int(os.environ.get("LIMIT", "9999"))
BATCH = int(os.environ.get("BATCH", "50"))
BATCH_SLEEP = float(os.environ.get("BATCH_SLEEP", "5"))


def load_tools():
    out = []
    for p in sorted(glob.glob(os.path.join(SRC, "*.md"))):
        txt = open(p, encoding="utf-8").read()
        if not txt.startswith("---"):
            continue
        _, fm, body = txt.split("---", 2)
        out.append({"meta": yaml.safe_load(fm) or {}, "body": body.lstrip("\n"), "path": os.path.basename(p)})
    return out[:LIMIT]


def main():
    tools = load_tools()
    print("소스 tools %d건" % len(tools))
    if "--dry" in sys.argv:
        print("dry: %d건 변환 예정" % len(tools))
        return

    existing = {}
    for r in q("SELECT id,title,status FROM ec_tools")[0]["results"]:
        existing[r["title"]] = r
    print("기존 %d건" % len(existing))

    author = q("SELECT id FROM users LIMIT 1")[0]["results"][0]["id"]
    todo = [t for t in tools if t["meta"].get("name") not in existing]
    print("작업 대상 %d건" % len(todo))

    slugs = set(r["slug"] for r in q("SELECT slug FROM ec_tools")[0]["results"] if r.get("slug"))
    total, errors, n = 0, [], 0
    for i, t in enumerate(todo, 1):
        m = t["meta"]
        title = m.get("name")
        if not title:
            errors.append((t["path"], "title 없음"))
            continue
        pid, rev = ulid(), ulid()
        slug, base, k = js_slugify(title), js_slugify(title), 2
        while slug in slugs:
            slug = "%s-%d" % (base[:77], k)
            k += 1
        slugs.add(slug)
        body_pt = json.dumps(md_to_pt(t["body"]), ensure_ascii=False)
        rev_data = json.dumps({"title": title, "summary": m.get("description"),
                               "body": json.loads(body_pt), "url": m.get("url"),
                               "pricing": m.get("price")}, ensure_ascii=False)
        pub = str(m.get("updated") or "")[:10] or None
        pub = "%sT00:00:00+00:00" % pub if pub else now_iso()
        stmts = ["INSERT INTO revisions (id,collection,entry_id,data,created_at) VALUES "
                 "(%s,'tools',%s,%s,datetime('now'))" % (lit(rev), lit(pid), lit(rev_data)),
                 "INSERT INTO ec_tools (id,slug,status,author_id,created_at,updated_at,published_at,"
                 "version,live_revision_id,locale,title,summary,body,url,pricing,logo) VALUES "
                 "(%s,%s,'published',%s,%s,%s,%s,2,%s,'en',%s,%s,%s,%s,%s,NULL)"
                 % (lit(pid), lit(slug), lit(author), lit(now_iso()), lit(now_iso()), lit(pub),
                    lit(rev), lit(title), lit(m.get("description")), lit(body_pt),
                    lit(m.get("url")), lit(m.get("price")))]
        try:
            res = q(";\n".join(stmts))
            total += rows_written(res)
            n += 1
        except Exception as e:
            errors.append((t["path"], str(e)[:200]))
            if len(errors) > 5:
                break
        if i % 50 == 0:
            print("  [%d/%d] ok=%d rowsWritten=%d" % (i, len(todo), n, total), flush=True)
        if i % BATCH == 0 and i != len(todo):
            time.sleep(BATCH_SLEEP)

    print("=== insert=%d 실패=%d 누적 rowsWritten=%d ===" % (n, len(errors), total))
    for e in errors:
        print("ERR", e)


if __name__ == "__main__":
    main()