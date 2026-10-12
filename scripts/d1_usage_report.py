#!/usr/bin/env python3
"""AIK24-D1-GUARD-01: 일일 D1 읽기 사용량 보고.

매일 08:30 KST(= 23:30 UTC, 리셋 30분 전) 실행돼 직전 UTC 하루치를 본다.
80% 초과일 때만 대표님께 Telegram 으로 알린다. 미만이면 조용히 종료한다.

읽기 전용 — D1 에 쓰지 않는다.
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import cfnew  # noqa: E402

THRESHOLD = 0.8
TAG = "[D1-GUARD]"


def load_env():
    """launchd 는 PATH 만 주므로 TELEGRAM_* 을 못 읽는다.
    ~/.env.common 은 setdefault(공통값 유지), 프로젝트 .env 는 덮어쓰기 — BRIEF-01 과 동일 규칙."""
    for p, overwrite in ((os.path.expanduser("~/.env.common"), False), (os.path.join(_ROOT, ".env"), True)):
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.strip().split("=", 1)[0], line.split("=", 1)[1].strip().strip('"').strip("'")
            if overwrite or k not in os.environ:
                os.environ[k] = v


def main():
    load_env()
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    used = cfnew.get_daily_rows_read(force=True)
    pct = used / cfnew.D1_READ_LIMIT
    msg = f"{TAG} D1 읽기 {used:,}/{cfnew.D1_READ_LIMIT:,} ({pct:.1%}) — 일 {day}"

    if pct < THRESHOLD:
        print(msg + " (정상, 보고 없음)")
        return 0

    print(msg + " → 초과, 대표님 알림")
    try:
        from pipeline.infra.telegram import send_telegram
        ok = send_telegram(msg)
        print(f"telegram 발송: {'성공' if ok else '실패(토큰/챗ID 없음 또는 API 오류)'}")
    except Exception as e:  # 알림 실패가 조기 종료를 만들면 안 됨
        print(f"telegram 실패(무시): {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())