#!/usr/bin/env python3
"""aikorea24 자동 뉴스 선정기"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_DIR = "/Users/twinssn/Projects/aikorea24"
CONFIG_PATH = os.path.join(PROJECT_DIR, "config", "crawlable_sources.json")
KST = timezone(timedelta(hours=9))


def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def load_crawlable_sources():
    with open(CONFIG_PATH) as f:
        data = json.load(f)
    return [s["name"] for s in data.get("crawlable", [])]


def d1_query(sql, retries=2):
    cmd = ["npx", "wrangler", "d1", "execute", "aikorea24-db", "--remote", "--command", sql]
    for attempt in range(retries):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=PROJECT_DIR)
            if r.returncode != 0:
                log(f"  D1 반환코드 {r.returncode}, 재시도 ({attempt+1}/{retries})")
                continue
            m = re.search(r'"results"\s*:\s*(\[[\s\S]*?\])\s*,\s*"success"', r.stdout)
            if m:
                return json.loads(m.group(1))
            return []
        except Exception as e:
            log(f"  D1 오류: {e}, 재시도 ({attempt+1}/{retries})")
    return []


def get_recent_news(hours=24):
    """D1에서 최근 뉴스 조회 (크롤링 가능 매체만 필터)"""
    crawlable = load_crawlable_sources()
    quoted = [f"'{s}'" for s in crawlable]
    sources_filter = ", ".join(quoted)

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

    sql = f"""
        SELECT id, title, link, description, source, category, pub_date
        FROM news
        WHERE source IN ({sources_filter})
          AND created_at >= '{cutoff}'
        ORDER BY created_at DESC
        LIMIT 100
    """

    rows = d1_query(sql)
    log(f"D1 조회: {len(rows)}건 (필터: 크롤링 가능 {len(crawlable)}개 매체)")
    return rows


def cluster_by_topic(articles):
    """주제별 클러스터링 (키워드 기반)"""
    clusters = {}
    keywords_map = {
        "openai": ["openai", "chatgpt", "gpt", "o1", "o3", "sora"],
        "google": ["google", "gemini", "deepmind"],
        "anthropic": ["anthropic", "claude"],
        "meta": ["meta", "llama"],
        "microsoft": ["microsoft", "copilot", "azure"],
        "nvidia": ["nvidia", "h100", "b200", "cuda"],
        "ai-regulation": ["regulation", "regulations", "규제", "정책", "policy", "ai act"],
        "investment": ["investment", "funding", "투자", "fundraise", "ipo", "valuation"],
        "opensource": ["open source", "opensource", "hugging face"],
    }

    for article in articles:
        title = (article.get("title") or "").lower()
        desc = (article.get("description") or "").lower()
        text = title + " " + desc

        matched = None
        for cluster_name, kws in keywords_map.items():
            if any(kw in text for kw in kws):
                matched = cluster_name
                break

        if not matched:
            matched = article.get("source", "unknown")

        if matched not in clusters:
            clusters[matched] = []
        clusters[matched].append(article)

    return clusters


def select_top_articles(clusters, max_count=6):
    """클러스터별 대표 기사 선정 (균형 있게 최대 max_count개)"""
    selected = []
    cluster_items = list(clusters.items())

    cluster_items.sort(key=lambda x: len(x[1]), reverse=True)

    # Round-robin: 각 클러스터에서 1개씩
    idx = 0
    used_ids = set()
    while len(selected) < max_count:
        taken = 0
        for keyword, articles in cluster_items:
            if len(selected) >= max_count:
                break
            if idx < len(articles):
                art = articles[idx]
                aid = str(art.get("id", ""))
                if aid not in used_ids:
                    selected.append(art)
                    used_ids.add(aid)
                    taken += 1
        if taken == 0:
            break
        idx += 1

    return selected


def print_report(articles, selected):
    log(f"\n{'='*50}")
    log(f"뉴스 선정 리포트")
    log(f"{'='*50}")
    log(f"전체 기사: {len(articles)}건 → 선정: {len(selected)}건\n")

    for i, art in enumerate(selected, 1):
        title = art.get("title", "(제목 없음)")
        source = art.get("source", "(출처 없음)")
        link = art.get("link", "(링크 없음)")
        log(f"{i}. {title}")
        log(f"   출처: {source}")
        log(f"   URL:  {link}")
        log("")

    # 소스별 통계
    source_counts = {}
    for art in articles:
        s = art.get("source", "unknown")
        source_counts[s] = source_counts.get(s, 0) + 1
    log("[소스별 기사 수]")
    for s, c in sorted(source_counts.items(), key=lambda x: -x[1]):
        log(f"  {s}: {c}건")


def main(dedup=True):
    log("=== aikorea24 자동 뉴스 선정 ===\n")

    articles = get_recent_news(hours=24)
    if not articles:
        log("수집된 뉴스가 없습니다.")
        return []

    clusters = cluster_by_topic(articles)
    log(f"주제 클러스터: {len(clusters)}개")
    for k, v in sorted(clusters.items(), key=lambda x: -len(x[1])):
        log(f"  {k}: {len(v)}건")

    selected = select_top_articles(clusters, max_count=6)
    log(f"\n선정 완료: {len(selected)}개 기사")

    if dedup:
        from briefing_dedup import filter_duplicates
        cutoff, removed = filter_duplicates(selected, d1_query)
        if removed:
            log(f"\n⚠️ 중복 제거: {len(removed)}건")
            for art, reason in removed:
                title = (art.get('title') or '')[:50]
                log(f"  [{reason}] {title}")
        selected = cutoff

    print_report(articles, selected)

    return selected


if __name__ == "__main__":
    main()
