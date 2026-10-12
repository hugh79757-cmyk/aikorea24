#!/usr/bin/env python3
"""AIK24-EMDASH-08 Day2-3 — chronicle/glossary 컬렉션 신설 + 필드 생성.

Worker write 경로는 10ms CPU 한도 때문에 연속 쓰기 시 1102 발생 → 호출당 긴 백오프.
PAT는 환경변수 EMDASH_PAT 로만 주입 (파일 기록 금지).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("EMDASH_BASE", "https://emdash.aikorea24.kr")

COLLECTIONS = [
    ("chronicle", "Chronicles", [
        ("title", "Title", "string", True),
        ("date", "Date", "datetime", False),
        ("category", "Category", "string", False),
        ("summary", "Summary", "text", False),
    ]),
    ("glossary", "Glossary", [
        ("title", "Term", "string", True),
        ("en", "English", "string", False),
        ("category", "Category", "string", False),
        ("level", "Level", "string", False),
        ("summary", "Summary", "text", False),
        ("body", "Detail", "portableText", False),
    ]),
]


def api(path, method="GET", body=None, tries=6, wait=25):
    for a in range(tries):
        req = urllib.request.Request(BASE + path, method=method)
        req.add_header("Authorization", "Bearer " + os.environ["EMDASH_PAT"])
        req.add_header("User-Agent", "curl/8.7.1")
        req.add_header("X-EmDash-Request", "1")
        req.add_header("Origin", BASE)
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode()
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, data, timeout=120) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                j = json.loads(raw or b"{}")
            except Exception:
                j = {"raw": raw[:200].decode("utf8", "replace")}
            st = e.code
        except Exception as e:
            st, j = 0, {"e": str(e)}
        if st not in (503, 0) and not (st == 400 and "already" in json.dumps(j)):
            return st, j
        print("   retry %d/%d http=%s %s" % (a + 1, tries, st, json.dumps(j)[:80]), flush=True)
        time.sleep(wait)
    return st, j


def main():
    ok = fail = 0
    for slug, label, fields in COLLECTIONS:
        if len(sys.argv) > 1 and sys.argv[1] != slug:
            continue
        st, d = api("/_emdash/api/schema/collections/" + slug)
        if st == 404:
            st, d = api("/_emdash/api/schema/collections", "POST",
                        {"slug": slug, "label": label, "supports": ["drafts", "search"],
                         "routable": True, "hasSeo": False, "editLocking": False})
        if st in (200, 201):
            print("[+] collection %s (http=%d)" % (slug, st), flush=True)
            ok += 1
        elif st == 409 or "exist" in json.dumps(d):
            print("[=] collection %s 이미 존재" % slug, flush=True)
            ok += 1
        else:
            print("[-] collection %s 실패 http=%d %s" % (slug, st, json.dumps(d)[:200]), flush=True)
            fail += 1
            continue

        st, d = api("/_emdash/api/schema/collections/%s/fields" % slug)
        have = {f.get("slug") for f in ((d.get("data") or {}).get("fields") or [])}
        for i, (fs, fl, ft, req) in enumerate(fields):
            if fs in have:
                print("    = %s.%s 이미 존재" % (slug, fs), flush=True)
                continue
            st, d = api("/_emdash/api/schema/collections/%s/fields" % slug, "POST",
                        {"slug": fs, "label": fl, "type": ft, "required": req,
                         "sortOrder": i, "searchable": True, "translatable": True})
            if st in (200, 201):
                print("    + %s.%s (%s)" % (slug, fs, ft), flush=True)
                ok += 1
            else:
                print("    [-] %s.%s http=%d %s" % (slug, fs, st, json.dumps(d)[:160]), flush=True)
                fail += 1
    print("=== ok=%d fail=%d ===" % (ok, fail), flush=True)


if __name__ == "__main__":
    main()