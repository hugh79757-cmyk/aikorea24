#!/usr/bin/env python3
"""AIK24-D1-EMDASH-01: emdash-db D1 읽기 비용 회귀 감시 · sqlite_stat1 자동 복구.

배경(2026-10-22 실측):
  Cloudflare D1 무료 티어 한도 5,000,000 rows_read/일 은 **계정 단위**이고,
  이 계정(Stylefactory9ai@gmail.com's Account = cfnew.ACCT)에 D1 DB 5개가 함께 붙어
  한도를 공유한다: aikorea24-db · aikorea24-emdash-db · taiwan-news-db · heritage-db · mbti-db.
  2026-10-20 UTC 하루에 합계 4,195,200행(83.9%)으로 한도 83% 알림이 발생했다.

  어제(2026-10-21) 두 프로젝트에서 절감을 이미 적용했다:
    - aikorea24 프로젝트: AIK24-D1-READ-01/02 (SSR D1 읽기 1,733→53행/뷰, /global/ 19,218→50행/뷰)
    - emdash 프로젝트:     AIK24-EMDASH-17/18 (/posts 뷰당 3,260행 → 39행, 절감률 98.8%)
  적용 후 10-21 UTC 합계 1,461,243행(29.2%), 10-22 UTC 는 3.0% 로 내려갔다.

  그런데 emdash 쪽 절감(태그 하이드레이션 1,734행 → 25행)은 **sqlite_stat1 통계에 의존**한다.
  D1 은 ANALYZE 를 자동 실행하지 않으므로(출처: emdash node_modules/emdash/src/plugins/storage-indexes.ts:77)
  · 마이그레이션이 테이블을 재생성하면 통계가 함께 사라진다
  · 데이터가 늘면 통계가 낡아 실행 계획이 원래(비싼) 것으로 돌아간다
  → 비용이 조용히 40배 되돌아온다. 이 스크립트가 그 회귀를 감시하고 자동 복구한다.

동작:
  1) 핫 테이블의 sqlite_stat1 엔트리 존재 확인
  2) PRAGMA optimize (저비용 — 실제 측정 42행, 통계가 안 틀렸으면 아무 것도 안 건드린다)
  3) 여전히 통계가 없으면 대상 테이블만 ANALYZE → 재확인 → 그래도 없으면 전체 ANALYZE
  4) emdash-db 의 최근 24시간 rowsRead 를 측정(GraphQL) → 기준 초과 시 1회 알림(muse)
  5) 결과 로그: scripts/logs/emdash_d1_maintain.log

비용(자체):
  PRAGMA optimize 42행 + stat1 확인 ~200행 + COUNT 비교 1,728행 ≈ 일 2,000행 (한도의 0.04%)
  ANALYZE 는 통계가 실제로 깨졌을 때만 실행(ec_posts 단독 ANALYZE 실측 56,259행).

사용법:
  .venv/bin/python3 scripts/emdash_d1_maintain.py            # 점검 + 필요 시 복구
  .venv/bin/python3 scripts/emdash_d1_maintain.py --report   # 점검만(복구 없음)
  .venv/bin/python3 scripts/emdash_d1_maintain.py --force-analyze   # 강제 전체 ANALYZE
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cfnew  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_DIR / "scripts" / "logs" / "emdash_d1_maintain.log"
STATE_PATH = PROJECT_DIR / "scripts" / ".emdash_d1_maintain_state.json"

# 통계가 깨지면 비용이 40배로 돌아가는 핫 테이블 (2026-10-22 실측 기준).
#   ec_posts          1,728행 — 게시글 본체
#   content_taxonomies 1,381행 — 태그/분류 피벗(EMDASH-18 이 1,734행→25행을 만든 지점)
#   taxonomies           27행
HOT_TABLES = ["ec_posts", "content_taxonomies", "taxonomies"]

# emdash-db 최근 24시간 읽기 기준선.
#   정상 궤적 10-21 UTC = 862,010행(전일비 59.7% — 68만행이 최적화 이전 시간대)
#   정상 궤적 10-22 UTC = 약 350,000행/24h 추정
#   10-20(최적화 이전) = 2,137,095행  → 6개월간 1,200,000 초과면 회귀로 본다.
USAGE_ALERT_THRESHOLD = 1_200_000


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(s: dict) -> None:
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


# AIK24-D1-READ-03 (D-1): D1 가드(80% 초과)로 쿼리가 차단되면 빈 결과가 돌아온다.
#   빈 결과를 "통계 없음"으로 오판하면 실행하지도 않은 ANALYZE 를 "수행했다"고 기록한다
#   (2026-10-24 05:10 실측: 80.2% 차단 상태에서 ANALYZE 4건 수행 기록, 실제 실행 0건).
#   → 차단 사실을 플래그로 남겨 통계 점검 자체를 건너뛴다.
_GUARD_BLOCKED = False


def d1(sql: str) -> list:
    """emdash-db 읽기. cfnew.sql 의 기본 대상이 EMDASH_DB 다."""
    global _GUARD_BLOCKED
    try:
        rows = cfnew.sql(sql)
    except cfnew.QuotaExceededError as e:
        _GUARD_BLOCKED = True
        log(f"  ⛔ D1 가드 중단: {e}")
        return []
    except Exception as e:  # noqa: BLE001 — 유지보수 잡은 예외에도 죽지 않는다
        log(f"  D1 예외: {e}")
        return []
    if isinstance(rows, dict):
        log(f"  D1 오류: {str(rows)[:200]}")
        return []
    return rows


def stat1_tables() -> set:
    """sqlite_stat1 에 통제가 있는 테이블 집합."""
    rows = d1("SELECT DISTINCT tbl FROM sqlite_stat1")
    return {str(r.get("tbl")) for r in rows if r.get("tbl")}


def ensure_stats(report_only: bool = False, force_analyze: bool = False) -> dict:
    """통계 건강 상태를 확인하고, 깨졌으면 복구한다."""
    result = {"before": sorted(set(HOT_TABLES) & stat1_tables()),
              "actions": [], "recovered": False}

    # 가드 차단 상태의 빈 결과는 "통계 없음"의 증거가 아니다 → 판정 자체를 보류한다.
    if _GUARD_BLOCKED:
        log("  ⏸️ D1 가드 차단으로 통계 확인 불가 — 이번 주기 통계 점검 건너뜀(거짓 복구 기록 방지)")
        result["blocked"] = True
        result["after"] = result["before"]
        result["still_missing"] = []
        return result

    missing = [t for t in HOT_TABLES if t not in set(result["before"])]

    if force_analyze:
        if report_only:
            log("  --force-analyze + --report 조합은 복구하지 않는다 (대기).")
        else:
            log("  강제 전체 ANALYZE 실행 (비용: 실측 13만행)")
            d1("ANALYZE")
            result["actions"].append("ANALYZE(전체) [강제]")

    elif missing:
        log(f"  ⚠️ 핫 테이블 통계 없음: {missing} → 복구 시도")
        if report_only:
            log("  (--report: 복구 없이 보고만)")
        else:
            for t in missing:
                d1(f"ANALYZE {t}")
                result["actions"].append(f"ANALYZE {t}")

    elif not report_only:
        # 통계가 있더라도 드리프트가 있을 수 있다 → 저비용 PRAGMA optimize 로 갱신 시도.
        d1("PRAGMA optimize")
        result["actions"].append("PRAGMA optimize")

    after = stat1_tables()
    result["after"] = sorted(set(HOT_TABLES) & after)
    still_missing = [t for t in HOT_TABLES if t not in after]

    if still_missing and not report_only:
        log(f"  ⚠️ 여전히 통계 없음: {still_missing} → 전체 ANALYZE")
        d1("ANALYZE")
        result["actions"].append("ANALYZE(전체) [복구 실패 후]")
        after = stat1_tables()
        result["after"] = sorted(set(HOT_TABLES) & after)
        still_missing = [t for t in HOT_TABLES if t not in after]

    result["still_missing"] = still_missing
    result["recovered"] = bool(result["actions"]) and not still_missing
    return result


def stat_drift() -> str:
    """ec_posts 의 실제 행 수와 sqlite_stat1 추정치 비교 (드리프트 판정)."""
    rows = d1(
        "SELECT (SELECT COUNT(*) FROM ec_posts) AS real_rows, "
        "(SELECT stat FROM sqlite_stat1 WHERE tbl='ec_posts' "
        "AND idx='sqlite_autoindex_ec_posts_1') AS stat1_est"
    )
    if not rows:
        return "판정 불가(조회 실패)"
    real = rows[0].get("real_rows")
    est_raw = rows[0].get("stat1_est")
    if real is None or not est_raw:
        return f"통계 없음 (실제 {real}행)"
    try:
        est = int(str(est_raw).split()[0])
    except (ValueError, IndexError):
        return f"추정치 파싱 실패: {est_raw!r}"
    if real == 0:
        return "ec_posts 비어 있음"
    diff = (real - est) / real * 100
    if abs(diff) <= 10:
        return f"일치 (실제 {real}행 / 추정 {est}행, 편차 {diff:+.1f}%)"
    return f"⚠️ 드리프트 (실제 {real}행 / 추정 {est}행, 편차 {diff:+.1f}%)"


def usage_last_24h() -> int:
    """emdash-db 최근 24시간 rowsRead (GraphQL, D1 행 소모 없음)."""
    import urllib.request

    end = datetime.datetime.now(datetime.timezone.utc)
    start = end - datetime.timedelta(hours=24)
    q = f"""query {{ viewer {{ accounts(filter:{{accountTag:"{cfnew.ACCT}"}}) {{
      d1AnalyticsAdaptiveGroups(limit:200, filter:{{datetime_geq:"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}", datetime_lt:"{end.strftime('%Y-%m-%dT%H:%M:%SZ')}"}}) {{
        dimensions {{ databaseId }} sum {{ rowsRead }} }} }} }} }}"""
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/graphql",
        data=json.dumps({"query": q}).encode(),
        headers={"Authorization": f"Bearer {cfnew.token()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    groups = data["data"]["viewer"]["accounts"][0]["d1AnalyticsAdaptiveGroups"]
    total = 0
    for g in groups:
        if g["dimensions"]["databaseId"] == cfnew.EMDASH_DB:
            total += g["sum"]["rowsRead"] or 0
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description="emdash-db D1 회귀 감시 · 통계 자동 복구")
    ap.add_argument("--report", action="store_true", help="점검만(복구 없음)")
    ap.add_argument("--force-analyze", action="store_true", help="강제 전체 ANALYZE")
    args = ap.parse_args()

    log("=" * 60)
    log("emdash-db D1 유지보수 시작" + (" (--report: 점검만)" if args.report else ""))

    st = ensure_stats(report_only=args.report, force_analyze=args.force_analyze)
    log(f"  통계 보유 테이블: before={st['before']} → after={st['after']}")
    if st["actions"]:
        log(f"  수행 작업: {st['actions']}")
    if st["still_missing"]:
        log(f"  ❌ 통계 여전히 없음: {st['still_missing']}")
    else:
        log(f"  ✅ 핫 테이블 통계 정상 (드리프트: {stat_drift()})")

    used = usage_last_24h()
    pct = used / cfnew.D1_READ_LIMIT * 100
    log(f"  emdash-db 최근 24시간 rowsRead = {used:,}행 (계정 한도의 {pct:.1f}%)")

    state = _state()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if used > USAGE_ALERT_THRESHOLD and state.get("alert_day") != today:
        log(f"  ⚠️ 기준 초과 ({used:,} > {USAGE_ALERT_THRESHOLD:,}) → 1회 알림")
        text = (
            f"[D1-GUARD] emdash-db 읽기 증가 — {used:,}행/24h "
            f"(기준 {USAGE_ALERT_THRESHOLD:,} 초과, 계정 한도 {pct:.1f}%)\n"
            f"원인 후보: sqlite_stat1 회귀 / sitemap 캐시 해제 / 페이지 풀스캔 확대\n"
            f"확인: python3 scripts/emdash_d1_maintain.py --report"
        )
        if cfnew.muse_send(text):
            state["alert_day"] = today
        else:
            log("  (알림 전송 실패 — 재시도 대상)")
    elif used > USAGE_ALERT_THRESHOLD:
        log("  (기준 초과지만 오늘 이미 알림함 — 중복 방지)")
    else:
        log(f"  ✅ 사용량 기준 이내 (≤ {USAGE_ALERT_THRESHOLD:,})")

    state["last_run"] = datetime.datetime.now().isoformat(timespec="seconds")
    state["last_actions"] = st["actions"]
    state["last_usage_24h"] = used
    _save_state(state)

    log("종료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
