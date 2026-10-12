#!/usr/bin/env python3
"""AIK24-EMDASH-04 Phase2 Day1 — src/content/blog 최신 500건 -> emDash ec_posts.

PAT는 환경변수 EMDASH_PAT 로만 주입 (파일 기록 금지).
사용: EMDASH_PAT=... LIMIT=500 python3 scripts/emdash04_migrate.py [--dry]
"""
import datetime
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import yaml

BASE = os.environ.get("EMDASH_BASE", "https://emdash.aikorea24.kr")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOG = os.path.join(ROOT, "src", "content", "blog")
LIMIT = int(os.environ.get("LIMIT", "500"))
SKIP = int(os.environ.get("SKIP", "0"))
BATCH = int(os.environ.get("BATCH", "50"))
BATCH_SLEEP = float(os.environ.get("BATCH_SLEEP", "5"))
UTC = datetime.timezone.utc

# ---------- markdown -> Portable Text (node_modules/emdash/dist/portable-text-*.mjs 재현) ----------

INLINE = re.compile(r"(\*\*(.+?)\*\*)|(_(.+?)_)|(`(.+?)`)|(\[(.+?)\]\((.+?)\))|(~~(.+?)~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
UNORDERED = re.compile(r"^(\s*)[-*+]\s+(.+)$")
ORDERED = re.compile(r"^(\s*)\d+\.\s+(.+)$")
IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
OPAQUE = re.compile(r"^<!--ec:block (.+) -->$")

_ctr = 0


def k():
    global _ctr
    s = "k%x" % _ctr
    _ctr += 1
    return s


def _spans(text):
    spans, defs, pos = [], [], 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            spans.append({"_type": "span", "_key": k(), "text": text[pos:m.start()], "marks": []})
        if m.group(2) is not None:
            spans.append({"_type": "span", "_key": k(), "text": m.group(2), "marks": ["strong"]})
        elif m.group(4) is not None:
            spans.append({"_type": "span", "_key": k(), "text": m.group(4), "marks": ["em"]})
        elif m.group(6) is not None:
            spans.append({"_type": "span", "_key": k(), "text": m.group(6), "marks": ["code"]})
        elif m.group(8) is not None:
            kk = k()
            defs.append({"_key": kk, "_type": "link", "href": m.group(9)})
            spans.append({"_type": "span", "_key": k(), "text": m.group(8), "marks": [kk]})
        else:
            spans.append({"_type": "span", "_key": k(), "text": m.group(11), "marks": ["strike-through"]})
        pos = m.end()
    if pos < len(text):
        spans.append({"_type": "span", "_key": k(), "text": text[pos:], "marks": []})
    return (spans or [{"_type": "span", "_key": k(), "text": "", "marks": []}]), defs


def _block(text, style):
    children, mark_defs = _spans(text)
    return {"_type": "block", "_key": k(), "style": style, "markDefs": mark_defs, "children": children}


def _li(text, list_item, level):
    children, mark_defs = _spans(text)
    return {"_type": "block", "_key": k(), "style": "normal", "listItem": list_item,
            "level": level, "markDefs": mark_defs, "children": children}


def md_to_pt(md):
    global _ctr
    _ctr = 0
    lines, blocks, i = md.split("\n"), [], 0
    while i < len(lines):
        line = lines[i]
        m = OPAQUE.match(line)
        if m:
            try:
                blocks.append(json.loads(m.group(1)))
            except Exception:
                blocks.append(_block(line, "normal"))
            i += 1
            continue
        if line.startswith("```"):
            lang = line[3:].strip()
            i += 1
            code = []
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            b = {"_type": "code", "_key": k(), "code": "\n".join(code)}
            if lang:
                b["language"] = lang
            blocks.append(b)
            continue
        if line.strip() == "":
            i += 1
            continue
        m = HEADING.match(line)
        if m:
            blocks.append(_block(m.group(2), "h%d" % len(m.group(1))))
            i += 1
            continue
        if line.startswith("> "):
            blocks.append(_block(line[2:], "blockquote"))
            i += 1
            continue
        m = UNORDERED.match(line)
        if m:
            blocks.append(_li(m.group(2), "bullet", len(m.group(1)) // 2 + 1))
            i += 1
            continue
        m = ORDERED.match(line)
        if m:
            blocks.append(_li(m.group(2), "number", len(m.group(1)) // 2 + 1))
            i += 1
            continue
        m = IMAGE.match(line)
        if m:
            blocks.append({"_type": "image", "_key": k(), "alt": m.group(1), "asset": {"url": m.group(2)}})
            i += 1
            continue
        blocks.append(_block(line, "normal"))
        i += 1
    return blocks


# ---------- emDash REST ----------

RETRY = int(os.environ.get("RETRY", "5"))  # DNS/timeout 등 일시 장애 재시도 횟수


def api(path, method="GET", body=None):
    """일시적 네트워크 장애는 재시도. 4xx 응답은 재시도하지 않음."""
    last = (0, {"error": "not attempted"})
    for attempt in range(RETRY + 1):
        try:
            st, d = _api_once(path, method, body)
            if st >= 500 or st == 0:
                last = (st, d)
                if attempt < RETRY:
                    time.sleep(min(2 ** attempt, 30))
                    continue
            return st, d
        except Exception as e:
            last = (0, {"error": repr(e)})
            if attempt < RETRY:
                time.sleep(min(2 ** attempt, 30))
    return last


def _api_once(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Authorization", "Bearer " + os.environ["EMDASH_PAT"])
    req.add_header("User-Agent", "curl/8.7.1")
    if method in ("POST", "PUT", "DELETE", "PATCH"):
        req.add_header("X-EmDash-Request", "1")
        req.add_header("Origin", BASE)
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data, timeout=90) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"{}")
        except Exception:
            return e.code, {"raw": raw.decode("utf-8", "replace")[:300]}
    except Exception as e:
        return 0, {"error": str(e)}


# ---------- 소스 로드 ----------

def _dt(v):
    if isinstance(v, str):
        try:
            v = datetime.datetime.fromisoformat(v)
        except Exception:
            v = datetime.datetime.min
    if not isinstance(v, datetime.datetime):
        v = datetime.datetime.min
    return v.replace(tzinfo=UTC) if v.tzinfo is None else v.astimezone(UTC)


def load_posts():
    posts = []
    for p in glob.glob(os.path.join(BLOG, "*.md")):
        txt = open(p, encoding="utf-8").read()
        if not txt.startswith("---"):
            continue
        _, fm, body = txt.split("---", 2)
        m = yaml.safe_load(fm) or {}
        posts.append({"date": _dt(m.get("date")), "meta": m, "body": body.lstrip("\n"),
                      "path": os.path.basename(p)})
    posts.sort(key=lambda r: r["date"], reverse=True)
    return posts[SKIP:SKIP + LIMIT]


def ensure_terms(posts):
    """taxonomy term 선행 생성. 반환: {label: slug}"""
    wanted = []
    for p in posts:
        c = p["meta"].get("category")
        if c and str(c) not in wanted:
            wanted.append(str(c))
    st, d = api("/_emdash/api/taxonomies/category/terms?limit=200")
    existing = {}
    data = d.get("data") if isinstance(d, dict) else None
    for t in (data or {}).get("terms", []) if isinstance(data, dict) else []:
        existing[t.get("label")] = t.get("slug")
    out = {}
    for label in wanted:
        if existing.get(label):
            out[label] = existing[label]
            continue
        st, d = api("/_emdash/api/taxonomies/category/terms", "POST", {"label": label})
        item = (d.get("data") or {}).get("term") if st == 201 else None
        if item:
            out[label] = item.get("slug")
            print("  + term %r -> %s" % (label, item.get("slug")))
        else:
            print("  ! term 실패 %r http=%s %s" % (label, st, json.dumps(d, ensure_ascii=False)[:200]))
    return out


def existing_titles():
    """이미 이관된 (title -> (id, status)) 수집 (재개용)."""
    seen = {}
    cursor = None
    for _ in range(300):
        path = "/_emdash/api/content/posts?limit=100&orderBy=createdAt&order=desc"
        if cursor:
            path += "&cursor=" + urllib.parse.quote(cursor)
        st, d = api(path)
        if st != 200:
            print("  ! existing 조회 실패 http=%s" % st)
            break
        data = d.get("data") or {}
        for it in data.get("items", []):
            t = (it.get("data") or {}).get("title") or it.get("title")
            if t:
                seen[t] = (it.get("id"), it.get("status"))
        cursor = data.get("nextCursor") or data.get("cursor") or (data.get("pagination") or {}).get("nextCursor")
        if not cursor:
            break
    return seen


def main():
    dry = "--dry" in sys.argv
    posts = load_posts()
    print("소스 %d건 로드 (최신 %s ~ 최-old %s)" % (
        len(posts), posts[0]["date"].isoformat(), posts[-1]["date"].isoformat()))
    cats = {}
    for p in posts:
        c = p["meta"].get("category")
        if c:
            cats[str(c)] = cats.get(str(c), 0) + 1
    print("category 분포:", cats)
    if dry:
        b = md_to_pt(posts[0]["body"])
        print("PT 블록 %d개, head=%s" % (len(b), json.dumps(b[0], ensure_ascii=False)[:300]))
        return

    terms = ensure_terms(posts)
    print("terms:", terms)

    done = existing_titles()
    if done:
        print("이미 이관됨 %d건 (건너뜀)" % len(done))
    todo = [p for p in posts if p["meta"].get("title") not in done]
    print("처리 대상 %d건" % len(todo))

    ok = fail = repub = 0
    errors = []
    for idx, p in enumerate(todo, 1):
        m = p["meta"]
        prior = done.get(m.get("title"))
        if prior and prior[0] and prior[1] != "published":
            # 이전 시도에서 create만 성공하고 publish 실패 → publish 재시도
            st2, d2 = api("/_emdash/api/content/posts/%s/publish" % prior[0], "POST",
                          {"publishedAt": p["date"].isoformat()})
            if st2 in (200, 201):
                repub += 1
            else:
                fail += 1
                errors.append((p["path"], "republish", st2, json.dumps(d2, ensure_ascii=False)[:300]))
            continue
        data = {"title": m.get("title"), "excerpt": m.get("description"),
                "content": md_to_pt(p["body"])}
        if m.get("image"):
            data["featured_image"] = str(m["image"])
        body = {"data": data}
        c = m.get("category")
        if c and str(c) in terms:
            body["taxonomies"] = {"category": [terms[str(c)]]}
        st, d = api("/_emdash/api/content/posts", "POST", body)
        if st != 201:
            fail += 1
            errors.append((p["path"], "create", st, json.dumps(d, ensure_ascii=False)[:300]))
            continue
        item = (d.get("data") or {}).get("item") or {}
        pid = item.get("id")
        st2, d2 = api("/_emdash/api/content/posts/%s/publish" % pid, "POST",
                      {"publishedAt": p["date"].isoformat()})
        if st2 not in (200, 201):
            fail += 1
            errors.append((p["path"], "publish", st2, json.dumps(d2, ensure_ascii=False)[:300]))
            continue
        ok += 1
        if idx % 10 == 0 or idx == 1:
            print("  [%d/%d] ok=%d fail=%d %s" % (idx, len(todo), ok, fail, p["path"][:50]), flush=True)
        if idx % BATCH == 0 and idx != len(todo):
            time.sleep(BATCH_SLEEP)

    print("=== create+publish ok=%d republish=%d fail=%d ===" % (ok, repub, fail))
    for e in errors[:20]:
        print("ERR", e)


if __name__ == "__main__":
    main()