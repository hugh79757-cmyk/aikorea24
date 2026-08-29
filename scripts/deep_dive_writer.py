#!/usr/bin/env python3
"""
S2: 심층 분석 작성 — 대비 쌍을 5단락 분석체 블로그 포스트로 작성.

입력: contrast_candidates (contrast_cluster_finder 출력) + 해당 기사 본문
출력: dict with keys: title, body (markdown), tags, source_links

모델: 이 단계만 gpt-4o 또는 상위 모델 사용 (품질 우선)
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
from scripts.abductive_finder import verify_quote

logger = get_scrubbed_logger(__name__)

# 심층 분석용 모델 — 품질 우선
DEEP_DIVE_MODEL = os.environ.get("DEEP_DIVE_MODEL", "gpt-4o")


# ---------------------------------------------------------------------------
# 프롬프트 빌드
# ---------------------------------------------------------------------------

def _build_writing_prompt(candidate: dict, articles_with_body: list[dict]) -> str:
    """
    대비 쌍 + 기사 본문 → 심층 분석 글쓰기 프롬프트.

    articles_with_body: [{id, title, body, source, pub_date, link}, ...]
    """
    article_blocks = []
    for i, art in enumerate(articles_with_body, 1):
        body = (art.get("body") or "")[:3000]
        article_blocks.append(
            f"[기사 {i}] {art['title']}\n"
            f"출처: {art['source']} | 날짜: {art.get('pub_date', '')}\n"
            f"본문:\n{body}"
        )

    articles_text = "\n\n---\n\n".join(article_blocks)

    # 근거 문장 강조
    evidence_lines = []
    if candidate.get("quote_1"):
        evidence_lines.append(f"근거 1: {candidate['quote_1']}")
    if candidate.get("quote_2"):
        evidence_lines.append(f"근거 2: {candidate['quote_2']}")
    evidence_text = "\n".join(evidence_lines) if evidence_lines else "(근거 문장 없음)"

    return f"""당신은 한국어 AI 뉴스 심층 분석 전문기자입니다. 아래 대비 구조를 분석해서 5단락 분석체 블로그 포스트를 작성해주세요.

[대비 주제] {candidate.get('topic', '')}
[대비 프레임] {candidate.get('contrast_frame', '')}
[해석 관점] {candidate.get('reading_angle', '')}

[원문 근거]
{evidence_text}

[기사 본문]
{articles_text}

[출력 형식]
다음 구조로 작성하되, 두 기사를 나란히 요약하는 '병렬 나열'이 아니라 하나의 통합된 분석 논리로 엮어 작성하세요. 각 소제목(H2)은 내용을 자연스러운 한국어 문장/구문으로 요약하고, 'A측', 'B측', '대비', '측:' 같은 기계적 라벨이나 구조 지시어를 절대 사용하지 마세요. 각 본문 섹션은 최소 6문장 이상으로 충분히 전개하세요.

TITLE: SEO 친화적 제목 (25자 이내)

--- (구분선)

## [도입 소제목: 이 대비가 왜 주목할 만한지 한 문장으로, 예: "효율성과 인간 가치, 맞서 있는 두 시각"]
배경과 쟁점의 의미를 3-4문장으로 소개.

## [두 입장이 부딪히는 지점을 자연스러운 소제목으로, 예: "편의성을 앞세운 혁신과 보호를 강조하는 당국"]
기사 1과 기사 2의 입장을 교차 대조하며 서술하세요. 각 기사의 핵심 주장을 원문 인용(" ")과 함께 제시하고, 두 입장이 어디서 충돌하는지 명시하세요. 인용 2개 이상 포함, 6-8문장.

## [분석 소제목을 자연스러운 문장으로, 예: "충돌이 생긴 배경"]
표면적 차이를 넘어 이 긴장을 만드는 근본 동인(시장 흐름, 규제의 한계, 기술 궤적 등)을 추론하세요. "~할 수 있다", "~가능성이 있다" 표현 사용. 구체적 숫자나 고유명사를 새로 만들지 마세요. 6-8문장.

## [전망 소제목을 자연스러운 문장으로, 예: "향후 전망"]
falsifiable한 전망을 제시하세요. 구체적 future 뉴스 이벤트로 검증 가능해야 하며, 독자가 주목할 지점을 4-5문장으로 정리.

[규칙]
1. 모든 인용은 위 원문 근거에서 직접 인용하세요. 따옴표(" ")로 감싸세요.
2. 직접 인용이 아닌 경우 반드시 "기사에 따르면", "보도에 의하면" 등으로 명시하세요.
3. 추론과 사실을 명확히 구분하세요.
4. "~할 수 있다", "~가능성이 있다", "~보인다" 같은 추론 표현을 사용하세요.
5. 소제목(H2)에는 'A측', 'B측', '대비', '측:' 등의 구조 지시어나 기계적 라벨을 절대 사용하지 마세요. 소제목은 해당 단락 내용을 자연스러운 한국어로 요약한 문장이어야 합니다.
6. 구체적 숫자, 고유명사, 통계를 새로 만들지 마세요.
7. 한국어로 작성하세요.
8. 원문 기사 링크를 글 하단에 포함하세요.
9. 제목은 25자 이내, SEO 친화적으로 작성하세요.
10. [중요] 모든 인용문은 반드시 위 원문 근거에서 발췌한 것이어야 합니다. 2차 해석, 일반적 지식, 재구성된 문장은 절대 사용하지 마세요. 인용문이 원문에 존재하지 않으면 해당 인용은 따옴표 없이 서술형으로 작성하세요.
11. 두 기사를 단순히 나열(기사1 요약 → 기사2 요약)하지 마세요. 하나의 분석 주제 아래 교차 대조하고 통합하세요."""


# ---------------------------------------------------------------------------
# 파싱
# ---------------------------------------------------------------------------

def _parse_deep_dive(raw_text: str) -> Optional[dict]:
    """LLM 출력에서 제목 + 본문 파싱."""
    if not raw_text:
        return None

    # TITLE: 라인 추출
    title_match = re.search(r'^TITLE:\s*(.+)$', raw_text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    # --- 구분선 이후를 본문으로
    parts = raw_text.split('---', 1)
    body = parts[1].strip() if len(parts) > 1 else raw_text

    # 제목이 없으면 본문에서 ## 첫 번째를 제목으로
    if not title:
        h2_match = re.search(r'^##\s+(.+)$', body, re.MULTILINE)
        if h2_match:
            title = h2_match.group(1).strip()

    if not title or len(body) < 100:
        logger.warning("deep_dive_parse_failed: title=%s body_len=%d", title, len(body))
        return None

    # 태그 추출 (H2 제목에서)
    tags = ["weekly-analysis", "contrast"]
    h2_matches = re.findall(r'^##\s+(.+)$', body, re.MULTILINE)
    for h2 in h2_matches:
        # 핵심 키워드만 태그로
        for kw in ["규제", "투자", "기술", "시장", "경쟁", "정책", "윤리"]:
            if kw in h2:
                tags.append(kw)
                break

    # 원문 링크 추출
    source_links = re.findall(r'https?://[^\s\)]+', body)

    return {
        "title": title,
        "body": body,
        "tags": list(set(tags)),
        "source_links": source_links,
    }


# ---------------------------------------------------------------------------
# 본문 크롤링 (선택적)
# ---------------------------------------------------------------------------

def _crawl_article_body(url: str) -> str:
    """기사 본문 크롤링 (간단한 requests + BeautifulSoup)."""
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {"User-Agent": "Mozilla/5.0 (compatible; AikoreaBot/1.0)"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # 불필요 태그 제거
        for tag in soup.find_all(["script", "style", "nav", "footer", "aside"]):
            tag.decompose()

        # 본문 영역 추출 (common patterns)
        article = (
            soup.find("article") or
            soup.find("div", class_=re.compile(r"(content|article|body|post)", re.I)) or
            soup.find("main") or
            soup.body
        )

        if article:
            text = article.get_text(separator="\n", strip=True)
            # 너무 짧으면 실패
            if len(text) < 100:
                return ""
            return text[:5000]  # 5000자로 제한

        return ""
    except Exception as e:
        logger.warning("crawl_failed: %s — %s", url, e)
        return ""


def _ensure_bodies(candidate: dict) -> list[dict]:
    """
    대비 쌍 기사에 body 추가.
    body가 없으면 (description만 있는 경우) 크롤링 시도.
    """
    articles = candidate.get("source_articles", [])
    result = []

    for art in articles:
        body = art.get("body", "")
        if not body and art.get("link"):
            logger.info("crawling_body: %s", art["title"][:50])
            body = _crawl_article_body(art["link"])

        result.append({
            "id": art.get("id"),
            "title": art.get("title", ""),
            "body": body,
            "description": art.get("description", ""),
            "source": art.get("source", ""),
            "pub_date": art.get("pub_date", ""),
            "link": art.get("link", ""),
        })

    return result


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def write_deep_dive(candidate: dict) -> Optional[dict]:
    """
    대비 쌍을 심층 분석 블로그 포스트로 작성.

    Args:
        candidate: contrast_cluster_finder 출력의 대비 후보

    Returns:
        dict: {title, body, tags, source_links, quality_judgment} or None
    """
    # 기사 본문 확보
    articles_with_body = _ensure_bodies(candidate)

    # 본문이 있는 기사가 2개 미만이면 불가
    valid = [a for a in articles_with_body if a.get("body")]
    if len(valid) < 2:
        logger.warning("insufficient_bodies: %d/%d articles have body text",
                       len(valid), len(articles_with_body))
        # description fallback: body 대신 description 사용
        for a in articles_with_body:
            if not a.get("body"):
                a["body"] = a.get("title", "") + ". " + a.get("source", "")
        # 재검증
        valid = [a for a in articles_with_body if a.get("body")]
        if len(valid) < 2:
            return None

    prompt = _build_writing_prompt(candidate, articles_with_body)

    messages = [{"role": "user", "content": prompt}]

    raw = chat_completion(
        messages=messages,
        system_prompt="당신은 한국어 AI 뉴스 심층 분석 전문기자입니다. 원문 근거에 기반한 분석만 작성하세요.",
        temperature=0.5,
        max_tokens=6000,
        model_override=None,
    )

    if not raw:
        logger.warning("deep_dive_llm_failed")
        return None

    result = _parse_deep_dive(raw)
    if not result:
        return None

    # source_links: candidate의 source_articles에서 직접 추출 (regex 의존성 제거)
    source_links = []
    for art in candidate.get("source_articles", []):
        link = art.get("link", "")
        if link and link not in source_links:
            source_links.append(link)
    result["source_links"] = source_links

    # 인용 검증: body에 따옴표로 감싼 직접 인용이 있는지 확인
    quotes_in_body = re.findall(r'"([^"]+)"', result["body"])

    # 다중 소스: 영어 본문 > D1 description > 기사 제목 순으로 결합
    source_combined = " ".join(
        (a.get("body") or "") + " " + (a.get("description") or "") + " " + (a.get("title") or "")
        for a in articles_with_body
    )

    verified_quotes = 0
    unverified_quotes = 0
    hallucinated_quotes = []
    for q in quotes_in_body:
        if len(q) < 10:
            continue
        # 1차: 정확한 substring 매칭 (영어 본문 + description)
        if verify_quote(q, source_combined):
            verified_quotes += 1
        else:
            # 2차: 핵심 토큰 매칭 (패러프레이즈 허용)
            from scripts.evidence_checker import check_evidence
            if check_evidence(q, source_combined, threshold=0.35, min_matched=3):
                verified_quotes += 1
                logger.info("quote_verified_by_token: %s...", q[:60])
            else:
                unverified_quotes += 1
                hallucinated_quotes.append(q)
                logger.warning("unverified_quote: %s...", q[:60])

    # 품질 판단
    quality = _assess_quality(candidate, result, verified_quotes, unverified_quotes, hallucinated_quotes)
    result["quality_judgment"] = quality

    if result:
        logger.info("deep_dive_written: %s (%d chars) [quality: %s]",
                     result["title"], len(result["body"]), quality["verdict"])
    return result


def _assess_quality(candidate: dict, result: dict,
                    verified_quotes: int, unverified_quotes: int,
                    hallucinated_quotes: list[str] = None) -> dict:
    """생성된 deep dive의 품질 판단."""
    issues = []
    verdict = "추천"
    hallucinated_quotes = hallucinated_quotes or []

    # 환각 인용 검증: 미검증 인용이 있으면 원문 대조
    if hallucinated_quotes:
        # 원문 결합
        source_articles = candidate.get("source_articles", [])
        source_texts = " ".join(
            (a.get("body", "") + " " + a.get("description", "") + " " + a.get("title", ""))
            for a in source_articles
        )
        truly_hallucinated = []
        for q in hallucinated_quotes:
            from scripts.evidence_checker import check_evidence
            if not check_evidence(q, source_texts, threshold=0.3, min_matched=2):
                truly_hallucinated.append(q)

        if truly_hallucinated:
            issues.append(f"환각 인용 {len(truly_hallucinated)}건 (원문에 존재하지 않는 인용)")
            verdict = "폐기"
        elif unverified_quotes > 0:
            issues.append(f"패러프레이즈 인용 {unverified_quotes}건 (의미 보존 확인 필요)")

    elif unverified_quotes > 0:
        issues.append(f"미검증 인용 {unverified_quotes}건 (원문 대조 필요)")

    if verified_quotes == 0 and unverified_quotes == 0:
        issues.append("직접 인용 없음 (추론으로만 구성)")
        # 추론만으로 구성된 기사는 발행 불가 → 보류 (사람 검토용)
        if verdict != "폐기":
            verdict = "보류"

    # source_links 확인
    if not result.get("source_links"):
        issues.append("출처 링크 없음")
        verdict = "보류"

    # 주제 구체성 확인
    topic = candidate.get("topic", "")
    generic_terms = {"혁신 vs 위협", "긍정 vs 부정", "기대 vs 우려", "AI의 두 얼굴"}
    if any(g in topic for g in generic_terms):
        issues.append("주제가 너무 일반적")
        verdict = "폐기"

    # 근거 문장 존재 확인
    if not candidate.get("quote_1"):
        issues.append("근거 문장(quote_1) 없음")
        verdict = "폐기"

    return {
        "verdict": verdict,
        "issues": issues,
        "verified_quotes": verified_quotes,
        "unverified_quotes": unverified_quotes,
        "hallucinated_quotes": len(truly_hallucinated) if hallucinated_quotes else 0,
        "source_links_count": len(result.get("source_links", [])),
    }


def write_all_deep_dives(candidates: list[dict], max_writes: int = 2) -> list[dict]:
    """
    여러 대비 쌍에 대해 심층 분석 작성.

    Args:
        candidates: 대비 후보 목록
        max_writes: 최대 작성 수 (기본 2건)

    Returns:
        list[dict]: 작성된 심층 분석 목록
    """
    results = []
    for candidate in candidates[:max_writes]:
        dive = write_deep_dive(candidate)
        if dive:
            dive["candidate"] = candidate  # 원본 후보 연결
            results.append(dive)

    logger.info("deep_dives_written: %d/%d", len(results), min(len(candidates), max_writes))
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI: python3 scripts/deep_dive_writer.py [--from-json FILE] [--max N]"""
    import argparse
    parser = argparse.ArgumentParser(description="심층 분석 작성")
    parser.add_argument("--from-json", type=str, help="대비 후보 JSON 파일")
    parser.add_argument("--max", type=int, default=2, help="최대 작성 수")
    args = parser.parse_args()

    if args.from_json:
        with open(args.from_json, "r", encoding="utf-8") as f:
            candidates = json.load(f)
    else:
        print("Usage: deep_dive_writer.py --from-json <candidates.json>")
        return

    results = write_all_deep_dives(candidates, max_writes=args.max)

    for i, r in enumerate(results, 1):
        print(f"\n{'='*60}")
        print(f"[{i}] {r['title']}")
        print(f"{'='*60}")
        print(r['body'][:500] + "...")
        print(f"\n태그: {', '.join(r['tags'])}")
        print(f"원문 링크: {len(r['source_links'])}건")

    # JSON 저장
    output_path = os.path.join(_PROJECT_ROOT, "tmp_test", "deep_dives.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        # candidate 필드 제거 (순환 참조 방지)
        clean = [{k: v for k, v in r.items() if k != "candidate"} for r in results]
        json.dump(clean, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    main()
