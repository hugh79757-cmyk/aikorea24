#!/usr/bin/env python3
"""근거 검증 모듈 — LLM 출력이 원문에 기반하는지 확인

검증 계층:
1. 단어 매칭 비율: claim의 핵심 단어 중 source에 매칭되는 비율
2. 구체적 수치 패턴: 숫자+단위(년, 개, %, 억, 조 등)가 source에 없는지 검사
3. 고유명사 검사: 원문에 없는 국가명/기관명/지역명 포함 여부
4. 절대 표현 검사: "완전히", "전혀", "모든" 등 원문 근거 없는 표현 사용 여부
"""

import re


# ── 불용어 (의미 파악에 기여 없는 매우 일반적인 단어) ──────────
KOREAN_STOPWORDS = frozenset([
    # 기존
    "있다", "없다", "하는", "되는", "위해", "대해", "따르면",
    "보면", "있는", "없는", "한", "할", "관한", "위한",
    # 추가
    "것이다", "것은", "될", "의해", "관해", "따라", "통해",
    "으로", "에서", "때문", "관련", "가장", "이번", "그리고",
    "보도", "발표", "소개", "지적", "분석", "전망", "우려",
    "총", "위한", "위한", "이후", "대상", "기반", "중심",
    "측은", "측이", "이런", "저런", "그런", "어떤",
])

# ── 구체적 수치+단위 패턴 ──────────────────────────────────
# 이 패턴이 claim에 있으면 source_text에도 같은 수치+단위가 있어야 함
NUMBER_UNIT_PATTERN = re.compile(
    r'(\d+[\s]*(?:년|개|%|퍼센트|조|억|만|천|달러|원|건|배|명|위|곳|회|차례|이상|이하|미만|초|분|시간|일|월))'
)

# ── 고유명사 (국가명, 주요 기관/지역) ──────────────────────
KNOWN_ENTITIES = [
    # 국가/지역
    "미국", "중국", "일본", "유럽", "유럽연합", "EU", "한국", "영국",
    "독일", "프랑스", "인도", "대만", "이스라엘", "캐나다", "호주",
    "동남아", "아시아", "아프리카", "남반구", "북반구",
    # 주요 기관/기업
    "OpenAI", "Google", "구글", "Apple", "애플", "Microsoft", "마이크로소프트",
    "Meta", "메타", "Amazon", "아마존", "NVIDIA", "엔비디아", "삼성", "SK하이닉스",
    "TSMC", "바이두", "알리바바", "텐센트", "화웨이",
    "유엔", "UN", "EU", "SEC", "FTC", "미 국방부", "백악관",
    "앤스로픽", "Anthropic", "DeepSeek", "딥시크", "xAI", "OpenAI",
]

ENTITY_PATTERN = re.compile(
    '|'.join(re.escape(e) for e in KNOWN_ENTITIES)
)

# ── 절대 표현 패턴 ─────────────────────────────────────────
ABSOLUTE_EXPRESSIONS = [
    "완전히", "전혀", "모든", "항상", "절대", "반드시",
    "모조리", "전부", "일체", "무조건",
]


def _extract_words(text: str) -> list[str]:
    """텍스트에서 내용 단어 추출.

    2글자 이상의 한글 단어, 영어 단어, 숫자 토큰.
    불용어 제외.
    """
    words = re.findall(r'[가-힣]{2,}|[a-zA-Z]{2,}|\d+', text)
    return [w for w in words if w not in KOREAN_STOPWORDS]


def _word_matches_source(word: str, source_words: set[str]) -> bool:
    """단어가 소스 단어들과 형태학적으로 매칭되는지 확인.

    매칭 전략 (우선순위 순):
    1. 부분 문자열 포함: word ⊂ sw 또는 sw ⊂ word
    2. 공통 접두사(2글자+): 한국어 조사 차이를 극복
       "구글이" ↔ "구글은" → 공통 접두사 "구글"
       "주장하여" ↔ "주장했다" → 공통 접두사 "주장"
    """
    if len(word) < 2:
        return False
    for sw in source_words:
        # 전략 1: 부분 문자열 포함
        if word in sw or sw in word:
            return True
        # 전략 2: 공통 접두사 (2글자 이상)
        min_len = min(len(word), len(sw))
        for prefix_len in range(min_len, 1, -1):
            if word[:prefix_len] == sw[:prefix_len]:
                return True
    return False


def _check_specific_numbers(claim: str, source_text: str) -> list[str]:
    """claim에 구체적 수치+단위가 있으면 source에도 있는지 검사.

    Returns:
        원문에 없는 구체적 수치 리스트 (비어있으면 모두 통과)
    """
    claim_numbers = NUMBER_UNIT_PATTERN.findall(claim)
    source_numbers = set(NUMBER_UNIT_PATTERN.findall(source_text))
    missing = []
    for num in claim_numbers:
        # 숫자 부분만 비교 (공백 정규화)
        num_clean = num.strip()
        if num_clean not in source_numbers:
            # 부분 매칭 시도: "200억" vs "200억 달러"
            found = False
            for sn in source_numbers:
                if num_clean in sn or sn in num_clean:
                    found = True
                    break
            if not found:
                missing.append(num_clean)
    return missing


def _check_entities(claim: str, source_text: str) -> list[str]:
    """claim에 원문에 없는 고유명사가 포함되어 있는지 검사.

    Returns:
        원문에 없는 고유명사 리스트 (비어있으면 모두 통과)
    """
    claim_entities = ENTITY_PATTERN.findall(claim)
    source_entities = set(ENTITY_PATTERN.findall(source_text))
    missing = []
    for ent in claim_entities:
        if ent not in source_entities:
            # 접미사 변형 허용: "유럽연합" ⊂ "유럽연합의"
            found = False
            for se in source_entities:
                if ent in se or se in ent:
                    found = True
                    break
            if not found:
                missing.append(ent)
    return missing


def _check_absolute_expressions(claim: str, source_text: str) -> list[str]:
    """claim에 원문 근거 없는 절대 표현이 포함되어 있는지 검사.

    "완전히 장악" → source에 "완전히"가 없으면 경고.
    다만 source에 "완전히"가 있으면 통과.

    Returns:
        원문에 없는 절대 표현 리스트
    """
    missing = []
    for expr in ABSOLUTE_EXPRESSIONS:
        if expr in claim and expr not in source_text:
            missing.append(expr)
    return missing


def check_evidence(
    claim: str,
    source_text: str,
    threshold: float = 0.4,
    min_matched: int = 3,
) -> bool:
    """claim이 source_text에 의해 지지되는지 확인.

    3중 검증:
    1. 단어 매칭 비율: threshold 이상 + min_matched 이상의 단어 매칭
    2. 구체적 수치: claim의 숫자+단위가 source에도 있어야 함
    3. 고유명사: claim의 국가명/기관명이 source에도 있어야 함

    Args:
        claim: 검증할 문장
        source_text: 원문 본문
        threshold: 핵심 단어 중 최소 몇 %가 매칭되어야 하는지
        min_matched: 최소 매칭 단어 수 (범용 단어만으로 통과 방지)

    Returns:
        True if supported, False otherwise
    """
    if not claim or not source_text:
        return False

    # ── 검증 1: 구체적 수치 ──
    missing_numbers = _check_specific_numbers(claim, source_text)
    if missing_numbers:
        return False

    # ── 검증 2: 고유명사 ──
    missing_entities = _check_entities(claim, source_text)
    if missing_entities:
        return False

    # ── 검증 3: 단어 매칭 비율 ──
    claim_words = _extract_words(claim)
    if not claim_words:
        return True

    source_words = set(_extract_words(source_text))
    if not source_words:
        return False

    matched = sum(1 for w in claim_words if _word_matches_source(w, source_words))
    ratio = matched / len(claim_words)
    return ratio >= threshold and matched >= min_matched


def check_gap_fidelity(
    gap_summary: str,
    quote_1: str,
    quote_2: str,
    source_text: str,
    threshold: float = 0.4,
) -> bool:
    """gap_summary가 인용문과 원문의 범위를 벗어나지 않는지 확인.

    gap_summary의 핵심 단어가 quote_1 + quote_2 + source_text에 나타나야 함.

    Args:
        gap_summary: S1에서 생성한 어긋남 요약
        quote_1: 인용문 1
        quote_2: 인용문 2
        source_text: 관련 뉴스 본문
        threshold: 핵심 단어 중 최소 비율

    Returns:
        True if faithful, False if gap_summary goes beyond source
    """
    if not gap_summary:
        return True

    combined = quote_1 + " " + quote_2 + " " + source_text

    # gap_summary에 구체적 수치가 있으면 source에도 있어야 함
    missing_numbers = _check_specific_numbers(gap_summary, combined)
    if missing_numbers:
        return False

    # gap_summary에 원문에 없는 고유명사가 있으면 폐기
    missing_entities = _check_entities(gap_summary, combined)
    if missing_entities:
        return False

    gap_words = _extract_words(gap_summary)
    if not gap_words:
        return True

    combined_words = set(_extract_words(combined))
    if not combined_words:
        return False

    matched = sum(1 for w in gap_words if _word_matches_source(w, combined_words))
    ratio = matched / len(gap_words)
    return ratio >= threshold
