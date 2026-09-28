#!/usr/bin/env python3
"""빈 url 툴 백필 — Product Hunt post 페이지의 websiteUrl 추출.

원인: scripts/tools_collector.py validate_tool_url()이 '?ref=producthunt' 포함
URL을 거부 → build_frontmatter()가 빈 url로 폴백. (별도 커밋으로 수정됨)

이 스크립트는 md frontmatter `url: ""` 건에 대해 Product Hunt post 페이지
(슬러그 = md 파일명)에서 websiteUrl을 읽어 md에 기록한다.

사용:
  python3 scripts/backfill_tool_urls_0928.py          # dry-run (해석만, JSON 저장)
  python3 scripts/backfill_tool_urls_0928.py --apply  # md에 실제 기록
"""
import glob
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO, "src", "content", "tools")
CACHE = "/tmp/tool_url_backfill_0928.json"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def slug_of(fp):
    return os.path.basename(fp)[:-3]


def empty_url_files():
    out = []
    for fp in sorted(glob.glob(os.path.join(TOOLS_DIR, "*.md"))):
        txt = open(fp, encoding="utf-8").read()
        if re.search(r'^url: ""\s*$', txt, re.M):
            out.append(fp)
    return out


def ph_website(slug, tries=3):
    """Product Hunt post 페이지에서 websiteUrl 추출. 실패 시 (None, reason)."""
    url = f"https://www.producthunt.com/posts/{slug}"
    last = None
    for i in range(tries):
        try:
            r = subprocess.run(
                ["curl", "-sSL", "--max-time", "20", "-A", UA,
                 "-H", "Accept-Language: en-US,en;q=0.9", url],
                capture_output=True, text=True, timeout=40)
            if r.returncode != 0:
                last = f"curl:{r.returncode}"
            elif not r.stdout:
                last = "empty"
            else:
                m = re.search(r'"websiteUrl":"(https?://[^"]+)"', r.stdout)
                if m:
                    return m.group(1).strip(), None
                # 404 page (no product JSON)
                last = "no-websiteUrl"
                break
        except subprocess.TimeoutExpired:
            last = "timeout"
        time.sleep(1.5 * (i + 1))
    return None, last


def url_alive(u, tries=2):
    for i in range(tries):
        r = subprocess.run(
            ["curl", "-sSL", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", "20", "-A", UA, u],
            capture_output=True, text=True, timeout=40)
        code = (r.stdout or "").strip()
        if code.startswith(("2", "3")):
            return True, code
        time.sleep(1.0 * (i + 1))
    return False, code


def main():
    apply = "--apply" in sys.argv
    files = empty_url_files()
    print(f"[backfill] empty url md: {len(files)}", flush=True)

    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE))

    results = {}
    for fp in files:
        slug = slug_of(fp)
        if slug in cache:
            results[slug] = cache[slug]
            continue
        site, reason = ph_website(slug)
        entry = {"path": fp, "ph_url": site, "reason": reason}
        if site:
            ok, code = url_alive(site)
            entry["alive"] = ok
            entry["code"] = code
        results[slug] = entry
        print(f"  {slug:55s} {site or '--':60s} {reason or ('alive' if entry.get('alive') else 'dead')}", flush=True)
        json.dump(results, open(CACHE, "w"), ensure_ascii=False, indent=1)
        time.sleep(1.2)

    resolved = {k: v for k, v in results.items() if v.get("ph_url")}
    alive = {k: v for k, v in resolved.items() if v.get("alive")}
    print(f"\n[backfill] resolved {len(resolved)}/{len(files)}  alive {len(alive)}", flush=True)
    print(f"[backfill] cache: {CACHE}", flush=True)

    if not apply:
        print("[backfill] DRY-RUN. rerun with --apply to write md.", flush=True)
        return

    written = 0
    for slug, v in sorted(alive.items()):
        fp = v["path"]
        txt = open(fp, encoding="utf-8").read()
        new = re.sub(r'^url: ""\s*$', f'url: "{v["ph_url"]}"', txt, count=1, flags=re.M)
        if new != txt:
            open(fp, "w", encoding="utf-8").write(new)
            written += 1
    print(f"[backfill] APPLIED to {written} files", flush=True)


if __name__ == "__main__":
    main()
