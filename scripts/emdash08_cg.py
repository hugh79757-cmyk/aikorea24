#!/usr/bin/env python3
"""AIK24-EMDASH-08 Day2-3 — chronicle 71 + glossary 55 -> emDash ec_chronicle / ec_glossary.

emdash08_tools.py 와 동일 패턴(Worker API 우회, D1 직접 SQL).
사용: python3 -u scripts/emdash08_cg.py [--dry]
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
BATCH = int(os.environ.get("BATCH", "50"))
BATCH_SLEEP = float(os.environ.get("BATCH_SLEEP", "5"))


def load(src):
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "src", "content", src, "*.md"))):
        txt = open(p, encoding="utf-8").read()
        if not txt.startswith("---"):
            continue
        _, fm, body = txt.split("---", 2)
        out.append({"meta": yaml.safe_load(fm) or {}, "body": body.lstrip("\n"), "path": os.path.basename(p)})
    return out


def run(src, table, title_key, pub_key, cols):
    """cols: [(프론트메터 키, D1 컬럼, 변환 fn)]"""
    items = load(src)
    print("소스 %s %d건" % (src, len(items)))
    if "--dry" in sys.argv:
        return 0, 0
    existing = {r["title"] for r in q("SELECT title FROM %s" % table)[0]["results"]}
    slugs = {r["slug"] for r in q("SELECT slug FROM %s" % table)[0]["results"] if r.get("slug")}
    author = q("SELECT id FROM users LIMIT 1")[0]["results"][0]["id"]
    todo = [x for x in items if str(x["meta"].get(title_key) or "") not in existing]
    print("기존 %d / 작업 대상 %d" % (len(existing), len(todo)))

    total, errors, n = 0, [], 0
    for i, x in enumerate(todo, 1):
        m = x["meta"]
        title = str(m.get(title_key) or "").strip()
        if not title:
            errors.append((x["path"], "title 없음"))
            continue
        pid, rev = ulid(), ulid()
        slug, base, k = js_slugify(title), js_slugify(title), 2
        while slug in slugs:
            slug = "%s-%d" % (base[:77], k)
            k += 1
        slugs.add(slug)
        pub = str(m.get(pub_key) or "")[:10]
        pub = "%sT00:00:00+00:00" % pub if pub else now_iso()
        vals = [fn(m) if fn else m.get(k_) for k_, _c, fn in cols]
        rev_data = json.dumps({"title": title}, ensure_ascii=False)
        col_names = ["title"] + [c for _k, c, _f in cols]
        stmts = ["INSERT INTO revisions (id,collection,entry_id,data,created_at) VALUES "
                 "(%s,%s,%s,%s,datetime('now'))" % (lit(rev), lit(src), lit(pid), lit(rev_data)),
                 "INSERT INTO %s (id,slug,status,author_id,created_at,updated_at,published_at,"
                 "version,live_revision_id,locale,%s) VALUES (%s,%s,'published',%s,%s,%s,%s,2,%s,'en',%s)"
                 % (table, ",".join(col_names), lit(pid), lit(slug), lit(author), lit(now_iso()),
                    lit(now_iso()), lit(pub), lit(rev),
                    ",".join([lit(title)] + [lit(v) for v in vals]))]
        try:
            total += rows_written(q(";\n".join(stmts)))
            n += 1
        except Exception as e:
            errors.append((x["path"], str(e)[:200]))
            if len(errors) > 5:
                break
        if i % 50 == 0:
            print("  [%d/%d] ok=%d rowsWritten=%d" % (i, len(todo), n, total), flush=True)
        if i % BATCH == 0 and i != len(todo):
            time.sleep(BATCH_SLEEP)
    print("=== %s insert=%d 실패=%d rowsWritten=%d ===" % (table, n, len(errors), total))
    for e in errors:
        print("ERR", e)
    return n, len(errors)


def main():
    a = run("chronicle", "ec_chronicle", "title", "date",
            [("category", "category", None), ("summary", "summary", None)])
    b = run("glossary", "ec_glossary", "term", "date",
            [("en", "en", None), ("category", "category", None), ("level", "level", None),
             ("short", "summary", None), ("detail", "body", lambda m: json.dumps(md_to_pt(str(m.get("detail") or "")), ensure_ascii=False))])
    print("=== 총 성공=%d 실패=%d ===" % (a[0] + b[0], a[1] + b[1]))


if __name__ == "__main__":
    main()