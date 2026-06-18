#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
enricher.py — 클러스터 컨텍스트 보강
- 우선: 구글 검색 (urllib + BeautifulSoup, User-Agent rotation)
- 검색 실패 시: 클러스터 내 기사 교차 분석으로 반전/대비 추출
"""
import os, re, urllib.request, urllib.parse, random
from datetime import datetime
from bs4 import BeautifulSoup

THREADS_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

def google_search(query, num=5):
    """구글 검색 — User-Agent rotation"""
    ua = random.choice(USER_AGENTS)
    url = f'https://www.google.com/search?q={urllib.parse.quote(query)}&hl=ko&num={num}'
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': ua,
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.5',
            'Accept': 'text/html,application/xhtml+xml'
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        log(f'  ⚠️ 검색 실패({type(e).__name__}): 재시도 없음')
        return []

    soup = BeautifulSoup(html, 'html.parser')
    results = []
    for div in soup.find_all('div'):
        # Google result divs
        h3 = div.find('h3')
        if h3:
            link_tag = div.find('a')
            link = link_tag.get('href', '') if link_tag else ''
            if link.startswith('/url?'):
                link = re.search(r'q=([^&]+)', link)
                link = urllib.parse.unquote(link.group(1)) if link else ''
            # Find snippet
            spans = div.find_all('span')
            snippet = ' '.join(s.get_text(strip=True) for s in spans if len(s.get_text(strip=True)) > 40)[:200]
            if h3.get_text(strip=True) and link:
                results.append({
                    'title': h3.get_text(strip=True),
                    'url': link,
                    'snippet': snippet,
                })
        if len(results) >= num:
            break

    if results:
        log(f'  검색 성공: {len(results)}건')
    return results

def extract_contrasts(articles):
    """
    [핵심] 클러스터 내 기사 교차 분석 → 반전/대비/비교 추출
    GPT가 '반전 구조'를 만들 수 있도록 구체적인 대비점을 찾는다.
    """
    result = {'background': [], 'twist': [], 'numbers': [], 'comparison': []}
    if len(articles) < 2:
        return result

    texts = []
    for a in articles:
        t = f"{a.get('title','')} {a.get('description','')} {a.get('comment','')}"
        texts.append(t)

    # 긍정/부정 사전
    pos_words = ['성장', '증가', '상승', '돌파', '최고', '신기록', '성공', '호조', '강세', '↑', '+', 'record', 'surge', 'grow', '突破']
    neg_words = ['위기', '하락', '감소', '차단', '규제', '반발', '갈등', '실패', '경고', '↓', '-', 'ban', 'block', 'crisis', 'drop', 'fall']
    
    # 기사 쌍 비교
    for i in range(len(articles)):
        for j in range(i+1, len(articles)):
            t1, t2 = texts[i], texts[j]
            a1, a2 = articles[i], articles[j]

            # 1. 긍정vs부정 반전 찾기
            t1_pos = sum(1 for w in pos_words if w in t1)
            t1_neg = sum(1 for w in neg_words if w in t1)
            t2_pos = sum(1 for w in pos_words if w in t2)
            t2_neg = sum(1 for w in neg_words if w in t2)

            if (t1_pos > t1_neg and t2_neg > t2_pos):
                result['twist'].append(f"↑{a1.get('title','')[:25]} ↔ ↓{a2.get('title','')[:25]}")
            elif (t1_neg > t1_pos and t2_pos > t2_neg):
                result['twist'].append(f"↓{a1.get('title','')[:25]} ↔ ↑{a2.get('title','')[:25]}")

            # 2. 같은 주체의 상반된 상황 비교
            entities = ['스페이스X', '아마존', '구글', 'MS', '메타', '애플', '오픈AI',
                        '삼성', 'SK', '네이버', '카카오', '테슬라', '엔비디아', '인텔',
                        '트럼프', '머스크', '알트만', '젠슨', '하사비스', '아모데이',
                        '중국', '미국', '한국', '일본', 'EU']
            for ent in entities:
                if ent in t1 and ent in t2:
                    c = f"{ent}: 「{a1.get('title','')[:20]}」 ←→ 「{a2.get('title','')[:20]}」"
                    if c not in result['comparison']:
                        result['comparison'].append(c)
                    break  # 한 쌍당 하나의 비교면 충분

            # 3. 같은 개념의 대비
            concepts = ['AI', '반도체', '데이터센터', '클라우드', '규제', '투자', '주가',
                        '시총', '로봇', '자율주행', '챗봇', 'LLM', '팹', '냉각', '전력']
            for conc in concepts:
                if conc in t1 and conc in t2:
                    c = f"[{conc}] {a1.get('title','')[:20]} vs {a2.get('title','')[:20]}"
                    if c not in result['comparison']:
                        result['comparison'].append(c)
                    break

    # 숫자 통합
    all_nums = []
    for t in texts:
        nums = re.findall(r'\d+[억만]?[원%달러]|\d+조|\d{1,3}(?:,\d{3})+', t)
        all_nums.extend(nums[:5])
    result['numbers'] = list(set(all_nums))[:8]

    # 배경 (첫 번째 기사 설명)
    if articles:
        result['background'] = [articles[0].get('description', '')[:300]]

    log(f'  fallback 보강: 반전 {len(result["twist"])}건, 비교 {len(result["comparison"])}건, 숫자 {len(result["numbers"])}건')
    return result

def enrich_cluster(cluster):
    """메인 진입점: 검색 시도 → 실패 시 클러스터 내부 분석"""
    keywords = cluster.get('keywords', {})
    all_kw = keywords.get('companies', [])[:3] + keywords.get('concepts', [])[:2] + keywords.get('persons', [])[:1]
    all_kw = [k for k in all_kw if k not in ('AI', '인공지능') and len(k) > 1]
    if not all_kw:
        titles = ' '.join(a.get('title', '') for a in cluster.get('articles', [])[:5])
        all_kw = [w for w in titles.split() if len(w) >= 2][:5]

    query = ' '.join(all_kw[:5])
    log(f'  검색: "{query}"')
    results = google_search(query)

    if results:
        texts = [f"{r['title']} {r['snippet']}" for r in results]
        enrichment = extract_enrichment_fast(texts)
    else:
        log('  검색 실패 → 클러스터 내부 교차 분석')
        articles = cluster.get('articles', [])
        enrichment = extract_contrasts(articles)

    # 압축: 가장 관련성 높은 상위 5개만 유지
    enrichment['twist'] = enrichment.get('twist', [])[:5]
    enrichment['comparison'] = enrichment.get('comparison', [])[:5]
    enrichment['numbers'] = enrichment.get('numbers', [])[:5]
    enrichment['background'] = enrichment.get('background', [])[:2]
    
    cluster['enrichment'] = enrichment
    log(f'  보강 완료: 배경 {len(enrichment.get("background",[]))}건, 반전 {len(enrichment.get("twist",[]))}건, 비교 {len(enrichment.get("comparison",[]))}건')
    return cluster

def extract_enrichment_fast(texts):
    """검색 결과 텍스트에서 키워드 기반 보강 정보 추출"""
    all_text = ' '.join(texts)
    result = {'background': [], 'twist': [], 'numbers': [], 'comparison': []}
    
    if all_text:
        result['background'] = [all_text[:300]]
    
    for kw in ['그러나', '하지만', '반면', '의외로', '알고보니', '근데', '역설', 'but', 'however', 'contrary']:
        if kw in all_text.lower():
            for m in re.finditer(re.escape(kw), all_text, re.IGNORECASE):
                idx = m.start()
                result['twist'].append(all_text[max(0,idx-40):idx+100])
                if len(result['twist']) >= 3:
                    break
        if len(result['twist']) >= 3:
            break
    
    for m in re.finditer(r'\d+[억만]?\s*(달러|원|%)|\d+조|\d{1,3}(?:,\d{3})+', all_text):
        result['numbers'].append(m.group(0))
    
    for kw in ['한국', '국내', '삼성', 'SK', '네이버', '서울', 'K-']:
        if kw in all_text:
            idx = all_text.index(kw)
            result['comparison'].append(all_text[max(0,idx-20):idx+60])
    
    result['numbers'] = list(set(result['numbers']))[:5]
    result['twist'] = result['twist'][:3]
    result['comparison'] = result['comparison'][:3]
    return result


if __name__ == '__main__':
    from db_reader_v2 import get_clusters
    from scorer_v2 import score_clusters, select_best_cluster
    clusters = get_clusters()
    scored = score_clusters(clusters)
    best = select_best_cluster(scored)
    if best:
        enriched = enrich_cluster(best)
        print(f'\n보강 결과 ({best["id"]}):')
        print(f'  배경: {str(enriched["enrichment"].get("background",[])[:1])[:100]}')
        print(f'  반전: {enriched["enrichment"].get("twist",[])}')
        print(f'  비교: {enriched["enrichment"].get("comparison",[])}')
        print(f'  숫자: {enriched["enrichment"].get("numbers",[])[:5]}')
    else:
        print('선택된 클러스터 없음')
