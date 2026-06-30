"""
briefing_scorer.py — 브리핑 선정용 임팩트 점수 산출

auto_news_selector.py와 scorer.py(threads)에 의존하지 않는 독립 모듈.
2단계 cascade 평가 (light → full)를 지원.

Usage:
    from briefing_scorer import score_article, load_weights, load_entity_tiers
    weights = load_weights()
    tiers = load_entity_tiers()
    result = score_article(article, weights, tiers, recent_briefings, mode="light")
"""

import json
import os
import re
import time
from datetime import datetime, timezone, timedelta

import requests

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEIGHTS_PATH = os.path.join(PROJECT_DIR, "config", "impact_weights.json")
TIERS_PATH = os.path.join(PROJECT_DIR, "config", "entity_tiers.json")

_AMOUNT_PATTERNS = [
    # USD
    (r"\$\s?(\d+(?:\.\d+)?)\s?(t|trillion|trn)\b", "usd", "trillion"),
    (r"\$\s?(\d+(?:\.\d+)?)\s?(b|bn|billion)\b", "usd", "billion"),
    (r"\$\s?(\d+(?:\.\d+)?)\s?(m|million)\b", "usd", "million"),
    # GBP
    (r"£\s?(\d+(?:\.\d+)?)\s?(b|bn|billion|m|million)\b", "gbp", None),
    # EUR
    (r"€\s?(\d+(?:\.\d+)?)\s?(b|bn|billion|m|million)\b", "eur", None),
    # KRW
    (r"(\d+(?:\.\d+)?)\s?(조|兆)\s?(?:달러|원)?", "krw", "jo"),
    (r"(\d+(?:\.\d+)?)\s?(억|億)\s?(?:달러|원)?", "krw", "eok"),
]

_ENG_ENTITY_RE = re.compile(r'\b[A-Z][a-zA-Z0-9.&+#\-]{2,}\b')


def load_weights():
    with open(WEIGHTS_PATH) as f:
        return json.load(f)


def load_entity_tiers():
    with open(TIERS_PATH) as f:
        return json.load(f)


def crawl_article_body(url, timeout=10):
    """원문 크롤링 — 간단한 HTML to text"""
    if not url or not url.startswith("http"):
        return None
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None
        html = resp.text
        texts = re.findall(r'<p[^>]*>(.*?)</p>', html, re.IGNORECASE | re.DOTALL)
        body = " ".join(re.sub(r'<[^>]+>', '', t) for t in texts)
        body = re.sub(r'\s+', ' ', body).strip()
        return body if body else None
    except Exception:
        return None


def normalize_timestamp(pub_date_str):
    """다양한 포맷의 pub_date를 UTC datetime으로 정규화"""
    if not pub_date_str:
        return None
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]:
        try:
            dt = datetime.strptime(pub_date_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    # fallback: 날짜만 추출
    m = re.search(r'(\d{4}-\d{2}-\d{2})', pub_date_str)
    if m:
        return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return None


def _parse_amounts(text):
    """본문에서 금액 추출 → 통화별 최댓값 (USD equiv for GBP/EUR)"""
    if not text:
        return [], {"usd_max": 0, "krw_max": 0}
    text_lower = text.lower()
    found = []
    usd_values = []
    krw_values = []
    fx_gbp = 1.27
    fx_eur = 1.08

    for pat, currency, unit in _AMOUNT_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            val = float(m.group(1))
            matched = m.group(0)
            if currency == "usd":
                if unit == "trillion":
                    usd_val = val * 1_000_000_000_000
                elif unit == "billion":
                    usd_val = val * 1_000_000_000
                elif unit == "million":
                    usd_val = val * 1_000_000
                else:
                    usd_val = val
                usd_values.append(usd_val)
                found.append({"raw": matched, "currency": "usd", "value": usd_val})
            elif currency == "gbp":
                if "b" in m.group(2).lower()[:1]:
                    usd_val = val * 1_000_000_000 * fx_gbp
                else:
                    usd_val = val * 1_000_000 * fx_gbp
                usd_values.append(usd_val)
                found.append({"raw": matched, "currency": "gbp", "value": val, "usd_value": usd_val})
            elif currency == "eur":
                if "b" in m.group(2).lower()[:1]:
                    usd_val = val * 1_000_000_000 * fx_eur
                else:
                    usd_val = val * 1_000_000 * fx_eur
                usd_values.append(usd_val)
                found.append({"raw": matched, "currency": "eur", "value": val, "usd_value": usd_val})
            elif currency == "krw":
                if unit == "jo":
                    krw_val = val * 1_000_000_000_000
                elif unit == "eok":
                    krw_val = val * 100_000_000
                else:
                    krw_val = val
                krw_values.append(krw_val)
                found.append({"raw": matched, "currency": "krw", "value": krw_val})

    return found, {"usd_max": max(usd_values) if usd_values else 0, "krw_max": max(krw_values) if krw_values else 0}


def _score_financial_impact(amounts_by_currency, weights):
    """금액 기반 점수 — USD와 KRW 각각 자체 맵 사용, 환율 환산 안 함"""
    usd_map = weights["financial_impact"]["usd"]
    krw_map = weights["financial_impact"]["krw"]
    usd_max = amounts_by_currency.get("usd_max", 0)
    krw_max = amounts_by_currency.get("krw_max", 0)

    usd_score = 0
    if usd_max >= 10_000_000_000:
        usd_score = usd_map["10B_plus"]
    elif usd_max >= 1_000_000_000:
        usd_score = usd_map["1B_10B"]
    elif usd_max >= 100_000_000:
        usd_score = usd_map["100M_1B"]
    else:
        usd_score = usd_map.get("lt_100M", 0)

    krw_score = 0
    if krw_max >= 1_000_000_000_000:
        krw_score = krw_map["1조_plus"]
    elif krw_max >= 100_000_000_000:
        krw_score = krw_map["1000억_1조"]
    elif krw_max >= 10_000_000_000:
        krw_score = krw_map["100억_1000억"]
    else:
        krw_score = krw_map.get("lt_100억", 0)

    return max(usd_score, krw_score)


def _match_entity_tiers(text, tiers):
    """엔티티 티어 매칭 → (최고 티어 번호, 매칭된 엔티티 목록)"""
    if not text:
        return 3, []
    tier1 = set(tiers.get("tier1", []))
    tier2 = set(tiers.get("tier2", []))
    matched_tier1 = []
    matched_tier2 = []
    for w in _ENG_ENTITY_RE.findall(text):
        if w in tier1:
            matched_tier1.append(w)
        elif w in tier2:
            matched_tier2.append(w)
    if matched_tier1:
        return 1, matched_tier1
    if matched_tier2:
        return 2, matched_tier2
    return 3, []


def _score_freshness(pub_date_dt, weights_weights):
    """발행 후 경과 시간 기반 점수"""
    if not pub_date_dt:
        return 0, -1
    now = datetime.now(timezone.utc)
    delta = now - pub_date_dt
    hours = delta.total_seconds() / 3600
    if hours < 0:
        hours = 0
    freshness = weights_weights.get("freshness", {})
    if hours < 1:
        return freshness.get("lt_1h", 15), hours
    elif hours <= 3:
        return freshness.get("lt_3h", 10), hours
    elif hours <= 6:
        return freshness.get("lt_6h", 5), hours
    else:
        return freshness.get("gt_6h", 0), hours


def _score_source_authority(source, weights):
    """출처 권위 점수"""
    sa = weights.get("source_authority", {})
    tier1 = set(sa.get("tier1_sources", []))
    source_clean = (source or "").strip()
    if source_clean in tier1:
        return sa.get("tier1_score", 10)
    return sa.get("tier2_score", 5)


def _score_topic_blast_radius(cluster, text, weights):
    """주제 파급력 — cluster + 본문 키워드 동시 매칭"""
    tb = weights.get("topic_blast_radius", {})
    high_topics = tb.get("high", [])
    mid_topics = tb.get("mid", [])
    cluster = (cluster or "").lower().strip()
    text_lower = (text or "").lower()

    if cluster in high_topics:
        return tb.get("high_score", 15)
    if cluster in mid_topics:
        return tb.get("mid_score", 8)
    # cluster가 high/mid가 아니면 본문 키워드로 판단
    for kw in high_topics:
        if kw in text_lower:
            return tb.get("high_score", 15)
    for kw in mid_topics:
        if kw in text_lower:
            return tb.get("mid_score", 8)
    return tb.get("low_score", 3)


def _score_conflict_drama(text, weights):
    """갈등/드라마 점수"""
    cd = weights.get("conflict_drama", {})
    keywords = cd.get("keywords", [])
    text_lower = (text or "").lower()
    for kw in keywords:
        if kw in text_lower:
            return cd.get("score", 10)
    return 0


def _penalty_low_tier_entity(tier, text, weights, entity_tiers):
    """tier-3 단독 기사 패널티 — 본문에 tier-1 동반 시 면제"""
    penalties = weights.get("penalties", {})
    if tier == 3:
        t1 = set(entity_tiers.get("tier1", []))
        if not t1:
            t1_config = load_entity_tiers().get("tier1", [])
            t1 = set(t1_config)
        for w in _ENG_ENTITY_RE.findall(text or ""):
            if w in t1:
                return 0
        return penalties.get("low_tier_entity_solo", -10)
    return 0


def _penalty_duplicate_theme(cluster, text, recent_briefings, weights, usd_max, krw_max):
    """최근 7일 브리핑과 동일 테마 패널티 — 임팩트 2배 이상이면 면제"""
    penalties = weights.get("penalties", {})
    if not recent_briefings:
        return 0
    cluster = (cluster or "").lower().strip()
    if not cluster:
        return 0
    text_orig = text or ""

    for rb in recent_briefings:
        rb_cluster = (rb.get("cluster") or "").lower().strip()
        if rb_cluster != cluster:
            continue
        # 엔티티 교집합 검사
        rb_entities = set(rb.get("entities", []))
        current_entities = set(_ENG_ENTITY_RE.findall(text_orig))
        if rb_entities and current_entities:
            overlap = rb_entities & current_entities
            if overlap:
                # 임팩트 2배 이상 면제
                rb_amount = rb.get("impact_amount", 0)
                current_max = max(usd_max, krw_max)
                if rb_amount > 0 and current_max >= rb_amount * 2:
                    continue
                return penalties.get("duplicate_theme_7d", -15)
    return 0


def score_article(article, weights, entity_tiers, recent_briefings=None, mode="light"):
    """
    2단계 cascade 평가.

    mode="light": title+description 기반, 4개 항목 (financial_impact, entity_tier, freshness, source_authority)
    mode="full":  body+title 기반, 7개 항목 전부

    article: {title, body?, description, source, pub_date, cluster, link, ...}
    """
    title = article.get("title", "") or ""
    description = article.get("description", "") or ""
    body = article.get("body", "") or ""
    source = article.get("source", "") or ""
    pub_date = article.get("pub_date", "") or ""
    cluster = article.get("cluster", "") or ""
    link = article.get("link", "") or ""

    crawl_failed = False
    text_light = f"{title} {description}"
    text_full = f"{title} {body} {description}"

    if mode == "full" and not body:
        crawl_failed = True

    # 금액 파싱 (항상 title+description 기반, body가 있으면 추가)
    found_light, amounts_light = _parse_amounts(text_light)
    found_list = found_light
    amounts_full = amounts_light
    if mode == "full" and body:
        found_full, amounts_full = _parse_amounts(text_full)
        found_list = found_full

    # 엔티티 매칭
    tier, matched_entities = _match_entity_tiers(text_light if mode == "light" else text_full, entity_tiers)

    # freshness
    pub_date_dt = normalize_timestamp(pub_date)
    freshness_score, hours_since = _score_freshness(pub_date_dt, weights)

    # source_authority
    source_score = _score_source_authority(source, weights)

    # financial_impact (mode 무관, 항상 title+description 기반)
    fi_score = _score_financial_impact(amounts_full, weights)

    breakdown = {
        "financial_impact": fi_score,
        "entity_tier": 0,
        "freshness": freshness_score,
        "source_authority": source_score,
        "topic_blast_radius": 0,
        "conflict_drama": 0,
        "penalty_low_tier_entity": 0,
        "penalty_duplicate_theme": 0,
    }

    evidence = {
        "matched_amounts": [_f["raw"] for _f in found_list] if found_list else [],
        "matched_entities": matched_entities,
        "matched_keywords": [],
        "hours_since_publish": round(hours_since, 2) if hours_since >= 0 else -1,
        "crawl_failed": crawl_failed,
    }

    # entity_tier 점수 (light/full 공통)
    tier_config = weights.get("entity_tier", {})
    if tier == 1:
        breakdown["entity_tier"] = tier_config.get("tier1", 20)
    elif tier == 2:
        breakdown["entity_tier"] = tier_config.get("tier2", 10)
    else:
        breakdown["entity_tier"] = tier_config.get("tier3", 0)

    if mode == "full":
        text_for_full = text_full
        # topic_blast_radius
        breakdown["topic_blast_radius"] = _score_topic_blast_radius(cluster, text_for_full, weights)
        # conflict_drama
        breakdown["conflict_drama"] = _score_conflict_drama(text_for_full, weights)
        # penalty_low_tier_entity
        breakdown["penalty_low_tier_entity"] = _penalty_low_tier_entity(tier, text_for_full, weights, entity_tiers)
        # penalty_duplicate_theme
        usd_max = amounts_full.get("usd_max", 0) if amounts_full else 0
        krw_max = amounts_full.get("krw_max", 0) if amounts_full else 0
        breakdown["penalty_duplicate_theme"] = _penalty_duplicate_theme(
            cluster, text_for_full, recent_briefings or [], weights, usd_max, krw_max
        )
        # evidence keywords
        tb = weights.get("topic_blast_radius", {})
        all_topic_kws = tb.get("high", []) + tb.get("mid", [])
        cd_kws = weights.get("conflict_drama", {}).get("keywords", [])
        matched_kw = set()
        for kw in all_topic_kws + cd_kws:
            if kw in text_for_full.lower():
                matched_kw.add(kw)
        evidence["matched_keywords"] = sorted(matched_kw)

    total = sum(v for k, v in breakdown.items() if not k.startswith("penalty"))
    total += breakdown.get("penalty_low_tier_entity", 0)
    total += breakdown.get("penalty_duplicate_theme", 0)
    total = max(0, min(weights.get("thresholds", {}).get("total_max", 95), total))

    usd_max_val = amounts_full.get("usd_max", 0) if amounts_full else 0
    krw_max_val = amounts_full.get("krw_max", 0) if amounts_full else 0

    tier_reasoning = _build_tier_reasoning(tier, matched_entities, total, weights)

    return {
        "total": total,
        "breakdown": breakdown,
        "evidence": evidence,
        "tier_reasoning": tier_reasoning,
        "mode": mode,
        "max_amount_usd": usd_max_val,
        "max_amount_krw": krw_max_val,
    }


def _build_tier_reasoning(tier, entities, total, weights):
    parts = []
    if tier == 1:
        parts.append(f"tier-1 엔티티 포함: {', '.join(entities[:3])}")
    elif tier == 2:
        parts.append(f"tier-2 엔티티 포함: {', '.join(entities[:3])}")
    else:
        parts.append("tier-3 (주요 엔티티 없음)")
    threshold = weights.get("thresholds", {}).get("impact_pass_min", 70)
    if total >= threshold:
        parts.append(f"임팩트 통과 (≥{threshold})")
    else:
        parts.append(f"임팩트 미달 (<{threshold})")
    return " | ".join(parts)
