#!/usr/bin/env python3
"""AIK24-EMDASH-15 — featured_image 미디어 URL 전수 헬스체크 (+ 선택적 수리).

배경 (2026-10-16 실측):
  free-models 페이지 og:image 가 404 였다. 원인은 EmDash 미디어 URL 규칙 —
  `/_emdash/api/media/file/<X>.<ext>` 의 <X> 는 **media.id 가 아니라 storage_key** 다.
  media.id 로 만든 URL 2건(`free-models`, `nvidianemotron-3-ultra-550b-a55bfree`)만
  404 였고, media 테이블의 storage_key 로 바꾼 URL 은 즉시 200 이 됐다 (storage_key
  형식으로 이미 쓰여 있던 17건은 그때도 200 = 정상). 즉 사람/도구가 업로드 응답의
  id 를 그대로 URL 에 넣으면 **조용히 404** 가 되고, og:image·목록 썸네일만 깨진다.

이 스크립트가 하는 일:
  1. ec_posts.featured_image 중 `/_emdash/api/media/file/` 를 쓰는 URL 을 전부 모아 HTTP 상태 측정
  2. 404 인 URL 은 그 키가 media.id 인지 조회해 storage_key 로 만든 대체 URL 을 제시하고, 대체 URL 도 200 인지 재측정
  3. --apply 면 수리 가능한 건만 D1 UPDATE (백업 파일 먼저 기록)

사용:
  python3 scripts/emdash15_media_url_health.py           # 탐지·보고만 (D1 쓰기 없음)
  python3 scripts/emdash15_media_url_health.py --apply    # 수리 가능한 건 교체
종료 코드: 0 = 이상 없음(또는 --apply 로 전부 수리됨) / 1 = 미수리 이상 잔존
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 쿼리스트링(?v=2 등)이 붙어도 키를 뽑도록 끝을 고정하지 않는다 (2026-10-16).
MEDIA_URL_RE = re.compile(r"/_emdash/api/media/file/([A-Za-z0-9]+)\.(webp|png|jpe?g|gif|avif)", re.IGNORECASE)
TIMEOUT = 20


def extract_key(url):
    """미디어 URL → 키(파일명 포함). 미디어 URL 이 아니면 None."""
    m = MEDIA_URL_RE.search((url or "").strip())
    return m.group(0).rsplit("/", 1)[-1] if m else None


def base_url(url):
    """미디어 URL → 접두부 (…/_emdash/api/media/file/). 아니면 빈 문자열."""
    u = (url or "").strip()
    idx = u.find("/_emdash/api/media/file/")
    return u[: idx + len("/_emdash/api/media/file/")] if idx >= 0 else ""


def fixed_src(url, storage_key):
    """storage_key 기반으로 바꾼 URL. storage_key 가 비면 None."""
    pre = base_url(url)
    if not pre or not storage_key:
        return None
    return pre + str(storage_key).strip()


def classify(status, storage_key, fixed_status=None):
    """측정 결과 분류 — 'ok' | 'fixable' | 'broken'."""
    if status == "200":
        return "ok"
    if storage_key and fixed_status == "200":
        return "fixable"
    return "broken"


def probe(url):
    """curl 로 HTTP 상태 코드만 측정 (urllib 은 이 엔드포인트에서 403 을 받는다)."""
    try:
        out = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(TIMEOUT), url],
            capture_output=True, text=True, timeout=TIMEOUT + 10,
        )
        return (out.stdout or "").strip() or "ERR"
    except Exception:  # noqa: BLE001 — 네트워크 실패도 '이상'으로 보고한다
        return "ERR"


def _lit(s):
    return "'" + str(s).replace("'", "''") + "'"


def _rows(resp):
    if not isinstance(resp, dict):
        return []
    result = resp.get("result") or []
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return result[0].get("results", []) or []
    return []


def main():
    ap = argparse.ArgumentParser(description="EmDash featured_image 미디어 URL 헬스체크")
    ap.add_argument("--apply", action="store_true", help="수리 가능한 건 D1 UPDATE")
    args = ap.parse_args()

    for line in open(os.path.expanduser("~/.env.common"), encoding="utf-8"):
        k = line.split("=", 1)[0]
        if k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
            os.environ[k] = line.split("=", 1)[1].strip().strip('"')

    from emdash02_measure import query  # noqa: E402 — env 로드 후 import

    posts = _rows(query("SELECT slug, featured_image FROM ec_posts "
                        "WHERE featured_image LIKE '%/_emdash/api/media/file/%';"))
    print(f"[1/4] 미디어 URL 을 쓰는 글: {len(posts)}건")

    url_to_slugs = {}
    for p in posts:
        try:
            src = json.loads(p.get("featured_image") or "{}").get("src") or ""
        except Exception:  # noqa: BLE001
            src = ""
        key = extract_key(src)
        if key:
            url_to_slugs.setdefault(src, []).append(p.get("slug"))
    print(f"      고유 URL: {len(url_to_slugs)}개")

    print("[2/4] HTTP 상태 측정 …")
    results = []
    for url, slugs in url_to_slugs.items():
        code = probe(url)
        results.append({"url": url, "status": code, "slugs": slugs})
    bad = [r for r in results if r["status"] != "200"]
    print(f"      200: {len(results) - len(bad)} / 이상: {len(bad)}")

    print("[3/4] 이상 URL 의 storage_key 대체안 조회 …")
    plan, unfixed = [], []
    for r in bad:
        key = (r["url"] or "").rsplit("/", 1)[-1]
        media_id = key.split(".")[0]
        rows = _rows(query("SELECT id, storage_key, filename FROM media WHERE id = %s;" % _lit(media_id)))
        storage_key = rows[0].get("storage_key") if rows else None
        cand = fixed_src(r["url"], storage_key)
        fixed_status = probe(cand) if cand else None
        verdict = classify(r["status"], storage_key, fixed_status)
        entry = {**r, "media_id": media_id, "storage_key": storage_key,
                 "fixed_url": cand, "fixed_status": fixed_status, "verdict": verdict}
        if verdict == "fixable":
            plan.append(entry)
            print(f"      ⚠️ {r['status']} → 수리 가능: {key} → {cand.rsplit('/', 1)[-1]} ({fixed_status})")
        else:
            unfixed.append(entry)
            print(f"      ❌ {r['status']} → 수리 불가: {key} (media 행: {'있음' if rows else '없음'}, "
                  f"대체 URL: {fixed_status or '없음'})")

    applied = 0
    if plan and args.apply:
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup = "/tmp/emdash15-media-url-backup-%s.json" % stamp
        with open(backup, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        print(f"[4/4] --apply: {len(plan)}건 교체 (백업 {backup})")
        stmts = []
        for e in plan:
            val = json.dumps({"provider": "external", "id": "", "src": e["fixed_url"]}, ensure_ascii=False)
            stmts.append("UPDATE ec_posts SET featured_image=%s WHERE slug=%s;"
                         % (_lit(val), _lit(e["slugs"][0])))
        resp = query("\n".join(stmts))
        ok = isinstance(resp, dict) and resp.get("success")
        print(f"      ok={ok}")
        if ok:
            for e in plan:
                new_code = probe(e["fixed_url"])
                print(f"      검증 {new_code}  {e['slugs'][0]}")
                if new_code == "200":
                    applied += 1
            unfixed.extend([{**e, "verdict": "broken"} for e in plan if probe(e["fixed_url"]) != "200"])
    else:
        print("[4/4] 쓰기 없음 (--apply 미지정)" if plan else "[4/4] 수리 대상 없음")

    remaining = [u for u in unfixed if u["verdict"] == "broken"]
    print(f"\n요약: 이상 {len(bad)} / 수리 가능 {len(plan)} / 실제 수리 {applied} / 잔존 {len(remaining)}")
    for u in remaining:
        print(f"  잔존: {u['status']}  {u['url']}  slugs={','.join(str(s) for s in u['slugs'])}")
    return 0 if not remaining else 1


if __name__ == "__main__":
    sys.exit(main())
