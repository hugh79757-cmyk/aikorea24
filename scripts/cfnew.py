#!/usr/bin/env python3
"""Shared CF helper for AIK24-EMDASH-02 (new account 7eb1b8cd...)."""
import datetime, json, os, time, urllib.request, urllib.error

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
READONLY_RATIO = 0.95
CACHE_TTL = 300  # 5분 — 매 sql() 마다 GraphQL 을 때리면 레이트리밋에 걸린다

GUARD_ENABLED = os.environ.get("D1_GUARD", "on").lower() != "off"
_cache = {"at": 0.0, "used": 0, "day": ""}


class QuotaExceededError(RuntimeError):
    """일일 D1 읽기 사용량이 임계값을 넘었을 때 sql() 이 던진다."""


def _analytics_rows_read(day, tok=None):
    """GraphQL analytics 에서 계정 전체 rowsRead 합계. 캐시 없음(하위 함수에서 캐시)."""
    q = """query($f: D1AdaptiveGroupsFilter_InputObject!, $acct: String!) {
      viewer { accounts(filter:{accountTag:$acct}) {
        d1AnalyticsAdaptiveGroups(limit:200, filter:$f) {
          sum { rowsRead } } } } }"""
    v = {"acct": ACCT, "f": {"datetime_geq": f"{day}T00:00:00Z", "datetime_lt": f"{day}T23:59:59Z"}}
    req = urllib.request.Request(
        GQ, data=json.dumps({"query": q, "variables": v}).encode(),
        headers={"Authorization": f"Bearer {tok or token()}", "Content-Type": "application/json", **UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        groups = json.loads(r.read())["data"]["viewer"]["accounts"][0]["d1AnalyticsAdaptiveGroups"]
    return sum((g["sum"]["rowsRead"] or 0) for g in groups)


def get_daily_rows_read(day=None, tok=None, force=False):
    """당일(UTC) 계정 전체 D1 rowsRead. 5분 캐시 — 같은 날 반복 조회를 GraphQL 로 때리지 않는다.

    캐시가 만료되면 재조회하되, 조회가 실패하면 마지막 성공값을 그대로 쓴다
    (한도를 확인 못 하느니 작업을 계속시키는 편이 낫다 — ponytail: fail-open).
    """
    day = day or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    now = time.monotonic()
    if not force and _cache["at"] and now - _cache["at"] < CACHE_TTL and _cache["day"] == day:
        return _cache["used"]
    try:
        used = _analytics_rows_read(day, tok=tok)
    except Exception:
        return _cache["used"]
    _cache.update({"at": now, "used": used, "day": day})
    return used


def check_quota(threshold=0.8, tok=None, raise_on_exceed=True):
    """일일 읽기 사용량 검사. sql() 시작점에서 호출된다.

    재귀 방지: 이 함수는 GraphQL analytics 를 직접 치지 않고 sql() 을 호출하지 않으므로
    sql() → check_quota() → sql() 순환이 생기지 않는다.
    D1_GUARD=off 환경변수로 가드를 끌 수 있다(긴급 복구용).
    """
    if not GUARD_ENABLED:
        return {"readonly": False, "used": 0, "limit": D1_READ_LIMIT, "pct": 0.0, "skipped": True}
    used = get_daily_rows_read(tok=tok)
    pct = used / D1_READ_LIMIT
    if pct >= READONLY_RATIO:
        return {"readonly": True, "used": used, "limit": D1_READ_LIMIT, "pct": pct}
    if pct >= threshold and raise_on_exceed:
        raise QuotaExceededError(
            f"[D1-GUARD] 일일 읽기 {used:,}/{D1_READ_LIMIT:,} ({pct:.1%}) — 작업 중단")
    return {"readonly": False, "used": used, "limit": D1_READ_LIMIT, "pct": pct}