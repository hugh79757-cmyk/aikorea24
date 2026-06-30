"""pipeline/threads/validator.py — 카드, 연도, 키워드 검증"""
import re
from datetime import datetime
from collections import Counter

FORMAT_CARD_COUNTS = {'D': 5}
FORMAT_CARD_COUNT_TOLERANCE = {'D': (4, 6)}

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



