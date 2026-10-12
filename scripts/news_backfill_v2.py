#!/usr/bin/env python3
"""news 테이블 v2_pass / v2_tag 백필 (AIK24-NEWS-01 Step 3-4).

최근 N일 행에 scripts/v2_filter.classify() 를 실행해 UPDATE 한다.
D1 쓰기 한도 보호로 배치(40건) 처리. --limit 으로 소량 시험 후 전체 실행.

  python3 scripts/news_backfill_v2.py --limit 100 --dry-run
  python3 scripts/news_backfill_v2.py --limit 100
  python3 scripts/news_backfill_v2.py --days 7
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfnew  # noqa: E402
import v2_filter as v2f  # noqa: E402

DB = cfnew.A24_DB
BATCH = 40


def lit(v):
    return "'" + str(v or "").replace("'", "''")[:200] + "'"


def fetch(days, limit):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    sql = (
        f"SELECT id,title,description,source FROM news "
        f"WHERE created_at >= '{since}' ORDER BY id DESC LIMIT {int(limit)}"
    )
    r = cfnew.sql(sql, database_id=DB)
    return r if isinstance(r, list) else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rows = fetch(a.days, a.limit)
    print(f"대상 {len(rows)}건 (최근 {a.days}일, limit {a.limit})")

    stmts, dist = [], {}
    for r in rows:
        ok, tag = v2f.classify(r.get("title") or "", r.get("description") or "", r.get("source") or "")
        dist[tag or "excluded"] = dist.get(tag or "excluded", 0) + 1
        stmts.append(
            f"UPDATE news SET v2_pass={1 if ok else 0}, v2_tag={lit(tag)} WHERE id={int(r['id'])};"
        )
    print(f"분포: {dist}")
    if a.dry_run:
        print("[DRY-RUN] D1 미쓰기")
        return

    for i in range(0, len(stmts), BATCH):
        res = cfnew.sql(";\n".join(stmts[i : i + BATCH]), database_id=DB)
        print(f"  배치 {i // BATCH + 1}: {len(stmts[i:i+BATCH])}건 (ok={isinstance(res, list)})")

    chk = cfnew.sql(
        "SELECT v2_pass, v2_tag, COUNT(*) c FROM news "
        f"WHERE created_at >= '{(datetime.now(timezone.utc) - timedelta(days=a.days)).strftime('%Y-%m-%d %H:%M:%S')}' "
        "GROUP BY v2_pass, v2_tag ORDER BY c DESC",
        database_id=DB,
    )
    print("결과 분포:", chk if not isinstance(chk, list) else [(x["v2_pass"], x["v2_tag"], x["c"]) for x in chk])


if __name__ == "__main__":
    main()