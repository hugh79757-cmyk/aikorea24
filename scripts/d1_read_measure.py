#!/usr/bin/env python3
"""AIK24-D1-READ-01 — SSR 경로 D1 읽기 행 수(과금 행) 측정 도구.

왜 필요한가:
  cfnew.sql() 은 결과 rows 만 돌려주고 meta.rows_read 를 버린다.
  홈(`/`)·`/global/` SSR 이 실제로 몇 행을 읽는지(Cloudflare D1 과금 기준)를
  보려면 meta 가 필요하다. SSR 경로는 cfnew.sql() 을 거치지 않아 로컬 가드가
  보이지 않으므로, 여기서 직접 재는 것이 유일한 계측 수단이다.

사용:
  python3 scripts/d1_read_measure.py --label before
  python3 scripts/d1_read_measure.py --label after

주의: 이 스크립트는 D1 을 실제로 읽는다. 계측 1회당 수천~2만 행을 소모하므로
  필요한 만큼만 실행할 것.
"""
import argparse
import json
import os
import sys

# urllib 가 기본 CA 를 못 찾는 환경(시스템 파이썬 + SSL_CERT_FILE 미설정) 대비.
# certifi 가 있으면 그 CA 를 SSL_CERT_FILE 로 물린다.
try:  # pragma: no cover - 환경 의존
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:  # pragma: no cover
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfnew  # noqa: E402

DB = cfnew.A24_DB

# --- 홈 SSR 쿼리 (src/pages/index.astro:26) ---------------------------------
Q_BRIEFINGS = (
    "SELECT * FROM briefings WHERE status = 'published' ORDER BY id DESC LIMIT 1"
)

# --- 홈 SSR 쿼리 (src/components/home/ToolsSection.astro:25) -----------------
Q_TOOLS_OLD = """SELECT name, slug, tagline, category, price, korean_support, difficulty FROM (
   SELECT name, slug, tagline, category, price, korean_support, difficulty, updated_at
   FROM tools
   UNION ALL
   SELECT name, slug, description AS tagline, category,
          COALESCE(NULLIF(price_detail, ''), price_model) AS price, korean_support,
          COALESCE(difficulty, '초보자') AS difficulty, updated_at
   FROM tool_submissions WHERE status = 'published'
 ) ORDER BY updated_at DESC LIMIT ?"""

# AIK24-D1-READ-01: 분기마다 LIMIT 을 거는 bounded UNION.
# 전체 상위 8개는 각 분기의 상위 8개 안에 반드시 포함되므로 결과 집합이 동일하다.
# 단, tools.updated_at 은 날짜 단위(예: '2026-10-20')라 동률이 생긴다.
#   → 변경 전 쿼리는 temp b-tree 안정 정렬이라 동률 때 "tools 먼저 + id 오름차순"으로
#     정렬됐다. 동일 순서를 확정적으로 재현하려고 (updated_at DESC, id ASC) 를 명시한다.
Q_TOOLS_NEW = """SELECT name, slug, tagline, category, price, korean_support, difficulty FROM (
   SELECT * FROM (
     SELECT name, slug, tagline, category, price, korean_support, difficulty, updated_at
     FROM tools ORDER BY updated_at DESC LIMIT ?
   )
   UNION ALL
   SELECT * FROM (
     SELECT name, slug, description AS tagline, category,
            COALESCE(NULLIF(price_detail, ''), price_model) AS price, korean_support,
            COALESCE(difficulty, '초보자') AS difficulty, updated_at
     FROM tool_submissions WHERE status = 'published' ORDER BY updated_at DESC LIMIT ?
   )
 ) ORDER BY updated_at DESC LIMIT ?"""

# 동률까지 결정적으로 맞춘 최종안 (src: tools=0, tool_submissions=1 → 변경 전 입력 순서)
Q_TOOLS_NEW2 = """SELECT name, slug, tagline, category, price, korean_support, difficulty FROM (
   SELECT * FROM (
     SELECT 0 AS src, id AS rid, name, slug, tagline, category, price, korean_support, difficulty, updated_at
     FROM tools ORDER BY updated_at DESC, id ASC LIMIT ?
   )
   UNION ALL
   SELECT * FROM (
     SELECT 1 AS src, id AS rid, name, slug, description AS tagline, category,
            COALESCE(NULLIF(price_detail, ''), price_model) AS price, korean_support,
            COALESCE(difficulty, '초보자') AS difficulty, updated_at
     FROM tool_submissions WHERE status = 'published' ORDER BY updated_at DESC, id ASC LIMIT ?
   )
 ) ORDER BY updated_at DESC, src ASC, rid ASC LIMIT ?"""

# --- /global/ SSR 쿼리 (src/pages/global.astro:11) --------------------------
Q_GLOBAL = """SELECT id, title, link, description, source, category, pub_date, original_title, country
   FROM news WHERE category = 'global' AND title != original_title
   ORDER BY created_at DESC LIMIT 50"""

# 변경 전 계획(구 인덱스 idx_news_category + temp b-tree) 강제 재현 — 동등성 대조용
Q_GLOBAL_OLD_PLAN = """SELECT id, title, link, description, source, category, pub_date, original_title, country
   FROM news INDEXED BY idx_news_category WHERE category = 'global' AND title != original_title
   ORDER BY created_at DESC LIMIT 50"""

QUERIES = {
    "home_briefings": (Q_BRIEFINGS, []),
    "home_tools": (Q_TOOLS_OLD, [8]),
    "home_tools_new": (Q_TOOLS_NEW, [8, 8, 8]),
    "home_tools_new2": (Q_TOOLS_NEW2, [8, 8, 8]),
    "global_news": (Q_GLOBAL, []),
    "global_news_oldplan": (Q_GLOBAL_OLD_PLAN, []),
}


def run(sql, params=None):
    """D1 query API 호출. meta.rows_read(과금 행) 를 반환."""
    # cfnew.check_quota() 와 같은 가드를 먼저 통과시킨다 — 계정 한도 80% 초과 시 중단.
    cfnew.check_quota()
    body = {"sql": sql}
    if params:
        body["params"] = params
    r = cfnew.rest(f"/accounts/{cfnew.ACCT}/d1/database/{DB}/query", "POST", body)
    if "result" not in r:
        raise SystemExit(f"D1 query failed: {json.dumps(r)[:400]}")
    res = r["result"][0]
    return res.get("meta", {}), res.get("results", [])


def explain(sql, params=None):
    meta, rows = run("EXPLAIN QUERY PLAN " + sql, params)
    return meta.get("rows_read", 0), rows


def compare(label, sql_a, params_a, sql_b, params_b):
    """두 쿼리의 결과가 원소 단위로 동일한지 대조 (표시 불변성 검증)."""
    ma, ra = run(sql_a, params_a)
    mb, rb = run(sql_b, params_b)
    print(f"\n=== [{label}] 동등성 대조 ===")
    print(f"A rows_read={ma.get('rows_read')} rows={len(ra)}")
    print(f"B rows_read={mb.get('rows_read')} rows={len(rb)}")
    same = ra == rb
    print(f"결과 완전 동일 = {same}")
    if not same:
        for i, (x, y) in enumerate(zip(ra, rb)):
            if x != y:
                print(f"  [{i}] A={x}")
                print(f"  [{i}] B={y}")
        if len(ra) != len(rb):
            print(f"  길이 불일치 A={len(ra)} B={len(rb)}")
    return same


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run", help="before/after 라벨")
    ap.add_argument("--only", default="", help="쿼리 이름(쉼표 구분)만 측정")
    ap.add_argument("--indexes", action="store_true", help="인덱스 목록만 출력")
    ap.add_argument("--adhoc", default="", help="임의 SQL 1개 실행 (rows_read 출력)")
    ap.add_argument("--compare", action="store_true", help="변경 전/후 결과 동등성 대조")
    args = ap.parse_args()

    if args.adhoc:
        m, res = run(args.adhoc)
        print(f"rows_read = {m.get('rows_read')}  rows_returned = {len(res)}")
        for r in res:
            print(f"  {r}")
        return

    if args.compare:
        ok1 = compare(
            f"{args.label}/tools(new2)",
            Q_TOOLS_OLD, [8],
            Q_TOOLS_NEW2, [8, 8, 8],
        )
        ok2 = compare(
            f"{args.label}/global",
            Q_GLOBAL_OLD_PLAN, [],
            Q_GLOBAL, [],
        )
        print(f"\nTOOLS 동일={ok1}  GLOBAL 동일={ok2}")
        return

    if args.indexes:
        meta, rows = run(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE type='index' AND tbl_name IN ('news','tools','tool_submissions','briefings') "
            "ORDER BY tbl_name, name"
        )
        print(f"[{args.label}] indexes rows_read={meta.get('rows_read')}")
        for r in rows:
            print(f"  {r['tbl_name']:20s} {r['name']:34s} {r.get('sql') or '(auto)'}")
        return

    names = [n.strip() for n in args.only.split(",") if n.strip()] or list(QUERIES)
    total = 0
    for name in names:
        sql, params = QUERIES[name]
        e_meta, e_rows = explain(sql, params)
        m, res = run(sql, params)
        rr = m.get("rows_read", 0)
        total += rr
        print(f"\n=== [{args.label}] {name} ===")
        print(f"rows_read = {rr}   (EXPLAIN rows_read = {e_meta})   returned = {len(res)}")
        for row in e_rows:
            print(f"  PLAN: {row.get('detail')}")
    print(f"\n[{args.label}] TOTAL rows_read = {total}")


if __name__ == "__main__":
    main()
