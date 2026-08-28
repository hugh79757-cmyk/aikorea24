#!/usr/bin/env python3
"""가설 생성기 (S2) — 어긋남 후보에 대해 관점별 가설 생성"""

import difflib
import json
import logging
import os
import re
import sys

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.join(_SCRIPT_DIR, 'threads', 'v3'))
from model_router import chat_completion
from evidence_checker import check_evidence


ABDUCTION_MODEL = os.environ.get("ABDUCTION_MODEL", "gpt-4o-mini")

PERSPECTIVES = [
    "기술적 한계", "시장 과열", "규제/정치", "한국 시장 특수성",
    "사용자 행동", "경쟁 구도", "미디어 과장", "시간차",
    "이해관계자 충돌", "정의의 문제",
]

MIN_HYPOTHESES = 5
DEDUPE_THRESHOLD = 0.8


def _build_prompt(candidate: dict, selected_items: list[dict]) -> str:
    """어긋남 후보 1건 + 관련 뉴스 → LLM 프롬프트 생성. 본문 800자 제한."""
    # 관련 뉴스 본문 수집
    ref_ids = candidate.get("source_item_ids", [])
    ref_blocks = []
    for item in selected_items:
        item_id = str(item.get("id", ""))
        if item_id in ref_ids:
            title = item.get("title", "")
            body = item.get("body") or item.get("summary") or ""
            body = body[:800]
            ref_blocks.append(f"[뉴스 {item_id}] 제목: {title}\n본문: {body}")

    return (
        "당신은 AI 산업 분석가다. 아래 어긋남(gap)에 대해 "
        "10개 관점에서 각각 하나씩, 총 10개의 가설을 작성하라.\n\n"
        "## 어긋남\n"
        f"- 유형: {candidate.get('type', '')}\n"
        f"- 요약: {candidate.get('gap_summary', '')}\n"
        f"- 근거 인용문 1: {candidate.get('quote_1', '')}\n"
        f"- 근거 인용문 2: {candidate.get('quote_2', '')}\n"
        f"- 검증 경로: {candidate.get('verification_path', '')}\n\n"
        "## 관련 뉴스\n\n"
        + "\n\n".join(ref_blocks)
        + "\n\n"
        "## 10개 관점\n"
        + "\n".join(f"{i+1}. {p}" for i, p in enumerate(PERSPECTIVES))
        + "\n\n"
        "## 규칙 (반드시 지켜라)\n"
        "1. 관점당 가설 1개. 앞 가설과 같은 메커니즘의 변형은 새 가설로 세우지 마라.\n"
        "2. falsifiable_news는 반드시 구체적인 미래 뉴스 형태로 써라.\n"
        "   나쁜 예: '시장이 안정될 것이다'\n"
        "   좋은 예: '앤스로픽이 컴퓨팅 계약 규모를 축소 재협상했다는 보도'\n"
        "3. 어떤 가설이 맞는지 판단하지 마라. 가능성을 넓히는 단계다.\n"
        "4. 원인이나 해석이 아닌 관측만 보고하라.\n"
        "5. ★★★ 근거 규칙: one_line에는 반드시 원문 뉴스에 명시된 사실만 사용하라.\n"
        "   - 구체적 수치(2년, 450억, 30%)를 원문에 없으면 절대 넣지 마라.\n"
        "   - 원문에 없는 고유명사(국가명, 기관명)를 추가하지 마라.\n"
        "   - 추론이나 예측은 반드시 '~할 것으로 예상된다', '~할 가능성이 있다',\n"
        "     '~될 수 있다' 등의 추론 표현을 사용하라. 현재 시제로 단정하지 마라.\n"
        "   - 원문에 없는 사실을 추가하면 검증에서 즉시 폐기된다.\n\n"
        "## 출력 형식 (JSON만 출력)\n"
        "{\n"
        '  "hypotheses": [\n'
        "    {\n"
        '      "perspective": "기술적 한계",\n'
        '      "one_line": "가설 한 줄 요약",\n'
        '      "falsifiable_news": "구체적 미래 뉴스 형태",\n'
        '      "confidence": "상 | 중 | 하"\n'
        "    }\n"
        "  ]\n"
        "}"
    )


def _parse_hypotheses(raw_text: str) -> list[dict]:
    """LLM 응답에서 hypotheses JSON 파싱"""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return data.get("hypotheses", [])


def _dedupe(hypotheses: list[dict]) -> list[dict]:
    """one_line 유사도로 중복 제거. ratio > 0.8이면 후순위 폐기."""
    kept = []
    for h in hypotheses:
        one_line = h.get("one_line", "")
        is_dup = False
        for existing in kept:
            existing_line = existing.get("one_line", "")
            ratio = difflib.SequenceMatcher(None, one_line, existing_line).ratio()
            if ratio > DEDUPE_THRESHOLD:
                is_dup = True
                break
        if not is_dup:
            kept.append(h)
    return kept


def generate_hypotheses(candidate: dict, selected_items: list[dict]) -> list[dict]:
    """가설 생성 메인 함수.

    Args:
        candidate: find_abduction_candidates()가 반환한 후보 1건
        selected_items: 원본 뉴스 6건

    Returns:
        가설 리스트 (빈 리스트 가능)
    """
    if not candidate or not selected_items:
        return []

    prompt = _build_prompt(candidate, selected_items)
    system_prompt = (
        "당신은 AI 산업 분석 전문가입니다. "
        "중국어(한자)를 절대 사용하지 마세요. 모든 내용을 순수 한국어로만 작성하세요."
    )

    try:
        raw = chat_completion(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.warning("LLM 호출 실패: %s", e)
        return []

    if not raw:
        return []

    hypotheses = _parse_hypotheses(raw)
    if not hypotheses:
        return []

    # perspective 검증: 유효한 관점만 유지
    valid = [h for h in hypotheses if h.get("perspective") in PERSPECTIVES]

    # dedupe
    deduped = _dedupe(valid)

    # 근거 검증: one_line이 원문에 기반하는지 확인
    # LLM은 위치 인덱스("1","2")를 반환하므로, 실제 ID와 인덱스 둘 다 매핑
    ref_ids = candidate.get("source_item_ids", [])
    ref_set = set(str(r) for r in ref_ids)
    # 인덱스 매핑: "1"→items[0], "2"→items[1], ...
    for i, item in enumerate(selected_items):
        ref_set.add(str(i + 1))
        ref_set.add(str(item.get("id", "")))
    source_text = ""
    for item in selected_items:
        item_id = str(item.get("id", ""))
        idx = str(selected_items.index(item) + 1)
        if item_id in ref_set or idx in ref_set:
            source_text += " " + (item.get("body") or item.get("summary") or "")

    verified = []
    for h in deduped:
        one_line = h.get("one_line", "")
        if check_evidence(one_line, source_text, threshold=0.4, min_matched=3):
            verified.append(h)
        else:
            logger.info("dropped_by_evidence_verification: one_line='%s'", one_line[:80])

    # 5개 미만이면 빈 리스트
    if len(verified) < MIN_HYPOTHESES:
        logger.info("hypotheses_below_minimum: %d < %d, returning []", len(verified), MIN_HYPOTHESES)
        return []

    return verified


if __name__ == "__main__":
    # 간이 테스트: S1 샘플 결과로 LLM 호출
    sample_candidate = {
        "type": "A",
        "source_item_ids": ["1", "2"],
        "quote_1": "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다.",
        "quote_2": "구글은 Gemini 2.0이 GPT-5와 대등한 성능을 보인다고 발표했다.",
        "gap_summary": "OpenAI는 GPT-5가 압도적 우위를 점한다고 주장하는 반면, 구글은 대등하다고 발표한다.",
        "verification_path": "양사 모델의 벤치마크 비교 결과가 나오면 검증 가능",
    }
    sample_items = [
        {"id": "1", "title": "OpenAI, GPT-5 출시 발표", "body": "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다.", "source": "TechCrunch"},
        {"id": "2", "title": "구글, Gemini 2.0 업데이트", "body": "구글은 Gemini 2.0이 GPT-5와 대등한 성능을 보인다고 발표했다.", "source": "The Verge"},
    ]
    results = generate_hypotheses(sample_candidate, sample_items)
    print(json.dumps(results, ensure_ascii=False, indent=2))
