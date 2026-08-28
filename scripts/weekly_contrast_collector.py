#!/usr/bin/env python3
"""
S0: 주간 기사 풀 수집 — 지난 7일간 D1 뉴스 테이블에서 모든 기사 수집.

출력: list[dict] with keys: id, title, description, source, pub_date, link
body는 이 단계에서 포함하지 않음 (S1에서 클러스터 선별 후 필요 시 크롤링).
description 신뢰도 검증: title과 description의 임베딩 유사도 < 0.7이면 플래그.
"""

import os
import sys
import math
from datetime import datetime, timedelta

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)

from pipeline.infra.d1_client import d1_query
from pipeline.infra.logger import get_scrubbed_logger

logger = get_scrubbed_logger(__name__)

# description 신뢰도 임계값
DESCRIPTION_SIMILARITY_THRESHOLD = 0.7


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """코사인 유사도 계산 (표준 라이브러리 only)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _check_description_reliability(article: dict) -> dict:
    """
    description이 원문 제목과 의미적으로 유사한지 임베딩 유사도로 검증.

    Returns:
        article with 'description_reliable' field added (True/False/None)
        None = 임베딩 호출 실패 (신뢰할 수 없으므로 보수적 처리)
    """
    title = article.get("title", "")
    desc = article.get("description", "")

    # description 없으면 검증 불가 → reliable=None (보수적: 사용함)
    if not desc or not desc.strip():
        article["description_reliable"] = None
        return article

    # title도 없으면 검증 불가
    if not title or not title.strip():
        article["description_reliable"] = None
        return article

    try:
        from pipeline.infra.vectorize_client import get_embedding
        title_emb = get_embedding(title)
        desc_emb = get_embedding(desc)

        if title_emb is None or desc_emb is None:
            article["description_reliable"] = None
            return article

        sim = _cosine_similarity(title_emb, desc_emb)
        article["description_reliable"] = sim >= DESCRIPTION_SIMILARITY_THRESHOLD
        article["description_similarity"] = round(sim, 3)

        if sim < DESCRIPTION_SIMILARITY_THRESHOLD:
            logger.info("description_unreliable: id=%s sim=%.3f title='%s' desc='%s'",
                        article.get("id"), sim, title[:40], desc[:40])

        return article
    except Exception as e:
        logger.warning("description_check_failed: id=%s — %s", article.get("id"), e)
        article["description_reliable"] = None
        return article


def collect_weekly_articles(days: int = 7) -> list[dict]:
    """
    지난 N일간의 브리핑 선별 기사를 D1에서 수집.
    briefing_items JOIN news → 브리핑에서 선택된 기사만 반환.

    Returns:
        list[dict]: 각 dict에 id, title, description, source, category, pub_date, link 포함
    """
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    # briefing_items JOIN news → 브리핑에서 선택된 기사만.
    # briefings.date 형식: YYYY-MM-DD-NN (하이픈 포함)
    sql = (
        f"SELECT n.id, n.title, n.description, n.source, n.category, n.pub_date, n.link "
        f"FROM briefing_items bi "
        f"JOIN news n ON bi.news_id = n.id "
        f"JOIN briefings b ON bi.briefing_id = b.id "
        f"WHERE b.date >= '{since}' "
        f"ORDER BY n.pub_date DESC"
    )

    rows = d1_query(sql)

    if not rows:
        logger.warning("weekly_pool_empty: no articles found since %s", since)
        return []

    articles = []
    seen_ids = set()
    for row in rows:
        aid = row.get("id")
        if aid in seen_ids:
            continue
        seen_ids.add(aid)
        articles.append({
            "id": aid,
            "title": row.get("title", ""),
            "description": row.get("description", ""),
            "source": row.get("source", ""),
            "category": row.get("category", "AI"),
            "pub_date": row.get("pub_date", ""),
            "link": row.get("link", ""),
        })

    # description 신뢰도 검증
    reliable_count = 0
    unreliable_count = 0
    for art in articles:
        _check_description_reliability(art)
        if art.get("description_reliable") is True:
            reliable_count += 1
        elif art.get("description_reliable") is False:
            unreliable_count += 1

    logger.info("weekly_pool_collected: %d unique articles since %s "
                "(description: %d reliable, %d unreliable, %d unknown)",
                len(articles), since, reliable_count, unreliable_count,
                len(articles) - reliable_count - unreliable_count)
    return articles


def main():
    """CLI: python3 scripts/weekly_contrast_collector.py [--days N]"""
    import argparse
    parser = argparse.ArgumentParser(description="주간 기사 풀 수집")
    parser.add_argument("--days", type=int, default=7, help="수집 기간 (일)")
    args = parser.parse_args()

    articles = collect_weekly_articles(days=args.days)

    if not articles:
        print("No articles found.")
        return

    print(f"\n{'='*60}")
    print(f"주간 기사 풀: {len(articles)}건 (최근 {args.days}일)")
    print(f"{'='*60}")

    for i, art in enumerate(articles, 1):
        desc_preview = (art['description'] or '')[:80]
        print(f"\n[{i:02d}] {art['title']}")
        print(f"     출처: {art['source']} | 카테고리: {art['category']}")
        print(f"     날짜: {art['pub_date']}")
        print(f"     요약: {desc_preview}...")

    # 통계
    sources = {}
    for art in articles:
        src = art['source']
        sources[src] = sources.get(src, 0) + 1
    print(f"\n{'='*60}")
    print("출처별 분포:")
    for src, cnt in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {src}: {cnt}건")


if __name__ == "__main__":
    main()
