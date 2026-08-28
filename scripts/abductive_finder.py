#!/usr/bin/env python3
"""어긋남 후보 생성 (S1) — 뉴스 간/통념과의/시점의 어uteness 탐지"""

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
from evidence_checker import check_gap_fidelity


ABDUCTION_MODEL = os.environ.get("ABDUCTION_MODEL", "gpt-4o-mini")


def verify_quote(quote: str, source_text: str) -> bool:
    """공백 정규화 후 source_text에 quote가 포함되는지 확인"""
    def normalize(t):
        return re.sub(r'\s+', ' ', t).strip()
    return normalize(quote) in normalize(source_text)


def _build_prompt(selected_items: list[dict]) -> str:
    """뉴스 6건 → LLM 프롬프트 생성. body는 1500자까지."""
    news_blocks = []
    for i, item in enumerate(selected_items, 1):
        title = item.get("title", "")
        body = item.get("body") or item.get("summary") or ""
        body = body[:1500]
        news_blocks.append(f"[뉴스 {i}] 제목: {title}\n본문: {body}")

    return (
        "아래는 오늘 선정한 AI 뉴스 6건의 제목과 본문이다.\n\n"
        + "\n\n".join(news_blocks)
        + "\n\n"
        "다음 세 종류의 '어긋남'을 찾아라. 각각 최소 1개, 최대 2개씩:\n\n"
        "A. 뉴스 간 어uteness: 두 뉴스의 주장이나 전제가 서로 충돌하거나, 동시에 참이기 어려워 보이는 조합\n"
        "B. 통념과의 어uteness: AI 업계의 일반적 통념(\"AI는 ~할 것이다\")과 이 뉴스의 내용이 어uteness하는 지점\n"
        "C. 시점의 어uteness: 1~2년 전의 예측이나 약속과 비교했을 때 예상과 다르게 흘러가고 있는 신호\n\n"
        "각 항목은 다음 형식의 JSON으로만 응답하라:\n"
        "{\n"
        '  "candidates": [\n'
        "    {\n"
        '      "type": "A" | "B" | "C",\n'
        '      "source_item_ids": ["1", "2"],\n'
        '      "quote_1": "본문에서 그대로 복사한 문장",\n'
        '      "quote_2": "본문에서 그대로 복사한 문장 또는 통념 진술",\n'
        '      "gap_summary": "1~2문장 평서체",\n'
        '      "verification_path": "어떤 뉴스가 나오면 이 가설이 검증되는가"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "단, 원인이나 해석은 절대 쓰지 마라. 관측만 보고하라."
    )


def _parse_candidates(raw_text: str) -> list[dict]:
    """LLM 응답에서 candidates JSON 파싱"""
    text = raw_text.strip()
    # 마크다운 코드 블록 제거
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return data.get("candidates", [])


def _verify_and_filter(candidates: list[dict], selected_items: list[dict]) -> list[dict]:
    """인용문 검증 + 필터링. Type B는 quote_2 검증 면제."""
    # id → item 매핑
    id_to_item = {}
    for item in selected_items:
        item_id = str(item.get("id", ""))
        id_to_item[item_id] = item
        # also map 1-based index strings
        idx = str(selected_items.index(item) + 1)
        id_to_item[idx] = item

    verified = []
    for c in candidates:
        ctype = c.get("type", "")
        if ctype not in ("A", "B", "C"):
            continue
        source_ids = c.get("source_item_ids", [])
        if not source_ids:
            continue

        # quote_1 검증
        q1 = c.get("quote_1", "")
        if not q1:
            continue
        q1_pass = False
        for sid in source_ids:
            item = id_to_item.get(str(sid))
            if item:
                body = item.get("body") or item.get("summary") or ""
                if verify_quote(q1, body):
                    q1_pass = True
                    break
        if not q1_pass:
            logger.info("dropped_by_quote_verification: quote_1 mismatch for type=%s ids=%s", ctype, source_ids)
            continue

        # quote_2 검증 (Type B는 면제)
        if ctype != "B":
            q2 = c.get("quote_2", "")
            if q2:
                q2_pass = False
                for sid in source_ids:
                    item = id_to_item.get(str(sid))
                    if item:
                        body = item.get("body") or item.get("summary") or ""
                        if verify_quote(q2, body):
                            q2_pass = True
                            break
                if not q2_pass:
                    logger.info("dropped_by_quote_verification: quote_2 mismatch for type=%s ids=%s", ctype, source_ids)
                    continue

        # gap_summary 충성도 검증: 인용문+원문 범위를 벗어나는 주장 포함 여부
        gap = c.get("gap_summary", "")
        q1 = c.get("quote_1", "")
        q2 = c.get("quote_2", "") if ctype != "B" else ""
        combined_source = ""
        for sid in source_ids:
            item = id_to_item.get(str(sid))
            if item:
                combined_source += " " + (item.get("body") or item.get("summary") or "")
        if not check_gap_fidelity(gap, q1, q2, combined_source):
            logger.info("dropped_by_gap_fidelity: gap_summary超出 source范围 for type=%s ids=%s", ctype, source_ids)
            continue

        verified.append(c)

    return verified


def find_abduction_candidates(selected_items: list[dict]) -> list[dict]:
    """어긋남 후보 생성 메인 함수.

    Args:
        selected_items: auto_news_selector.py main() 반환값 (6건)

    Returns:
        검증 통과한 후보 리스트 (빈 리스트 가능)
    """
    if not selected_items:
        return []

    prompt = _build_prompt(selected_items)
    system_prompt = (
        "당신은 AI 뉴스 분석 전문가입니다. "
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

    candidates = _parse_candidates(raw)
    if not candidates:
        return []

    verified = _verify_and_filter(candidates, selected_items)
    return verified


if __name__ == "__main__":
    # 간이 테스트: 샘플 입력으로 LLM 호출
    sample = [
        {"id": "1", "title": "OpenAI, GPT-5 출시 발표", "body": "OpenAI가 GPT-5를 공개하며 성능 대폭 향상을 주장했다.", "source": "TechCrunch", "url": "https://example.com/1"},
        {"id": "2", "title": "구글, Gemini 2.0 업데이트", "body": "구글은 Gemini 2.0이 GPT-5와 대등한 성능을 보인다고 발표했다.", "source": "The Verge", "url": "https://example.com/2"},
        {"id": "3", "title": "AI 규제 강화 논의", "body": "유럽연합이 AI 모델에 대한 엄격한 규제안을 발표했다.", "source": "Reuters", "url": "https://example.com/3"},
        {"id": "4", "title": "AI 일자리 대체 우려", "body": "최근 연구에서 AI가 향후 5년 내 사무직의 30%를 대체할 수 있다고 발표했다.", "source": "Bloomberg", "url": "https://example.com/4"},
        {"id": "5", "title": "AI 스타트업 투자 감소", "body": "2분기 AI 스타트업 투자가 전 분기 대비 40% 감소했다.", "source": "Crunchbase", "url": "https://example.com/5"},
        {"id": "6", "title": "AI 에너지 소비 증가", "body": "대규모 AI 모델 학습에 사용되는 전력이 연간 2배로 증가했다는 보고가 나왔다.", "source": "Nature", "url": "https://example.com/6"},
    ]
    results = find_abduction_candidates(sample)
    print(json.dumps(results, ensure_ascii=False, indent=2))
