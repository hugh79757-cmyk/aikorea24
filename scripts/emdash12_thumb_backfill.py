#!/usr/bin/env python3
"""AIK24-THUMB-BACKFILL-01: ec_posts featured_image NULL 48건 백필.

정상 1,423건과 동일한 형태( {"provider":"external","id":"","src":...} )로
aikorea24.kr 절대 URL만 설정한다. EmDash R2 업로드 없음 — 1,423건이 이미 그
형태로 동작 중이므로 같은 패턴이 최소 위험이다.

  phase 1 (기본) : 48건 전수 조사 → CSV 생성, D1 쓰기 없음
  --apply        : NULL인 48건의 featured_image UPDATE (50건 청크)

사용:
    python3 scripts/emdash12_thumb_backfill.py
    python3 scripts/emdash12_thumb_backfill.py --apply
"""
import csv
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from emdash02_measure import query as d1_query  # noqa: E402
from emdash06_direct import lit  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = PROJECT_DIR / "public" / "images"
ORIGIN = "https://aikorea24.kr"
CHUNK = 50


def norm(slug):
    """Astro 슬러그(2026-10-08-012-제목)와 EmDash 슬러그(제목)의 정규화 비교 키."""
    s = re.sub(r"^\d{4}-\d{2}-\d{2}-\d{3}-", "", unicodedata.normalize("NFC", slug))
    return re.sub(r"[^0-9a-z가-힣]", "", s.lower())


def build_index():
    """로컬에 실제 thumbnail.webp가 있는 Astro 이미지 디렉터리 → 정규화 키 인덱스."""
    idx = {}
    for d in os.listdir(IMAGES_DIR):
        if os.path.exists(IMAGES_DIR / d / "thumbnail.webp"):
            idx.setdefault(norm(d), d)
    return idx


def head_ok(url):
    """Raw 한글 URL을 quote해 실제 200인지 확인 (브라우저가 하는 인코딩을 재현)."""
    p = urllib.parse.urlsplit(url)
    quoted = urllib.parse.urlunsplit(p._replace(path=urllib.parse.quote(p.path, safe="/%:@!$&'()*+,;=~")))
    req = urllib.request.Request(quoted, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


def featured_image_json(src):
    return json.dumps({"provider": "external", "id": "", "src": src}, ensure_ascii=False)


def main():
    apply = "--apply" in sys.argv

    rows = d1_query(
        "SELECT id, slug, status, created_at FROM ec_posts "
        "WHERE featured_image IS NULL ORDER BY created_at DESC"
    )["result"][0]["results"]
    print(f"featured_image NULL 대상: {len(rows)}건")
    if not rows:
        return

    idx = build_index()
    print(f"로컬 thumbnail.webp 보유 디렉터리: {len(idx)}개")

    plan, need_gen, skipped = [], [], []
    for r in rows:
        slug = r["slug"]
        d = idx.get(norm(slug))
        if d:
            url = f"{ORIGIN}/images/{d}/thumbnail.webp"
            if head_ok(url):
                plan.append({**r, "src": url, "source": "reuse-astro"})
            else:
                need_gen.append(r)
        else:
            need_gen.append(r)

    print(f"\nAstro 썸네일 재사용: {len(plan)}건")
    print(f"Pexels 신규 생성 필요: {len(need_gen)}건")

    # CSV 산출물 (지시서 §8)
    out = PROJECT_DIR / "docs" / "thumbnail-backfill-list.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["slug", "status", "created_at", "source", "thumbnail_url", "http_200"])
        for p in plan:
            w.writerow([p["slug"], p["status"], p["created_at"], p["source"], p["src"], "200"])
        for r in need_gen:
            w.writerow([r["slug"], r["status"], r["created_at"], "pexels-needed", "", ""])
    print(f"\nCSV: {out}")

    if need_gen:
        print("\n--- Pexels 생성 대상 ---")
        for r in need_gen:
            print("   ", r["slug"][:70])

    if not apply:
        print("\n[dry-run] D1 쓰기 없음. --apply 로 실제 반영.")
        return

    if need_gen:
        print("\n[!] Pexels 생성 건이 남아 --apply 를 중단합니다. 생성 후 재실행하세요.")
        return

    stmts = [
        "UPDATE ec_posts SET featured_image=%s WHERE id=%s;" % (lit(featured_image_json(p["src"])), lit(p["id"]))
        for p in plan
    ]
    done = 0
    for i in range(0, len(stmts), CHUNK):
        res = d1_query("\n".join(stmts[i:i + CHUNK]))
        ok = all(s.get("success", True) for s in res.get("result", []))
        if not ok:
            print(f"  ! 청크 {i//CHUNK} 실패, 중단")
            return
        done += len(stmts[i:i + CHUNK])
        print(f"  UPDATE {done}/{len(stmts)}")
    print(f"\n완료: {done}건 반영")


if __name__ == "__main__":
    main()