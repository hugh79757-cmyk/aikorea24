"""pipeline/threads/validator.py — 카드, 연도, 키워드, 최종 출력 검증"""
import re
import unicodedata
from datetime import datetime
from collections import Counter

from pipeline.threads.pitch import detect_prompt_leak

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

FORMAT_CARD_COUNTS = {'D': 6}
FORMAT_CARD_COUNT_TOLERANCE = {'D': (4, 7)}

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


def validate_year(cards, article_body_text):
    """연도 검증: 쓰레드 본문(1번 카드 첫 줄 제외)의 연도가 기사 본문에 있는 연도인지 확인"""
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

    allowed = body_years | {current_year}
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


# === 최종 출력 통합 검증 (3차 방어) ===
_KOREAN_PATTERN = re.compile(r'[가-힣]')


def validate_final_output(cards: list[str]) -> tuple[bool, str]:
    """최종 카드 통합 검증 — 발행 전 3차 방어
    검증 순서: 프롬프트 노출 → unicodedata NFKC 정규화 → 외국어 → 한글 비율 → 모델 메시지
    """
    for i, card in enumerate(cards, 1):
        # 1. 프롬프트 노출 검사
        leaked, reason = detect_prompt_leak(card)
        if leaked:
            return False, f"Card {i}: {reason}"
        
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
        
        # 4. 한글 비율 검사 (출처 링크 카드 제외)
        if not card.strip().startswith('🔗'):
            korean = len(_KOREAN_PATTERN.findall(card_normalized))
            total = len(card.strip())
            if total > 10 and korean < total * 0.3:
                return False, f"Card {i}: 한글 비율 부족 ({korean}/{total})"

        # 5. 모델 설명 메시지 검사
        for pattern in ALL_MESSAGE_PATTERNS:
            if re.match(pattern, card.strip()):
                return False, f"Card {i}: 모델 메시지 탐지"
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

        # Skip link cards for most checks
        if card.startswith('🔗'):
            continue

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
    for i, card in enumerate(cards[2:], 3):  # Skip hook and link
        card = card.strip()
        if card.startswith('🔗'):
            continue
        if len(card) < body_min or len(card) > 500:
            return False, f"Card {i}: 길이 비정상 ({len(card)}자)"

    return True, "OK"




