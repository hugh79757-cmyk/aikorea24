#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
db_reader_v2.py — 토픽 클러스터링 엔진
- 기존 db_reader.py의 get_articles() 재사용
- 기사 간 키워드 유사도 기반 클러스터링
"""
import os, sys
from datetime import datetime
from collections import defaultdict

THREADS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THREADS_DIR)
from db_reader import get_articles

LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

PERSONS = [
    '일론 머스크', '샘 알트만', '데미스 하사비스', '다리오 아모데이',
    '젠슨 황', '트럼프', '저커버그', '피차이', '나델라', '쿡',
    '머스크', '알트만', '아모데이', '하사비스',
    '미라 무라티', '수닥르', '에머슨', '스튜어트 러셀',
]

COMPANIES = [
    'OpenAI', 'Anthropic', '구글', 'MS', '마이크로소프트', '메타', '애플',
    '아마존', '테슬라', '스페이스X', '엔비디아', '삼성', 'SK', '네이버',
    '카카오', 'LG', '현대', '인텔', 'AMD', 'TSMC', 'Cursor',
    'DeepMind', 'Mistral', 'Runway', 'Hugging Face',
    'AWS', 'GCP', 'Azure', 'Cloudflare',
]

CONCEPTS = [
    '데이터센터', '반도체', '팹', '냉각', '물', '전력', '클라우드',
    'LLM', '에이전트', '로봇', '규제', '투자', '인수', 'IPO',
    '상장', '주가', '시총', '일자리', '실직', '노동', '교육',
    '정책', '안전', '보안', '사이버', '핵무기', '군사', '전쟁',
    '특허', '저작권', '데이터', '프라이버시', '에너지', '탄소',
    '환경', '헬스케어', '의료', '신약', '단백질',
]

LOCATIONS = [
    '한국', '서울', '새만금', '용인', '판교', '부산',
    '미국', '실리콘밸리', '샌프란시스코', '뉴욕', '워싱턴',
    '중국', '베이징', '상하이', '대만',
    '일본', '도쿄', '유럽', '영국', '독일', '프랑스',
]

BROAD_CONCEPTS = {'AI', '인공지능', '데이터', '규제', '투자', '보안'}

def extract_keywords(text):
    result = {'persons': [], 'companies': [], 'concepts': [], 'locations': []}
    for p in PERSONS:
        if p in text:
            result['persons'].append(p)
    for c in COMPANIES:
        if c in text:
            result['companies'].append(c)
    for c in CONCEPTS:
        if c in text and c not in BROAD_CONCEPTS:
            result['concepts'].append(c)
    for l in LOCATIONS:
        if l in text:
            result['locations'].append(l)
    for k in result:
        result[k] = list(set(result[k]))
    return result

def calculate_similarity(kw1, kw2):
    score = 0
    same_persons = set(kw1['persons']) & set(kw2['persons'])
    score += len(same_persons) * 50
    same_companies = set(kw1['companies']) & set(kw2['companies'])
    score += len(same_companies) * 35
    same_concepts = set(kw1['concepts']) & set(kw2['concepts'])
    score += len(same_concepts) * 25
    same_locations = set(kw1['locations']) & set(kw2['locations'])
    score += len(same_locations) * 15
    return score

def cluster_articles(articles):
    if not articles:
        return []

    for art in articles:
        text = f"{art.get('title', '')} {art.get('description', '')} {art.get('comment', '')}"
        art['_keywords'] = extract_keywords(text)

    n = len(articles)
    sim = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            s = calculate_similarity(articles[i]['_keywords'], articles[j]['_keywords'])
            sim[i][j] = s
            sim[j][i] = s

    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[py] = px

    for i in range(n):
        for j in range(i + 1, n):
            if sim[i][j] >= 35:
                union(i, j)

    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(articles[i])

    # 큰 그룹 분할 (최대 5개 기사)
    MAX_SIZE = 5
    all_groups = []
    for group in groups.values():
        if len(group) <= MAX_SIZE:
            all_groups.append(group)
            continue
        m = len(group)
        sub_p = list(range(m))
        def sf(x):
            while sub_p[x] != x:
                sub_p[x] = sub_p[sub_p[x]]
                x = sub_p[x]
            return x
        def su(x, y):
            px, py = sf(x), sf(y)
            if px != py:
                sub_p[py] = px
        for a in range(m):
            for b in range(a + 1, m):
                if calculate_similarity(group[a]['_keywords'], group[b]['_keywords']) >= 50:
                    su(a, b)
        sub_map = defaultdict(list)
        for a in range(m):
            sub_map[sf(a)].append(group[a])
        all_groups.extend(sub_map.values())

    clusters = []
    for idx, group in enumerate(all_groups, 1):
        if len(group) == 1:
            art = group[0]
            if not any(art['_keywords'][k] for k in art['_keywords']):
                continue

        merged_kw = {'persons': [], 'companies': [], 'concepts': [], 'locations': []}
        themes = set()
        for art in group:
            for k in merged_kw:
                merged_kw[k].extend(art['_keywords'][k])
            for c in art['_keywords']['concepts'][:3]:
                themes.add(c)
        for k in merged_kw:
            merged_kw[k] = list(set(merged_kw[k]))

        clusters.append({
            'id': f'cluster_{idx:03d}',
            'articles': group,
            'keywords': merged_kw,
            'total_score': 0,
            'themes': list(themes)[:5],
            'article_count': len(group),
        })

    log(f'  클러스터링: {n}개 기사 → {len(clusters)}개 클러스터')
    return clusters

def get_clusters():
    articles = get_articles()
    if not articles:
        return []
    return cluster_articles(articles)

if __name__ == '__main__':
    clusters = get_clusters()
    print(f'\n클러스터 현황 (총 {len(clusters)}개)')
    print(f'{"="*70}')
    for c in sorted(clusters, key=lambda x: len(x['articles']), reverse=True)[:10]:
        titles = [a['title'][:30] for a in c['articles']]
        kw = c['keywords']
        kw_str = ' | '.join((kw['persons'] + kw['companies'] + kw['concepts'])[:5])
        print(f'  [{c["id"]}] {len(c["articles"])}개 | {kw_str}')
        for t in titles:
            print(f'         - {t}')
    if len(clusters) > 10:
        print(f'  ... 외 {len(clusters)-10}개')
