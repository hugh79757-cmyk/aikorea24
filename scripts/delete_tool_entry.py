#!/usr/bin/env python3
"""AIK24-TOOLDEDUP-01 — /tools 중복 항목 삭제 도구 (dry-run 기본).

삭제 방식
  --slug <slug>            : src/content/tools/<slug>.md 삭제 + D1 `tools` 미러 행 삭제
  --retire-submission <id> : D1 `tool_submissions` 행을 status='retired' 로 소프트 삭제

안전장치 (모두 통과해야 실행)
  1) 삭제 대상 slug 의 tool_submissions 가 published/pending 이면 거부
     (md 를 지워도 D1 카드로 되살아나므로)
  2) 다른 글/페이지가 `/tools/<slug>` 를 참조하면 거부 (--force 로만 우회)
  3) --apply 없으면 아무것도 쓰지 않는다
  4) apply 전 백업 JSON 을 항상 먼저 쓴다 (scripts/logs/)
  5) apply 후 재조회로 검증하고 결과를 출력한다

복원
  python3 scripts/delete_tool_entry.py --restore scripts/logs/backup_tool_delete_<ts>.json --apply
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfnew  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(ROOT, "src", "content", "tools")
LOG_DIR = os.path.join(ROOT, "scripts", "logs")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,80}$")


def q(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def md_count() -> int:
    return len(glob.glob(os.path.join(TOOLS_DIR, "*.md")))


def counts() -> dict:
    rows = cfnew.sql("SELECT COUNT(*) c FROM tools;", database_id=cfnew.A24_DB)
    tools_n = rows[0]["c"] if isinstance(rows, list) and rows else None
    rows = cfnew.sql(
        "SELECT status, COUNT(*) c FROM tool_submissions GROUP BY status;",
        database_id=cfnew.A24_DB,
    )
    sub = {r["status"]: r["c"] for r in rows} if isinstance(rows, list) else rows
    return {"md": md_count(), "tools": tools_n, "tool_submissions": sub}


def ref_check(slug: str) -> list[str]:
    """src/ 전체에서 /tools/<slug> 참조를 찾는다 (content/tools 자신 제외)."""
    pat = re.compile(r"/tools/" + re.escape(slug) + r"(?![a-z0-9-])")
    hits = []
    for base, dirs, files in os.walk(os.path.join(ROOT, "src")):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules"}]
        for f in files:
            if not f.endswith((".md", ".astro", ".ts", ".tsx", ".js", ".json", ".xml", ".yaml", ".yml")):
                continue
            p = os.path.join(base, f)
            if p.startswith(TOOLS_DIR + os.sep):
                continue
            try:
                txt = open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            if pat.search(txt):
                hits.append(os.path.relpath(p, ROOT))
    return hits


def plan_slugs(slugs: list[str], force: bool) -> tuple[list[dict], list[str]]:
    plan, errors = [], []
    for slug in slugs:
        if not SLUG_RE.match(slug):
            errors.append(f"{slug}: 슬러그 형식 오류")
            continue
        path = os.path.join(TOOLS_DIR, f"{slug}.md")
        if not os.path.exists(path):
            errors.append(f"{slug}: md 파일 없음 ({os.path.relpath(path, ROOT)})")
            continue
        sub = cfnew.sql(
            f"SELECT id,status FROM tool_submissions WHERE slug={q(slug)};",
            database_id=cfnew.A24_DB,
        )
        if not isinstance(sub, list):
            errors.append(f"{slug}: tool_submissions 조회 실패 {sub}")
            continue
        live = [r for r in sub if r["status"] in ("published", "pending")]
        if live:
            errors.append(
                f"{slug}: tool_submissions 가 {live[0]['status']} (id={live[0]['id']}) — "
                "md 삭제해도 D1 카드로 남으므로 먼저 retire 해야 함"
            )
            continue
        refs = ref_check(slug)
        if refs and not force:
            errors.append(f"{slug}: 참조 {len(refs)}건 → {refs[:3]} (--force 로만 우회)")
            continue
        rows = cfnew.sql(f"SELECT * FROM tools WHERE slug={q(slug)};", database_id=cfnew.A24_DB)
        if not isinstance(rows, list):
            errors.append(f"{slug}: tools 조회 실패 {rows}")
            continue
        plan.append({
            "slug": slug,
            "md_path": os.path.relpath(path, ROOT),
            "md_content": open(path, encoding="utf-8").read(),
            "tools_rows": rows,
            "refs_forced": refs,
        })
    return plan, errors


def plan_retire(ids: list[int], reason: str) -> tuple[list[dict], list[str]]:
    plan, errors = [], []
    for i in ids:
        rows = cfnew.sql(
            f"SELECT * FROM tool_submissions WHERE id={int(i)};", database_id=cfnew.A24_DB
        )
        if not isinstance(rows, list) or not rows:
            errors.append(f"submission {i}: 행 없음 / 조회 실패")
            continue
        r = rows[0]
        if r["status"] == "retired":
            errors.append(f"submission {i} ({r['slug']}): 이미 retired")
            continue
        md = os.path.join(TOOLS_DIR, f"{r['slug']}.md")
        if os.path.exists(md):
            errors.append(
                f"submission {i} ({r['slug']}): 동일 slug 의 md 가 존재 → retire 해도 카드가 남는다"
            )
            continue
        plan.append({"id": int(i), "slug": r["slug"], "name": r["name"], "row": r,
                     "from_status": r["status"], "reason": reason})
    return plan, errors


def write_backup(payload: dict) -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(LOG_DIR, f"backup_tool_delete_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def do_apply(plan: list[dict], retire: list[dict], before: dict) -> dict:
    result = {"removed_md": [], "deleted_tools_rows": [], "retired": [], "errors": []}
    for item in plan:
        try:
            os.remove(os.path.join(ROOT, item["md_path"]))
            result["removed_md"].append(item["slug"])
        except OSError as e:
            result["errors"].append(f"{item['slug']}: md 삭제 실패 {e}")
            continue
        try:
            cfnew.sql(f"DELETE FROM tools WHERE slug={q(item['slug'])};", database_id=cfnew.A24_DB)
            result["deleted_tools_rows"].append(
                {"slug": item["slug"], "rows": [r["id"] for r in item["tools_rows"]]}
            )
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"{item['slug']}: tools DELETE 예외 {e}")
    for item in retire:
        try:
            cfnew.sql(
                "UPDATE tool_submissions SET status='retired', rejection_reason="
                f"{q(item['reason'])}, updated_at=datetime('now') WHERE id={item['id']};",
                database_id=cfnew.A24_DB,
            )
            result["retired"].append({"id": item["id"], "slug": item["slug"]})
        except Exception as e:  # noqa: BLE001
            result["errors"].append(f"submission {item['id']}: UPDATE 예외 {e}")
    result["before"] = before
    result["after"] = counts()
    return result


def verify(plan: list[dict], retire: list[dict]) -> list[str]:
    problems = []
    for item in plan:
        p = os.path.join(ROOT, item["md_path"])
        if os.path.exists(p):
            problems.append(f"{item['slug']}: md 여전히 존재")
        rows = cfnew.sql(f"SELECT id FROM tools WHERE slug={q(item['slug'])};", database_id=cfnew.A24_DB)
        if rows:
            problems.append(f"{item['slug']}: tools 행 여전히 존재 {rows}")
        sub = cfnew.sql(
            f"SELECT status FROM tool_submissions WHERE slug={q(item['slug'])};", database_id=cfnew.A24_DB
        )
        if any(r["status"] == "published" for r in sub or []):
            problems.append(f"{item['slug']}: published submission 존재 → 카드 부활")
    for item in retire:
        rows = cfnew.sql(
            f"SELECT status FROM tool_submissions WHERE id={item['id']};", database_id=cfnew.A24_DB
        )
        if not rows or rows[0]["status"] != "retired":
            problems.append(f"submission {item['id']}: retired 아님 {rows}")
    return problems


def do_restore(path: str) -> dict:
    data = json.load(open(path, encoding="utf-8"))
    out = {"restored_md": [], "restored_tools_rows": [], "errors": []}
    for item in data.get("slugs", []):
        p = os.path.join(ROOT, item["md_path"])
        try:
            if not os.path.exists(p):
                with open(p, "w", encoding="utf-8") as f:
                    f.write(item["md_content"])
                out["restored_md"].append(item["slug"])
        except OSError as e:
            out["errors"].append(f"{item['slug']}: md 복원 실패 {e}")
            continue
        for row in item["tools_rows"]:
            cols = [k for k in row if k != "id"]
            vals = ",".join(str(row[k]) if isinstance(row[k], (int, float)) else q(row[k]) for k in cols)
            try:
                cfnew.sql(
                    f"INSERT INTO tools (id,{','.join(cols)}) VALUES ({int(row['id'])},{vals});",
                    database_id=cfnew.A24_DB,
                )
                out["restored_tools_rows"].append({"slug": item["slug"], "id": row["id"]})
            except Exception as e:  # noqa: BLE001
                out["errors"].append(f"{item['slug']}#{row['id']}: INSERT 예외 {e}")
    for item in data.get("retire", []):
        try:
            cfnew.sql(
                f"UPDATE tool_submissions SET status={q(item['from_status'])} WHERE id={int(item['id'])};",
                database_id=cfnew.A24_DB,
            )
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"submission {item['id']}: status 복원 실패 {e}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", action="append", default=[])
    ap.add_argument("--retire-submission", action="append", type=int, default=[])
    ap.add_argument("--reason", default="게재 해제 — 목록 정리(2026-11-19)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--restore", metavar="BACKUP_JSON")
    args = ap.parse_args()

    if args.restore:
        if not args.apply:
            print(f"[dry-run] 복원 예정: {args.restore}")
            return 0
        out = do_restore(args.restore)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 1 if out["errors"] else 0

    if not args.slug and not args.retire_submission:
        ap.error("--slug 또는 --retire-submission 이 필요합니다")

    before = counts()
    plan, errors = plan_slugs(args.slug, args.force)
    retire, rerr = plan_retire(args.retire_submission, args.reason)
    errors += rerr

    print(f"현재: md={before['md']} tools={before['tools']} submissions={before['tool_submissions']}")
    for item in plan:
        print(f"[md 삭제] {item['slug']:34} {item['md_path']}  tools행={[r['id'] for r in item['tools_rows']]}")
        if item["refs_forced"]:
            print(f"    ⚠ 참조 강제 무시: {item['refs_forced']}")
    for item in retire:
        print(f"[retire]   id={item['id']:3d} {item['slug']:24} {item['name']} ({item['from_status']} → retired)")
    if errors:
        print("\n거부/오류:")
        for e in errors:
            print("  -", e)
        return 2
    if not args.apply:
        print("\n[dry-run] 쓰기 없음. 실행하려면 --apply")
        return 0

    backup = write_backup({"ts": dt.datetime.now().isoformat(timespec="seconds"),
                           "slugs": plan, "retire": retire, "before": before})
    print(f"\nbackup: {os.path.relpath(backup, ROOT)}")
    result = do_apply(plan, retire, before)
    problems = verify(plan, retire)
    result["verify_problems"] = problems
    print(json.dumps({k: result[k] for k in ("removed_md", "deleted_tools_rows", "retired", "errors")},
                     ensure_ascii=False, indent=2))
    print(f"after: md={result['after']['md']} tools={result['after']['tools']} "
          f"submissions={result['after']['tool_submissions']}")
    print("검증:", "OK" if not problems else problems)
    return 0 if not problems and not result["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
