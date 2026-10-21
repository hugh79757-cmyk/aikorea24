#!/usr/bin/env python3
"""Shared CF helper for AIK24-EMDASH-02 (new account 7eb1b8cd...)."""
import datetime, json, os, shutil, subprocess, time, urllib.request, urllib.error

ACCT = "7eb1b8cd178de269758ec94b2e03330b"
EMDASH_DB = "bbbcbc34-f346-49e0-9aab-058836bee16d"
A24_DB = "3f4cedde-eabc-4d7c-b459-f6abe8733767"
API = "https://api.cloudflare.com/client/v4"
GQ = "https://api.cloudflare.com/client/v4/graphql/analytics"
UA = {"User-Agent": "curl/8.7.1", "Accept": "*/*"}


def token():
    for line in open(os.path.expanduser("~/.env.common")):
        if line.startswith("CF_MIGRATE_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("CF_MIGRATE_TOKEN not found")


def rest(path, method="GET", body=None, tok=None):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {tok or token()}", "Content-Type": "application/json", **UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode()[:600]}


def sql(statement, database_id=EMDASH_DB, tok=None):
    check_quota()
    r = rest(f"/accounts/{ACCT}/d1/database/{database_id}/query", "POST", {"sql": statement}, tok=tok)
    if "result" not in r:
        return r
    return r["result"][0].get("results", [])


def schema(database_id=EMDASH_DB, tok=None):
    rows = sql("SELECT type,name,tbl_name FROM sqlite_master ORDER BY type,name", database_id, tok)
    if isinstance(rows, dict):
        return rows
    tables = [r["name"] for r in rows if r["type"] == "table"]
    idx = [r for r in rows if r["type"] == "index"]
    return {"tables": tables, "n_tables": len(tables), "n_indexes": len(idx),
            "index_by_table": {}}


# --- AIK24-D1-GUARD-01: 일일 읽기 한도 가드 --------------------------------
# 무료 티어 D1 읽기 한도 = 계정 단위 5,000,000행/일 (자정 UTC 초기화).
# 2026-10-10 실제 초과(5,356,078) → sql() 이 7500 에러를 반환하며 페이지가 조용히 빈 데이터로 렌더됨.
#
# 필드 선택 근거: 지시서는 d1QueriesAdaptiveGroups / d1Storage 를 예시로 들었으나,
# 실제로 200 을 돌려주는 필드는 d1AnalyticsAdaptiveGroups 뿐이다
# (d1QueriesAdaptiveGroups = "unknown field" 실측). day 로 'YYYY-MM-DD' 만 받는다 —
# D1 어댑터는 datetimeHour 를 쓰므로 datetimeMinute 가 없어 일자 경계가 안 맞는다.
D1_READ_LIMIT = 5_000_000
D1_WRITE_LIMIT = 100_000  # 2026-10-17 AIK24-QUOTA-WARN-01: 쓰기 추적 추가 — 10-09 쓰기 183% 초과 실측 (백필)
READONLY_RATIO = 0.95
CACHE_TTL = 300  # 5분 — 매 sql() 마다 GraphQL 을 때리면 레이트리밋에 걸린다
# 3단계 경보 (2026-10-17 대표님 지시): 읽기·쓰기 각각 50/70/90% 돌파 시 muse-cli 기본채팅 알림
ALERT_TIERS = ((0.50, "1단계(50%)"), (0.70, "2단계(70%)"), (0.90, "3단계(90%)"))
TIER_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".d1_tier_alert_state.json")

GUARD_ENABLED = os.environ.get("D1_GUARD", "on").lower() != "off"
_cache = {"at": 0.0, "used": 0, "written": 0, "day": ""}


class QuotaExceededError(RuntimeError):
    """일일 D1 읽기 사용량이 임계값을 넘었을 때 sql() 이 던진다."""


def _analytics_daily_usage(day, tok=None):
    """GraphQL analytics 에서 계정 전체 rowsRead + rowsWritten 합계. 캐시 없음(하위 함수에서 캐시)."""
    q = """query($f: D1AdaptiveGroupsFilter_InputObject!, $acct: String!) {
      viewer { accounts(filter:{accountTag:$acct}) {
        d1AnalyticsAdaptiveGroups(limit:200, filter:$f) {
          sum { rowsRead rowsWritten } } } } }"""
    v = {"acct": ACCT, "f": {"datetime_geq": f"{day}T00:00:00Z", "datetime_lt": f"{day}T23:59:59Z"}}
    req = urllib.request.Request(
        GQ, data=json.dumps({"query": q, "variables": v}).encode(),
        headers={"Authorization": f"Bearer {tok or token()}", "Content-Type": "application/json", **UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        groups = json.loads(r.read())["data"]["viewer"]["accounts"][0]["d1AnalyticsAdaptiveGroups"]
    used = sum((g["sum"]["rowsRead"] or 0) for g in groups)
    written = sum((g["sum"]["rowsWritten"] or 0) for g in groups)
    return used, written


def _analytics_rows_read(day, tok=None):
    """호환 유지: 읽기만. 실제 조회는 _analytics_daily_usage 1회로 읽기·쓰기를 함께 본다."""
    used, _ = _analytics_daily_usage(day, tok=tok)
    return used


def get_daily_rows_read(day=None, tok=None, force=False):
    """당일(UTC) 계정 전체 D1 rowsRead. 5분 캐시 — 같은 날 반복 조회를 GraphQL 로 때리지 않는다.

    캐시가 만료되면 재조회하되, 조회가 실패하면 마지막 성공값을 그대로 쓴다
    (한도를 확인 못 하느니 작업을 계속시키는 편이 낫다 — fail-open).
    """
    day = day or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    now = time.monotonic()
    if not force and _cache["at"] and now - _cache["at"] < CACHE_TTL and _cache["day"] == day:
        return _cache["used"]
    try:
        used, written = _analytics_daily_usage(day, tok=tok)
    except Exception:
        return _cache["used"]
    _cache.update({"at": now, "used": used, "written": written, "day": day})
    return used


def get_daily_rows_written(day=None, tok=None, force=False):
    """당일(UTC) 계정 전체 D1 rowsWritten (AIK24-QUOTA-WARN-01).

    get_daily_rows_read 와 같은 조회·같은 캐시를 공유한다 — 한 번의 GraphQL 호출로
    읽기·쓰기가 함께 오므로 별도 조회 비용은 없다.
    """
    day = day or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    get_daily_rows_read(day=day, tok=tok, force=force)  # 캐시 충전
    if _cache.get("day") != day:
        return 0
    return _cache.get("written", 0)


# --- 3단계 경보 (2026-10-17 대표님 지시): muse-cli 기본채팅 -------------------

# AIK24-D1-ALERT-02: muse-cli 는 uv 툴이라 ~/.local/bin 에 심볼릭 링크로 있고
# launchd PATH(plist: /opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin)
# 에 ~/.local/bin 이 없다 → 이름만으로는 못 찾는다.
# 2026-10-18~ 실측: scripts/d1_usage_report.log 에 "No such file or directory: 'muse-cli'"
# 62건 → D1 50/70/90% 3단계 경보가 한 번도 전달되지 않았다.
MUSE_CLI_FALLBACKS = (
    os.path.expanduser("~/.local/bin/muse-cli"),
    os.path.expanduser("~/.local/share/uv/tools/muse-cli/bin/muse-cli"),
)


def muse_cli_candidates():
    """muse-cli 실행 파일 후보 목록 — PATH 검색 결과 + 알려진 절대경로.

    실패 로그에 "무엇을 찾아봤는지"를 남기기 위한 목록이기도 하다.
    """
    cands = []
    found = shutil.which("muse-cli")
    if found:
        cands.append(found)
    for p in MUSE_CLI_FALLBACKS:
        if p not in cands:
            cands.append(p)
    return cands


def muse_cli_path():
    """muse-cli 실행 파일 경로 결정. 없으면 기존처럼 이름 그대로(에러는 무시 처리)."""
    for c in muse_cli_candidates():
        if os.path.isabs(c) and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return "muse-cli"


def muse_send(text):
    """muse.ai 기본채팅(메인 말랑이)으로 전송. --thread 없이 보내는 것이 기본채팅.

    --wait 0은 ack 누락으로 실발송이 습끼지 않는 실측 사례(2026-10-17)가 있어
    --wait 15 로 바꿨다. 15초 지켜본 후 stdout에 무언가(발송 JSON)가 돌아와야 성공으로 본다.
    명령 실패·타임아웃·쿠키 만료 시 False — 이 함수가 예외를 던져 파이프라인이 죽는 일은 없어야 한다.
    """
    cands = muse_cli_candidates()
    try:
        exe = muse_cli_path()
        cp = subprocess.run(
            [exe, "send", "--wait", "15", text],
            capture_output=True, timeout=75, text=True)
        ok = cp.returncode == 0 and bool((cp.stdout or "").strip())
        if not ok:
            print(f"[D1-GUARD] muse 응답 부실(rc={cp.returncode}, exe={exe}) — "
                  f"stdout={((cp.stdout or '') + (cp.stderr or ''))[:200]!r}", flush=True)
        return ok
    except Exception as e:
        print(f"[D1-GUARD] muse 전송 실패(무시): {e} — 탐색 경로: {cands}", flush=True)
        return False


def _tier_state_load(day):
    """3단계 경보의 중복발송 방지 상태. UTC 날짜가 바뀌면 자동 리셋(한도 리셋과 동기화)."""
    try:
        with open(TIER_STATE_PATH, encoding="utf-8") as f:
            s = json.load(f)
        if s.get("day") == day:
            return s
    except (OSError, ValueError):
        pass
    keys = [str(int(t * 100)) for t, _ in ALERT_TIERS]
    return {"day": day, "read": {k: False for k in keys}, "write": {k: False for k in keys}}


def _tier_state_save(state):
    tmp = TIER_STATE_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp, TIER_STATE_PATH)
    except OSError as e:
        print(f"[D1-GUARD] 경보 상태 저장 실패(무시): {e}", flush=True)


def _tier_message(metric_korean, label, used, limit, pct, day):
    tier = label.split("(")[0]
    kst = time.strftime("%H:%M", time.gmtime(time.time() + 9 * 3600))
    head = {"1단계": "ℹ️ 관측 시작", "2단계": "⚠️ 확인 필요", "3단계": "🚨 즉시 조치"}[tier]
    extra = ""
    if metric_korean == "읽기" and tier == "2단계":
        extra = " — 진입 가드(D1_HEADROOM 70%)가 파이프라인을 차단하기 시작"
    elif metric_korean == "읽기" and tier == "3단계":
        extra = " — 80% 차단·95% readonly 작동 중. 리셋(KST 09:00) 대기 권장"
    elif metric_korean == "쓰기" and tier == "3단계":
        extra = " — 도달 시 D1 쓰기가 에러 반환. 백필·INSERT 폭주 스크립트 중단 권장"
    return (f"{head} [D1-GUARD] D1 {metric_korean} {label} 돌파: "
            f"{used:,}/{limit:,}행 ({pct:.1%}) · UTC {day} KST {kst}{extra}")


def maybe_alert_tiers(pct_read, pct_write, day=None, notify=None):
    """읽기·쓰기 각각 3단계(50/70/90%) 돌파를 판정해 muse-cli 기본채팅으로 알림.

    - 판독 기준: 계정 합산(aikorea24-db + emdash-db) — 한도가 계정 단위이기 때문.
    - UTC 날짜·임계·지표별 1회만 발송(상태 파일 dedup) → 30분 모니터가 반복 발화 못 함.
    - 발송에 '성공'했을 때만 발송됨으로 기록 — muse 장애 시 다음 주기가 재시도한다.
    - notify 를 주면 muse 대신 그 함수로 테스트한다(실측 대상 아님).
    """
    day = day or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    state = _tier_state_load(day)
    fired = []
    for metric_key, metric_name, pct, limit in (
            ("read", "읽기", pct_read, D1_READ_LIMIT),
            ("write", "쓰기", pct_write, D1_WRITE_LIMIT)):
        if pct is None or pct <= 0:
            continue
        for thr, label in ALERT_TIERS:
            key = str(int(thr * 100))
            if pct >= thr and not state[metric_key].get(key):
                msg = _tier_message(metric_name, label, int(pct * limit), limit, pct, day)
                ok = notify(msg) if notify else muse_send(msg)
                print(f"[D1-GUARD] 경보 {metric_name} {label} — "
                      f"{'muse 발송 성공' if ok else '발송 실패(다음 주기 재시도)'}", flush=True)
                if ok:
                    state[metric_key][key] = True
                fired.append((metric_key, label, ok))
    if any(ok for _, _, ok in fired):
        _tier_state_save(state)
    return fired


def check_quota(threshold=0.8, tok=None, raise_on_exceed=True):
    """일일 읽기 사용량 검사. sql() 시작점에서 호출된다.

    재귀 방지: 이 함수는 GraphQL analytics 를 직접 치지 않고 sql() 을 호출하지 않으므로
    sql() → check_quota() → sql() 순환이 생기지 않는다.
    D1_GUARD=off 환경변수로 가드를 끌 수 있다(긴급 복구용).
    """
    if not GUARD_ENABLED:
        return {"readonly": False, "used": 0, "limit": D1_READ_LIMIT, "pct": 0.0, "skipped": True}
    used = get_daily_rows_read(tok=tok)
    written = get_daily_rows_written(tok=tok)
    pct = used / D1_READ_LIMIT
    # 3단계 경보 — 파이프라인 실행 중 임계 돌파도 바로 알린다(된 경보는 상태 dedup).
    # 경보가 실패해도 이 함수의 차단 판정(read 80/95%)은 유지되어야 한다.
    try:
        maybe_alert_tiers(pct, written / D1_WRITE_LIMIT if D1_WRITE_LIMIT else 0.0)
    except Exception as e:
        print(f"[D1-GUARD] 경보 처리 실패(무시): {e}", flush=True)
    if pct >= READONLY_RATIO:
        return {"readonly": True, "used": used, "limit": D1_READ_LIMIT, "pct": pct}
    if pct >= threshold and raise_on_exceed:
        raise QuotaExceededError(
            f"[D1-GUARD] 일일 읽기 {used:,}/{D1_READ_LIMIT:,} ({pct:.1%}) — 작업 중단")
    return {"readonly": False, "used": used, "limit": D1_READ_LIMIT, "pct": pct}


def require_d1_headroom(script, threshold=None):
    """스크립트 진입부 가드. 여유가 없으면 SystemExit(3).

    왜 필요한가: check_quota() 는 cfnew.sql() 안에서만 돈다. EmDash **HTTP API** 를 때리는
    스크립트(emdash13_repair / emdash04_migrate / fix_tables)는 그 가드를 우회해서, 2026-10-14
    한도 초과 사고 때 244건 × 재시도 폭풍을 그대로 질렀다. 초과하면 D1 을 읽는 모든 경로
    (EmDash 관리자 로그인·게시물 렌더 포함)가 죽으므로, 폭주 가능성이 있는 스크립트는
    시작 전에 스스로 멈춰야 한다.

    임계 기본 0.7 (env D1_HEADROOM). 처음엔 0.5 로 뒀으나 2026-10-14 실측 baseline 이
    이미 220~270만행(한도의 44~54%)이라 평상일 후반 작업까지 막았다 — 0.7 로 올렸다.
    초과 직전에 멈추면 늦다는 건 그대로다(여유 150만행).
    조회 실패는 fail-open(_cache 마지막 값). 한도를 못 보는 것과 작업을 막는 것은 다르다.
    """
    th = D1_READ_LIMIT * (threshold if threshold is not None else float(os.environ.get("D1_HEADROOM", "0.7")))
    used = get_daily_rows_read(force=True)
    if used >= th:
        print(f"[D1-GUARD] {script} 중단 — D1 읽기 {used:,}/{D1_READ_LIMIT:,} "
              f"({used / D1_READ_LIMIT:.1%}) >= 임계 {th:,.0f}. "
              f"이대로 돌리면 계정 전체 D1 이 죽는다(자정 UTC 초기화).", flush=True)
        raise SystemExit(3)
    print(f"[D1-GUARD] D1 읽기 {used:,}/{D1_READ_LIMIT:,} ({used / D1_READ_LIMIT:.1%}) — {script} 진행", flush=True)
    return used