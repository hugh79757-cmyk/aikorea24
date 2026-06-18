#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 소재 점수화기
- 0~100점 채점 (날짜 가중치 없음)
- 브리핑 포함 기사 +5 보너스
- 형식 A/B/C 자동 선택
- --dry-run 지원
"""
import os, sys, re
from datetime import datetime

THREADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

def score_article(article):
    """0~100점 채점"""
    score = 0
    details = []
    text = f"{article.get('title', '')} {article.get('description', '')} {article.get('comment', '')}"
    text_lower = text.lower()

    # 1. 인물/기업 구체적 행동 (+30)
    person_actions = [
        r'(일론 머스크|샘 알트만|데미스 하사비스|다리오 아모데이|트럼프|저커버그|피차이|나델라|쿡|머스크|알트만|아모데이|하사비스)\S{0,4}\s*(발표|인수|출시|투자|사퇴|해고|폐쇄|경고|선언|맞섬|항복|백기|초월|추월|제치)',
        r'(스페이스X|구글|MS|메타|애플|아마존|테슬라|오픈AI|Anthropic|마이크로소프트)\S{0,3}\s*(발표|인수|출시|투자|해고|사퇴|폐쇄|초월|추월|제치|계약|인상|증가|하락)',
        r'(대표|CEO|창업자|의장|장관|대통령)\S{0,2}\s*(말하|밝히|발언|표명|사퇴|선언|결정|경고|제안|요구)',
    ]
    for pat in person_actions:
        if re.search(pat, text):
            score += 30
            details.append('인물/기업 행동 (+30)')
            break

    # 2. 감정/갈등/반전 (+25)
    emotion_kw = ['논란', '반발', '갈등', '충격', '반전', '폭로', '내부', '경고', '위기',
                  '배신', '항복', '해고', '사퇴', '백기', '파장', '분노', '맞섬', '고발']
    emotion_count = sum(1 for kw in emotion_kw if kw in text)
    if emotion_count >= 3:
        score += 25; details.append(f'감정/갈등 {emotion_count}개 (+25)')
    elif emotion_count >= 1:
        score += 15; details.append(f'감정 요소 {emotion_count}개 (+15)')

    # 3. 구체적 숫자/데이터 (+20)
    num_pat = r'\d+[억만]?\s*(달러|원|%)|\d+조|\d{1,3}(?:,\d{3})+|[0-9]+\s*[만천백]'
    num_count = len(re.findall(num_pat, text))
    if num_count >= 2:
        score += 20; details.append(f'숫자 데이터 {num_count}개 (+20)')
    elif num_count >= 1:
        score += 10; details.append(f'숫자 데이터 {num_count}개 (+10)')

    # 4. 인물 간 대립 구도 (+15)
    conf_kw = ['vs', '대립', '경쟁', '충돌', '대결', '맞서', '견제', 'rival', 'battle', '대']
    conf_count = sum(1 for kw in conf_kw if kw in text_lower)
    if conf_count >= 2:
        score += 15; details.append(f'대립 구도 {conf_count}개 (+15)')

    # 5. 한국 독자 연결점 (+10)
    korea_kw = ['한국', '국내', 'K-', '서울', '삼성', 'SK', '카카오', '네이버', 'LG', '현대']
    if any(kw in text for kw in korea_kw):
        score += 10; details.append('한국 연결점 (+10)')

    # 6. 브리핑 보너스 (+5)
    if article.get('priority') == 1:
        score += 5; details.append('브리핑 포함 (+5)')

    score = min(100, max(0, score))
    return score, details

def determine_format(score):
    if score >= 70: return 'A'
    elif score >= 40: return 'B'
    return 'C'

def score_articles(articles):
    scored = []
    for art in articles:
        score, details = score_article(art)
        art['score'] = score
        art['score_details'] = details
        scored.append(art)
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    from db_reader import get_articles
    articles = get_articles()
    scored = score_articles(articles)
    print(f'\n점수화 결과 (총 {len(scored)}개)')
    print(f'{"="*70}')
    for s in scored[:10]:
        fmt = determine_format(s['score'])
        print(f'  [{s["score"]:3d}점|{fmt}] P{s["priority"]} {s["title"][:55]}')
        for d in s.get('score_details', []):
            print(f'         {d}')
    if len(scored) > 10:
        print(f'  ... 외 {len(scored)-10}개')
