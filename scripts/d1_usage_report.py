#!/usr/bin/env python3
"""AIK24-D1-GUARD-01: D1 읽기 사용량 감시.

배경 (2026-10-14 사고): 계정 D1 무료 한도(5,000,000행/일, 자정 UTC 초기화)가 소진돼
EmDash 관리자 로그인·게시물 렌더·API 가 전부 죽었다. 정작 이 가드는 그날
"0.6% (정상)" 만 찍고 조용히 있었다.

왜 못 잡았나: 이 스크립트는 원래 "08:30 KST(= 23:30 UTC, 리셋 30분 전)" 를 가정했지만
이 머신의 로컬 TZ 는 **UTC+7(방콕)** 이다. launchd 08:30 = **01:30 UTC** — UTC 하루가
1.5시간밖에 안 지난 시점이라 표본이 거의 항상 0 에 가깝고, 한도 접근을 경고할 수 없다.
→ 그래서 2026-10-14 부터 30분 간격으로 돌며 하루치 추이를 본다(plist StartInterval=1800).

80% 이상이면 대표님께 Telegram(기존 경로 유지). 3단계(50/70/90%)는 
muse-cli 기본채팅으로 간다(2026-10-17 대표님 지시, AIK24-QUOTA-WARN-01). 
회동 중복발송 방지 상태는 cfnew.TIER_STATE_PATH(.d1_tier_alert_state.json) 가 UTC 날짜 단위로 관리한다.
읽기·쓰기 모두 추적한다. 읽기 전만 수행하던 시절과 달리 GraphQL 조회 1회에 둘 다 나온다.
읽기 전용 — D1 에 쓰지 않는다.
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import cfnew  # noqa: E402

THRESHOLD = 0.8  # Telegram 상시 경보(기존 경로 유지) — muse 3단계는 ALERT_TIERS
TAG = "[D1-GUARD]"
MARKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".d1_guard_alert_day")


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


def _already_alerted(day):
    """UTC 하루에 한 번만 Telegram 을 보낸다 (30분 간격 실행이므로)."""
    try:
        return open(MARKER, encoding="utf-8").read().strip() == day
    except OSError:
        return False


def _mark_alerted(day):
    try:
        open(MARKER, "w", encoding="utf-8").write(day)
    except OSError:
        pass


def main():
    load_env()
    if "--test-alert" in sys.argv[1:]:
        kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
        text = (f"[D1-GUARD] 테스트 경보 — 3단계(50/70/90%) 시스템 연결 확인 "
                f"(AIK24-QUOTA-WARN-01, KST {kst:%H:%M}). 이 메시지는 발송 테스트이며 임계와 무관합니다.")
        ok = cfnew.muse_send(text)
        print(f"{TAG} muse 테스트 발송: {'성공' if ok else '실패'}")
        return 0

    utc = datetime.datetime.now(datetime.timezone.utc)
    day = utc.strftime("%Y-%m-%d")
    used = cfnew.get_daily_rows_read(force=True)
    written = cfnew.get_daily_rows_written()
    pct = used / cfnew.D1_READ_LIMIT
    wpct = written / cfnew.D1_WRITE_LIMIT if cfnew.D1_WRITE_LIMIT else 0.0
    kst = (utc + datetime.timedelta(hours=9)).strftime("%H:%M")
    msg = f"{TAG} D1 읽기 {used:,}/{cfnew.D1_READ_LIMIT:,} ({pct:.1%}) · 쓰기 {written:,}/{cfnew.D1_WRITE_LIMIT:,} ({wpct:.1%}) — UTC 일 {day} (KST {kst})"

    # 3단계 muse 경보 (50/70/90%) — 낮은 수준이면 조용히 종료
    if pct < 0.5 and wpct < 0.5:
        print(msg + " (정상, 보고 없음)")
        return 0

    for outcome in cfnew.maybe_alert_tiers(pct, wpct):
        pass  # 발송 결과 로그는 maybe_alert_tiers 내부에서 출력됨

    if pct < THRESHOLD:
        print(msg + " (50% 이상 — muse 경보 발송 여부는 위 로그)")
        return 0

    if _already_alerted(day):
        print(msg + " (80% 초과지만 오늘 이미 Telegram 발송 — 중복 발송 안 함)")
        return 0

    print(msg + " → 읽기 80% 초과, Telegram 병행 알림")
    try:
        from pipeline.infra.telegram import send_telegram
        ok = send_telegram(msg + " — 한도 초과 시 EmDash 로그인·게시물이 죽는다. 폭주 스크립트 중단 권장.")
        print(f"telegram 발송: {'성공' if ok else '실패(토큰/챗ID 없음 또는 API 오류)'}")
        if ok:
            _mark_alerted(day)
    except Exception as e:  # 알림 실패가 조기 종료를 만들면 안 됨
        print(f"telegram 실패(무시): {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())