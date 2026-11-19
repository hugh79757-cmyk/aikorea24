#!/usr/bin/env python3
"""EmDash **초안(draft)** 1건을 soft-delete 한다 (기본 dry-run).

2026-11-19: 발행하지 않은 초안 「무료 코딩 모델 Hy4 flash Free 사용법 및 설정 가이드」를
정리하려고 만들었다. 이 초안은 `:free` 접미사·이미지 입력처럼 **근거 없는 서술**을 담고 있어
그대로 두면 잘못 발행될 위험이 있었다.

안전장치
  1. `status='published'` 는 **거부**한다. 발행글은 이 도구로 지우지 않는다
     (발행글 정리는 라이브 영향 검토가 먼저다).
  2. 지우기 전에 행 전체를 `scripts/logs/backup_draft_delete_<ts>.json` 에 남긴다.
  3. D1 의 `deleted_at` 만 채우는 **soft-delete** 다(되돌리려면 NULL 로 되돌린다).
     초안은 공개 렌더 대상이 아니므로 revision/publish 절차가 필요 없다.
  4. 참조 검사 — `briefing_items.deep_dive_url` 과 발행글 본문이 이 id/slug 를 가리키면 중단한다.
  5. 실행 후 재조회로 deleted_at 이 채워졌는지, 초안 총계가 1 줄었는지 확인한다.

사용
  ../.venv/bin/python3 scripts/delete_draft_post.py --id 01M7KEQDK42QB4D7YEV4AZT5GV
  ../.venv/bin/python3 scripts/delete_draft_post.py --id 01M7KEQDK42QB4D7YEV4AZT5GV --apply
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfnew  # noqa: E402

LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def fetch(post_id):
    rows = cfnew.sql(
        "SELECT id, slug, title, status, published_at, created_at, updated_at, deleted_at, "
        "content FROM ec_posts WHERE id = '%s';" % post_id.replace("'", "''"),
        database_id=cfnew.EMDASH_DB)
    return rows[0] if rows else None


def draft_count():
    r = cfnew.sql("SELECT COUNT(*) c FROM ec_posts WHERE status='draft' AND deleted_at IS NULL;",
                  database_id=cfnew.EMDASH_DB)
    return (r[0] if r else {}).get("c")


def _rows(res, label):
    """cfnew.sql 은 실패 시 {'http_error':…} dict 를 돌려준다 — 그대로 순회하면 오판한다."""
    if isinstance(res, dict):
        print(f"! {label} 조회 실패: {json.dumps(res, ensure_ascii=False)[:200]}")
        raise SystemExit(4)
    return res or []


def references(post_id, slug):
    """참조가 있으면 사유 목록을 돌려준다(없으면 빈 목록).

    LIKE 는 긴 한글 slug 에서 'pattern too complex' 로 실패한다(SQLite) — instr 을 쓴다.
    """
    out = []
    q = ("SELECT id, briefing_id, deep_dive_url FROM briefing_items "
         "WHERE instr(deep_dive_url, '{s}') > 0 OR instr(deep_dive_url, '{i}') > 0;").format(
             s=slug.replace("'", "''"), i=post_id.replace("'", "''"))
    b = _rows(cfnew.sql(q, database_id=cfnew.A24_DB), "briefing_items")
    if b:
        out.append(f"briefing_items {len(b)}건이 이 초안을 가리킨다: {b[:3]}")
    q2 = ("SELECT id, slug FROM ec_posts WHERE status='published' AND deleted_at IS NULL "
          "AND instr(content, '{i}') > 0;").format(i=post_id.replace("'", "''"))
    p = _rows(cfnew.sql(q2, database_id=cfnew.EMDASH_DB), "발행글 본문")
    if p:
        out.append(f"발행글 {len(p)}건 본문이 이 초안 id 를 참조한다: {p[:3]}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="ec_posts.id")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    row = fetch(a.id)
    if not row:
        print(f"! {a.id}: 해당 글이 없다")
        return 1
    print(f"대상: {row['title']}")
    print(f"  slug={row['slug']} status={row['status']} published_at={row['published_at']} "
          f"deleted_at={row['deleted_at']}")
    if row["status"] == "published" or row["published_at"]:
        print("! 발행된 글은 이 도구로 지우지 않는다 — 중단")
        return 2
    if row["deleted_at"]:
        print("이미 soft-delete 된 글이다 — 할 일 없음")
        return 0

    refs = references(a.id, row["slug"])
    if refs:
        for r in refs:
            print("! " + r)
        print("! 참조가 있어 중단한다 (참조를 먼저 정리해야 한다)")
        return 3

    before = draft_count()
    print(f"초안 총계(삭제 전): {before}")

    if not a.apply:
        print("\n[DRY-RUN] 쓰기 없음. 적용하려면 --apply")
        return 0

    os.makedirs(LOGS, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(LOGS, f"backup_draft_delete_{ts}.json")
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(row, f, ensure_ascii=False, indent=1)
    print(f"백업: {backup}")

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    cfnew.sql("UPDATE ec_posts SET deleted_at='%s' WHERE id='%s';"
              % (now, a.id.replace("'", "''")), database_id=cfnew.EMDASH_DB)

    after_row = fetch(a.id)
    after_count = draft_count()
    print(f"초안 총계(삭제 후): {after_count} (기대 {before - 1 if before else '?'})")
    print(f"사후검증 — deleted_at={after_row['deleted_at']} | status={after_row['status']}")
    ok = bool(after_row["deleted_at"]) and (before is None or after_count == before - 1)
    print("결과:", "정상" if ok else "확인 필요")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
