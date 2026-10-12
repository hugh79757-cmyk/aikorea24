"""pipeline/threads/fact_gate.py — G4 2-layer fact gate for compass slot3_context."""
import re

# English→Korean phonetic mapping for proper nouns (Task 4-1).
# 50 major names/organizations — try Korean phonetic match when
# English token not found verbatim in body.
_EN_KOR_PHONETIC = {
    "OpenAI": "오픈AI", "Anthropic": "앤트로픽", "Google": "구글",
    "Microsoft": "마이크로소프트", "Meta": "메타", "Apple": "애플",
    "Amazon": "아마존", "Nvidia": "엔비디아", "Samsung": "삼성",
    "SK": "에스케이", "KT": "케이티", "LG": "엘지", "Hyundai": "현대",
    "Hyundai Motor": "현대자동차", "Kia": "기아", "Genesis": "제네시스",
    "NAVER": "네이버", "Kakao": "카카오", "Daum": "다음",
    "Coupang": "쿠팡", "Woowa": "우아한형제들", "Baemin": "배민",
    "Karrot": "당근", "Soop": "소금", "Market Kurly": "마켓컬리",
    "Ssam": "쌈", "E-Mart": "이마트", "Shinsegae": "신세계",
    "Lotte": "롯데", "CJ": "씨제이", "Haitai": "해태",
    "Orion": "오리온", "Baskin Robbins": "배스킨라빈스", "Paris Baguette": "파리바게뜨",
    "TomN Toms": "톰앤톰스", "Starbucks": "스타벅스", "Dunkin": "던킨",
    "Costco": "코스트코", "Walmart": "월마트", "Target": "타겟",
    "Tesla": "테슬라", "Rivian": "리비안", "Lucid": "루시드",
    "Waymo": "웨이모", "Cruise": "크루즈", "Zoox": "주옥",
    "Boeing": "보잉", "Airbus": "에어버스", "Lockheed": "로클리드",
    "Raytheon": "레이시온", "Northrop": "노스롭",
    "NASA": "나사", "ESA": "유럽우주국", "JAXA": "재팬",
    "SpaceX": "스페이스X", "Blue Origin": "블루오리진", "Rocket Lab": "로켓랩",
    "DeepMind": "딥마인드", "OpenAI": "오픈AI", "Anthropic": "앤트로픽",
    "Mistral": "미스트랄", "Cohere": "코허", "Stability AI": "스테이빌리티 AI",
    "Hugging Face": "허깅페이스", "Midjourney": "미드저니", "DALL-E": "달리",
    "GPT": "지피티", "Claude": "클로드", "Gemini": "지미니", "Llama": "래글라",
    "Aleph Alpha": "알레프 알파", "Cohere": "코허", "AI21": "에이아이21",
    "Inflection": "인플렉션", "Perplexity": "퍼플렉시티", "You": "유 AI",
    "Grok": "그록", "xAI": "엑스아이", "Safe Superintelligence": "안전 초지능",
    "Windsurf": "윈드서프", "Cursor": "커서", "GitHub Copilot": "깃허브 코파일럿",
    "Claude Code": "클로드 코드", "Devin": "데빈", "SWE-agent": "에스더 에이전트",
}

# Language-neutral patterns: numbers, dates, percentages, currencies.
# Always try to match regardless of article language (Task 4-2).
_LANGUAGE_NEUTRAL_RE = re.compile(
    r'\d[\d,.]*\s*%?'   # numbers and percentages
    r'|'
    r'\b\d{1,4}년\b'    # years
    r'|'
    r'\b\d{1,2}월\d{1,2}일\b'  # dates
    r'|'
    r'\b\$[\d,.]+\b'    # USD
    r'|'
    r'\b[\d,.]+\s*(?:조|억|만|원)\b'  # KRW
)


def check_slot3(slot3_context: str, crawled_body: str) -> tuple[bool, str]:
    """Check slot3_context claims against crawled_body source text.

    Layer 1: substring/n-gram match of key nouns and numbers.
    Layer 2: LLM ruling via chat_completion.
    Block if either layer fails.

    Returns (passed, reason).
    """
    if not slot3_context or not slot3_context.strip():
        return False, "slot3_context 비어있음"
    if not crawled_body or not crawled_body.strip():
        return False, "crawled_body 비어있음 — 출처 검증 불가"

    _korean_chars = sum(1 for c in crawled_body if '가' <= c <= '힣')
    _body_len = len(crawled_body)
    _korean_ratio = _korean_chars / _body_len if _body_len else 0

    # Language-neutral elements always try Layer 1 (Task 4-2).
    _has_neutral = bool(_LANGUAGE_NEUTRAL_RE.search(slot3_context))

    if _korean_ratio < 0.1:
        # Predominantly English: skip Layer 1, Layer 2 only.
        print(f"[G4] 본문 영어 비중 {_korean_chars}/{_body_len} — Layer1 스킵, Layer2만")
        layer2_ok, layer2_reason = _layer2_llm_ruling(slot3_context, crawled_body)
        if not layer2_ok:
            return False, f"Layer2 차단 (영어 소스 Layer1 스킵): {layer2_reason}"
        return True, "통과 (영어 소스: Layer2만)"

    # Mixed language (10~50% Korean): partial Layer 1 (Task 4-3).
    # Try Korean→Korean and English→English matches only.
    # Cross-language matching is attempted only for language-neutral
    # elements (numbers, dates, percentages).
    if _korean_ratio <= 0.5:
        print(
            f"[G4] 혼합 언어 비중 {_korean_ratio:.0%} "
            f"({_korean_chars}/{_body_len}) — Layer1 부분 매칭"
        )
        layer1_ok, layer1_reason = _layer1_substring_match(
            slot3_context, crawled_body, partial=True,
        )
        if not layer1_ok:
            # Fallback: try LLM ruling for partial matches
            layer2_ok, layer2_reason = _layer2_llm_ruling(
                slot3_context, crawled_body,
            )
            if not layer2_ok:
                return False, (
                    f"Layer1 부분 차단 → Layer2로 승계: {layer1_reason}"
                )
            return True, f"통과 (부분 Layer1 + Layer2): {layer1_reason}"
    else:
        # Korean > 50%: full Layer 1 + Layer 2.
        layer1_ok, layer1_reason = _layer1_substring_match(
            slot3_context, crawled_body, partial=False,
        )
        if not layer1_ok:
            return False, f"Layer1 차단: {layer1_reason}"

    # Layer 2: LLM ruling
    layer2_ok, layer2_reason = _layer2_llm_ruling(slot3_context, crawled_body)
    if not layer2_ok:
        return False, f"Layer2 차단: {layer2_reason}"

    return True, "통과"


def _layer1_substring_match(
    slot3: str, body: str, partial: bool = False,
) -> tuple[bool, str]:
    """Heuristic: key nouns/numbers from slot3 must appear in crawled_body.

    partial=True: mixed-language mode — language-neutral elements (numbers,
    dates) always try; cross-language phonetic matching enabled.
    partial=False: standard mode — full strict matching.
    """
    numbers = re.findall(r'\d[\d,.]*\s*[가-힣a-zA-Z%]*', slot3)
    nouns = re.findall(r'[가-힣]{2,8}', slot3)
    eng_words = re.findall(r'[A-Za-z]{3,}', slot3)

    _connectives = {
        '이번', '이에', '관련', '대한', '위한', '그리고', '하지만', '그러나',
        '때문', '으로', '로서', '에서', '에게', '은', '는', '이', '가',
        '을', '를', '의', '도', '만', '에서', '까지', '부터',
    }
    _suffixes = sorted({
        '입니다', '했습니다', '합니다', '됩니다', '됐습니다', '였습니다',
        '하겠습니다', '하겠습니다', '했습니다', '합니다', '됩니다',
        'afen습니다', 'afen았습니다', '있습니다', '없습니다', '했었다',
        '하고', '된', '할', '한', '일', '기', '의', '를', '이', '가',
        '은', '는', '에', '에서', '으로', '와', '과', '도', '만',
        '까지', '부터', '하고', '하다', '을', '습니다', '했습니다',
    }, key=len, reverse=True)
    _verb_endings = ('했습니다', '했습니다', '합니다', '입니다', '됩니다', '됐습니다',
                      '였습니다', '겠습니다', '겠습니다', '합니다',
                      '했습니다', '합니다', '됩니다', 'afen습니다', 'afen았습니다',
                      '있습니다', '없습니다', '했습니다', '합니다', '됩니다',
                      '했었다', '하고 있다', '더한다', '한다', '된다')
    nouns = [n for n in nouns if n not in _connectives and len(n) >= 3]
    nouns_stem = []
    for n in nouns:
        stem = n
        for ending in _verb_endings:
            if stem.endswith(ending) and len(stem) - len(ending) >= 2:
                stem = stem[:-len(ending)]
                break
        for suf in _suffixes:
            if stem.endswith(suf) and len(stem) - len(suf) >= 2:
                stem = stem[:-len(suf)]
                break
        if stem and len(stem) >= 2:
            nouns_stem.append((n, stem))
        else:
            nouns_stem.append((n, n))

    if not numbers and not nouns and not eng_words:
        return True, "검증할 토큰 없음 — 통과"

    body_lower = body.lower()
    missing = []

    # Language-neutral: numbers/dates/percentages (Task 4-2) — always match
    _neutral_in_slot3 = _LANGUAGE_NEUTRAL_RE.search(slot3)
    _neutral_in_body = _LANGUAGE_NEUTRAL_RE.search(body)

    # Check numbers (with surrounding context)
    for num in numbers:
        num_clean = num.strip()
        num_base = re.sub(r'[가-힣a-zA-Z%]+$', '', num_clean).strip().rstrip(',.')
        if num_base and num_base not in body:
            if num_clean not in body:
                # Language-neutral: don't fail in partial mode
                if partial and _neutral_in_slot3 and _neutral_in_body:
                    continue
                missing.append(f"수치 '{num_clean}'")

    # Check Korean nouns (Task 4-1: phonetic fallback)
    for noun, stem in nouns_stem:
        if noun in body:
            continue
        if stem and stem in body:
            continue
        if len(noun) >= 4 and noun[:len(noun)-1] in body:
            continue
        # Phonetic fallback: English→Korean (partial mode only)
        if partial and noun in _EN_KOR_PHONETIC:
            kor_phonetic = _EN_KOR_PHONETIC[noun]
            if kor_phonetic in body:
                continue
        missing.append(f"명사 '{noun}'")

    # Check English words (Task 4-1: phonetic fallback)
    for word in eng_words:
        if word.lower() in body_lower:
            continue
        # In partial mode, skip common lowercase English words
        # (functional words: the, and, of, from, etc.)
        if partial and word[0].islower():
            continue
        # Phonetic fallback (Task 4-1)
        if word in _EN_KOR_PHONETIC:
            kor_phonetic = _EN_KOR_PHONETIC[word]
            if kor_phonetic in body:
                continue
        # Language-neutral check (Task 4-2)
        if partial and _neutral_in_slot3 and _neutral_in_body:
            continue
        missing.append(f"용어 '{word}'")

    if len(missing) >= 3:
        return False, f"출처 미매칭 토큰 {len(missing)}개: {', '.join(missing[:5])}"

    return True, "OK"


def _layer2_llm_ruling(slot3: str, body: str) -> tuple[bool, str]:
    """LLM ruling: ask model whether each claim follows from source text."""
    try:
        from v3.model_router import chat_completion
    except ImportError:
        try:
            from scripts.threads.v3.model_router import chat_completion
        except ImportError:
            return True, "chat_completion 임포트 실패 — LLM 검증 건너뜀"

    system_prompt = (
        "당신은 팩트체크 검증자입니다. 아래 [소스 텍스트]에서 도출할 수 있는 주장만 통과시킵니다. "
        "소스에 없는 사실을 새로 만들었거나, 수치가 소스와 다르면 'BLOCK'하십시오. "
        "출력은 JSON만: {\"verdict\": \"PASS\" 또는 \"BLOCK\", \"reason\": \"...\"}"
    )
    user_msg = (
        f"[검증 대상 slot3_context]\n{slot3}\n\n"
        f"[소스 텍스트]\n{body[:4000]}"
    )

    try:
        result = chat_completion(
            messages=[{"role": "user", "content": user_msg}],
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
    except Exception:
        return True, "LLM 호출 실패 — 통과"

    if not result:
        return True, "LLM 응답 없음 — 통과"

    try:
        import json
        data = json.loads(result.strip())
        verdict = data.get("verdict", "PASS").upper()
        reason = data.get("reason", "")
        if verdict == "BLOCK":
            return False, f"LLM 차단: {reason}"
    except (json.JSONDecodeError, AttributeError):
        pass

    return True, "LLM 통과"
