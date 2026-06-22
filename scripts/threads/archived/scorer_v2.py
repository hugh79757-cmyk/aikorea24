#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
scorer_v2.py — 클러스터 스토리텔링 잠재력 점수화 (0~300점)
"""
import os, re
from datetime import datetime

THREADS_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

def score_cluster(cluster):
    score = 0
    details = []
    articles = cluster['articles']
    n = len(articles)

    # === 1. 기사 다양성 (최대 80점) ===
    if n == 1:
        score += 10
        details.append(f'기사 1개 (+10)')
    elif n == 2:
        score += 30
        details.append(f'기사 2개 (+30)')
    elif n == 3:
        score += 60
        details.append(f'기사 3개 (+60)')
    else:
        score += 80
        details.append(f'기사 {n}개 (+80)')

    # 출처 다양성
    sources = set(a.get('source', '') for a in articles if a.get('source'))
    if len(sources) >= 2:
        score += 20
        details.append(f'출처 다양성 ({len(sources)}개, +20)')
    if len(sources) == 1 and n >= 2:
        score -= 20
        details.append(f'모든 출처 동일 (-20)')

    # === 2. 인물 행동 (최대 60점) ===
    all_text = ' '.join(f"{a.get('title','')} {a.get('description','')} {a.get('comment','')}" for a in articles)
    person_actions = re.findall(
        r'(일론 머스크|샘 알트만|데미스 하사비스|머스크|알트만|아모데이|젠슨 황|저커버그|트럼프|나델라)'
        r'\S{0,4}\s*(발표|인수|출시|투자|사퇴|해고|폐쇄|경고|선언|맞섬|항복|백기|초월|제치|인상|계약|증가)',
        all_text
    )
    if len(person_actions) >= 2:
        score += 60
        details.append(f'인물 대립/행동 구조 ({len(person_actions)}건, +60)')
    elif len(person_actions) == 1:
        score += 40
        details.append(f'인물 행동 1건 (+40)')

    # === 3. 반전/갈등 (최대 80점) ===
    twist_kw = ['그러나', '하지만', '반면', '의외로', '알고보니', '근데', '반전', '역설']
    twist_count = sum(1 for kw in twist_kw if kw in all_text)
    if twist_count >= 2:
        score += 50
        details.append(f'반전/역설 구조 (+50)')
    elif twist_count >= 1:
        score += 30
        details.append(f'반전 요소 (+30)')

    emotion_kw = ['논란', '반발', '충격', '폭로', '내부', '위기', '갈등', '경고']
    emotion_count = sum(1 for kw in emotion_kw if kw in all_text)
    if emotion_count >= 2:
        score += 30
        details.append(f'갈등/위기 요소 {emotion_count}개 (+30)')

    # === 4. 한국 연결점 (최대 40점) ===
    korea_kw = ['한국', '국내', '삼성', 'SK', '카카오', '네이버', 'LG', '현대', '서울', '새만금']
    korea_count = sum(1 for kw in korea_kw if kw in all_text)
    if korea_count >= 2:
        score += 40
        details.append(f'한국 연결점 {korea_count}개 (+40)')
    elif korea_count >= 1:
        score += 20
        details.append(f'한국 연결점 (+20)')

    # === 5. 숫자 밀도 (최대 40점) ===
    nums = re.findall(r'\d+[억만]?\s*(달러|원|%)|\d+조|\d{1,3}(?:,\d{3})+|[0-9]+\s*[만천백]', all_text)
    num_count = len(nums)
    if num_count >= 6:
        score += 40
        details.append(f'숫자 {num_count}개 (+40)')
    elif num_count >= 3:
        score += 20
        details.append(f'숫자 {num_count}개 (+20)')

    # === 보너스: 브리핑 포함 ===
    has_briefing = any(a.get('priority') == 1 for a in articles)
    if has_briefing:
        score += 20
        details.append(f'브리핑 포함 (+20)')

    score = min(300, max(0, score))
    cluster['total_score'] = score
    cluster['score_details'] = details
    return cluster

def score_clusters(clusters):
    for c in clusters:
        score_cluster(c)
    clusters.sort(key=lambda x: x['total_score'], reverse=True)
    return clusters

def select_best_cluster(clusters):
    candidates = [c for c in clusters if c['total_score'] >= 150]
    if candidates:
        return candidates[0]
    # fallback: 단일 기사 중 최고점
    singles = [c for c in clusters if c['total_score'] > 0]
    if singles:
        return singles[0]
    return None

if __name__ == '__main__':
    from db_reader_v2 import get_clusters
    clusters = get_clusters()
    scored = score_clusters(clusters)
    best = select_best_cluster(scored)
    print(f'\n클러스터 점수화 (총 {len(scored)}개)')
    print(f'{"="*70}')
    for c in scored[:10]:
        print(f'  [{c["total_score"]:3d}점] {c["id"]} ({len(c["articles"])}개 기사)')
        for d in c.get('score_details', []):
            print(f'         {d}')
        for a in c['articles'][:2]:
            print(f'         · {a["title"][:40]}')
    if best:
        print(f'\n🏆 선택: [{best["total_score"]}점] {best["id"]}')
