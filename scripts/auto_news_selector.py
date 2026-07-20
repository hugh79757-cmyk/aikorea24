#!/usr/bin/env python3
"""aikorea24 자동 뉴스 선정기 — 2-Pass 임팩트 평가 (cascade)

Shadow diff log format (logs/briefing_shadow_diff.log):
    3-layer JSONL:
    Layer 1: {"ts":..., "layer":1, "mode":"dry_run|shadow", "data":{"diff":"NO_CHANGE|CHANGED", ...}}
    Layer 2: {"ts":..., "layer":2, "mode":"dry_run|shadow", "data":{"light_histogram":..., "full_histogram":...}}
    Layer 3: {"ts":..., "layer":3, "mode":"shadow", "data":{"borderline_count":N, "borderline_articles":[...]}}  (shadow only)
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from pipeline.infra.d1_client import d1_query
from pipeline.infra import project_root; PROJECT_DIR = project_root()

from pipeline.infra.logger import get_scrubbed_logger
logger = get_scrubbed_logger(__name__)

CONFIG_PATH = os.path.join(PROJECT_DIR, "config", "crawlable_sources.json")
KST = timezone(timedelta(hours=9))
SHADOW_LOG_PATH = os.path.join(PROJECT_DIR, "scripts", "logs", "briefing_shadow_diff.log")

_BRIEFING_SCORER_MODE = os.environ.get("BRIEFING_SCORER_MODE", "dry_run")


# Strangler Fig: replace with logger.info() in Phase 3
def log(msg):
    ts = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def load_crawlable_sources():
    with open(CONFIG_PATH) as f:
        data = json.load(f)
    return [s["name"] for s in data.get("crawlable", [])]


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


def get_recent_briefings_7d():
    """최근 7일 브리핑 기사 조회 (penalty_duplicate_theme_7d용)"""
    cutoff = (datetime.now(KST) - timedelta(days=7)).strftime("%Y-%m-%d")
    sql = f"""
        SELECT DISTINCT n.id, n.title, n.original_title, n.description, n.link, b.date
        FROM briefings b
        JOIN briefing_items bi ON b.id = bi.briefing_id
        JOIN news n ON bi.news_id = n.id
        WHERE b.status = 'published'
          AND b.date >= '{cutoff}'
        ORDER BY b.date DESC
    """
    rows = d1_query(sql) or []
    # 엔티티 전처리해서 반환
    from briefing_scorer import _ENG_ENTITY_RE
    result = []
    for r in rows:
        text = f"{r.get('title', '')} {r.get('description', '')} {r.get('original_title', '')}"
        entities = list(set(_ENG_ENTITY_RE.findall(text)))
        result.append({
            "cluster": "",  # auto_briefing의 to_scorer_recent_briefing에서 채움
            "entities": entities,
            "impact_amount": 0,  # auto_briefing에서 채움
            "title": r.get("title", ""),
            "link": r.get("link", ""),
        })
    return result


def cluster_by_topic(articles):
    """주제별 클러스터링 (키워드 기반) + 각 article에 cluster 라벨 부착"""
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
            matched = "misc"
        article["cluster"] = matched
        clusters.setdefault(matched, []).append(article)

    return clusters


def _expand_misc_for_legacy(clusters):
    """레거시 round-robin용: misc를 출처별 서브클러스터로 확장"""
    result = {}
    for k, v in clusters.items():
        if k == "misc":
            for a in v:
                source = a.get("source", "unknown")
                result.setdefault(source, []).append(a)
        else:
            result[k] = v
    return result


def select_top_articles(clusters, max_count=6):
    """클러스터별 대표 기사 선정 (round-robin) — 레거시"""
    selected = []
    cluster_items = list(clusters.items())
    cluster_items.sort(key=lambda x: len(x[1]), reverse=True)
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


def _compute_light_scores(articles, weights, entity_tiers, recent_briefings):
    """Phase A: 모든 후보에 light score 산출"""
    from briefing_scorer import score_article
    scored = []
    for a in articles:
        result = score_article(a, weights, entity_tiers, recent_briefings, mode="light")
        a["light_score"] = result["total"]
        a["score_breakdown_light"] = result["breakdown"]
        a["score_evidence_light"] = result["evidence"]
        a["light_score_max_amount_usd"] = result.get("max_amount_usd", 0)
        a["light_score_max_amount_krw"] = result.get("max_amount_krw", 0)
        scored.append((result["total"], a))
    scored.sort(key=lambda x: -x[0])
    return scored


def _crawl_and_full_score(top_n_articles, weights, entity_tiers, recent_briefings):
    """Phase B: Top-N 크롤링 + full score"""
    from briefing_scorer import crawl_article_body, score_article
    for a in top_n_articles:
        url = a.get("link", "")
        log(f"  [crawl] {url[:70]}...")
        body = crawl_article_body(url)
        a["body"] = body or ""
        result = score_article(a, weights, entity_tiers, recent_briefings, mode="full")
        a["full_score"] = result["total"]
        a["score_breakdown"] = result["breakdown"]
        a["score_evidence"] = result["evidence"]
        a["full_score_max_amount_usd"] = result.get("max_amount_usd", 0)
        a["full_score_max_amount_krw"] = result.get("max_amount_krw", 0)
        log(f"    full_score={result['total']} ({result['tier_reasoning']})")


def _two_pass_selection(clusters, max_count=6):
    """
    2-Pass 선택 알고리즘 (shadow/live 모드).
    각 article에 impact_score, score_breakdown, light_score, full_score가 이미 있어야 함.
    """
    impact_pass_min = 70
    impact_pass_max_slots = 3
    light_min_misc = 20

    all_articles = []
    for ca in clusters.values():
        all_articles.extend(ca)

    pass1 = []
    pass1_clusters = set()
    pass1_ids = set()

    scored = [(a.get("full_score") or 0, a) for a in all_articles if a.get("full_score") is not None]
    scored.sort(key=lambda x: -x[0])
    for score, a in scored:
        if len(pass1) >= impact_pass_max_slots:
            break
        if str(a.get("id", "")) in pass1_ids:
            continue
        if score >= impact_pass_min:
            pass1.append(a)
            pass1_ids.add(str(a.get("id", "")))
            pass1_clusters.add(a.get("cluster", ""))

    pass2 = []
    pass2_ids = set(pass1_ids)
    remaining_slots = max_count - len(pass1)

    if remaining_slots > 0:
        cluster_items = [(k, v) for k, v in clusters.items() if k not in pass1_clusters]
        cluster_items.sort(key=lambda x: -len(x[1]))

        # round-robin 잔여 slot 채움
        idx = 0
        while len(pass2) < remaining_slots:
            taken = 0
            for keyword, articles in cluster_items:
                if len(pass2) >= remaining_slots:
                    break
                if idx < len(articles):
                    art = articles[idx]
                    aid = str(art.get("id", ""))
                    if aid not in pass2_ids:
                        # misc cluster: light_score 하한 체크
                        if keyword == "misc":
                            ls = art.get("light_score", 0)
                            if ls < light_min_misc:
                                continue
                        pass2.append(art)
                        pass2_ids.add(aid)
                        taken += 1
            if taken == 0:
                break
            idx += 1

        # misc slot 하한 미달로 빈 경우, 다른 cluster에서 차순위 인출
        if len(pass2) < remaining_slots:
            deficit = remaining_slots - len(pass2)
            for keyword, articles in cluster_items:
                if deficit <= 0:
                    break
                if keyword == "misc":
                    continue
                for art in articles:
                    if deficit <= 0:
                        break
                    aid = str(art.get("id", ""))
                    if aid not in pass2_ids:
                        pass2.append(art)
                        pass2_ids.add(aid)
                        deficit -= 1

        # 최종 fallback: deficit가 남으면 misc에서 full_score 순으로 인출 (light_score 하한 무시)
        if len(pass2) < remaining_slots:
            deficit = remaining_slots - len(pass2)
            misc_articles = sorted(
                clusters.get("misc", []),
                key=lambda a: -(a.get("full_score") or 0)
            )
            for art in misc_articles:
                if deficit <= 0:
                    break
                aid = str(art.get("id", ""))
                if aid not in pass2_ids:
                    pass2.append(art)
                    pass2_ids.add(aid)
                    deficit -= 1

    return pass1, pass2


def _log_shadow_diff(legacy_selected, pass1, pass2, all_articles, mode):
    """3층 shadow diff 로그 기록"""
    os.makedirs(os.path.dirname(SHADOW_LOG_PATH), exist_ok=True)
    ts = datetime.now().isoformat()

    legacy_ids = {str(a.get("id", "")) for a in legacy_selected}
    shadow_selected = pass1 + pass2
    shadow_ids = {str(a.get("id", "")) for a in shadow_selected}

    # Layer 1: Selection diff
    added = shadow_ids - legacy_ids
    removed = legacy_ids - shadow_ids
    if not added and not removed:
        layer1 = {"diff": "NO_CHANGE", "legacy_ids": list(legacy_ids), "shadow_ids": list(shadow_ids)}
    else:
        layer1 = {
            "diff": "CHANGED",
            "added": list(added),
            "removed": list(removed),
            "added_titles": [a.get("title", "")[:60] for a in shadow_selected if str(a.get("id", "")) in added],
            "removed_titles": [a.get("title", "")[:60] for a in legacy_selected if str(a.get("id", "")) in removed],
        }

    # Layer 2: Score distribution
    light_scores = [a.get("light_score", 0) for a in all_articles if a.get("light_score") is not None]
    full_scores = [a.get("full_score", 0) for a in all_articles if a.get("full_score") is not None]
    def _histogram(scores):
        bins = {}
        for s in scores:
            b = (s // 10) * 10
            bins[b] = bins.get(b, 0) + 1
        return bins
    layer2 = {
        "light_histogram": _histogram(light_scores),
        "full_histogram": _histogram(full_scores),
        "light_count": len(light_scores),
        "full_count": len(full_scores),
    }

    with open(SHADOW_LOG_PATH, "a") as f:
        f.write(f"{json.dumps({'ts': ts, 'layer': 1, 'mode': mode, 'data': layer1}, ensure_ascii=False)}\n")
        f.write(f"{json.dumps({'ts': ts, 'layer': 2, 'mode': mode, 'data': layer2}, ensure_ascii=False)}\n")

    # Layer 3: shadow 전용 — Pass 1 경계역 분석
    if mode == "shadow":
        borderline = []
        for a in all_articles:
            fs = a.get("full_score")
            if fs is not None and 65 <= fs <= 75:
                borderline.append({
                    "id": a.get("id", ""),
                    "title": (a.get("title") or "")[:60],
                    "full_score": fs,
                    "light_score": a.get("light_score"),
                    "breakdown": a.get("score_breakdown"),
                    "evidence": a.get("score_evidence"),
                    "cluster": a.get("cluster"),
                    "in_pass1": str(a.get("id", "")) in {str(x.get("id", "")) for x in pass1},
                    "reason": "통과" if str(a.get("id", "")) in {str(x.get("id", "")) for x in pass1} else "탈락",
                })
        layer3 = {"borderline_count": len(borderline), "borderline_articles": borderline}
        with open(SHADOW_LOG_PATH, "a") as f:
            f.write(f"{json.dumps({'ts': ts, 'layer': 3, 'mode': mode, 'data': layer3}, ensure_ascii=False)}\n")

    log(f"[shadow diff] Layer 1: {layer1['diff']} ({len(added)} added, {len(removed)} removed)")
    log(f"[shadow diff] Layer 2: light={layer2['light_count']}, full={layer2['full_count']}")
    if mode == "shadow":
        log(f"[shadow diff] Layer 3: borderline {len(borderline)}건")


def print_report(articles, selected):
    log(f"\n{'='*50}")
    log(f"뉴스 선정 리포트")
    log(f"{'='*50}")
    log(f"전체 기사: {len(articles)}건 → 선정: {len(selected)}건\n")
    for i, art in enumerate(selected, 1):
        title = art.get("title", "(제목 없음)")
        source = art.get("source", "(출처 없음)")
        link = art.get("link", "(링크 없음)")
        fs = art.get("full_score")
        ls = art.get("light_score")
        score_tag = f" [full={fs}]" if fs is not None else f" [light={ls}]" if ls is not None else ""
        log(f"{i}.{score_tag} {title}")
        log(f"   출처: {source}")
        log(f"   URL:  {link}")
        log("")
    source_counts = {}
    for art in articles:
        s = art.get("source", "unknown")
        source_counts[s] = source_counts.get(s, 0) + 1
    log("[소스별 기사 수]")
    for s, c in sorted(source_counts.items(), key=lambda x: -x[1]):
        log(f"  {s}: {c}건")


def main(dedup=True):
    mode = _BRIEFING_SCORER_MODE
    log("=== aikorea24 자동 뉴스 선정 ===\n")
    log(f"[mode] BRIEFING_SCORER_MODE={mode}")

    # 0. 환경변수에 따라 weights/entity_tiers 로드
    weights = None
    entity_tiers = None
    recent_briefings = []
    if mode != "dry_run" or mode == "shadow":
        from briefing_scorer import load_weights, load_entity_tiers
        weights = load_weights()
        entity_tiers = load_entity_tiers()
        recent_briefings = get_recent_briefings_7d()
    else:
        # dry_run에서도 shadow 들어갈 수 있으니 로드
        try:
            from briefing_scorer import load_weights, load_entity_tiers
            weights = load_weights()
            entity_tiers = load_entity_tiers()
            recent_briefings = get_recent_briefings_7d()
        except Exception:
            pass

    # 1. 뉴스 조회
    articles = get_recent_news(hours=24)
    if not articles:
        log("수집된 뉴스가 없습니다.")
        return []

    # 2. 클러스터링
    clusters = cluster_by_topic(articles)
    log(f"주제 클러스터: {len(clusters)}개")
    for k, v in sorted(clusters.items(), key=lambda x: -len(x[1])):
        log(f"  {k}: {len(v)}건")

    # 3. Phase 1 dedup (후보 풀에 대해 먼저 수행)
    if dedup:
        from briefing_dedup import filter_duplicates
        articles, removed = filter_duplicates(articles, d1_query)
        if removed:
            log(f"\n⚠️ Phase 1 중복 제거: {len(removed)}건")
            for art, reason in removed:
                title = (art.get('title') or '')[:50]
                log(f"  [{reason}] {title}")
        # 제거 후 클러스터 재구성
        clusters = cluster_by_topic(articles)

    # 4. Phase A + B scoring
    if weights and entity_tiers:
        all_flat = [a for ca in clusters.values() for a in ca]
        log(f"\n[Phase A] light score 산출 ({len(all_flat)}개)...")
        scored = _compute_light_scores(all_flat, weights, entity_tiers, recent_briefings)
        top_n_count = weights.get("thresholds", {}).get("top_n_crawl", 20)
        top_n = [a for _, a in scored[:top_n_count]]
        log(f"[Top-N] 상위 {len(top_n)}개 크롤링 + full score...")
        _crawl_and_full_score(top_n, weights, entity_tiers, recent_briefings)
        log("")

    # 5. 선택
    if mode == "live":
        # 2-Pass 선택
        pass1, pass2 = _two_pass_selection(clusters)
        selected = pass1 + pass2
        for a in selected:
            a["pass_source"] = "pass1" if a in pass1 else "pass2"
    else:
        # 레거시 round-robin (dry_run, shadow 모두 동일) — misc를 출처별로 확장하여 원래 동작 회귀 유지
        legacy_clusters = _expand_misc_for_legacy(clusters)
        selected = select_top_articles(legacy_clusters, max_count=6)

        if mode == "shadow" and weights:
            # shadow: 2-Pass 계산 후 diff 로깅
            pass1_shadow, pass2_shadow = _two_pass_selection(clusters)
            _log_shadow_diff(selected, pass1_shadow, pass2_shadow, [a for ca in clusters.values() for a in ca], mode)
            # shadow log Layer 1,2도 dry_run에 출력
        elif mode == "dry_run" and weights:
            pass1_shadow, pass2_shadow = _two_pass_selection(clusters)
            _log_shadow_diff(selected, pass1_shadow, pass2_shadow, [a for ca in clusters.values() for a in ca], "dry_run")

    for a in selected:
        a["impact_score"] = a.get("full_score") or a.get("light_score") or 0
        a["score_breakdown"] = a.get("score_breakdown") or a.get("score_breakdown_light") or {}
        if a.get("pass_source") is None:
            a["pass_source"] = "legacy"

    log(f"\n선정 완료: {len(selected)}개 기사")
    print_report(articles, selected)

    return selected


if __name__ == "__main__":
    main()
