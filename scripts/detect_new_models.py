#!/usr/bin/env python3
"""AIK24-PIPE-01 — 일일 신규 무료 모델 감지.

CLI 로 평가하므로 자동 평가 파이프라인은 죽었다(FREE-PIPE-01 에서 AIK24-PIPE-01 로 전환).
"모델 리스트 파악"만 하루 1회 자동 유지한다: 수집은 이미 model_catalog 가 하고,
이 스크립트는 그 결과와 직전 스냅샷을 비교해 신규 모델만 알린다.

D1 을 쓰지 않는다 — 외부 API 호출만이라 CF 자원 소모가 없다.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_catalog as mc  # noqa: E402

ALERT_PATH = mc.CATALOG_DIR / "new_models_alert.json"
BASELINE_PATH = mc.CATALOG_DIR / "model_catalog_baseline.json"
FREEPIPE_LOG = Path(__file__).resolve().parent / "logs" / "free-model-pipe.log"


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        FREEPIPE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FREEPIPE_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass  # 로그는 부가물이므로 실패해도 감지 결과에 영향 없다


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, str(path))


def main(day=None):
    day = day or time.strftime("%Y-%m-%d")
    mc.load_env()
    rows, all_ids, failed = mc.collect()
    mc._write_json(mc.snapshot_path(day), sorted(
        rows, key=lambda r: (r["provider"] or "", r["model_id"] or "")))

    # 첫 실행 이거나 베이스라인이 없으면 오늘을 베이스라인으로 삼는다 — 첫날을 전부 신규로 알리지 않기 위함.
    first_run = not BASELINE_PATH.exists()
    if first_run:
        base = {}
        log("베이스라인 없음 — 오늘 스냅샷을 베이스라인으로 기록한다(오늘은 신규로 알리지 않음)")
    else:
        try:
            base = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        except Exception:
            base = {}

    added = {}
    removed = {}
    if first_run:
        log("첫 실행 — 신규/제외 비교를 건너뛴다")
    else:
        for prov, ids in (all_ids or {}).items():
            known = set(base.get(prov) or [])
            new = [i for i in ids if i not in known]
            if new:
                added[prov] = new
        for prov, ids in (all_ids or {}).items():
            gone = sorted(set(base.get(prov) or []) - set(ids))
            if gone:
                removed[prov] = gone

    alert = {
        "day": day,
        "checked_at": time.time(),
        "total_rows": len(rows),
        "failed_providers": failed,
        "new_by_provider": added,
        "removed_by_provider": removed,
    }
    write_json(ALERT_PATH, alert)

    total_new = sum(len(v) for v in added.values())
    if total_new:
        log(f"신규 모델 {total_new}건")
        for prov, ids in added.items():
            log(f"  {prov}: {', '.join(ids)}")
        log(f"→ {ALERT_PATH}")
    else:
        log(f"신규 모델 없음 (전체 {len(rows)}건) → {ALERT_PATH}")

    # 수집 성공한 프로바이더만 베이스라인에 반영. 실패한 프로바이더를 비우면
    # 다음 날 그쪽 전부가 신규로 잡힌다.
    for prov, ids in (all_ids or {}).items():
        if prov in failed:
            continue
        base[prov] = list(ids)
    write_json(BASELINE_PATH, base)

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None))