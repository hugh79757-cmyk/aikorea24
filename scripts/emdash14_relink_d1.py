#!/usr/bin/env python3
"""AIK24-EMDASH-04: aikorea24 D1 briefing_items 의 astro 블로그 URL → EmDash URL 교체.

Astro 저장소를 지우기 전에 브리핑의 deep_dive_url 과 코멘트에 박힌 분석 링크를
실제 글 위치인 emdash.aikorea24.kr 로 바꾼다.

사용:
    python3 scripts/emdash14_relink_d1.py            # dry — 매핑만 확인
    python3 scripts/emdash14_relink_d1.py --apply    # UPDATE 실행
"""
import argparse
import csv
import json
import os
import re
import subprocess
import tempfile
import urllib.parse

WRANGLER = "/opt/homebrew/bin/wrangler"
DB = "aikorea24-db"
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URLMAP = os.path.join(PROJECT, "docs", "emdash_url_map.csv")
CHUNK = 200  # 한 statement 에 넣을 WHEN 분기 수


def d1(sql):
    """wrangler d1 execute → results 리스트. OAuth 프로필 충돌 env 는 제거한다.

    두 가지 함정이 있어 나눠 쓴다 (둘 다 실측):
      - SELECT 은 반드시 --command. --file 로 올리면 행이 아니라 요약 통계만 나온다.
      - UPDATE 는 반드시 --file. --command 로 인자를 넘기면 exit 0 인데 rows_written=0
        으로 조용히 반영되지 않는다 (CASE WHEN 200분기 ≈ 60KB).
    """
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")}
    if sql.lstrip().upper().startswith("SELECT"):
        r = subprocess.run([WRANGLER, "d1", "execute", DB, "--remote", "--command", sql, "--json"],
                           capture_output=True, text=True, timeout=300, env=env, cwd=PROJECT)
        if r.returncode != 0:
            raise RuntimeError((r.stderr.strip() or r.stdout.strip())[:400])
        return json.loads(r.stdout)[0]["results"]
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as f:
        f.write(sql)
        path = f.name
    try:
        r = subprocess.run([WRANGLER, "d1", "execute", DB, "--remote", "--file=" + path, "--json"],
                           capture_output=True, text=True, timeout=300, env=env, cwd=PROJECT)
    finally:
        os.unlink(path)
    if r.returncode != 0:
        raise RuntimeError((r.stderr.strip() or r.stdout.strip())[:400])
    return json.loads(r.stdout[r.stdout.index("["):])[0]["results"]


def q(s):
    return "'" + s.replace("'", "''") + "'"


def load_urlmap():
    """astro_slug -> emdash_url."""
    m = {}
    with open(URLMAP, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m[r["astro_slug"]] = r["emdash_url"]
    return m


def match(pairs_dry):
    """D1 의 astro URL 목록을 슬러그로 복원해 urlmap 과 대조.

    D1 에는 원본 슬러그가, urlmap 에는 소문자화된 슬러그가 들어있는 경우가 있어
    대소문자 무시 인덱스를 쓴다 (그렇지 않으면 152건이 미매칭으로 남는다).
    """
    rows = d1("SELECT DISTINCT deep_dive_url FROM briefing_items "
              "WHERE deep_dive_url LIKE '%aikorea24.kr/blog/%'")
    urlmap = load_urlmap()
    lower = {k.lower(): v for k, v in urlmap.items()}
    hits, miss = [], []
    for r in rows:
        u = r["deep_dive_url"]
        m = re.match(r"^https://aikorea24\.kr/blog/(.+?)/?$", u)
        slug = urllib.parse.unquote(m.group(1)) if m else None
        hit = urlmap.get(slug or "") or lower.get((slug or "").lower())
        (hits if hit else miss).append((u, hit, slug))
    print("D1 astro URL %d건 — 매칭 %d / 미매칭 %d" % (len(rows), len(hits), len(miss)), flush=True)
    for _, _, slug in miss[:15]:
        print("  미매칭:", (slug or "?")[:70])
    return hits, miss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    import cfnew
    cfnew.check_quota(threshold=0.8)  # [D1-GUARD] 읽기 한도 80% 초과 시 중단

    hits, _ = match(args.apply)
    if not args.apply:
        print("(dry — --apply 시 UPDATE 실행)")
        return

    ok = fail = 0
    for i in range(0, len(hits), CHUNK):
        part = hits[i:i + CHUNK]
        # CASE WHEN 200분기(~60KB)를 --file 로 올리면 exit 0 이고 rows_written=0 으로
        # 조용히 반영되지 않는다(실측). URL 하나짜리 UPDATE 를 파일에 여러 개 이어붙여
        # 한 번에 올리는 게 확실히 동작한다.
        stmts = ["UPDATE briefing_items SET deep_dive_url=%s WHERE deep_dive_url=%s;" % (q(new), q(old))
                 for old, new, _slug in part]
        try:
            written = sum(r.get("Rows written", 0) for r in d1("\n".join(stmts)))
            ok += len(part)
            print("  deep_dive_url %d/%d (rows_written %d)" % (ok, len(hits), written), flush=True)
        except Exception as e:
            fail += len(part)
            print("  [%d/%d] 실패: %s" % (i, i + len(part), str(e)[:160]), flush=True)

    # 코멘트에 박힌 분석 링크 — astro URL 을 담은 행만 골라 UPDATE.
    # (이전 구현은 hits 전체 1,173건에 UPDATE 를 날려 wrangler 를 1,173번 띄워 30분+.
    #  실제로 astro URL 이 들어 있는 코멘트는 7건뿐이라 여기서 먼저 거른다.)
    rows = d1("SELECT id, comment FROM briefing_items WHERE comment LIKE '%aikorea24.kr/blog/%'")
    lower = {k.lower(): v for k, v in load_urlmap().items()}
    n = 0
    for r in rows:
        try:
            comment = r["comment"]
            for m in re.findall(r"https://aikorea24\.kr/blog/([^/\s\")]+)/?", comment):
                new = lower.get(urllib.parse.unquote(m).lower())
                if not new:
                    continue
                comment = comment.replace("https://aikorea24.kr/blog/%s/" % m, new)
                comment = comment.replace("https://aikorea24.kr/blog/%s" % m, new)
                n += 1
            if n:
                d1("UPDATE briefing_items SET comment=%s WHERE id=%d" % (q(comment), r["id"]))
        except Exception as e:
            print("  코멘트 실패 id=%s: %s" % (r.get("id"), str(e)[:120]))
            flush=True
    print("  코멘트 URL %d건 교체" % n)

    left = d1("SELECT COUNT(*) c FROM briefing_items WHERE deep_dive_url LIKE '%aikorea24.kr/blog/%'")[0]["c"]
    left_c = d1("SELECT COUNT(*) c FROM briefing_items WHERE comment LIKE '%aikorea24.kr/blog/%'")[0]["c"]
    print("=== deep_dive_url %d건 교체 (실패 %d) / 코멘트 %d건 시도 ===" % (ok, fail, n))
    print("=== 잔여: deep_dive_url %d, comment %d ===" % (left, left_c))


if __name__ == "__main__":
    main()