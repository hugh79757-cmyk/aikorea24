"""브리핑 중복 발행 방지 — 3단계 방어

Phase 1 (뉴스 선정): 과거 N일 브리핑 기사와 exact + semantic + entity overlap 검사
Phase 2 (저장 전): D1 재조회 + local history 추가 검증
Phase 3 (저장 후): local history에 entity 기록 → 이후 Phase 2에서 활용

Usage:
    from briefing_dedup import filter_duplicates, record_briefing
    kept, removed = filter_duplicates(articles, d1_query_func)
    record_briefing(briefing_id, articles, d1_query_func)
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from threads.dedup import is_same_topic, extract_entities

DEDUP_LOOKBACK_DAYS = 3
ENTITY_OVERLAP_THRESHOLD = 2
KST = timezone(timedelta(hours=9))

HISTORY_PATH = Path(__file__).parent / "briefing_dedup.json"


def normalize_url(url):
    if not url:
        return ''
    url = url.split('?')[0].split('#')[0]
    url = url.rstrip('/')
    return url.lower()


def get_history_articles(d1_query):
    """D1에서 최근 N일 발행된 브리핑의 뉴스 기사 목록 조회"""
    cutoff = (datetime.now(KST) - timedelta(days=DEDUP_LOOKBACK_DAYS)).strftime('%Y-%m-%d')
    sql = f"""
        SELECT DISTINCT n.id, n.title, n.original_title, n.description, n.link
        FROM briefings b
        JOIN briefing_items bi ON b.id = bi.briefing_id
        JOIN news n ON bi.news_id = n.id
        WHERE b.status = 'published'
          AND b.date >= '{cutoff}'
        ORDER BY b.date DESC, bi.sort_order ASC
    """
    return d1_query(sql) or []


def is_duplicate_article(article, history_articles):
    """3단계 중복 판정 — 단일 기사 × 전체 히스토리

    Returns:
        (True/False, reason_string)
    """
    aid = str(article.get('id', '')) or str(article.get('news_id', ''))
    link = normalize_url(article.get('link', ''))
    title = (article.get('title', '') or '')[:50]
    orig = (article.get('original_title', '') or '')[:30]
    desc = article.get('description', '') or ''

    for h in history_articles:
        hid = str(h.get('id', '')) or str(h.get('news_id', ''))
        h_link = normalize_url(h.get('link', ''))
        h_title = (h.get('title', '') or '')[:50]
        h_orig = (h.get('original_title', '') or '')[:30]

        # Layer 1: Exact match (id, link, title, original_title)
        if aid and hid and aid == hid:
            return True, 'exact_id'
        if link and h_link and link == h_link:
            return True, 'exact_link'
        if title and h_title and title == h_title:
            return True, 'exact_title'
        if orig and h_orig and orig == h_orig:
            return True, 'exact_original_title'

        # Layer 2: Semantic similarity (언어 통합)
        if is_same_topic(
            title, orig, desc,
            h.get('title', ''), h.get('original_title', ''), h.get('description', ''),
        ):
            return True, 'semantic'

        # Layer 3: Entity overlap (capitalized entity ≥ 2)
        ent1 = extract_entities(title, orig, desc)
        ent2 = extract_entities(
            h.get('title', ''), h.get('original_title', ''), h.get('description', ''),
        )
        overlap = len(ent1 & ent2)
        if overlap >= ENTITY_OVERLAP_THRESHOLD:
            return True, f'entity({overlap})'

    return False, None


def filter_duplicates(articles, d1_query):
    """기사 목록에서 중복 제거 + local history 추가 검증"""
    history = get_history_articles(d1_query)

    # local history에도 동일 기사가 있는지 확인
    local = load_local_history()

    kept = []
    removed = []
    for art in articles:
        dup, reason = is_duplicate_article(art, history)
        if dup:
            removed.append((art, reason))
            continue

        dup2, reason2 = is_duplicate_article(art, local)
        if dup2:
            removed.append((art, f'local_{reason2}'))
            continue

        kept.append(art)
    return kept, removed


def load_local_history():
    """local history JSON 로드"""
    if HISTORY_PATH.exists():
        try:
            data = json.loads(HISTORY_PATH.read_text())
            return data.get('articles', [])
        except (json.JSONDecodeError, Exception):
            return []
    return []


def record_briefing(briefing_id, articles, d1_query):
    """브리핑 발행 후 local history에 기록"""
    data = {"briefings": [], "articles": []}
    if HISTORY_PATH.exists():
        try:
            data = json.loads(HISTORY_PATH.read_text())
        except (json.JSONDecodeError, Exception):
            data = {"briefings": [], "articles": []}

    today = datetime.now(KST).strftime('%Y-%m-%d')

    history_articles = []
    for art in articles:
        title = (art.get('title') or '')[:50]
        orig = art.get('original_title', '') or ''
        desc = art.get('description', '') or ''
        link = art.get('link', '') or ''
        news_id = art.get('id', '') or art.get('news_id', '')
        entities = list(extract_entities(title, orig, desc))

        entry = {
            'id': str(news_id),
            'title': title,
            'original_title': orig,
            'description': desc[:200],
            'link': link,
            'entities': entities,
        }
        history_articles.append(entry)

    data['briefings'].append({
        'date': today,
        'briefing_id': briefing_id,
        'articles': history_articles,
    })
    data['articles'].extend(history_articles)

    # 각 article entry에 date 추가 (cleanup용)
    for a in data['articles']:
        if 'date' not in a:
            a['date'] = today

    # 오래된 데이터 정리 (30일 초과)
    cutoff = (datetime.now(KST) - timedelta(days=30)).strftime('%Y-%m-%d')
    data['briefings'] = [b for b in data['briefings'] if b.get('date', '') >= cutoff]
    data['articles'] = [a for a in data['articles'] if a.get('date', '') >= cutoff] if data.get('articles') else []

    HISTORY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
