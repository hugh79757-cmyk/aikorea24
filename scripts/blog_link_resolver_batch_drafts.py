#!/usr/bin/env python3
"""AIK24-PIPE-06 Phase B — 글 필요 큐 전수 draft 작성 (1회성 배치 실행).

- AIK24-PIPE-05 지시서 §5 / PIPE-06 Phase B: **상태는 draft 고정. 자동 발행 금지.**
- 정기 파이프라인(blog_draft_generator 5e)의 기본값은 건드리지 않는다
  (limit=3, only_in_briefing=True). 전수 처리는 이 스크립트로 1회성 실행한다.
- 재실행 가능 — 이미 draft 가 있는 모델은 건너뛴다.

사용:
    python3 scripts/blog_link_resolver_batch_drafts.py --limit 143 --all
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KST = timezone(timedelta(hours=9))
LOG_DIR = Path(__file__).resolve().parent / "logs"
RESULT_PATH = LOG_DIR / "pipe06_batch_drafts_result.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=143)
    ap.add_argument("--all", action="store_true", help="브리핑 노출 제한 해제 (전수)")
    ap.add_argument("--only-briefing", action="store_true", help="브리핑에 실린 모델만")
    args = ap.parse_args()

    import blog_link_resolver as blr

    only_in_briefing = not args.all
    started = datetime.now(KST)
    print("=" * 72)
    print("AIK24-PIPE-06 Phase B — 큐 전수 draft 작성")
    print("  시작: %s  limit=%d  only_in_briefing=%s" % (
        started.strftime("%Y-%m-%d %H:%M:%S"), args.limit, only_in_briefing))
    print("=" * 72, flush=True)

    result = blr.create_drafts(limit=args.limit, only_in_briefing=only_in_briefing)

    finished = datetime.now(KST)
    payload = {
        "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": finished.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_sec": int((finished - started).total_seconds()),
        "limit": args.limit,
        "only_in_briefing": only_in_briefing,
        "result": result,
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 72)
    print("완료: %s" % json.dumps(payload, ensure_ascii=False))
    print("결과 파일: %s" % RESULT_PATH)
    print("=" * 72)


if __name__ == "__main__":
    main()
