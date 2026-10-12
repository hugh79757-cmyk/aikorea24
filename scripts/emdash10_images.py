#!/usr/bin/env python3
"""AIK24-EMDASH-10 — ec_posts.featured_image 를 emdash MediaValue + 절대 URL 로 정규화.

배경: emdash.aikorea24.kr 은 /images/ 를 서빙하지 않는다(404). 원본 aikorea24.kr 이
서빙하므로 src 를 https://aikorea24.kr 로 절대화한다(지시서 B안).

저장 형태가 2종 섞여 있다:
  - '{"provider":"external","id":"","src":"/images/..."}'  (EMDASH-04 API 경로)
  - '/images/...'                                          (D1 SQL 경로, JSON 아님)
둘 다 {provider:"external", id:"", src:"https://aikorea24.kr/..."} 로 통일한다.

사용: python3 scripts/emdash10_images.py [--dry]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emdash02_measure import query  # noqa: E402

ORIGIN = os.environ.get("IMG_ORIGIN", "https://aikorea24.kr")
CHUNK = 50


def lit(s):
    return "'" + s.replace("'", "''") + "'"


def desired(current):
    """저장된 값 -> 목표 MediaValue JSON 문자열. 이미目标이면 None."""
    raw = (current or "").strip()
    if not raw:
        return None
    src = None
    if raw.startswith("{"):
        try:
            src = json.loads(raw).get("src")
        except Exception:
            return None
    else:
        src = raw  # 원본 경로 문자열
    if not src:
        return None
    if src.startswith("/") and not src.startswith("//"):
        src = ORIGIN + src
    elif not src.startswith("http"):
        return None  # 예상 못한 형태 — 건드리지 않음
    out = json.dumps({"provider": "external", "id": "", "src": src}, ensure_ascii=False)
    return None if out == raw else out


def main():
    dry = "--dry" in sys.argv
    rows = query("SELECT id, featured_image FROM ec_posts WHERE featured_image IS NOT NULL") \
        .get("result", [{}])[0].get("results", [])
    print("featured_image 보유 행: %d" % len(rows))

    stmts, skipped = [], 0
    for r in rows:
        new = desired(r["featured_image"])
        if new is None:
            skipped += 1
            continue
        stmts.append("UPDATE ec_posts SET featured_image=%s WHERE id=%s;" % (lit(new), lit(r["id"])))

    print("변경 대상 %d건 / 미변경·제외 %d건" % (len(stmts), skipped))
    if dry:
        for s in stmts[:3]:
            print("  ", s[:140])
        return

    done = 0
    for i in range(0, len(stmts), CHUNK):
        chunk = "\n".join(stmts[i:i + CHUNK])
        res = query(chunk)
        if not res.get("success"):
            print("  ! 청크 %d 실패: %s" % (i // CHUNK, json.dumps(res, ensure_ascii=False)[:200]))
            continue
        done += i + CHUNK if i + CHUNK > len(stmts) else CHUNK
        done = min(done, len(stmts))
        print("  %d/%d" % (done, len(stmts)), flush=True)
    print("UPDATE 전송 완료")


if __name__ == "__main__":
    main()