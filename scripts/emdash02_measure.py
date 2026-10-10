#!/usr/bin/env python3
"""AIK24-EMDASH-02 §3/§5 measurement helper.

Read-only unless --probe is passed (1-row INSERT test for write amplification).
Usage:
    python3 scripts/emdash02_measure.py snapshot   # analytics + sqlite_master, no writes
    python3 scripts/emdash02_measure.py delta A B  # rowsWritten delta between two snapshots
    python3 scripts/emdash02_measure.py probe      # 1-row INSERT into posts (costs ~20 rows)
"""
import json, os, sys, urllib.request, urllib.error, datetime

ACCT = "7eb1b8cd178de269758ec94b2e03330b"
EMDASH_DB = "bbbcbc34-f346-49e0-9aab-058836bee16d"
API = "https://api.cloudflare.com/client/v4"
GQ = "https://api.cloudflare.com/client/v4/graphql/analytics"
TOKEN = None
for line in open(os.path.expanduser("~/.env.common")):
    if line.startswith("CF_MIGRATE_TOKEN="):
        TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")


def rest(path, method="GET", body=None):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode()[:500]}


def analytics_written(database_id=None, day=None):
    """rowsWritten/rowsRead for the account (or one DB) for a UTC day."""
    q = """query($f: D1AdaptiveGroupsFilter_InputObject!, $acct: String!) {
      viewer { accounts(filter:{accountTag:$acct}) {
        d1AnalyticsAdaptiveGroups(limit:200, filter:$f) {
          sum { rowsWritten rowsRead } dimensions { datetimeHour databaseId } } } } }"""
    day = day or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    v = {"acct": ACCT, "f": {"datetime_geq": f"{day}T00:00:00Z", "datetime_lt": f"{day}T23:59:59Z"}}
    r = urllib.request.Request(GQ, data=json.dumps({"query": q, "variables": v}).encode(),
                               headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as resp:
        data = json.loads(resp.read())
    groups = data["data"]["viewer"]["accounts"][0]["d1AnalyticsAdaptiveGroups"]
    per_db = {}
    for g in groups:
        dims = g.get("dimensions")
        if isinstance(dims, dict):
            dims = [dims]
        for d in dims or []:
            per_db[d["databaseId"]] = per_db.get(d["databaseId"], 0) + (g["sum"]["rowsWritten"] or 0)
    return {"day": day, "total": sum(per_db.values()), "per_db": per_db,
            "rowsRead": sum((g["sum"]["rowsRead"] or 0) for g in groups)}


def query(sql, database_id=EMDASH_DB):
    return rest(f"/accounts/{ACCT}/d1/database/{database_id}/query", "POST", {"sql": sql})


def snapshot():
    out = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(), "analytics": analytics_written()}
    t = query("SELECT name,type FROM sqlite_master WHERE type IN ('table','index') ORDER BY type,name")
    rows = t.get("result", [{}])[0].get("results", []) if "result" in t else []
    tables = [r["name"] for r in rows if r["type"] == "table"]
    indexes = [r["name"] for r in rows if r["type"] == "index"]
    out["db"] = {"tables": len(tables), "indexes": len(indexes),
                 "collections": query("SELECT slug FROM _emdash_collections"),
                 "has_posts": "ec_posts" in tables, "has_pages": "ec_pages" in tables,
                 "has_tools": "ec_tools" in tables, "table_names": tables}
    out["counts"] = {}
    for tname in ("ec_posts", "ec_pages", "ec_tools"):
        if tname in tables:
            r = query(f"SELECT COUNT(*) AS c FROM {tname}")
            out["counts"][tname] = r["result"][0]["results"][0]["c"]
    try:
        req = urllib.request.Request("https://emdash.aikorea24.kr/_emdash/api/setup/status",
                                     headers={"User-Agent": "curl/8.7.1"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            out["setup"] = json.loads(resp.read()).get("data", {})
    except Exception as e:
        out["setup"] = {"error": str(e)}
    out["users"] = query("SELECT COUNT(*) AS c FROM users")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def probe():
    """Insert 1 synthetic post row directly, then read rows_written. Costs ~20 rows of quota."""
    marker = "emdash02_write_probe_" + datetime.datetime.now(datetime.timezone.utc).strftime("%H%M%S")
    before = analytics_written()["per_db"].get(EMDASH_DB, 0)
    sql = ("INSERT INTO ec_posts (id,slug,status,locale,created_at,updated_at) "
           f"VALUES ('{marker}','{marker}','draft','en','2026-10-10T00:00:00Z','2026-10-10T00:00:00Z')")
    r = query(sql)
    print(json.dumps({"insert_result": r.get("result", r), "marker": marker}, ensure_ascii=False, indent=2))
    print("rowsWritten before:", before, "(check 'after' snapshot for delta; analytics lags ~1min)")
    qd = query(f"DELETE FROM ec_posts WHERE id='{marker}'")
    print("cleanup DELETE:", json.dumps(qd.get("result", qd), ensure_ascii=False)[:300])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    if cmd == "snapshot":
        snapshot()
    elif cmd == "delta":
        print(analytics_written())
    elif cmd == "probe":
        probe()
    else:
        print(__doc__)