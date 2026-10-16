#!/usr/bin/env python3
"""일일 모델 호출 검증 (AIK24-EVAL-07 작업 1·2)

free_models_cli.json 의 cli_id 전부를 `opencode run` 으로 한 번씩 울려
살아 있는 모델만 캐시에 남긴다. daily 갱신이 캐시 읽기만 하던 간극 해소.

    python3 scripts/verify_models_daily.py                    # 실제 검증 + 캐시 갱신
    python3 scripts/verify_models_daily.py --extra-cli-id openrouter/nope:free --cli-json /tmp/t.json --out /tmp/o.json --verify-out /tmp/v.json  # FAIL 시뮬레이션

판정: 응답 텍스트에 "PONG" 포함 → PASS, 그 외(타임아웃·빈 응답·CLI 오류) → FAIL.

FAIL 처리 (2026-10-16 보강 — 실측 사고):
  - 사유가 제공 중단(Model unavailable·404·401·403 등, DEAD_MARKERS)이면 캐시에서 제거한다.
  - 그 외(타임아웃·빈 응답)는 **일시 실패**로 보고 free_models_pending.json 에 남긴다.
    이전에는 타임아웃 한 번에 모델이 캐시에서 영구 삭제됐다(재수집 경로 없음).
    다음 실행은 캐시 + 대기 목록을 함께 검증하므로 복구된 모델은 자동 복귀한다.

호출은 model_eval.cli_call() 재사용 — --format json 파싱·타임아웃 처리가 이미 있다.
shortcut: exit code를 직접 보지 않고 cli_call 추상화에 의존, 정밀한 실패 분류가 필요해지면 cli_call을 확장할 것.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts", "threads", "v3"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_eval  # noqa: E402
from model_catalog import CATALOG_DIR, _write_json  # noqa: E402

CLI_JSON_PATH = CATALOG_DIR / "free_models_cli.json"
VERIFY_PATH = CATALOG_DIR / "free_models_verify.json"
# AIK24-EVAL-07 후속(2026-10-16): 일시 실패(타임아웃 등) 모델을 담아 두는 대기 목록.
# 이 파일이 없으면 타임아웃 한 번에 모델이 목록에서 영구히 사라진다 — 오늘 실측:
# 16:17 검증에서 nemotron 4종이 60초 타임아웃으로 캐시에서 삭제됐고, 재수집 경로가
# 없어 복구되지 않았다. 다음 검증은 캐시 + 대기 목록을 함께 재검증한다.
PENDING_PATH = CATALOG_DIR / "free_models_pending.json"
PROBE_PROMPT = "한 단어로 대답: PONG"

# 모델이 "사라졌다"고 단정할 수 있는 사유. 이외의 실패(타임아웃·빈 응답·429)는
# 일시 실패로 보고 목록에서 지우지 않는다 — 복구되면 다음 검증에서 자동 복귀한다.
DEAD_MARKERS = (
    "model unavailable", "no-route", "not found", "404", "401", "403",
    "model_not_found", "no cookie auth",
)


def classify_fail(reason):
    """'dead'(제공 중단) 또는 'transient'(일시 실패). 모르면 살려 둔다."""
    r = (reason or "").lower()
    return "dead" if any(m in r for m in DEAD_MARKERS) else "transient"


def merge_candidates(entries, pending):
    """검증 대상 = 캐시 + 대기 목록. cli_id 기준 중복 제거(캐시 우선)."""
    out, seen = [], set()
    for e in list(entries or []) + list(pending or []):
        if not isinstance(e, dict):
            continue
        key = e.get("cli_id") or e.get("model_id")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def split_results(results):
    """(통과, 중단, 일시 실패) — verify_one 결과 리스트를 세 갈래로 나눈다."""
    passed, dead, pending = [], [], []
    for entry, ok, note in results:
        if ok:
            passed.append(entry)
        elif classify_fail(note) == "dead":
            dead.append((entry, note))
        else:
            pending.append((entry, note))
    return passed, dead, pending


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] [verify_models] {msg}", flush=True)


def verify_one(entry, timeout):
    """(entry, True/False, 사유) — FAIL 사유는 로그용으로 자른다."""
    cli_id = entry.get("cli_id", "")
    text, reason = model_eval.cli_call(cli_id, PROBE_PROMPT, timeout=timeout)
    if text and "PONG" in text:
        return entry, True, text[:40]
    return entry, False, (reason or "PONG 없음")[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli-json", default=str(CLI_JSON_PATH))
    ap.add_argument("--out", default=str(CLI_JSON_PATH))
    ap.add_argument("--verify-out", default=str(VERIFY_PATH))
    ap.add_argument("--pending", default=str(PENDING_PATH))
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--extra-cli-id", default=None)  # 완료기준 4 FAIL 시뮬레이션용
    a = ap.parse_args()

    try:
        entries = json.loads(Path(a.cli_json).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log(f"캐시 읽기 실패 — {e}")
        return 1
    if not isinstance(entries, list) or not entries:
        log("검증 대상 없음 (빈 캐시)")
        return 1
    if a.extra_cli_id:
        entries = list(entries) + [{"model_id": a.extra_cli_id.split("/")[-1],
                                    "provider": "test", "cli_id": a.extra_cli_id}]

    # 지난 실행에서 일시 실패로 빠진 모델을 함께 재검증한다 (복구 시 자동 복귀).
    try:
        prev_pending = json.loads(Path(a.pending).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev_pending = []
    if not isinstance(prev_pending, list):
        prev_pending = []
    entries = merge_candidates(entries, prev_pending)
    if prev_pending:
        log(f"대기 목록 {len(prev_pending)}건 합류 — 총 검증 대상 {len(entries)}건")

    # 이 저장소에서 돌리면 AGENTS.md 가 컨텍스트에 들어가 호출이 무거워지므로 빈 디렉터리에서 친다.
    os.chdir(tempfile.gettempdir())

    results = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, (entry, ok, note) in enumerate(
            ex.map(lambda e: verify_one(e, a.timeout), entries), 1
        ):
            tag = "PASS" if ok else "FAIL"
            kind = "" if ok else f"({classify_fail(note)})"
            log(f"[{i}/{len(entries)}] {tag}{kind} {entry.get('cli_id')} — {note}")
            results.append((entry, ok, note))

    passed, dead, pending = split_results(results)

    # 작업 2: PASS만 캐시에 기록. 원본은 날짜 백업 후 갱신.
    bak = Path(a.cli_json + f".bak-{datetime.now().strftime('%Y%m%d')}")
    shutil.copy2(a.cli_json, bak)
    _write_json(Path(a.out), passed)
    log(f"캐시 갱신: {len(passed)}건 PASS → {a.out} (백업 {bak.name})")

    # 일시 실패는 다음 실행에서 재검증하도록 대기 목록에 남긴다 (제공 중단은 남기지 않는다).
    _write_json(Path(a.pending), [e for e, _ in pending])
    if pending:
        log(f"대기 목록 {len(pending)}건 (일시 실패) → {a.pending}")

    verify = {"verified_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
              "pass": [e.get("cli_id") for e in passed],
              "fail": [{"cli_id": e.get("cli_id"), "model_id": e.get("model_id"),
                        "reason": r, "kind": classify_fail(r)} for e, r in dead + pending]}
    _write_json(Path(a.verify_out), verify)
    log(f"검증 기록 → {a.verify_out} "
        f"(PASS {len(passed)} / 중단 {len(dead)} / 일시 실패 {len(pending)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
