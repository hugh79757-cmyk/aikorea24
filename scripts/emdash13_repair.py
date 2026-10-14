#!/usr/bin/env python3
"""AIK24-EMDASH-04: EmDash 이관 결함 일괄 수리.

고치는 것 (전부 EmDash API 경유, revisions 정합성 유지):
  1. 본문 잔존 구분선 `---` 블록 제거
  2. 상대경로 이미지 `/images/...` -> https://aikorea24.kr/images/... (본문 + featured_image)
  3. 본문 내 aikorea24.kr/blog/{slug}/ 링크 -> emdash.aikorea24.kr/posts/{slug} (docs/emdash_url_map.csv)
  4. 마크다운 링크 리터럴 `[text](url)` 잔여 제거

쓰지 않는 것: EmDash D1 직접 UPDATE (revisions 정합성 깨짐 확인됨).

사용:
    EMDASH_PAT=... python3 scripts/emdash13_repair.py [--dry] [--limit N]
"""
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("EMDASH_BASE", "https://emdash.aikorea24.kr").rstrip("/")
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = "/tmp/emdash_audit.json"
URLMAP = os.path.join(PROJECT, "docs", "emdash_url_map.csv")
SITE = "https://aikorea24.kr"
MD_LINK = re.compile(r"\[[^\]]{0,80}\]\((https?://[^)]{1,200})\)")


def pat():
    return os.environ["EMDASH_PAT"]


def _headers(extra=None):
    h = {"Authorization": "Bearer " + pat(), "User-Agent": "curl/8.7.1",
         "X-EmDash-Request": "1", "Origin": BASE, "Content-Type": "application/json"}
    h.update(extra or {})
    return h


def rest(method, path, body=None, tries=3):
    """REST 호출. 5xx/네트워크 오류는 지수 백오프로 재시도, 최종 실패면 (status, body)."""
    for n in range(tries):
        req = urllib.request.Request(BASE + path,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     method=method, headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            code, txt = e.code, e.read().decode()[:200]
            if code >= 500 or code == 429:
                time.sleep(5 * (n + 1))
                continue
            return code, txt
        except Exception as e:  # 네트워크 일시 오류 — 재시도 대상
            if n == tries - 1:
                return 0, str(e)[:120]
            time.sleep(5 * (n + 1))
    return 0, "retries exhausted"


def mcp(tool, args, tries=4):
    """MCP tools/call. content_get 는 _rev 토큰을 발급한다 (PUT 필수)."""
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": tool, "arguments": args}}
    req = urllib.request.Request(BASE + "/_emdash/api/mcp", data=json.dumps(body).encode(),
                                 method="POST",
                                 headers=_headers({"Accept": "application/json, text/event-stream"}))
    last = None
    for n in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode()
            m = re.search(r"data: (.*)", raw)
            if m:  # SSE 파싱 실패도 재시도 대상 (throttle 시 빈 응답이 온다)
                return json.loads(m.group(1))
            last = RuntimeError("no SSE data frame: %s" % raw[:120])
        except Exception as e:
            last = e
        time.sleep(5 * (n + 1))
    raise last


def get_item(item_id):
    """(_rev, data, status, has_draft) 반환."""
    res = mcp("content_get", {"collection": "posts", "id": item_id})
    obj = json.loads(res["result"]["content"][0]["text"])
    item = obj["item"] if "item" in obj else obj
    return (obj.get("_rev") or item.get("_rev"), item.get("data") or {},
            item.get("status"), bool(item.get("draftRevisionId")))


def load_urlmap():
    """astro_slug -> emdash_url."""
    m = {}
    with open(URLMAP, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m[r["astro_url"].rstrip("/").split("/blog/")[-1]] = r["emdash_url"]
    return m


def blocks_text(block):
    return "".join(c.get("text", "") for c in block.get("children", []) or [])


def transform(data, urlmap):
    """data 를 복제해 고친다. (수정 여부, 로그) 반환."""
    out = json.loads(json.dumps(data, ensure_ascii=False))
    log = {"dash": 0, "img": 0, "link": 0, "md": 0}

    # 1) 구분선 블록 제거 — 본문 첫 줄에 붙은 프론트매터 닫는 '---'
    keep = []
    for b in out.get("content") or []:
        if b.get("style") == "normal" and blocks_text(b).strip() == "---":
            log["dash"] += 1
            continue
        keep.append(b)
    out["content"] = keep

    def fix_url(u):
        """상대 이미지 경로 -> 절대. astro 블로그 링크 -> emdash."""
        if not isinstance(u, str) or not u:
            return u, False
        if u.startswith("/images/"):
            return SITE + u, True
        m = re.match(r"https?://aikorea24\.kr/blog/([^/?#]+)/?$", u)
        if m:
            target = urlmap.get(m.group(1))
            if target:
                return target, True
        return u, False

    def walk(node):
        if isinstance(node, dict):
            if node.get("_type") == "image":
                asset = node.get("asset")
                if isinstance(asset, dict):
                    new, ch = fix_url(asset.get("url"))
                    if ch:
                        asset["url"] = new
                        log["img"] += 1
            for key in ("url", "href"):
                if key in node:
                    new, ch = fix_url(node.get(key))
                    if ch:
                        node[key] = new
                        if new.startswith("http"):
                            log["link"] += 1
            # 4) 마크다운 링크 리터럴 — 렌더에、文章 그대로 노출된다
            for child in node.get("children") or []:
                t = child.get("text")
                if isinstance(t, str) and MD_LINK.search(t):
                    child["text"] = MD_LINK.sub(lambda m: m.group(1), t)
                    log["md"] += 1
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(out.get("content") or [])

    # featured_image
    fi = out.get("featured_image")
    if isinstance(fi, dict) and isinstance(fi.get("src"), str) and fi["src"].startswith("/images/"):
        fi["src"] = SITE + fi["src"]
        log["img"] += 1
    return out, log


def needs_fix(data, urlmap):
    return any(transform(data, urlmap)[1].values())


def main():
    dry = "--dry" in sys.argv
    limit = 0
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    urlmap = load_urlmap()
    items = json.load(open(CACHE, encoding="utf-8"))
    os.environ["EMDASH_PAT"] = os.environ.get(
        "EMDASH_PAT", os.environ.get("EMDASH_AIKOREA24_API_TOKEN", ""))
    items = [it for it in items if needs_fix(it.get("data") or {}, urlmap)]
    if limit:
        items = items[:limit]
    print("수정 대상 %d건 (dry=%s)" % (len(items), dry), flush=True)
    if dry:
        return

    tally = {"dash": 0, "img": 0, "link": 0, "md": 0}
    done = fail = skip = 0
    for n, it in enumerate(items, 1):
        pid = it["id"]
        try:
            rev, data, status, draft = get_item(pid)
            # 이전 실행이 남긴 draft 가 있으면 먼저 publish — 안 그러면 fix 가 live 에 반영 안 됨
            if draft:
                rest("POST", "/_emdash/api/content/posts/%s/publish" % pid, {})
            new, log = transform(data, urlmap)
            if not any(log.values()):
                skip += 1
                continue
            st, body = rest("PUT", "/_emdash/api/content/posts/" + pid,
                            {"collection": "posts", "id": pid, "data": new, "_rev": rev})
            if st not in (200, 201):
                print("  [%d/%d] PUT 실패 %s %s" % (n, len(items), st, str(body)[:110]), flush=True)
                fail += 1
                continue
            # PUT 은 draft revision 을 만든다 — status 가 published 여도 publish 필수
            st2, b2 = rest("POST", "/_emdash/api/content/posts/%s/publish" % pid, {})
            if st2 not in (200, 201):
                print("  [%d/%d] publish 실패 %s %s" % (n, len(items), st2, str(b2)[:110]), flush=True)
                fail += 1
                continue
            for k in tally:
                tally[k] += log[k]
            done += 1
            if done % 25 == 0 or log["dash"] or log["link"]:
                print("  [%d/%d] 완료 %d (---:%d img:%d link:%d md:%d)"
                      % (n, len(items), done, log["dash"], log["img"], log["link"], log["md"]), flush=True)
        except Exception as e:
            print("  [%d/%d] 예외 %s" % (n, len(items), str(e)[:110]), flush=True)
            fail += 1
        time.sleep(2.0)  # EmDash 인스턴스가 503/1102 로 쓰러지지 않게 넉넉히
    print("=== 수정 %d / 무변경 %d / 실패 %d ===" % (done, skip, fail))
    print("누적 제거·치환:", tally, flush=True)


if __name__ == "__main__":
    main()