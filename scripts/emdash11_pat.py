"""AIK24-EMDASH-11: emDash PAT 회전 (발급 → 검증 → 기존 폐기 → 파일 저장).

토큰 평문은 stdout/로그/파일에 남기지 않는다. 최종 산출물은 /tmp/aik24-pat.txt (0600) 뿐.
기존 행 폐기는 신규 토큰 MCP 검증 성공 뒤에만 수행한다.
"""
import base64
import hashlib
import json
import os
import secrets
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emdash02_measure as M
from emdash06_direct import ulid

PREFIX = "ec_pat_"
NAME = "muse-agent-2026-10-10"
OLD_ID = "01M4HKX4HAARE21HN4C3HSJANG"  # name='aikorea24', prefix=ec_pat_6ONI
OUT = "/tmp/aik24-pat.txt"
ORIGIN = "https://emdash.aikorea24.kr"

SCOPES = [
    "content:read", "content:write", "media:read", "media:write",
    "schema:read", "schema:write", "taxonomies:manage",
    "menus:manage", "settings:read", "settings:manage",
    "mcp:tools", "admin",
]
USER_ID = "01M4HKV7ZCNZZ11DN43Q5J4WCT"  # info@aikorea24.kr


def rows(resp):
    if isinstance(resp, dict):
        v = resp.get("results")
        if isinstance(v, list):
            yield from v
            return
        for k in ("result", "results"):
            if k in resp:
                yield from rows(resp[k])
    elif isinstance(resp, list):
        for x in resp:
            yield from rows(x)


def q1(sql):
    out = list(rows(M.query(sql)))
    return out[0] if out else None


def lit(v):
    return "'" + str(v).replace("'", "''") + "'"


def mint():
    raw = PREFIX + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    h = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest()).decode().rstrip("=")
    return raw, h, raw[: len(PREFIX) + 4]


def mcp_init(raw):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}).encode()
    req = urllib.request.Request(
        ORIGIN + "/_emdash/api/mcp", data=body, method="POST",
        headers={
            "Authorization": "Bearer " + raw,
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "X-EmDash-Request": "1",
            "Origin": ORIGIN,
            "Accept": "application/json, text/event-stream",
        })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read(600).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(400).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, repr(e)[:300]


def main():
    before = q1("SELECT COUNT(*) c FROM _emdash_api_tokens")
    print(f"[1] 기존 토큰 행 수 = {before['c']}")

    raw, h, pfx = mint()
    nid = ulid()
    M.query(
        "INSERT INTO _emdash_api_tokens (id,name,token_hash,prefix,user_id,scopes,expires_at) "
        f"VALUES ({lit(nid)},{lit(NAME)},{lit(h)},{lit(pfx)},{lit(USER_ID)},{lit(json.dumps(SCOPES))},NULL);")
    print(f"[2] 신규 토큰 INSERT 완료 — id={nid} prefix={pfx} (평문 미출력)")

    st, txt = mcp_init(raw)
    print(f"[3] MCP initialize → HTTP {st} · body[:200]={txt[:200]!r}")
    if st != 200:
        M.query(f"DELETE FROM _emdash_api_tokens WHERE id={lit(nid)};")
        print("[3] 검증 실패 → 신규 행 롤백, 기존 토큰 유지")
        return 1

    ch = q1(f"SELECT COUNT(*) c FROM _emdash_api_tokens WHERE id={lit(OLD_ID)}")
    M.query(f"DELETE FROM _emdash_api_tokens WHERE id={lit(OLD_ID)};")
    print(f"[4] 기존 토큰 폐기 — 삭제 대상 존재 여부 was {ch['c']}")

    after = q1("SELECT id,name,prefix,user_id,expires_at FROM _emdash_api_tokens")
    print(f"[5] 잔여 토큰 = {list(rows(after))}")

    fd = os.open(OUT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(raw + "\n")
    print(f"[6] 토큰 저장 → {OUT} (mode 0600, {os.stat(OUT).st_size} bytes)")
    print("[7] 대표님: 해당 파일을 Secure Vault에 등록 후 '확인' 지시 → /tmp 파일 삭제 예정")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())