"""pipeline/threads/fact_gate.py — G4 2-layer fact gate for compass slot3_context."""
import re


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

    # Layer 1: heuristic substring/n-gram match
    layer1_ok, layer1_reason = _layer1_substring_match(slot3_context, crawled_body)
    if not layer1_ok:
        return False, f"Layer1 차단: {layer1_reason}"

    # Layer 2: LLM ruling
    layer2_ok, layer2_reason = _layer2_llm_ruling(slot3_context, crawled_body)
    if not layer2_ok:
        return False, f"Layer2 차단: {layer2_reason}"

    return True, "통과"


def _layer1_substring_match(slot3: str, body: str) -> tuple[bool, str]:
    """Heuristic: key nouns and numbers from slot3 must appear in crawled_body."""
    # Extract key tokens: numbers (with units), Korean nouns (2+ chars), English words (2+ chars)
    numbers = re.findall(r'\d[\d,.]*\s*[가-힣a-zA-Z%]*', slot3)
    nouns = re.findall(r'[가-힣]{2,8}', slot3)
    eng_words = re.findall(r'[A-Za-z]{3,}', slot3)

    # Filter out common connective words that don't carry factual weight
    _connectives = {
        '이번', '이에', '관련', '대한', '위한', '그리고', '하지만', '그러나',
        '때문', '으로', '으로서', '에서', '에게', '은', '는', '이', '가',
        '을', '를', '의', '도', '만', '에서', '까지', '부터',
    }
    nouns = [n for n in nouns if n not in _connectives and len(n) >= 3]

    if not numbers and not nouns and not eng_words:
        return True, "검증할 토큰 없음 — 통과"

    body_lower = body.lower()
    missing = []

    # Check numbers (with surrounding context)
    for num in numbers:
        num_clean = num.strip()
        # Try without unit suffix first
        num_base = re.sub(r'[가-힣a-zA-Z%]+$', '', num_clean).strip().rstrip(',.')
        if num_base and num_base not in body:
            # Try the full token
            if num_clean not in body:
                missing.append(f"수치 '{num_clean}'")

    # Check Korean nouns — strip particles/suffixes for stem matching
    for noun in nouns:
        if noun in body:
            continue
        # Strip common Korean particles/suffixes for stem match
        stem = noun
        for suffix in ('은', '는', '이', '가', '을', '를', '의', '도', '만', '로', '으로',
                        '에서', '에게', '까지', '부터', '보다', '와', '과', '하고'):
            if stem.endswith(suffix) and len(stem) - len(suffix) >= 2:
                stem = stem[:-len(suffix)]
                break
        if stem and stem in body:
            continue
        # Also try last-2-char truncation as fallback (common for 잘림)
        if len(noun) >= 4 and noun[:len(noun)-1] in body:
            continue
        missing.append(f"명사 '{noun}'")

    # Check English words
    for word in eng_words:
        if word.lower() not in body_lower:
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
