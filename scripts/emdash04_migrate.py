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
# D1-03: N+1 완화 — 기존 제목 조회 페이지 크기 확대(기본 100 → 500) 및 로컬 캐시
EXISTING_TITLES_LIMIT = int(os.environ.get("EXISTING_TITLES_LIMIT", "500"))
EXISTING_TITLES_CACHE = "/tmp/emdash_existing_titles.json"
EXISTING_TITLES_CACHE_TTL = int(os.environ.get("EXISTING_TITLES_CACHE_TTL", "3600"))  # 1시간
UTC = datetime.timezone.utc

# ---------- markdown -> Portable Text (node_modules/emdash/dist/portable-text-*.mjs 재현) ----------

INLINE = re.compile(r"(\*\*(.+?)\*\*)|(_(.+?)_)|(`(.+?)`)|(\[(.+?)\]\((.+?)\))|(~~(.+?)~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
UNORDERED = re.compile(r"^(\s*)[-*+]\s+(.+)$")
ORDERED = re.compile(r"^(\s*)\d+\.\s+(.+)$")
IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
OPAQUE = re.compile(r"^<!--ec:block (.+) -->$")

# bare URL 자동링크 (2026-10-29 SK 글 실측: _spans가 마크다운 링크만 처리해
# 본문 bare URL이 평문 span으로 남아 클릭이 안 되고 URL이 그대로 노출됐다)
BARE_URL = re.compile(r"https?://[A-Za-z0-9\-._~:/?#@!$&'()*+,;=%]+")
REF_LINE = re.compile(r"^(?P<title>.+?)\s+[–—-]\s*(?P<url>https?://\S+)\s*$")
_URL_STRIP = ".,;:!?\"'“”‘’「」『』"


def _ref_title(t):
    """참고 자료형 제목 정리: 끝의 [태그]·(원문) 제거 (순서 무관하게 반복)."""
    prev = None
    while prev != t:
        prev = t
        t = re.sub(r"\s*\[[^\]]*\]\s*$", "", t)
        t = re.sub(r"\s*\(원문\)\s*$", "", t)
    return t.strip()


def _plain_spans(chunk, defs):
    """평문 구간 내 bare URL을 링크 span으로 쪼갠다.

    마크다운 링크는 INLINE이 이미 소비했으므로 여긴 순수 평문만 온다.
    URL 끝 문장부호(.,;:!?·따옴표)는 링크 밖으로 빼고, 닫는 괄호는
    균형이 맞을 때만(위키식 URL) 링크 안에 둔다.
    """
    out, pos = [], 0
    for um in BARE_URL.finditer(chunk):
        url = um.group(0)
        tail = ""
        while url and url[-1] in _URL_STRIP:
            tail = url[-1] + tail
            url = url[:-1]
        if url.endswith(")") and url.count("(") < url.count(")"):
            tail = ")" + tail
            url = url[:-1]
        if um.start() > pos:
            out.append({"_type": "span", "_key": k(), "text": chunk[pos:um.start()], "marks": []})
        if url:
            kk = k()
            defs.append({"_key": kk, "_type": "link", "href": url})
            out.append({"_type": "span", "_key": k(), "text": url, "marks": [kk]})
        if tail:
            out.append({"_type": "span", "_key": k(), "text": tail, "marks": []})
        pos = um.end()
    if pos < len(chunk):
        out.append({"_type": "span", "_key": k(), "text": chunk[pos:], "marks": []})
    return out or [{"_type": "span", "_key": k(), "text": "", "marks": []}]

_ctr = 0


def k():
    global _ctr
    s = "k%x" % _ctr
    _ctr += 1
    return s


def _spans(text):
    # 참고 자료형 한 줄: "제목 – URL" → 제목만 링크로 (URL 원문 노출 제거).
    # 제목 안에 마크다운 링크가 있으면 REF 규칙을 건너뛰고 아래 INLINE 경로로 간다.
    rm = REF_LINE.match(text.strip())
    if rm and not re.search(r"\[[^\]]*\]\(", rm.group("title")):
        title = _ref_title(rm.group("title"))
        url = rm.group("url").rstrip(".,;:!?\"'")
        kk = k()
        return ([{"_type": "span", "_key": k(), "text": title, "marks": [kk]}],
                [{"_key": kk, "_type": "link", "href": url}])
    spans, defs, pos = [], [], 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            spans.extend(_plain_spans(text[pos:m.start()], defs))
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
        spans.extend(_plain_spans(text[pos:], defs))
    return (spans or [{"_type": "span", "_key": k(), "text": "", "marks": []}]), defs


def _block(text, style):
    children, mark_defs = _spans(text)
    return {"_type": "block", "_key": k(), "style": style, "markDefs": mark_defs, "children": children}


def _li(text, list_item, level):
    children, mark_defs = _spans(text)
    return {"_type": "block", "_key": k(), "style": "normal", "listItem": list_item,
            "level": level, "markDefs": mark_defs, "children": children}


# ---------- 마크다운 표 -> EmDash table 블록 (AIK24-EMDASH-09) ----------
# 파싱 로직은 AIK24-EMDASH-06 의 scripts/fix_tables.py 를 그대로 가져왔다.
# 저장소만 다를 뿐 같은 알고리즘이므로 중복 구현 대신 같은 판단을 쓴다.

DELIM_CELL = re.compile(r"^:?-{3,}:?$")


def _split_row(text):
    """`| a | b |` → ['a', 'b']. 파이프 행이 아니면 None."""
    t = text.strip()
    if "|" not in t:
        return None
    if t.startswith("|"):
        t = t[1:]
    if t.endswith("|"):
        t = t[:-1]
    cells = [c.strip() for c in t.split("|")]
    return cells or None


def _is_delim(cells):
    return bool(cells) and all(DELIM_CELL.match(c.replace(" ", "")) for c in cells)


def _align(c):
    """구분선 셀 → 열 정렬 (`:---:`→center, `---:`→right, `:---`→left)."""
    c = c.replace(" ", "")
    if c.startswith(":") and c.endswith(":"):
        return "center"
    if c.endswith(":"):
        return "right"
    if c.startswith(":"):
        return "left"
    return None


def _cell(text, is_header, align):
    children, mark_defs = _spans(text)
    c = {"_type": "tableCell", "_key": k(), "content": children, "isHeader": is_header}
    if align:
        c["textAlign"] = align
    if mark_defs:
        c["markDefs"] = mark_defs
    return c


def _table(rows, aligns):
    """헤더행(rows[0]) + 데이터행 → table 블록 1개."""
    width = max(len(r) for r in rows)
    trows = []
    for idx, r in enumerate(rows):
        header = idx == 0
        trows.append({"_type": "tableRow", "_key": k(),
                      "cells": [_cell(r[c] if c < len(r) else "", header,
                                      aligns[c] if c < len(aligns) else None)
                                for c in range(width)]})
    return {"_type": "table", "_key": k(), "rows": trows, "hasHeaderRow": True}


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
        # 표: 헤더행 + 구분선행이 같이 있어야 인정한다. `GitHub | Pages | Vercel` 같은
        # 구분선 없는 파이프 나열은 그대로 일반 문단이다 (AIK24-EMDASH-06 원칙).
        row = _split_row(line)
        delim = _split_row(lines[i + 1]) if i + 1 < len(lines) else None
        if row and delim and _is_delim(delim):
            aligns = [_align(c) for c in delim]
            rows = [row]
            i += 2
            while i < len(lines):
                nxt = _split_row(lines[i])
                if not nxt:
                    break
                rows.append(nxt)
                i += 1
            blocks.append(_table(rows, aligns))
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
    """이미 이관된 (title -> (id, status)) 수집 (재개용). 캐시 지원으로 N+1 완화."""
    import os
    import time
    cache_path = EXISTING_TITLES_CACHE
    # 캐시 유효성 검사
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                cached = json.load(f)
            if time.time() - cached.get("ts", 0) < EXISTING_TITLES_CACHE_TTL:
                print(f"  [캐시] 기존 제목 {len(cached['data'])}건 로드 (age={int(time.time()-cached['ts'])}s)")
                return cached["data"]
        except Exception:
            pass

    seen = {}
    cursor = None
    page_limit = EXISTING_TITLES_LIMIT
    max_pages = max(1, (1500 + page_limit - 1) // page_limit)  # 최대 예상 건수 기준 페이지 수
    for page_num in range(max_pages):
        path = f"/_emdash/api/content/posts?limit={page_limit}&orderBy=createdAt&order=desc"
        if cursor:
            path += "&cursor=" + urllib.parse.quote(cursor)
        st, d = api(path)
        if st != 200:
            print("  ! existing 조회 실패 http=%s" % st)
            break
        data = d.get("data") or {}
        items = data.get("items", [])
        if not items:
            break
        for it in items:
            t = (it.get("data") or {}).get("title") or it.get("title")
            if t:
                seen[t] = (it.get("id"), it.get("status"))
        cursor = data.get("nextCursor") or data.get("cursor") or (data.get("pagination") or {}).get("nextCursor")
        if not cursor:
            break
        if len(items) < page_limit:
            break

    # 캐시 저장
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "data": seen}, f, ensure_ascii=False)
    except Exception:
        pass
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

    # 2026-10-14 사고 후속: existing_titles() 가 ?limit=100 을 최대 300회 돌며 1,479건 본문을
    # hydrate 한다. D1 한도를 태우면 EmDash 관리자 로그인까지 죽는다 → 시작 전에 스스로 멈춘다.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import cfnew
    cfnew.require_d1_headroom("emdash04_migrate")

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