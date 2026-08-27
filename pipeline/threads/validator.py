"""pipeline/threads/validator.py — 카드, 연도, 키워드, 최종 출력 검증"""
import re
import unicodedata
from datetime import datetime
from collections import Counter

from pipeline.threads.pitch import detect_prompt_leak

# Contrast pivot leak guard — ensure contrast system labels never leak to cards.
# detect_prompt_leak covers these via pitch.py LEAKED_PROMPT_PATTERNS/_SYSTEM_PROMPT_FRAGMENTS.
# This block documents the 3 contrast patterns for validator 3중 방어 traceability.
_CONTRAST_LEAK_PATTERNS = [
    r'상위\s*주제\s*[:：]',
    r'근본\s*문제\s*[:：]',
    r'대비\s*논지\s*[:：]',
    r'차트는\s*정리됐고',
    r'차트가\s*정리됐고',
    r'기술적\s*검증\s*차원을\s*넘어',
    r'영국\s*외\s*미국\s*사례에서도',
    r'730억\s*갤런',
    r'구원투수',
    r'^[^0-9"\“\”]{400,}$',  # Wave4: 근거 필드 없이 400자 이상 서술형만 → low density hard fail
]
_CONTRAST_FRAGMENTS = ['상위 주제', '근본 문제', '대비 논지', '차트는 정리됐고', '기술적 검증 차원을 넘어', '영국 외 미국', '730억 갤런', '구원투수']

# Wave3: causal bridge leak — bridge_claim 없이 인과 접속으로 seed/background를
# 한 사건처럼 이어붙이는 서술 차단. validate_final_output이 _CONTRAST_LEAK_PATTERNS로 검사.
_CAUSAL_BRIDGE_LEAK_PATTERNS = [
    r'그러자',
    r'이에\s*따라',
    r'이러한\s*상황에서',
    r'발생하자.*경고',
    r'사건에\s*대한\s*반응',
]
_CONTRAST_LEAK_PATTERNS = _CONTRAST_LEAK_PATTERNS + _CAUSAL_BRIDGE_LEAK_PATTERNS

MODEL_MESSAGE_PATTERNS = [
    r'^수정할\s+글자\s+단위',
    r'^원본을\s+그대로\s+반환',
    r'^수정할\s+게\s+없',
    r'^오류가\s+발견되지',
    r'^변경\s+사항이?\s+없',
    r'^수정\s+불필요',
    r'^AI\s+티가?\s+나는',
    r'^교정할\s+부분이?\s+없',
]

ADDITIONAL_MESSAGE_PATTERNS = [
    # Polite forms
    r'^수정이?\s+필요\s+없',
    r'^변경\s+사항이?\s+없',
    # Short responses
    r'^네[,.]?\s*$',
    r'^확인[됨했]*[,.]?\s*$',
    r'^완료[됨했]*[,.]?\s*$',
    r'^통과[됨했]*[,.]?\s*$',
    # English messages
    r'^No\s+changes',
    r'^No\s+errors',
    r'^Returning\s+original',
    r'^Original\s+content',
    # Question responses
    r'^질문에\s+답변',
    r'^답변[입니다]*\s*:',
    # Explanation prefixes
    r'^이\s+텍스트는',
    r'^이\s+내용은',
    r'^이\s+카드는',
    r'^여기서는',
    # Meta commentary
    r'^참고[로事项]*:',
    r'^주의[사항]*:',
    r'^알림:',
]

ALL_MESSAGE_PATTERNS = MODEL_MESSAGE_PATTERNS + ADDITIONAL_MESSAGE_PATTERNS

FORMAT_CARD_COUNTS = {'D': 5, 'contrast': 8}
FORMAT_CARD_COUNT_TOLERANCE = {'D': (5, 5), 'contrast': (3, 8)}

STOPLIST = {
    '무단전재', '수정하거나', '관련기사', '보도했다', '보도했음',
    '기사제공', '저작권자', '기사보기', '바로가기', '메일로',
    '카카오톡', '페이스북', '트위터', '구독하기', '네이버',
    '데일리', '머니투데이', '조선일보', '동아일보', '한국경제',
    '매일경제', '서울경제', '헤럴드경제', '아시아경제',
    '입력', '수정', '기자', '사진', '제공', '문의', '저작권',
    '구독', '뉴스', '대표', '대표번호', '이메일', '전화번호',
    '블로그', '인스타그램', '유튜브', '채널', '팔로우',
    'All', 'Rights', 'Reserved', 'Copyright',
}


def validate_cards(cards, pitch, format_choice='D'):
    """기본 검증 (format별 카드 수 + hook 근사 일치)"""
    lo, hi = FORMAT_CARD_COUNT_TOLERANCE.get(format_choice, (5, 6))
    if not cards:
        return False, "카드 없음"
    if len(cards) < lo:
        return False, f"카드 수 부족 ({len(cards)}개, 최소 {lo}개 필요)"
    if len(cards) > hi:
        return False, f"카드 수 초과 ({len(cards)}개, 최대 {hi}개 제한)"
    first_line = cards[0].strip().split('\n')[0].strip()
    if len(first_line) < 3:
        return False, f"Hook 첫 줄 너무 짧음 ({len(first_line)}자)"
    return True, "OK"


def validate_year(cards, article_body_text, pub_date=None):
    """연도 검증: 쓰레드 연도가 기사 본문 연도 또는 pub_date 연도만 허용"""
    body_text = article_body_text or ''
    current_year = datetime.now().year

    first_card = cards[0] if cards else ''
    hook_line = first_card.split('\n')[0] if first_card else ''
    rest_text = ' '.join(cards)
    rest_text = rest_text.replace(hook_line, '', 1)

    rest_years = set()
    for m in re.finditer(r'(?<!\d)20\d{2}(?!\d)', rest_text):
        rest_years.add(int(m.group()))

    body_years = set()
    for m in re.finditer(r'(?<!\d)20\d{2}(?!\d)', body_text):
        body_years.add(int(m.group()))

    if not rest_years:
        return True, "OK"

    pub_years = set()
    if pub_date:
        for m in re.finditer(r'(?<!\d)20\d{2}(?!\d)', str(pub_date)):
            pub_years.add(int(m.group()))
        allowed = body_years | pub_years
    else:
        allowed = body_years
    invented = rest_years - allowed
    if invented:
        return False, f"만들어진 연도: {invented}"

    return True, "OK"


def validate_keywords(cards, article_body_text):
    """키워드 검증: 기사 본문 핵심 한글 단어가 쓰레드에서 누락/변형됐는지 확인"""
    body_text = article_body_text or ''
    thread_text = ' '.join(cards)
    if not body_text or not thread_text:
        return True, "OK"

    body_words = re.findall(r'[가-힣]{2,8}', body_text)
    body_counter = Counter(body_words)
    keywords = {w for w, cnt in body_counter.items() if cnt >= 2 and len(w) >= 3}

    keywords = keywords - STOPLIST

    if len(keywords) <= 5:
        return True, "OK"

    thread_words = set(re.findall(r'[가-힣]{2,}', thread_text))

    missing = []
    for kw in keywords:
        if kw not in thread_words:
            truncated = False
            for tw in thread_words:
                if len(tw) < 3:
                    continue
                if len(tw) >= 2 and kw.startswith(tw) and len(tw) < len(kw):
                    truncated = True
                    missing.append((kw, tw, '접두사 잘림'))
                    break
                if len(tw) >= 2 and kw.endswith(tw) and len(tw) < len(kw):
                    truncated = True
                    missing.append((kw, tw, '접미사 잘림'))
                    break
            if not truncated and len(kw) >= 4:
                missing.append((kw, '', '누락'))

    if missing:
        critical = [m for m in missing if '잘림' in m[2]]
        if len(critical) >= 3:
            return False, f"키워드 {len(critical)}개 잘림/누락"
        return True, "OK"

    return True, "OK"


# === 외국어 감지 패턴 ===
_CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]')
_JAPANESE_PATTERN = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')

# 공개 export — pitch.py에서 import하여 사용
CHINESE_PATTERN = _CHINESE_PATTERN
JAPANESE_PATTERN = _JAPANESE_PATTERN


def validate_no_foreign_language(cards: list[str]) -> tuple[bool, str]:
    """카드 전체에서 외국어(한자, 일본어) 사용 금지 검증"""
    for i, card in enumerate(cards, 1):
        chinese = _CHINESE_PATTERN.findall(card)
        if chinese:
            return False, f"Card {i}: 한자 감지 ({len(chinese)}개) — {''.join(chinese[:5])}"
        japanese = _JAPANESE_PATTERN.findall(card)
        if japanese:
            return False, f"Card {i}: 일본어 감지 ({len(japanese)}개) — {''.join(japanese[:5])}"
    return True, "OK"


def validate_output_language(cards: list[str], whitelist: set[str] | None = None, target_lang: str = "ko") -> tuple[bool, str]:
    """출력 언어 순수성 검증: 라틴 연속 8자 이상 또는 라틴 15% 초과 시 hard fail.
    whitelist에 포함된 고유명사(EON, QNX 등 seed 본문 고유명사)는 예외.
    """
    wl = set(w or "" for w in (whitelist or set()))
    wl_norm = {w.lower() for w in wl if w}
    for i, card in enumerate(cards, 1):
        work = card
        # remove whitelisted tokens before check (case-insensitive)
        if wl:
            for w in wl:
                if w and len(w) >= 2:
                    work = re.sub(re.escape(w), " ", work, flags=re.IGNORECASE)
        latin_chars = re.findall(r'[A-Za-z]', work)
        total = len(work.strip())
        # 연속 라틴 8자 이상
        if re.search(r'[A-Za-z]{8,}', work):
            # find offending snippet
            m = re.search(r'[A-Za-z]{8,}[A-Za-z\s\.,\'\"\-]*', work)
            snippet = m.group(0)[:40] if m else ""
            return False, f"Card {i}: 영문 블록 노출 ({snippet.strip()}) — whitelist 외 라틴 8자 연속"
        # 전체 라틴 비율 15% 초과
        if total > 20 and len(latin_chars) / max(1, total) >= 0.15:
            ratio = len(latin_chars) / total
            return False, f"Card {i}: 영문 비율 초과 {ratio:.0%} ({len(latin_chars)}/{total}) — whitelist 외"
    return True, "OK"


# === 최종 출력 통합 검증 (3차 방어) ===
_KOREAN_PATTERN = re.compile(r'[가-힣]')


def validate_final_output(cards: list[str]) -> tuple[bool, str]:
    """최종 카드 통합 검증 — 발행 전 3차 방어
    검증 순서: 프롬프트 노출 → unicodedata NFKC 정규화 → 외국어 → 한글 비율 → 모델 메시지
    """
    for i, card in enumerate(cards, 1):
        # 1. 프롬프트 노출 검사 (pitch patterns + contrast literals)
        leaked, reason = detect_prompt_leak(card)
        if leaked:
            return False, f"Card {i}: {reason}"
        for pat in _CONTRAST_LEAK_PATTERNS:
            if re.search(pat, card):
                return False, f"Card {i}: contrast 리터럴 노출 — {pat}"
        
        # NFKC 정규화: 전각/반각 문자 통합 (중국어·일본어 감지 정확도 향상)
        card_normalized = unicodedata.normalize('NFKC', card)
        
        # 2. 외국어 검사 (한자) — 정규화된 카드 기준
        chinese = _CHINESE_PATTERN.findall(card_normalized)
        if chinese:
            return False, f"Card {i}: 한자 감지 ({len(chinese)}개) — {''.join(chinese[:5])}"
        
        # 3. 외국어 검사 (일본어) — 정규화된 카드 기준
        japanese = _JAPANESE_PATTERN.findall(card_normalized)
        if japanese:
            return False, f"Card {i}: 일본어 감지 ({len(japanese)}개) — {''.join(japanese[:5])}"
        
        # 4. 한글 비율 검사
        korean = len(_KOREAN_PATTERN.findall(card_normalized))
        total = len(card.strip())
        if total > 10 and korean < total * 0.3:
            return False, f"Card {i}: 한글 비율 부족 ({korean}/{total})"

        # 5. 모델 설명 메시지 검사
        for pattern in ALL_MESSAGE_PATTERNS:
            if re.match(pattern, card.strip()):
                return False, f"Card {i}: 모델 메시지 탐지"

    # 6. Hook↔본문 고유명사 교차 검증 (2026-08-14 추가)
    ok, reason = _validate_hook_body_entity_consistency(cards)
    if not ok:
        return False, reason

    return True, "OK"


def _extract_hook_entities(hook: str) -> set[str]:
    """Hook에서 주요 고유명사 추출.

    대상:
    - 대문자 시작 영문 토큰 (예: Wrtn, Cisco, Gemini, Anthropic)
    - 따옴표로 감싼 영문 고유명사만 (예: 'FireSat', "CISA")
    """
    entities = set()
    # 대문자 시작 영문 단어 (앞뒤에 영문 알파벳이 없는 경계, 3글자 이상만 고유명사로 간주)
    for m in re.finditer(r'(?<![a-zA-Z])[A-Z][a-zA-Z]+(?![a-zA-Z])', hook):
        word = m.group()
        if len(word) >= 3:
            entities.add(word)
    # 따옴표로 감싼 영문 고유명사만 추출 (한글 따옴표 표현 제외)
    for m in re.finditer(r"""['"]([A-Za-z][A-Za-z0-9.&+#\-]{2,})['"]""", hook):
        entities.add(m.group(1).strip())
    return entities


def _validate_hook_body_entity_consistency(cards: list[str]) -> tuple[bool, str]:
    """Hook(카드1)에 등장하는 주요 고유명사가 본문 카드(2~5)에 최소 1개 이상 등장하는지 검증.

    훅이 특정 엔티티(예: Wrtn)를 지목했는데 본문 카드가 다른 엔티티(예: 크랙)만
    언급하면 사실 오류. 최소 1개 고유명사가 본문에서 재현되어야 함.
    """
    if len(cards) < 2:
        return True, "OK"

    hook_text = cards[0]
    body_text = '\n'.join(cards[1:])

    entities = _extract_hook_entities(hook_text)
    if not entities:
        return True, "OK"  # 추출할 고유명사 없음 → 검사 건너뜀

    body_lower = body_text.lower()
    matched = False
    for entity in entities:
        # 영문 고유명사는 대소문자 구분 없이 검색
        if entity[0].isalpha() and entity[0].isupper():
            if entity.lower() in body_lower:
                matched = True
                break
        else:
            # 한글 등 따옴표 엔티티는 원문 검색
            if entity in body_text:
                matched = True
                break

    if not matched:
        entity_list = ', '.join(sorted(entities)[:5])
        return False, f"Hook 고유명사({entity_list})가 본문 카드에 없음 — 사실 오류 가능"

    return True, "OK"


def validate_model_message(card: str) -> bool:
    """Check if card is a model message (returns False if message detected)."""
    card = card.strip()

    # Skip link cards
    if card.strip().startswith('🔗'):
        return True, "OK"

    # Check against all patterns
    for pattern in ALL_MESSAGE_PATTERNS:
        if re.match(pattern, card):
            return False, "모델 메시지 패턴 탐지"

    # Structural checks
    # 1. Minimum length (절 스타일: 10자까지 허용)
    if len(card) < 10:
        return False, f"최소 길이 미달 ({len(card)}자)"

    # 2. Korean content requirement
    korean_chars = len(re.findall(r'[가-힣]', card))
    if len(card) > 0 and korean_chars / len(card) < 0.3:
        return False, f"한글 비율 부족 ({korean_chars}/{len(card)})"

    return True, "OK"


def validate_card_structure(cards: list[str]) -> tuple[bool, str]:
    """Validate structural integrity of all cards."""
    if not cards:
        return False, "카드 없음"

    # 1. Check for duplicates
    seen = set()
    for i, card in enumerate(cards, 1):
        normalized = card.strip().lower()
        if normalized in seen:
            return False, f"Card {i}: 중복 카드"
        seen.add(normalized)

    # 2. Check each card
    for i, card in enumerate(cards, 1):
        card = card.strip()

        # 3. Minimum length (절 스타일: 짧은 절도 허용)
        if len(card) < 10:
            return False, f"Card {i}: 너무 짧음 ({len(card)}자)"

        # 4. Korean content (AI/tech 뉴스는 고유명사/모델명/숫자가 많아 15%로 완화)
        korean_chars = len(re.findall(r'[가-힣]', card))
        if len(card) > 0 and korean_chars / len(card) < 0.15:
            return False, f"Card {i}: 한글 비율 부족 ({korean_chars}/{len(card)})"

        # 5. Content density (절 + 줄바꿈 스타일 허용 — 개행은 공백으로 치지 않음)
        no_newlines = card.replace('\n', '')
        content_chars = len(re.findall(r'\S', no_newlines))
        if len(no_newlines) > 0 and content_chars / len(no_newlines) < 0.5:
            return False, f"Card {i}: 공백 과다"

        # 6. Sentence completeness (body cards only)
        if i > 1:  # Skip hook
            sentence_enders = ['.', '!', '?', '음', '임', '됨', '했음', '있음', '없음', '다', '함', '란다', '한데', '었다', '았다', '\u3002']
            # Strip trailing quotes/brackets before checking ender (e.g. "— Anil Seth" → ends with ")
            check = card.rstrip('\'"」』》])}」』》').rstrip()
            if not any(check.endswith(ender) for ender in sentence_enders):
                if not card.endswith('...') and not card.endswith('…'):
                    return True, "OK"  # relaxed: log but don't block

    # 7. Hook length (first card — first line only) + content boundary check
    hook = cards[0].strip()
    if not hook.startswith('🔗'):
        hook_first_line = hook.split('\n')[0]
        # Content boundary check: 문장 종결 과다 → 카드 경계 붙음 의심
        enders_count = len(re.findall(r'(?:~임\.|~했음\.|~있음\.|~됨\.|~함\.|[.!?])', hook_first_line))
        if enders_count > 10:
            return False, f"Hook: 문장 종결 과다 ({enders_count}개) — 카드 경계 붙음 의심"
        if len(hook_first_line.strip()) < 8 or len(hook_first_line) > 350:
            return False, f"Hook 길이 비정상 ({len(hook_first_line)}자)"

    # 8. Body card length (절 스타일: 12자까지 허용, 상한 500자 유지)
    body_min = 12
    for i, card in enumerate(cards[1:], 2):  # Skip hook (card 1), body starts at card 2
        card = card.strip()
        if len(card) < body_min or len(card) > 500:
            return False, f"Card {i}: 길이 비정상 ({len(card)}자)"

    # 9. Last card must open reply (답글 유도형 강제 — 2026-08-14 추가)
    last_ok, last_reason = _validate_last_card_opens_reply(cards)
    if not last_ok:
        return False, last_reason

    return True, "OK"


def _validate_last_card_opens_reply(cards: list[str]) -> tuple[bool, str]:
    """마지막 콘텐츠 카드가 답글을 유도하는 열린 형태로 끝나는지 검사.

    CARD 5 RULE: D=열린질문, contrast=확정통찰 모두 허용 (통찰은 ~임 종결)
    닫힌 종결("~했다", "~이다" 등)로 끝나면 거부.
    """
    if len(cards) < 4:
        return True, "OK"  # 카드 수 자체가 문제 — 다른 검증에서 처리

    last_card = cards[-1].strip()
    if not last_card:
        return False, "마지막 카드가 비어있음"

    # strip trailing quotes/period for check (e.g. "있음." -> "있음")
    check_card = last_card.rstrip('"」』》])} ').rstrip('.…! ')
    last_char = check_card[-1] if check_card else ""
    open_endings = ("?", "까", "까?", "일수록", "인데", "을까", "일까", "ㄹ까", "임", "했음", "있음", "됨", "함", "남", "잡음", "줌", "봄", "음", "했음.")  # contrast 확정 통찰 허용 — 줌/봄/음 포괄

    if check_card.endswith("?") or last_char == "?":
        return True, "OK"

    for ending in open_endings:
        if check_card.endswith(ending):
            return True, "OK"

    return False, f"마지막 카드가 닫힌 종결로 끝남 — 답글 유도형 필요 (끝: '{last_card[-20:]}' )"


# === Wave3: 인용 귀속 검증 (joint_statement 단독 화자 축약 차단) ===
def validate_speaker_attribution(cards: list[str], extracted_facts: dict) -> tuple[bool, str]:
    """joint_statement 인용을 단독 화자로 축약했는지 검증 (hard fail).

    extracted_facts["C"] 항목 중 speaker_type == "joint_statement" 이고 speakers 2인 이상인 것만 검사.
    해당 인용문(text_translated 앞 10자)을 담은 카드가 speakers 중 1명만 언급하고
    "공동" 키워드도 없으면 귀속 오류로 판정.
    """
    c_items = (extracted_facts or {}).get('C') or []
    if not cards or not c_items:
        return True, "OK"

    for c in c_items:
        if not isinstance(c, dict):
            continue
        if (c.get('speaker_type') or 'solo') != 'joint_statement':
            continue
        speakers = [str(s).strip() for s in (c.get('speakers') or []) if str(s or '').strip()]
        if not speakers:
            solo = str(c.get('speaker') or '').strip()
            speakers = [solo] if solo else []
        if len(speakers) < 2:
            continue  # 병기할 화자가 없음 → 검사 불가

        quote = str(c.get('text_translated') or c.get('text') or '').strip()
        frag = quote[:10]
        if len(frag) < 4:
            continue  # 대조할 인용 조각 부족

        for i, card in enumerate(cards, 1):
            if frag not in card:
                continue
            if '공동' in card:
                break
            found = [s for s in speakers if s in card]
            if len(found) >= 2:
                break
            return False, (
                f"Card {i}: joint_statement 인용을 단독 화자로 축약 "
                f"(언급 {found or ['없음']} / 필요 {speakers}) — '공동' 병기 또는 화자 2인 이상 필요"
            )

    return True, "OK"


def validate_no_paraphrased_duplicate(cards: list[str], extracted_facts: dict | None = None) -> tuple[bool, str]:
    """동일 수치/인용을 표현만 바꿔 재등장시키는지 정규화 대조 (Wave4).
    숫자 추출 + 화자명 매칭으로 2개 이상 카드에서 동일 원자적 사실 재사용 탐지 → hard fail.
    """
    if not cards:
        return True, "OK"
    # 수치 중복: 각 카드의 숫자 토큰 집합
    per_card_nums: list[set[str]] = []
    per_card_quotes: list[set[str]] = []
    for c in cards:
        nums = set(re.findall(r'\d[\d,\.]*\s*[%‰]?|\d+', c))
        # 정규화: 콤마/공백 제거, 소수점 유지
        norm_nums = {re.sub(r'[\s,]+', '', n).lower() for n in nums}
        per_card_nums.append(norm_nums)
        # 인용 조각: 따옴표 안 8자 이상
        qs = set(re.findall(r'"([^"]{8,})"', c) + re.findall(r'“([^”]{8,})”', c))
        norm_q = {re.sub(r'\s+', '', q)[:20] for q in qs}
        per_card_quotes.append(norm_q)
    for i in range(len(cards)):
        for j in range(i + 1, len(cards)):
            dup_nums = per_card_nums[i] & per_card_nums[j]
            # 동일 숫자 2카드 이상 등장 시 hard fail (단 1-2자리 일반 숫자는 제외)
            dup_nums_filtered = {n for n in dup_nums if len(re.sub(r'[^0-9]', '', n)) >= 2}
            if dup_nums_filtered:
                return False, f"Card {i+1}↔{j+1}: 동일 수치의 표현만 바꾼 중복 — {sorted(dup_nums_filtered)[:2]}"
            dup_q = per_card_quotes[i] & per_card_quotes[j]
            if dup_q:
                return False, f"Card {i+1}↔{j+1}: 동일 인용의 재서술 중복 — {list(dup_q)[0][:12]}"
    return True, "OK"


def _has_causal_bridge_violation(cards: list[str], bridge_claim_ids) -> tuple[bool, str]:
    """bridge_claim 없이 인과 접속사로 서로 다른 출처를 한 사건처럼 잇는지 검사.

    bridge_claim_ids가 있으면 인과 서술이 근거를 가진 것으로 보고 통과.
    Returns (True, OK) on pass, (False, reason) on violation.
    """
    if bridge_claim_ids:
        return True, "OK"
    for i, card in enumerate(cards or [], 1):
        for pat in _CAUSAL_BRIDGE_LEAK_PATTERNS:
            if re.search(pat, card):
                return False, f"Card {i}: bridge_claim 없는 인과 접속 — {pat}"
    return True, "OK"




