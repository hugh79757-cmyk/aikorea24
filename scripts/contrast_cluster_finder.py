#!/usr/bin/env python3
"""
S1: 클러스터링 및 대비 쌍 탐지 — 84개 기사에서 대비 선명한 쌍을 LLM으로 탐지.

접근:
  Stage 1: 84개 제목+요약 → LLM에게 "대비될 만한 주제 그룹 5개" 추출
  Stage 2: 각 그룹 내에서 A vs B 대비 프레임 + 원문 근거 문장 추출

입력: list[dict] (weekly_contrast_collector 출력)
출력: list[dict] — 대비 쌍 후보
"""

import json
import os
import re
import sys
from typing import Optional

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)

from scripts.threads.v3.model_router import chat_completion
from pipeline.infra.logger import get_scrubbed_logger

logger = get_scrubbed_logger(__name__)

ABDUCTION_MODEL = os.environ.get("ABDUCTION_MODEL", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# Stage 1: 제목 기반 클러스터링
# ---------------------------------------------------------------------------

def _build_cluster_prompt(articles: list[dict]) -> str:
    """기사 제목+요약 → 대비 주제 그룹 추출용 프롬프트."""
    lines = []
    for art in articles:
        # description 신뢰도가 낮으면 description 사용 안 함
        if art.get("description_reliable") is False:
            desc = ""
        else:
            desc = (art.get("description") or "")[:100]
        aid = art.get("id", "?")
        lines.append(f"[ID:{aid}] {art['title']} | {art['source']} | {desc}")

    titles_block = "\n".join(lines)

    return f"""당신은 한국어 AI 뉴스 분석가입니다. 아래 뉴스 목록을 분석해서, 서로 대비(contrast)되는 주제 그룹을 찾아주세요.

[뉴스 목록]
{titles_block}

[출력 형식]
다음 JSON 형식으로 출력하세요:
{{
  "groups": [
    {{
      "topic": "그룹 주제 (예: EU 규제 vs 중국 규제 완화)",
      "article_ids": [기사ID1, 기사ID2],
      "contrast_frame": "A vs B 형태의 대비 설명",
      "why_contrast": "왜 이 기사들이 대비되는지 한 줄 설명",
      "category": "규제|기술|시장|정책|윤리|노동|투자|보안|국제정세 중 하나"
    }}
  ]
}}

[규칙]
1. 최소 3개, 최대 7개 그룹을 찾으세요.
2. 각 그룹은 최소 2개 이상의 기사를 포함해야 합니다.
3. 같은 기사가 여러 그룹에 속할 수 있습니다.
4. "대비"란: 상반된 입장, 예상과 실제의 괴리, 시간에 따른 변화, 정책vs현실 등
5. 한국어로 출력하세요.
6. 반드시 JSON만 출력하세요. 다른 텍스트를 포함하지 마세요.
7. [ID:12345]의 숫자가 기사 고유 ID입니다. article_ids에 해당 ID를 그대로 사용하세요.
8. category를 반드시 지정하세요. 각 그룹은 서로 다른 category여야 합니다.

[품질 규칙 — 중요]
- "혁신 vs 위협", "긍정 vs 부정", "기대 vs 우려" 같은 뻔한 대비는 금지.
- 구체적 정책, 기술 방향, 기업 전략, 시장 구조의 대비를 찾으세요.
- 나쁜 예: "AI의 두 얼굴" (너무 일반적)
- 좋은 예: "EU AI 규제법 시행 vs 중국 AI 규제 완화", "온디바이스 AI 경량화 vs 클라우드 확장"
- 좋은 예: "스케일러블 캐피털 AI 투자 vs 금융감독원 소비자 경고"
- 좋은 예: "OpenAI 데이터센터 임원 퇴사 vs 구글 AI 인프라 투자 확대"
- 각 그룹의 contrast_frame은 최소 10자 이상 구체적으로 서술하세요."""


def _parse_clusters(raw_text: str) -> list[dict]:
    """LLM 출력에서 클러스터 JSON 파싱."""
    # markdown code block 제거
    cleaned = re.sub(r'```json\s*', '', raw_text)
    cleaned = re.sub(r'```\s*', '', cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # JSON 브레이스 매칭 시도
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start >= 0 and end > start:
            try:
                data = json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                logger.warning("cluster_parse_failed: invalid JSON")
                return []
        else:
            logger.warning("cluster_parse_failed: no JSON found")
            return []

    groups = data.get("groups", [])
    if not groups:
        return []

    validated = []
    for g in groups:
        if not g.get("topic") or not (g.get("article_ids") or g.get("article_indices")):
            continue
        validated.append({
            "topic": g["topic"],
            "article_ids": g.get("article_ids") or g.get("article_indices", []),
            "contrast_frame": g.get("contrast_frame", ""),
            "why_contrast": g.get("why_contrast", ""),
            "category": g.get("category", ""),
        })

    return validated


def find_clusters(articles: list[dict], max_articles: int = 50) -> list[dict]:
    """
    Stage 1: 기사 제목+요약으로 대비 클러스터 탐지.
    max_articles: 프롬프트 크기 제한 (50개 이하 권장).

    Returns:
        list[dict]: 클러스터 목록 (topic, article_indices, contrast_frame, why_contrast)
    """
    if len(articles) < 2:
        return []

    # 최신 기사 우선으로 제한
    limited = articles[:max_articles]
    if len(articles) > max_articles:
        logger.info("clusters_input_truncated: %d → %d articles", len(articles), max_articles)

    prompt = _build_cluster_prompt(limited)

    messages = [
        {"role": "user", "content": prompt}
    ]

    raw = chat_completion(
        messages=messages,
        system_prompt="당신은 한국어 AI 뉴스 분석 전문가입니다. JSON만 출력하세요.",
        temperature=0.3,
        max_tokens=4000,
        model_override=None,
    )

    if not raw:
        logger.warning("cluster_llm_failed: no response")
        return []

    clusters = _parse_clusters(raw)
    logger.info("clusters_found: %d groups", len(clusters))
    return clusters


# ---------------------------------------------------------------------------
# Stage 2: 대비 쌍 상세 분석 + 근거 문장 추출
# ---------------------------------------------------------------------------

def _build_evidence_prompt(cluster: dict, articles: list[dict]) -> str:
    """특정 클러스터의 대비 쌍에 대한 근거 문장 추출용 프롬프트."""
    # 클러스터에 속한 기사들을 ID로 필터
    article_ids = cluster.get("article_ids", [])
    id_to_article = {art.get("id"): art for art in articles}
    matched = [id_to_article[aid] for aid in article_ids if aid in id_to_article]

    if len(matched) < 2:
        return ""

    article_blocks = []
    for art in matched:
        # description 신뢰도가 낮으면 description 사용 안 함
        if art.get("description_reliable") is False:
            desc = ""
        else:
            desc = (art.get("description") or "")[:300]
        article_blocks.append(
            f"[기사 ID {art.get('id')}] {art['title']}\n"
            f"출처: {art['source']} | 날짜: {art['pub_date']}\n"
            f"요약: {desc}"
        )

    articles_text = "\n\n".join(article_blocks)

    return f"""아래 기사들을 분석해서 대비 구조를 분석해주세요.

[기사 목록]
{articles_text}

[주제] {cluster['topic']}
[대비 프레임] {cluster['contrast_frame']}

[출력 형식]
다음 JSON 형식으로 출력하세요:
{{
  "contrast_pairs": [
    {{
      "type": "A",
      "article_1_id": 기사ID1,
      "article_2_id": 기사ID2,
      "quote_1": "기사 1에서 대비를 보여주는 핵심 문장",
      "quote_2": "기사 2에서 대비를 보여주는 핵심 문장",
      "gap_summary": "이 대비가 의미하는 것 (1-2문장, 추론 표현 사용)",
      "reading_angle": "이 대비를 해석하는 관점"
    }}
  ]
}}

[규칙]
1. quote_1, quote_2는 반드시 위 기사 요약에서 직접 인용하세요. 새로 만드지 마세요.
2. type은 A(뉴스-vs-뉴스), B(뉴스-vs-통념), C(시간대-변화) 중 하나
3. gap_summary에는 "~할 수 있다", "~가능성이 있다" 같은 추론 표현을 사용하세요.
4. 구체적 숫자나 고유명사를 새로 만들지 마세요.
5. article_1_id, article_2_id는 위 [기사 ID xxx]의 숫자를 그대로 사용하세요.
6. 반드시 JSON만 출력하세요."""


def _parse_evidence(raw_text: str) -> list[dict]:
    """LLM 출력에서 근거 문장 JSON 파싱."""
    cleaned = re.sub(r'```json\s*', '', raw_text)
    cleaned = re.sub(r'```\s*', '', cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start >= 0 and end > start:
            try:
                data = json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                logger.warning("evidence_parse_failed: invalid JSON")
                return []
        else:
            return []

    pairs = data.get("contrast_pairs", [])
    validated = []
    for p in pairs:
        if p.get("type") not in ("A", "B", "C"):
            continue
        if not p.get("quote_1") or not p.get("gap_summary"):
            continue
        validated.append(p)

    return validated


# ---------------------------------------------------------------------------
# Diversity filter — 주제 중복 방지
# ---------------------------------------------------------------------------

def _extract_topic_tokens(topic: str) -> set[str]:
    """주제에서 핵심 토큰 추출 (2글자 이상)."""
    tokens = set(re.findall(r'[가-힣]{2,}|[a-zA-Z]{2,}', topic))
    # 불용어 제외
    stopwords = {"vs", "그리고", "하지만", "그러나", "대한", "관한", "위한", "에서", "으로"}
    return tokens - stopwords


def _diversity_filter(candidates: list[dict], max_overlap_ratio: float = 0.5) -> list[dict]:
    """
    이미 선택된 대비 쌍과 주제가 겹치는 후보를 제외.

    Args:
        candidates: 대비 후보 목록 (이미 정렬됨)
        max_overlap_ratio: 토큰 겹침 허용 비율 (0.5 = 절반 이상 겹치면 제외)

    Returns:
        다양성이 보장된 후보 목록
    """
    if not candidates:
        return []

    selected = []
    used_tokens: list[set[str]] = []

    for c in candidates:
        topic = c.get("topic", "") + " " + c.get("contrast_frame", "")
        tokens = _extract_topic_tokens(topic)

        if not tokens:
            selected.append(c)
            continue

        # 기존 선택된 것들과 겹침 검사
        is_diverse = True
        for prev_tokens in used_tokens:
            if not prev_tokens:
                continue
            overlap = tokens & prev_tokens
            smaller = min(len(tokens), len(prev_tokens))
            if smaller > 0 and len(overlap) / smaller > max_overlap_ratio:
                is_diverse = False
                logger.info("diversity_dropped: '%s' overlaps with previous (overlap=%d/%d)",
                           c.get("topic", ""), len(overlap), smaller)
                break

        if is_diverse:
            selected.append(c)
            used_tokens.append(tokens)

    return selected


def find_contrast_evidence(cluster: dict, articles: list[dict]) -> list[dict]:
    """
    Stage 2: 특정 클러스터의 대비 근거 문장 추출.

    Returns:
        list[dict]: 대비 쌍 목록 (type, article_1_index, article_2_index, quote_1, quote_2, gap_summary, reading_angle)
    """
    prompt = _build_evidence_prompt(cluster, articles)
    if not prompt:
        return []

    messages = [{"role": "user", "content": prompt}]

    raw = chat_completion(
        messages=messages,
        system_prompt="당신은 한국어 AI 뉴스 분석 전문가입니다. JSON만 출력하세요.",
        temperature=0.3,
        max_tokens=2000,
        model_override=None,
    )

    if not raw:
        return []

    pairs = _parse_evidence(raw)
    logger.info("evidence_found: %d pairs in cluster '%s'", len(pairs), cluster.get("topic", ""))
    return pairs


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def find_contrast_candidates(articles: list[dict]) -> list[dict]:
    """
    전체 대비 후보 탐색: 클러스터링 → 근거 추출.

    Returns:
        list[dict]: 대비 쌍 후보 목록
            - topic: 클러스터 주제
            - contrast_frame: 대비 설명
            - type: A/B/C
            - source_articles: 관련 기사 목록 [{id, title, source, pub_date, link}]
            - quote_1, quote_2, gap_summary, reading_angle
    """
    # Stage 1: 클러스터링
    clusters = find_clusters(articles)
    if not clusters:
        logger.info("no_contrast_clusters_found")
        return []

    # Stage 2: 각 클러스터에서 근거 추출
    all_candidates = []
    for cluster in clusters:
        pairs = find_contrast_evidence(cluster, articles)
        for pair in pairs:
            # 기사 ID로 정보 매핑
            id1 = pair.get("article_1_id")
            id2 = pair.get("article_2_id")
            id_to_art = {art.get("id"): art for art in articles}
            source_articles = []
            for aid in [id1, id2]:
                art = id_to_art.get(aid)
                if art:
                    source_articles.append({
                        "id": art.get("id"),
                        "title": art.get("title", ""),
                        "source": art.get("source", ""),
                        "pub_date": art.get("pub_date", ""),
                        "link": art.get("link", ""),
                    })

            candidate = {
                "topic": cluster.get("topic", ""),
                "contrast_frame": cluster.get("contrast_frame", ""),
                "type": pair.get("type", "A"),
                "source_articles": source_articles,
                "quote_1": pair.get("quote_1", ""),
                "quote_2": pair.get("quote_2", ""),
                "gap_summary": pair.get("gap_summary", ""),
                "reading_angle": pair.get("reading_angle", ""),
                "category": cluster.get("category", ""),
            }
            all_candidates.append(candidate)

    #多样性 필터: 주제 중복 제거
    filtered = _diversity_filter(all_candidates)
    logger.info("total_contrast_candidates: %d → after diversity filter: %d",
                len(all_candidates), len(filtered))
    return filtered


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI: python3 scripts/contrast_cluster_finder.py [--from-json FILE]"""
    import argparse
    parser = argparse.ArgumentParser(description="대비 클러스터 탐지")
    parser.add_argument("--from-json", type=str, help="JSON 파일에서 기사 목록 로드")
    args = parser.parse_args()

    if args.from_json:
        with open(args.from_json, "r", encoding="utf-8") as f:
            articles = json.load(f)
    else:
        from scripts.weekly_contrast_collector import collect_weekly_articles
        articles = collect_weekly_articles()

    if not articles:
        print("No articles to analyze.")
        return

    print(f"\nAnalyzing {len(articles)} articles for contrast patterns...\n")

    candidates = find_contrast_candidates(articles)

    if not candidates:
        print("No contrast candidates found.")
        return

    print(f"\n{'='*60}")
    print(f"발견된 대비 후보: {len(candidates)}건")
    print(f"{'='*60}")

    for i, c in enumerate(candidates, 1):
        print(f"\n[{i}] {c['topic']}")
        print(f"    타입: {c['type']} | 프레임: {c['contrast_frame']}")
        print(f"    근거1: {c['quote_1'][:80]}...")
        if c['quote_2']:
            print(f"    근거2: {c['quote_2'][:80]}...")
        print(f"    해석: {c['gap_summary'][:100]}...")
        for art in c['source_articles']:
            print(f"    기사: {art['title']} ({art['source']})")

    # JSON 출력
    output_path = os.path.join(_PROJECT_ROOT, "tmp_test", "contrast_candidates.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
