#!/usr/bin/env python3
"""AIK24-EMDASH-02 §4-4 — Astro ↔ EmDash URL 매핑 테이블 생성 (301 리다이렉트 준비용).

src/content/blog/*.md (Astro URL) 와 EmDash published 글 (https://emdash.aikorea24.kr/posts/<slug>)
을 제목 기준으로 1:1 매칭해 CSV 로.dump 한다.

사용:
    EMDASH_AIKOREA24_API_TOKEN=... python3 scripts/emdash02_urlmap.py
출력:
    docs/emdash_url_map.csv   (astro_slug, astro_url, emdash_slug, emdash_url, title)
301 리다이렉트 설정은 별도 지시서 범위 — 여기서는 테이블만 만든다.
"""
import csv
import glob
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml  # noqa: E402

BLOG = os.path.join(ROOT, "src", "content", "blog")
OUT = os.path.join(ROOT, "docs", "emdash_url_map.csv")
BASE = os.environ.get("EMDASH_BASE", "https://emdash.aikorea24.kr").rstrip("/")
ASTRO_BASE = "https://aikorea24.kr/blog"


def emdash_posts():
    """published 포스트 전체 수집 (커서 페이지네이션)."""
    pat = (os.environ.get("EMDASH_AIKOREA24_API_TOKEN")
           or os.environ.get("EMDASH_PAT") or "").strip().strip('"').strip("'")
    if not pat:
        sys.exit("EMDASH_AIKOREA24_API_TOKEN 환경변수 필요")
    out, cursor = {}, None
    for _ in range(300):
        path = "/_emdash/api/content/posts?limit=100&orderBy=createdAt&order=desc"
        if cursor:
            path += "&cursor=" + urllib.parse.quote(cursor)
        req = urllib.request.Request(BASE + path)
        req.add_header("Authorization", "Bearer " + pat)
        req.add_header("User-Agent", "curl/8.7.1")
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read() or b"{}").get("data") or {}
        for it in data.get("items", []):
            t = (it.get("data") or {}).get("title") or it.get("title")
            if t:
                out.setdefault(t, it)
        cursor = (data.get("nextCursor") or data.get("cursor")
                  or (data.get("pagination") or {}).get("nextCursor"))
        if not cursor:
            break
    return out


def astro_posts():
    rows = []
    for p in sorted(glob.glob(os.path.join(BLOG, "*.md"))):
        txt = open(p, encoding="utf-8").read()
        if not txt.startswith("---"):
            continue
        _, fm, _body = txt.split("---", 2)
        meta = yaml.safe_load(fm) or {}
        rows.append((os.path.basename(p)[:-3], (meta.get("title") or "").strip()))
    return rows


def _norm(t):
    """문장부호만 다른 제목(쉼표/콜론)을 같은 글로 보기 위한 정규화 키."""
    return re.sub(r"[^\w가-힣]", "", (t or "").lower())


def main():
    em = emdash_posts()
    # 과거 실행본이 쉼표/콜론을 조금 다르게 저장한 것이 있어 정규화 키로 보조 매칭한다
    fuzzy = {}
    for t, it in em.items():
        fuzzy.setdefault(_norm(t), it)
    ast = astro_posts()
    print("Astro %d건 / EmDash %d건" % (len(ast), len(em)))
    matched = fuzzy_hit = missing = 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["astro_slug", "astro_url", "emdash_slug", "emdash_url", "title"])
        for slug, title in ast:
            it = em.get(title) or fuzzy.get(_norm(title))
            if it is None:
                missing += 1
                w.writerow([slug, "%s/%s/" % (ASTRO_BASE, slug.lower()), "", "", title])
                print("  미매칭:", title[:70])
                continue
            if title not in em:
                fuzzy_hit += 1
                print("  ⚠ 제목 불일치(정규화 매칭): %s  ≠  %s"
                      % (title[:45], ((it.get("data") or {}).get("title") or "")[:45]))
            matched += 1
            es = it.get("slug") or ""
            w.writerow([slug, "%s/%s/" % (ASTRO_BASE, slug.lower()), es,
                        "%s/posts/%s" % (BASE, es), title])
    print("매칭 %d건 (정규화 보조매칭 %d건) / 미매칭 %d건 → %s"
          % (matched, fuzzy_hit, missing, OUT))
    return 0 if missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())