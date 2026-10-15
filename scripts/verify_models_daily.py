#!/usr/bin/env python3
"""일일 모델 호출 검증 (AIK24-EVAL-07 작업 1·2)

free_models_cli.json 의 cli_id 전부를 `opencode run` 으로 한 번씩 울려
살아 있는 모델만 캐시에 남긴다. daily 갱신이 캐시 읽기만 하던 간극 해소.

    python3 scripts/verify_models_daily.py                    # 실제 검증 + 캐시 갱신
    python3 scripts/verify_models_daily.py --extra-cli-id openrouter/nope:free --cli-json /tmp/t.json --out /tmp/o.json --verify-out /tmp/v.json  # FAIL 시뮬레이션

판정: 응답 텍스트에 "PONG" 포함 → PASS, 그 외(타임아웃·빈 응답·CLI 오류) → FAIL.
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
PROBE_PROMPT = "한 단어로 대답: PONG"


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

    # 이 저장소에서 돌리면 AGENTS.md 가 컨텍스트에 들어가 호출이 무거워지므로 빈 디렉터리에서 친다.
    os.chdir(tempfile.gettempdir())

    passed, failed = [], []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, (entry, ok, note) in enumerate(
            ex.map(lambda e: verify_one(e, a.timeout), entries), 1
        ):
            tag = "PASS" if ok else "FAIL"
            log(f"[{i}/{len(entries)}] {tag} {entry.get('cli_id')} — {note}")
            if ok:
                passed.append(entry)
            else:
                failed.append((entry, note))

    # 작업 2: PASS만 기록. 원본은 날짜 백업 후 갱신.
    bak = Path(a.cli_json + f".bak-{datetime.now().strftime('%Y%m%d')}")
    shutil.copy2(a.cli_json, bak)
    _write_json(Path(a.out), passed)
    log(f"캐시 갱신: {len(passed)}건 PASS → {a.out} (백업 {bak.name})")

    verify = {"verified_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
              "pass": [e.get("cli_id") for e in passed],
              "fail": [{"cli_id": e.get("cli_id"), "model_id": e.get("model_id"),
                        "reason": r} for e, r in failed]}
    _write_json(Path(a.verify_out), verify)
    log(f"검증 기록 → {a.verify_out} (PASS {len(passed)} / FAIL {len(failed)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
