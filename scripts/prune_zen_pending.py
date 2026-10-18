#!/usr/bin/env python3
"""zen_pending.json 잔재 정리 (AIK24-BLOG-03 §정리, 2026-10-18).

배경: `zen_pending.json` 은 "Zen 모델인데 CLI 호출 경로를 못 찾았다"는 **대기 원장**이다.
모델이 Zen 무료 목록에서 아예 사라지면 그 대기 사유는 의미가 없어지는데, 원장에는
계속 남는다 (2026-10-18 실측: cat-jam-free 가 10-14 사유로 잔존 — 실제 상태는
"Model unavailable → 목록에서 제외").

이 도구는 **최신 카탈로그 스냅샷에 없는 모델의 항목**을 잔재로 보고 제거한다.
화면(`free_models_page.py`)은 이 파일을 읽지 않지만, 평가 파이프라인
(`cmd_evaluate → mark_zen_pending`)이 읽고 쓰므로 정확해야 한다.

안전장치
  1. 기본이 dry-run. 쓰려면 `--apply`.
  2. 쓰기 전 원본을 `scripts/logs/backup_zen_pending_<ts>.json` 에 남긴다.
  3. 남길 항목은 손대지 않는다 (키·값 그대로).

사용
  python3 scripts/prune_zen_pending.py                 # 미리보기
  python3 scripts/prune_zen_pending.py --apply         # 실행
  python3 scripts/prune_zen_pending.py --day 2026-10-17  # 기준 스냅샷 날짜 지정
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import model_catalog as mc  # noqa: E402

BACKUP_DIR = mc.CATALOG_DIR


def catalog_ids(day=None):
    """카탈로그 스냅샷의 model_id 집합. 스냅샷이 없으면 None(=판정 불가)."""
    path = mc.snapshot_path(day or mc.time.strftime("%Y-%m-%d"))
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        rows = json.load(f) or []
    ids = set()
    for r in (rows if isinstance(rows, list) else []):
        mid = (r or {}).get("model_id")
        if mid:
            ids.add(mid)
    return ids


def stale_entries(pending, ids):
    """최신 카탈로그에 없는 모델의 항목만 골라낸다 (ids 가 None 이면 빈 리스트).

    이름 정규화는 하지 않는다 — 원장 키와 카탈로그 model_id 는 같은 표기를 쓴다
    (`zen_pending.json` 은 split_zen 이 카탈로그 added 행의 model_id 로 기록한다).
    """
    if not ids or not isinstance(pending, dict):
        return []
    return sorted(k for k in pending if k and k not in ids)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=None, help="기준 카탈로그 스냅샷 날짜 (기본: 오늘)")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다(기본은 dry-run).")
    a = ap.parse_args(argv)

    path = mc.CATALOG_DIR / "zen_pending.json"
    if not os.path.exists(path):
        print("zen_pending.json 없음 — 정리 대상 없음")
        return 0
    with open(path, encoding="utf-8") as f:
        pending = json.load(f) or {}

    ids = catalog_ids(a.day)
    if ids is None:
        print("카탈로그 스냅샷이 없어 판정 불가 — 아무것도 하지 않는다")
        return 1
    stale = stale_entries(pending, ids)

    print("기준 스냅샷: %s (모델 %d건)" % (a.day or mc.time.strftime("%Y-%m-%d"), len(ids)))
    print("원장 %d건 · 잔재 %d건: %s" % (len(pending), len(stale), ", ".join(stale) or "없음"))
    for k in stale:
        print("  - %s → %s" % (k, (pending.get(k) or {}).get("reason")))
    if not stale:
        return 0
    if not a.apply:
        print("DRY-RUN — 쓰려면 --apply")
        return 0

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(BACKUP_DIR, "backup_zen_pending_%s.json" % ts)
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)
    kept = {k: v for k, v in pending.items() if k not in set(stale)}
    mc._write_json(path, kept)
    print("정리 완료 — %d건 → %d건" % (len(pending), len(kept)))
    print("백업: %s" % backup)
    with open(path, encoding="utf-8") as f:
        after = json.load(f) or {}
    assert set(after) == set(kept), "쓰기 후 검증 실패"
    print("쓰기 후 검증 OK (%d건)" % len(after))
    return 0


if __name__ == "__main__":
    sys.exit(main())
