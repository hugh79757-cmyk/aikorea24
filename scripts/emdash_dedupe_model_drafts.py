#!/usr/bin/env python3
"""AIK24-PIPE-06 Phase B 후처리 — 모델별 draft 중복 정리.

배치 실행을 여러 번 돌리면 같은 모델의 초안이 2~5건 생긴다(제목이 매번 달라
슬러그도 다르면 EmDash 는 soft-delete 하지 않는다). 검수자가 模型당 1건만
보게 하��� **최신 1건만 남기고 나머지는 soft-delete** 한다.

주의: `ec_posts.deleted_at` 을 직접 쓴다. 발행된 글은 건드리지 않는다
(status='published' 는 대상에서 제외). soft-delete 라 되돌릴 수 있다.

사용:
    python3 scripts/emdash_dedupe_model_drafts.py           # 조사만
    python3 scripts/emdash_dedupe_model_drafts.py --apply   # 실제 반영
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cfnew  # noqa: E402
import blog_link_resolver as blr  # noqa: E402

KST = timezone(timedelta(hours=9))
BACKUP = Path(__file__).resolve().parent / "logs" / "pipe06_dedupe_backup.json"


def main():
    apply = "--apply" in sys.argv
    q = json.load(open(blr.QUEUE_PATH, encoding="utf-8"))
    entries = q.get("models") or []
    drafts = [p for p in blr.load_posts(include_draft=True) if p["status"] == "draft"]
    rows = cfnew.sql(
        "SELECT id, slug, created_at FROM ec_posts WHERE status='draft' AND deleted_at IS NULL",
        database_id=cfnew.EMDASH_DB) or []
    created = {r["slug"]: r for r in rows}

    per_model = defaultdict(list)
    for e in entries:
        # (a) 정밀 매칭
        hits = []
        for orig in e.get("original_titles", []):
            for p in drafts:
                if blr.match_post([p], orig) and p["slug"] in created:
                    hits.append(p["slug"])
        # (b) 느슨한 슬러그 키 매칭 (점 표기·접미사 차이로 정밀 매칭이 놓친 경우)
        # 모델 키 뒤에 **알파벳·숫자가 이어지면 다른 모델이다**
        # ("qwenimage" ⊂ "qwenimageedit", "glm5" ⊂ "glm52") → 거부.
        # 삭제는 되돌릴 수 없으므로 보수적으로 간다 — 겹쳐도 남는 게 삭제되는 것보다 낫다.
        loose = blr.loose_slug_key(e["key"])
        if loose and len(loose) >= 6:
            for p in drafts:
                if p["slug"] not in created:
                    continue
                dkey = blr.loose_slug_key(p["slug"])
                i = dkey.find(loose)
                if i == -1:
                    continue
                nxt = dkey[i + len(loose):i + len(loose) + 1]
                if nxt.isalnum():
                    continue
                hits.append(p["slug"])
        if hits:
            per_model[e["key"]] = sorted(set(hits))
    dups = {k: v for k, v in per_model.items() if len(v) > 1}
    print("모델별 draft 2건 이상: %d개 (정리 대상 draft %d건)"
          % (len(dups), sum(len(v) - 1 for v in dups.values())))

    to_delete = []
    seen_ids = set()
    for key, slugs in sorted(dups.items()):
        rows_ = [created[s] for s in sorted(set(slugs), key=lambda s: created[s]["created_at"])]
        keep = rows_[-1]
        drop = [r for r in rows_[:-1] if r["id"] not in seen_ids]
        for r in drop:
            seen_ids.add(r["id"])
        to_delete.extend(drop)
        print("  %s → 유지 %s (%s) / 삭제 %d건"
              % (key, keep["slug"][:44], str(keep["created_at"])[:19], len(drop)))
    if not apply:
        print("\n[dry-run] D1 쓰기 없음. --apply 로 실제 반영.")
        return

    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps(
        {"saved_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
         "rows": to_delete}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n백업: %s" % BACKUP)

    now = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    done = 0
    for i in range(0, len(to_delete), 40):
        chunk = to_delete[i:i + 40]
        sql = ";\n".join(
            "UPDATE ec_posts SET deleted_at='%s' WHERE id='%s'" % (now, r["id"])
            for r in chunk)
        cfnew.sql(sql, database_id=cfnew.EMDASH_DB)
        done += len(chunk)
    print("soft-delete: %d건" % done)
    left = cfnew.sql(
        "SELECT COUNT(*) c FROM ec_posts WHERE status='draft' AND deleted_at IS NULL",
        database_id=cfnew.EMDASH_DB)
    print("남은 유효 draft: %s" % left[0]["c"])


if __name__ == "__main__":
    main()
