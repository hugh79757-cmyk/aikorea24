"""pipeline/threads/validator.py — 카드, 연도, 키워드, 최종 출력 검증"""
import re
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

FORMAT_CARD_COUNTS = {'D': 6}
FORMAT_CARD_COUNT_TOLERANCE = {'D': (5, 7)}

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
    if not cards or len(cards) < lo or len(cards) > hi:
        return False
    first_line = cards[0].strip().split('\n')[0].strip()
    if len(first_line) < 3:
        return False
    return True


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
        return True

    allowed = body_years | {current_year}
    invented = rest_years - allowed
    if invented:
        return False

    return True


def validate_keywords(cards, article_body_text):
    """키워드 검증: 기사 본문 핵심 한글 단어가 쓰레드에서 누락/변형됐는지 확인"""
    body_text = article_body_text or ''
    thread_text = ' '.join(cards)
    if not body_text or not thread_text:
        return True

    body_words = re.findall(r'[가-힣]{2,8}', body_text)
    body_counter = Counter(body_words)
    keywords = {w for w, cnt in body_counter.items() if cnt >= 2 and len(w) >= 3}

    keywords = keywords - STOPLIST

    if len(keywords) <= 5:
        return True

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
            return False
        return True

    return True


# === 외국어 감지 패턴 ===
_CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff]')
_JAPANESE_PATTERN = re.compile(r'[\u3040-\u309f\u30a0-\u30ff]')


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
    검증 순서: 프롬프트 노출 → 외국어 → 한글 비율
    """
    for i, card in enumerate(cards, 1):
        # 1. 프롬프트 노출 검사
        leaked, reason = detect_prompt_leak(card)
        if leaked:
            return False, f"Card {i}: {reason}"
        
        # 2. 외국어 검사 (한자)
        chinese = _CHINESE_PATTERN.findall(card)
        if chinese:
            return False, f"Card {i}: 한자 감지 ({len(chinese)}개) — {''.join(chinese[:5])}"
        
        # 3. 외국어 검사 (일본어)
        japanese = _JAPANESE_PATTERN.findall(card)
        if japanese:
            return False, f"Card {i}: 일본어 감지 ({len(japanese)}개) — {''.join(japanese[:5])}"
        
        # 4. 한글 비율 검사 (출처 링크 카드 제외)
        if not card.strip().startswith('🔗'):
            korean = len(_KOREAN_PATTERN.findall(card))
            total = len(card.strip())
            if total > 10 and korean < total * 0.1:
                return False, f"Card {i}: 한글 비율 부족 ({korean}/{total})"

        # 5. 모델 설명 메시지 검사
        for pattern in MODEL_MESSAGE_PATTERNS:
            if re.match(pattern, card.strip()):
                return False, f"Card {i}: 모델 메시지 탐지"
    
    return True, "OK"



