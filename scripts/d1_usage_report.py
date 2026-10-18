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


def _gq_history(days):
    """AIK24-D1-OPT-01(2026-10-18): 최근 N일(UTC) 일자×DB rowsRead/rowsWritten — GraphQL 1회.

    기존 경보 경로(오늘 하루 누적 1점)로는 "어제 대비 줄었나"를 볼 수 없어 추가했다.
    읽기 전용 · D1 에 쓰지 않는다. 차원은 date·databaseId 만 쓴다
    (D1 어댑터가 지원하는 차원 = databaseId·date·datetimeHour 실측, cfnew.py 주석 참조).
    """
    import json
    import urllib.request

    end = datetime.datetime.now(datetime.timezone.utc).date()
    start = end - datetime.timedelta(days=max(1, days) - 1)
    q = """query($f: D1AdaptiveGroupsFilter_InputObject!, $acct: String!) {
      viewer { accounts(filter:{accountTag:$acct}) {
        d1AnalyticsAdaptiveGroups(limit:1000, filter:$f) {
          dimensions { date databaseId } sum { rowsRead rowsWritten } } } } }"""
    v = {"acct": cfnew.ACCT,
         "f": {"datetime_geq": f"{start}T00:00:00Z", "datetime_lt": f"{end}T23:59:59Z"}}
    req = urllib.request.Request(
        cfnew.GQ, data=json.dumps({"query": q, "variables": v}).encode(),
        headers={"Authorization": f"Bearer {cfnew.token()}", "Content-Type": "application/json", **cfnew.UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["data"]["viewer"]["accounts"][0]["d1AnalyticsAdaptiveGroups"]


def _db_names():
    """DB uuid → 이름. CF API 조회(읽기 전용, D1 행 미소모)로 채우고 실패 시 대체표로 폴백.

    DB 를 새로 만들면 코드 수정 없이 표에 이름이 나온다.
    """
    import json
    import urllib.request

    names = {cfnew.A24_DB: "aikorea24-db", cfnew.EMDASH_DB: "aikorea24-emdash-db"}
    try:
        req = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/accounts/{cfnew.ACCT}/d1/database?per_page=20",
            headers={"Authorization": f"Bearer {cfnew.token()}", **cfnew.UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            for it in (json.loads(r.read()).get("result") or []):
                if it.get("uuid") and it.get("name"):
                    names[it["uuid"]] = it["name"]
    except Exception:  # noqa: BLE001 — 이름은 표시용. 조회 실패가 표를 막지 않게 한다.
        pass
    return names


def history(days=7, by_db=False):
    """일자별·(옵션)DB별 D1 사용량 표. 한도 대비 %와 함께 출력한다."""
    groups = _gq_history(days)
    names = _db_names()
    per_day = {}
    per_db = {}
    for g in groups:
        d = (g.get("dimensions") or {}).get("date")
        dbid = (g.get("dimensions") or {}).get("databaseId") or "?"
        rd = g["sum"]["rowsRead"] or 0
        wr = g["sum"]["rowsWritten"] or 0
        a = per_day.setdefault(d, {"read": 0, "write": 0})
        a["read"] += rd
        a["write"] += wr
        b = per_db.setdefault((d, dbid), {"read": 0, "write": 0})
        b["read"] += rd
        b["write"] += wr

    print(f"{TAG} D1 이력 {days}일 (UTC · 한도 읽기 {cfnew.D1_READ_LIMIT:,} / 쓰기 {cfnew.D1_WRITE_LIMIT:,})")
    print(f"  {'UTC 일자':<12}{'읽기':>14}{'한도%':>9}{'쓰기':>12}{'한도%':>9}")
    for d in sorted(per_day):
        a = per_day[d]
        print(f"  {d:<12}{a['read']:>14,}{a['read'] / cfnew.D1_READ_LIMIT:>8.1%}"
              f"{a['write']:>12,}{a['write'] / cfnew.D1_WRITE_LIMIT:>8.1%}")
    if per_day:
        ds = sorted(per_day)
        reads = [per_day[d]["read"] for d in ds]
        print(f"  ── {days}일 범위 {min(reads):,} ~ {max(reads):,} · 평균 {sum(reads) // len(reads):,}")
    if by_db:
        print(f"\n  {'UTC 일자':<12}{'DB':<24}{'읽기':>14}{'쓰기':>12}")
        for (d, dbid) in sorted(per_db):
            b = per_db[(d, dbid)]
            print(f"  {d:<12}{names.get(dbid, dbid[:12] + '…'):<24}{b['read']:>14,}{b['write']:>12,}")
    return 0


def _worker_to_db():
    """Worker(scriptName) → DB uuid. 양쪽 이름에서 파생하므로 고정표가 없다.

    규칙: 소문자화 → '-'/'_' 제거 → 끝의 'db' 제거.
    예) aikorea24-emdash-db → 'aikorea24emdash' == Worker 'aikorea24emdash'.
    """
    def norm(s):
        s = str(s or "").lower().replace("-", "").replace("_", "")
        return s[:-2] if s.endswith("db") else s

    m = {}
    for uuid, name in _db_names().items():
        m.setdefault(norm(name), uuid)
    return m


def _gq_requests(days):
    """Workers 요청 수 (scriptName×일자 UTC). D1 행을 쓰지 않는다 — 단가 분모용."""
    import json
    import urllib.request

    end = datetime.datetime.now(datetime.timezone.utc).date()
    start = end - datetime.timedelta(days=max(1, days) - 1)
    q = f"""query {{ viewer {{ accounts(filter:{{accountTag:"{cfnew.ACCT}"}}) {{
        workersInvocationsAdaptive(limit:1000, filter:{{date_geq:"{start}", date_leq:"{end}"}}) {{
          dimensions {{ date scriptName }} sum {{ requests }} }} }} }} }}"""
    req = urllib.request.Request(
        cfnew.GQ, data=json.dumps({"query": q}).encode(),
        headers={"Authorization": f"Bearer {cfnew.token()}", "Content-Type": "application/json", **cfnew.UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["data"]["viewer"]["accounts"][0]["workersInvocationsAdaptive"]


def unit(days=7):
    """보조 지표: 행/요청 = 그 DB 의 D1 읽기 ÷ 그 DB 를 서빙하는 Worker 요청수.

    주의 — 요청당 단가는 그날 '어떤 페이지가 얼마나 맞았는지'(페이지 구성)에 따라
    요동한다(2026-10-18 시간대 실측 53~889행/요청). 일 총량 비교의 트래픽 교란을
    완전히 제거하지는 못하므로 단독 판정에 쓰지 않고 추이만 본다.
    """
    pairs = _worker_to_db()
    reqs = {}
    for g in _gq_requests(days):
        dbid = pairs.get(g["dimensions"]["scriptName"])
        if dbid:
            k = (g["dimensions"]["date"], dbid)
            reqs[k] = reqs.get(k, 0) + (g["sum"]["requests"] or 0)
    reads = {}
    for g in _gq_history(days):
        k = (g["dimensions"]["date"], g["dimensions"]["databaseId"])
        reads[k] = reads.get(k, 0) + (g["sum"]["rowsRead"] or 0)

    names = _db_names()
    print(f"{TAG} 행/요청 단가 (보조 지표 · D1 읽기 ÷ Worker 요청 · 최근 {days}일 UTC)")
    print(f"  {'UTC 일자':<12}{'DB':<24}{'요청':>9}{'D1읽기':>13}{'행/요청':>9}")
    for (d, dbid) in sorted(reqs):
        rq = reqs[(d, dbid)]
        rd = reads.get((d, dbid), 0)
        print(f"  {d:<12}{names.get(dbid, dbid[:12] + '…'):<24}{rq:>9,}{rd:>13,}"
              f"{(rd / rq if rq else 0.0):>9.1f}")
    print("  ※ 페이지 구성에 따라 요동한다 — 추이 관찰용. 단독으로 '절감/미절감'을 판정하지 않는다.")
    return 0


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
    argv = sys.argv[1:]
    # AIK24-D1-OPT-01(2026-10-18): 이력 재측정 모드 — 읽기 전용, 경보 경로를 타지 않는다.
    #   python3 scripts/d1_usage_report.py --history 7 [--by-db]
    if "--history" in argv:
        i = argv.index("--history")
        days = int(argv[i + 1]) if len(argv) > i + 1 and argv[i + 1].isdigit() else 7
        return history(days, by_db="--by-db" in argv)
    if "--unit" in argv:
        i = argv.index("--unit")
        days = int(argv[i + 1]) if len(argv) > i + 1 and argv[i + 1].isdigit() else 7
        return unit(days)
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