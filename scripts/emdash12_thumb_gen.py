#!/usr/bin/env python3
"""AIK24-THUMB-BACKFILL-01 §4.2-2: Pexels 신규 생성 12건.

기존 auto_thumbnail.process_thumbnail()을 그대로 재사용한다 (house component).
slug는 EmDash 슬러그를 그대로 쓴다 → public/images/{slug}/thumbnail.webp 생성.

사용:
    python3 scripts/emdash12_thumb_gen.py --dry
    python3 scripts/emdash12_thumb_gen.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJECT_DIR = Path(__file__).resolve().parent.parent

from auto_thumbnail import process_thumbnail, PUBLIC_IMAGES_DIR  # noqa: E402
from emdash02_measure import query as d1_query  # noqa: E402

SLUGS = [
    "정체-공개-huggingface-trending-1위-embeddinggemma-2-는-도대체-뭐냐",
    "벤치마크-비교-무료-inkling-small-vs-claude-opus-점수-차이-뭐가-남나",
    "오늘의-추천-llm-inkling-small-입출력-무료-컨텍스트-1048576",
    "이번-주-무료-llm-순위-top-5와-이번-주-추천-1개",
    "스탠퍼드-ai-보고서-2026-전문가-낙관-56퍼센트-vs-일반인-기대-10퍼센트-역대-최대-인식-격차",
    "openai의-새로운-ai-키패드-사용-후기-코더에게는-재미-일반인에게는-신비로운-이유",
    "삼성-브로드컴-2000억-달러-규모-칩-계약-체결-메모리-파운드리-고급-패키지의-미래-전망",
    "코그니션의-포크-인수-ai-개성이-경쟁-우위가-된-이유를-분석합니다",
    "제미니-메모리-개선과-스마트-홈-업데이트-자동화-구글-ai-비서의-새로운-진화를-분석합니다",
    "알파폴드-ai가-유전자-편집-단백질을-더-안전하게-재설계하는-방법과-미래-전망",
    "오푸스-5-브라우저-기반-프롬프트-인젝션-문제-해결-가능성-분석-ai-보안의-새로운-전환점",
    "오픈ai의-또-다른-안전-관련-퇴사-공개-경고와-함께-이탈-패턴-이어져-인공지능-안전의-위기",
]


def main():
    dry = "--dry" in sys.argv
    inlist = ",".join("'" + s.replace("'", "''") + "'" for s in SLUGS)
    rows = d1_query("SELECT slug, title, excerpt FROM ec_posts WHERE slug IN (%s)" % inlist)["result"][0]["results"]
    meta = {r["slug"]: r for r in rows}
    print(f"대상 {len(SLUGS)}건 (D1 조회 {len(rows)}건)\n")

    ok, fail = [], []
    for i, slug in enumerate(SLUGS, 1):
        r = meta.get(slug, {})
        text = (r.get("excerpt") or "").strip() or (r.get("title") or "").strip()
        out = PUBLIC_IMAGES_DIR / slug / "thumbnail.webp"
        if out.exists():
            print(f"[{i}/{len(SLUGS)}] 이미 존재 → skip: {slug[:50]}")
            ok.append(slug)
            continue
        print(f"[{i}/{len(SLUGS)}] {slug[:50]}")
        if dry:
            print(f"      (dry) text={text[:70]!r}")
            continue
        try:
            rel = process_thumbnail("", slug, title=r.get("title", ""), description=text)
        except Exception as e:
            print(f"      ! 예외: {type(e).__name__}: {e}")
            fail.append((slug, f"{type(e).__name__}: {e}"))
            continue
        if rel and out.exists():
            print(f"      OK {rel} ({os.path.getsize(out):,}B)")
            ok.append(slug)
        else:
            print(f"      ! 미생성 (rel={rel})")
            fail.append((slug, f"미생성 rel={rel}"))

    print(f"\n성공 {len(ok)} / 실패 {len(fail)}")
    for s, why in fail:
        print("  FAIL", s[:60], "|", why)
    if not dry and fail:
        sys.exit(1)


if __name__ == "__main__":
    main()