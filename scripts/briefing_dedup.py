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
from threads.dedup import is_same_topic, extract_entities, is_topic_related
from auto_news_selector import PROVIDER_SOURCES

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
    """3단계 중복 판정 — 단일 기사 × 전체 히스토리 (기존 동작 유지)

    Layer 3(엔티티 겹침)은 **엔티티 단독**으로도 판정한다. 최근 발행분처럼
    표본이 작은 이력(D1 3일 창)에 쓰는 fail-safe 경로다.

    Returns:
        (True/False, reason_string)
    """
    return _is_duplicate_article(article, history_articles, entity_needs_topic=False)


def is_duplicate_article_strict(article, history_articles):
    """3단계 중복 판정 — Layer 3(엔티티) 에 **주제어 겹침을 동시 요구**한다.

    AIK24-PIPE-08: 엔티티가 겹치기만 하고 주제어가 겹치지 않으면 차단하지 않는다.
    근거: 2026-10-21 실측 — 30일 local 이력(272행)에 범용 엔티티 {AI, API} 만 겹친
    미발행 기사(56076·56389)가 entity(2) 로 탈락해 브리핑이 0건이 되었다.
    행이 누적되는 이력(local)에는 이 경로를 쓴다.

    Returns:
        (True/False, reason_string)
    """
    return _is_duplicate_article(article, history_articles, entity_needs_topic=True)


def _is_duplicate_article(article, history_articles, entity_needs_topic=False):
    """3단계 중복 판정 구현부 — is_duplicate_article / _strict 가 공유한다."""
    aid = str(article.get('id', '')) or str(article.get('news_id', ''))
    link = normalize_url(article.get('link', ''))
    title = (article.get('title', '') or '')[:50]
    orig = (article.get('original_title', '') or '')[:30]
    desc = article.get('description', '') or ''

    # AIK24-EFFICIENCY-04 §4-1: 모델 카드는 exact_id 만으로 중복 판정한다.
    # 같은 모델이 여러 프로바이더로 수집되면 original_title(=모델ID)이 같아서
    # exact_original_title 이 걸리고, 제목이 비슷해 semantic·entity 까지 같이 걸린다
    # (2026-10-14 실측: Kilo/OpenRouter ling 이 semantic·exact_original_title 로 탈락).
    # id 가 없는 항목은 통과시킨다 — 판정 근거가 없으면 막지 않는 쪽이 낫다.
    if article.get('source') in PROVIDER_SOURCES:
        if any(aid and aid == (str(h.get('id', '')) or str(h.get('news_id', '')))
               for h in history_articles):
            return True, 'exact_id'
        return False, None

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
        # AIK24-PIPE-08: strict 경로(= local 30일 이력)에서는 엔티티 **단독** 겹침으로
        #   탈락시키지 않는다 — 주제어(토큰) 겹침을 동시에 요구한다.
        #   근거: 2026-10-21 실측 — 범용 엔티티 {AI, API} 만 겹친 미발행 기사
        #         (56076·56389)가 entity(2) 로 탈락해 브리핑이 0건이 되었다.
        #   D1 3일 창(최근 발행분)은 표본이 작아 fail-safe 로 엔티티 단독 판정을 유지한다.
        ent1 = extract_entities(title, orig, desc)
        ent2 = extract_entities(
            h.get('title', ''), h.get('original_title', ''), h.get('description', ''),
        )
        overlap = len(ent1 & ent2)
        if overlap >= ENTITY_OVERLAP_THRESHOLD:
            if entity_needs_topic and not is_topic_related(
                title, orig, desc,
                h.get('title', ''), h.get('original_title', ''), h.get('description', ''),
            ):
                continue  # 엔티티 단독 겹침 → 차단하지 않는다 (오탐)
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

        # AIK24-PIPE-08: local 30일 이력은 행이 272개로 누적돼 범용 엔티티 충돌이
        # 잦다 → 엔티티 단독 겹침으로는 막지 않고 주제어 겹침을 동시 요구한다.
        dup2, reason2 = is_duplicate_article_strict(art, local)
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
