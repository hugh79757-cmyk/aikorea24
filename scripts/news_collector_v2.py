#!/usr/bin/env python3
"""aikorea24 뉴스 수집기 v2 (AIK24-PIPE-02 Step 2)

기획브리프 §4 기준 소스 체계:
  - 무료 LLM   : OpenRouter free models API
  - 오픈소스   : HuggingFace trending API + HF blog RSS
  - 실용       : (Product Hunt·r/LocalLLaMA 는 RSS 403/이므로 v2.1 로 보류)
  - 빅테크 공식: (AIK24-NEWS-01 에서 수집 중단 — OpenAI/Google/GitHub RSS 3종제거)

설계 메모:
  - 계정을 코드에 명시한다. 기존 api_test/news_collector.py 는 `npx wrangler d1 execute`
    를 계정 미지정으로 호출해 BRIEF-01 잔존 위험 2(쓰기 대상 계정 불일치)가 열려 있다.
    이 수집기는 D1 REST SQL + scripts/cfnew.py 의 CF_MIGRATE_TOKEN(신규 계정 7eb1b8cd)만 쓴다.
  - 수집 결과는 기존 `news` 테이블에 넣는다. 하위 파이프라인(auto_news_selector →
    auto_briefing → auto_email_sender)은 손대지 않는다.

사용:
  python3 scripts/news_collector_v2.py --dry-run     # 수집만, D1 미쓰기
  python3 scripts/news_collector_v2.py               # 수집 + D1 INSERT
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfnew  # noqa: E402  (ACCT / A24_DB / token / sql)
import v2_filter as v2f  # noqa: E402  (AIK24-NEWS-01 v2 판정)

UA = {"User-Agent": "curl/8.7.1", "Accept": "*/*"}
NOW = datetime.now(timezone.utc)

# --- v2 소스 정의 -----------------------------------------------------------
OPENROUTER_API = "https://openrouter.ai/api/v1/models"
HF_TRENDING_API = "https://huggingface.co/api/models?sort=trendingScore&limit=15"

RSS_SOURCES = [
    # AIK24-NEWS-01: OpenAI News / Google AI Blog / GitHub AI/ML Blog 3종 수집 중단.
    # 레거시 수집기(26개 매체)와 중복되고, v2 페이지에서 기업 뉴스 덤프로만 드러났음.
    # HuggingFace Blog 는 유지(오픈소스 태그 판정 대상).
    ("HuggingFace Blog", "https://huggingface.co/blog/feed.xml", "us"),
]

# v2.1 보류: 2026-10-10 실측 응답 코드
#   https://www.reddit.com/r/LocalLLaMA/.rss        → 403 (bot 차단)
#   https://www.anthropic.com/news/rss.xml          → 404 (RSS 미제공)
#   https://opencode.ai/feed.xml                    → 404 (RSS 미제공)
DEFERRED_SOURCES = [
    ("r/LocalLLaMA", "https://www.reddit.com/r/LocalLLaMA/.rss"),
    ("Anthropic News", "https://www.anthropic.com/news/rss.xml"),
    ("OpenCode Zen", "https://opencode.ai/feed.xml"),
    ("Product Hunt free tier", "인증 필요 — v2.1"),
]


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _pub_date(offset_hours=0):
    """news.pub_date 는 'YYYY-MM-DD HH:MM:SS' 문자열 (auto_news_selector 가 이 포맷을 파싱)."""
    return (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=offset_hours)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def collect_openrouter_free():
    """무료 LLM 목록 — 지시서 §18 일간/주간 블로그의 1차 데이터 소스."""
    data = json.loads(fetch(OPENROUTER_API))
    models = data.get("data", [])
    out = []
    for m in models:
        p = m.get("pricing", {}) or {}
        if str(p.get("prompt")) != "0" or str(p.get("completion")) != "0":
            continue  # 완전 무료(입출력 모두 0원)만
        mid = m.get("id", "")
        ctx = m.get("context_length") or 0
        out.append(
            {
                "title": f"[무료 LLM] {mid} — OpenRouter 무료 티어",
                "link": f"https://openrouter.ai/{mid.replace('/', '/').split(':')[0]}",
                "description": (
                    f"OpenRouter에서 입출력 모두 무료인 모델. 컨텍스트 {ctx:,} 토큰. "
                    f"지금 바로 무료로 써볼 수 있다."
                ),
                "source": "OpenRouter Free Models",
                "category": "AI",
                "pub_date": _pub_date(),
                "source_url": OPENROUTER_API,
                "original_title": mid,
                "country": "us",
            }
        )
    return out


def collect_hf_trending():
    data = json.loads(fetch(HF_TRENDING_API))
    out = []
    for m in data:
        mid = m.get("id") or m.get("modelId") or ""
        if not mid:
            continue
        likes = m.get("likes") or 0
        dl = m.get("downloads") or 0
        pipeline = m.get("pipeline_tag") or "-"
        out.append(
            {
                "title": f"[무료 모델] {mid} — HuggingFace trending",
                "link": f"https://huggingface.co/{mid}",
                "description": (
                    f"트렌딩 상위 오픈소스 모델. task={pipeline}, 좋아요 {likes:,}, 다운로드 {dl:,}."
                    f" 라이선스 확인 후 무료로 로컬 실행 가능."
                ),
                "source": "HuggingFace Trending",
                "category": "AI",
                "pub_date": _pub_date(),
                "source_url": "https://huggingface.co/models?sort=trending",
                "original_title": mid,
                "country": "us",
            }
        )
    return out


def _text(el):
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def collect_rss():
    out = []
    for name, url, country in RSS_SOURCES:
        try:
            raw = fetch(url)
            root = ET.fromstring(raw)
        except Exception as e:  # noqa: BLE001 — 소스 1개 실패가 전체를 막지 않게
            print(f"  [warn] {name}: {e}")
            continue
        items = root.findall(".//item")[:10]
        for it in items:
            title = _text(it.find("title"))
            link = _text(it.find("link"))
            if not title or not link:
                continue
            desc = _text(it.find("description"))[:400]
            pub = _text(it.find("pubDate"))
            out.append(
                {
                    "title": title,
                    "link": link,
                    "description": desc,
                    "source": name,
                    "category": "AI",
                    "pub_date": _pub_date(),
                    "source_url": url,
                    "original_title": title,
                    "country": country,
                    "_rss_pub": pub,
                }
            )
    return out


def collect_all():
    rows = []
    for fn, label in (
        (collect_openrouter_free, "OpenRouter free models"),
        (collect_hf_trending, "HuggingFace trending"),
        (collect_rss, "RSS (HuggingFace Blog) — AIK24-NEWS-01"),
    ):
        try:
            got = fn()
            rows.extend(got)
            print(f"  {label}: {len(got)}건")
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] {label} 실패: {e}")
    return rows


def save(rows):
    """신규 계정 D1 로만 쓴다 (cfnew.sql → REST API, account pinned)."""
    existing = set()
    r = cfnew.sql(
        "SELECT link FROM news ORDER BY id DESC LIMIT 3000;", database_id=cfnew.A24_DB
    )
    if isinstance(r, list):
        for row in r:
            if isinstance(row, dict) and row.get("link"):
                existing.add(row["link"])

    def lit(v):
        return "'" + str(v or "").replace("'", "''")[:500] + "'"

    stmts, skipped = [], 0
    for a in rows:
        if a["link"] in existing:
            skipped += 1
            continue
        # AIK24-NEWS-01: v2 판정(무료 사용 가능 여부 + 태그)을 저장 시점에 계산해 함께 기록.
        v2_pass, v2_tag = v2f.classify(
            a["title"], a.get("description", ""), a.get("source", "")
        )
        a["_v2"] = (1 if v2_pass else 0, v2_tag)
        stmts.append(
            "INSERT OR IGNORE INTO news "
            "(title, link, description, source, category, pub_date, source_url, original_title, country, v2_pass, v2_tag) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);"
            % (
                lit(a["title"][:200]), lit(a["link"]), lit(a.get("description", "")),
                lit(a["source"]), lit(a.get("category", "AI")), lit(a["pub_date"]),
                lit(a.get("source_url", "")), lit(a.get("original_title", "")), lit(a.get("country", "us")),
                a["_v2"][0], lit(a["_v2"][1]),
            )
        )
    if not stmts:
        print(f"  신규 없음 (건너뜀 {skipped}건)")
        return 0
    BATCH = 40
    saved = 0
    for i in range(0, len(stmts), BATCH):
        res = cfnew.sql(";\n".join(stmts[i : i + BATCH]), database_id=cfnew.A24_DB)
        saved += len(stmts[i : i + BATCH])
        print(f"  배치 {i // BATCH + 1}: {len(stmts[i : i + BATCH])}건 전송 (ok={isinstance(res, list)})")
    return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="수집만 하고 D1 미쓰기")
    a = ap.parse_args()

    print(f"aikorea24 뉴스 수집기 v2 (AIK24-PIPE-02) — account={cfnew.ACCT[:8]}…")
    rows = collect_all()
    by_src = {}
    for r in rows:
        by_src[r["source"]] = by_src.get(r["source"], 0) + 1
    print(f"  합계 {len(rows)}건 / 소스 {len(by_src)}개: {by_src}")
    print("  v2.1 보류 소스:")
    for n, u in DEFERRED_SOURCES:
        print(f"    - {n}: {u}")

    if a.dry_run:
        print("\n[DRY-RUN] D1 미쓰기")
        for r in rows[:5]:
            print(f"    - [{r['source']}] {r['title'][:70]}")
        return

    n = save(rows)
    print(f"\nD1 저장: {n}건 (건너뜀 포함)")
    v = cfnew.sql(
        "SELECT COUNT(*) c, MAX(created_at) mx FROM news WHERE source LIKE '%OpenRouter%' "
        "OR source LIKE '%HuggingFace%' OR source IN ('OpenAI News','Google AI Blog','HuggingFace Blog','GitHub AI/ML Blog');",
        database_id=cfnew.A24_DB,
    )
    print(f"  v2 소스 누적: {v}")


if __name__ == "__main__":
    main()