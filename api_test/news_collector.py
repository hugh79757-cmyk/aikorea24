#!/usr/bin/env python3
"""
aikorea24.kr 뉴스 수집기 v2.1
- AI 관련 뉴스만 3단계 정밀 필터링
- 중복 방지 (제목 해시)
- 수집 후 D1 저장
"""

import os, json, subprocess, urllib.request, urllib.parse, hashlib, re
from datetime import datetime
from xml.etree import ElementTree as ET
from html import unescape

def load_env(path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or '=' not in line:
                continue
            line = line.replace('export ', '')
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip().strip('"').strip("'")

load_env('/Users/twinssn/Projects/aikorea24/api_test/.env.sh')

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
NAVER_ID = os.environ.get('NAVER_CLIENT_ID', '')
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET', '')
DATA_KEY = os.environ.get('DATA_GO_KR_KEY', '')

def clean(text):
    text = unescape(text or '')
    return re.sub(r'<[^>]+>', '', text).strip()

# ===== AI 3단계 필터 =====
STRONG = ['AI', 'A.I', '인공지능', 'GPT', 'ChatGPT', '챗GPT', 'LLM',
    '생성형', '딥러닝', '머신러닝', '딥페이크', '자연어처리',
    '앤트로픽', 'Anthropic', '오픈AI', 'OpenAI', '클로드', 'Claude',
    'Gemini', '제미나이', 'Copilot', '코파일럿', '코덱스',
    'Midjourney', '미드저니', 'Stable Diffusion', 'DALL-E', 'Sora',
    'AI 바우처', 'AI바우처', 'AI 스타트업', '휴머노이드',
    '피지컬 AI', 'AI 서비스', 'AI 기반', 'AI 모드']

WEAK = ['데이터센터', '클라우드', '반도체', '엔비디아', 'GPU',
    '자율주행', '로봇', '알고리즘', '빅데이터', '테크', '4차 산업',
    '디지털 전환', '소프트웨어', '스타트업']

EXCLUDE = ['귀촌', '귀어', '귀농', '축산', '양식', '어업',
    '교복', '생리대', '시승', '전시장 이벤트', '부동산', '아파트',
    '야구', '축구', '농구', '올림픽', '날씨', '태풍', '폭설',
    '결혼', '출산', '장례', '과학관', '과학특강', '마약',
    '행정통합', '통합특별', '도서관', '연휴 이벤트', '르노',
    '교육청', '임대', '재건축']

# SOFT_EXCLUDE: 제목에 STRONG 키워드가 있으면 통과 허용, 없으면 차단
SOFT_EXCLUDE = ['배터리', '전기차', '완성차', '희망퇴직', '위로금',
    '구조조정', '파업', '노조', '주가', '시가총액', '배당',
    '공모주', '상장폐지', '부채', '적자', '감원']

def is_ai(title, desc=''):
    title_up = title.upper()
    desc_up = desc.upper()
    text = title_up + ' ' + desc_up
    # 1. 제외 키워드 체크 (무조건 차단)
    for kw in EXCLUDE:
        if kw.upper() in text: return False
    # 1.5. SOFT_EXCLUDE: 제목에 STRONG 없으면 차단
    for kw in SOFT_EXCLUDE:
        if kw.upper() in text:
            # 제목에 STRONG이 있으면 통과 허용
            title_has_strong = False
            for sk in STRONG:
                sku = sk.upper()
                if len(sku) <= 3:
                    if re.search(r'(?<![A-Z])' + re.escape(sku) + r'(?![A-Z])', title_up):
                        title_has_strong = True; break
                else:
                    if sku in title_up:
                        title_has_strong = True; break
            if not title_has_strong:
                return False
    # 2. STRONG 키워드 매칭 (단어 경계 체크)
    def has_strong(s):
        for kw in STRONG:
            ku = kw.upper()
            # 2글자 이하 키워드(AI, A.I)는 단어 경계 체크
            if len(ku) <= 3:
                if re.search(r'(?<![A-Z])' + re.escape(ku) + r'(?![A-Z])', s):
                    return True
            else:
                if ku in s:
                    return True
        return False
    # 3. STRONG이 제목에 있으면 → 바로 통과
    if has_strong(title_up): return True
    # 4. STRONG이 설명에만 있으면 → WEAK 2개 이상 + 제목에도 관련 단서 필요
    if has_strong(desc_up):
        weak_count = sum(1 for kw in WEAK if kw.upper() in text)
        if weak_count >= 2: return True
    # 5. STRONG 없이 WEAK만 → 통과 불가
    return False

# ===== 중복 체크 =====
def title_hash(title):
    normalized = re.sub(r'[^가-힣a-zA-Z0-9]', '', title)
    return hashlib.md5(normalized.encode()).hexdigest()

def get_existing():
    try:
        r = subprocess.run(
            ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote',
             '--command', 'SELECT title FROM news', '--json'],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=120)
        hashes = set()
        if r.returncode == 0 and r.stdout.strip():
            import json as _json
            data = _json.loads(r.stdout)
            # wrangler --json 출력: [{"results": [{"title": "..."}, ...]}]
            if isinstance(data, list) and data:
                results = data[0].get('results', [])
                for row in results:
                    t = row.get('title', '')
                    if t:
                        hashes.add(title_hash(t))
        print(f"  기존 D1 항목: {len(hashes)}개")
        return hashes
    except Exception as e:
        print(f"  get_existing 실패: {e}")
        return set()

# ===== 1. 과기부 사업공고 =====
def fetch_msit_announce(limit=30):
    url = f"http://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList?ServiceKey={DATA_KEY}&pageNo=1&numOfRows={limit}&returnType=json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        items = data['response'][1]['body']['items']
        results = []
        for entry in items:
            item = entry['item']
            title = clean(item.get('subject', ''))
            desc = f"담당: {item.get('deptName','')}"
            if is_ai(title, desc):
                results.append({'title': title, 'link': item.get('viewUrl', ''),
                    'description': desc, 'source': '과기부 사업공고',
                    'category': 'grant', 'pub_date': item.get('pressDt', '')})
        print(f"  과기부 사업공고: {len(results)}건")
        return results
    except Exception as e:
        print(f"  과기부 사업공고 실패: {e}"); return []

# ===== 2. 과기부 보도자료 =====
def fetch_msit_press(limit=20):
    url = f"http://apis.data.go.kr/1721000/msitpressreleaseinfo/pressReleaseList?ServiceKey={DATA_KEY}&pageNo=1&numOfRows={limit}&returnType=json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        items = data['response'][1]['body']['items']
        results = []
        for entry in items:
            item = entry['item']
            title = clean(item.get('subject', ''))
            desc = f"담당: {item.get('deptName','')}"
            if is_ai(title, desc):
                results.append({'title': title, 'link': item.get('viewUrl', ''),
                    'description': desc, 'source': '과기부 보도자료',
                    'category': 'policy', 'pub_date': item.get('pressDt', '')})
        print(f"  과기부 보도자료: {len(results)}건")
        return results
    except Exception as e:
        print(f"  과기부 보도자료 실패: {e}"); return []

# ===== 3. 정부24 혜택 =====
def fetch_gov_benefits(limit=50):
    url = f"https://api.odcloud.kr/api/gov24/v3/serviceList?page=1&perPage={limit}&serviceKey={DATA_KEY}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        results = []
        for item in data.get('data', []):
            name = item.get('서비스명', '')
            summary = item.get('서비스목적요약', '')
            if is_ai(name, summary):
                results.append({'title': name,
                    'link': f"https://www.gov.kr/portal/rcvfvrSvc/dtlEx/{item.get('서비스ID','')}",
                    'description': summary[:200], 'source': '정부24 혜택',
                    'category': 'benefit', 'pub_date': datetime.now().strftime('%Y-%m-%d')})
        print(f"  정부24 혜택: {len(results)}건")
        return results
    except Exception as e:
        print(f"  정부24 혜택 실패: {e}"); return []

# ===== 4. 네이버 뉴스 =====
QUERIES = ['인공지능 AI 서비스', 'ChatGPT 활용법', '생성형AI 스타트업',
    'AI 바우처 지원사업', '딥러닝 기술 트렌드', 'AI 정책 규제']

def fetch_naver(query, display=10):
    encoded = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display={display}&sort=date"
    req = urllib.request.Request(url, headers={
        'X-Naver-Client-Id': NAVER_ID, 'X-Naver-Client-Secret': NAVER_SECRET})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        results = []
        for item in data.get('items', []):
            title = clean(item['title'])
            desc = clean(item['description'])
            if is_ai(title, desc):
                results.append({'title': title, 'link': item['link'],
                    'description': desc[:200], 'source': '네이버뉴스',
                    'category': 'news', 'pub_date': datetime.now().strftime('%Y-%m-%d')})
        return results
    except Exception as e:
        print(f"  네이버 '{query}' 실패: {e}"); return []

# ===== 5. RSS =====
RSS_FEEDS = [
    ('https://www.aitimes.com/rss/allArticle.xml', 'AI타임스'),
]

def fetch_rss(url, source_name, limit=15):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        xml = urllib.request.urlopen(req, timeout=10).read()
        tree = ET.fromstring(xml)
        results = []
        for item in tree.findall('.//item')[:limit]:
            title = clean(item.findtext('title', ''))
            desc = clean(item.findtext('description', ''))
            if is_ai(title, desc):
                results.append({'title': title, 'link': item.findtext('link', ''),
                    'description': desc[:200], 'source': source_name,
                    'category': 'news', 'pub_date': datetime.now().strftime('%Y-%m-%d')})
        return results
    except Exception as e:
        print(f"  RSS {source_name} 실패: {e}"); return []
        
# ===== 6. 국가AI전략위원회 / 대통령실 브리핑 (네이버 뉴스 검색) =====
AI_POLICY_QUERIES = [
    'AI 기본사회 정책',
    '국가AI전략위원회',
    'AI 행동전략 정부',
    'AI 복지 지원 정부',
    'AI 접근성 디지털 격차',
    'AI 인재양성 교육부',
    'AI 바우처 중소기업',
    'AI 윤리 기본법',
]

def fetch_naver_policy():
    """정부 AI 정책 전용 네이버 뉴스 수집 (category='policy')"""
    results = []
    for q in AI_POLICY_QUERIES:
        encoded = urllib.parse.quote(q)
        url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display=5&sort=date"
        req = urllib.request.Request(url, headers={
            'X-Naver-Client-Id': NAVER_ID,
            'X-Naver-Client-Secret': NAVER_SECRET
        })
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=10).read())
            for item in data.get('items', []):
                title = clean(item['title'])
                desc = clean(item['description'])
                if is_ai(title, desc):
                    results.append({
                        'title': title,
                        'link': item['link'],
                        'description': desc[:200],
                        'source': '네이버뉴스',
                        'category': 'policy',   # ← 'news'가 아니라 'policy'
                        'pub_date': datetime.now().strftime('%Y-%m-%d')
                    })
        except Exception as e:
            print(f"  정책뉴스 '{q}' 실패: {e}")
    print(f"  정책 뉴스(네이버): {len(results)}건")
    return results


# ===== 7. 행안부 보도자료 (AI/디지털 관련) =====
def fetch_mois_press(limit=20):
    """행정안전부 보도자료에서 AI/디지털 관련 수집"""
    url = f"http://apis.data.go.kr/1741000/newPressRelease/getNewPressReleaseList?serviceKey={DATA_KEY}&pageNo=1&numOfRows={limit}&returnType=json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        items = data.get('response', [{}])
        if len(items) > 1:
            items = items[1].get('body', {}).get('items', [])
        else:
            items = []
        results = []
        for entry in items:
            item = entry.get('item', entry)
            title = clean(item.get('subject', item.get('title', '')))
            desc = clean(item.get('contents', item.get('description', '')))[:200]
            if is_ai(title, desc):
                results.append({
                    'title': title,
                    'link': item.get('viewUrl', item.get('link', '')),
                    'description': desc,
                    'source': '행안부 보도자료',
                    'category': 'policy',
                    'pub_date': item.get('pressDt', item.get('pubDate', ''))
                })
        print(f"  행안부 보도자료: {len(results)}건")
        return results
    except Exception as e:
        print(f"  행안부 보도자료 실패: {e}")
        return []


# ===== 8. 모두의 창업 프로젝트 뉴스 수집 =====
STARTUP_QUERIES = [
    'AI 스타트업 창업 지원',
    'AI 창업 바우처 지원사업',
    '중소벤처기업부 AI 창업',
    'AI 기반 창업 오디션',
]

def fetch_startup_news():
    results = []
    for q in STARTUP_QUERIES:
        encoded = urllib.parse.quote(q)
        url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display=10&sort=date"
        req = urllib.request.Request(url, headers={
            'X-Naver-Client-Id': NAVER_ID,
            'X-Naver-Client-Secret': NAVER_SECRET
        })
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=10).read())
            for item in data.get('items', []):
                title = clean(item['title'])
                desc = clean(item['description'])
                if not is_ai(title, desc):
                    continue
                results.append({
                    'title': title,
                    'link': item['link'],
                    'description': desc[:200],
                    'source': '네이버뉴스',
                    'category': 'startup',
                    'pub_date': datetime.now().strftime('%Y-%m-%d')
                })
        except Exception as e:
            print(f"  모두의창업 '{q}' 실패: {e}")
    print(f"  모두의 창업 뉴스: {len(results)}건")
    return results

# ===== 9. 복지 관련 뉴스 수집 =====
WELFARE_QUERIES = [
    'AI 돌봄 서비스 도입',
    'AI 장애인 접근성 기술',
    'AI 시니어 디지털 교육',
    'AI 사회안전망 복지',
    'AI 일자리 지원 정책',
]

SENIOR_QUERIES = [
    'AI 노인 돌봄 서비스',
    'AI 시니어 디지털 교육',
    'AI 치매 예방 기술',
    'AI 고령자 복지 정책',
    'AI 요양 로봇 서비스',
    '노인 디지털 격차 해소',
    '독거노인 돌봄 정책',
    '기초연금 인상 변경',
    '노인 일자리 지원사업',
    '요양보호사 처우 개선',
    '치매 요양 서비스',
    '노인복지관 프로그램',
    '시니어 건강관리 서비스',
    '고령자 주거 지원',
    '노인 학대 예방',
    '경로당 운영 지원',
]

def fetch_welfare_news():
    """AI+복지 관련 뉴스 수집 (category='benefit')"""
    results = []
    for q in WELFARE_QUERIES:
        encoded = urllib.parse.quote(q)
        url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display=5&sort=date"
        req = urllib.request.Request(url, headers={
            'X-Naver-Client-Id': NAVER_ID,
            'X-Naver-Client-Secret': NAVER_SECRET
        })
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=10).read())
            for item in data.get('items', []):
                title = clean(item['title'])
                desc = clean(item['description'])
                if not is_ai(title, desc):
                    continue
                results.append({
                    'title': title,
                    'link': item['link'],
                    'description': desc[:200],
                    'source': '네이버뉴스',
                    'category': 'benefit',
                    'pub_date': datetime.now().strftime('%Y-%m-%d')
                })
        except Exception as e:
            print(f"  복지뉴스 '{q}' 실패: {e}")
    print(f"  복지/접근성 뉴스: {len(results)}건")
    return results
        

def fetch_senior_news():
    """[12] 노인복지 뉴스 수집 (category='senior') - AI 필터 없이 폭넓게"""
    results = []
    senior_kw = ['노인', '시니어', '고령', '돌봄', '치매', '요양',
                 '실버', '어르신', '경로', '독거', '노후', '간병',
                 '기초연금', '요양보호사', '복지관', '경로당', '노인복지',
                 '장기요양', '노인학대', '치매안심', '노인일자리']
    for q in SENIOR_QUERIES:
        encoded = urllib.parse.quote(q)
        url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display=10&sort=date"
        req = urllib.request.Request(url, headers={
            'X-Naver-Client-Id': NAVER_ID,
            'X-Naver-Client-Secret': NAVER_SECRET
        })
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=10).read())
            for item in data.get('items', []):
                title = clean(item['title'])
                desc = clean(item['description'])
                full = (title + ' ' + desc).lower()
                # 제외 키워드
                skip = ['부동산', '아파트', '분양', '주식', '증권', '코인']
                if any(s in full for s in skip):
                    continue
                # 노인복지 키워드 1개 이상 필수
                if not any(kw in full for kw in senior_kw):
                    continue
                results.append({
                    'title': title,
                    'link': item['link'],
                    'description': desc[:200],
                    'source': '네이버뉴스',
                    'category': 'senior',
                    'pub_date': datetime.now().strftime('%Y-%m-%d')
                })
        except Exception as e:
            print(f"  노인복지 '{q}' 실패: {e}")
    seen = set()
    unique = []
    for r in results:
        if r['title'] not in seen:
            seen.add(r['title'])
            unique.append(r)
    print(f"  노인복지 뉴스: {len(unique)}건")
    return unique


# ===== D1 저장 (배치) =====

def fetch_bizinfo_grants():
    """[11] 기업마당 소상공인 AI 지원사업 공고"""
    api_key = os.environ.get('BIZINFO_API_KEY', '')
    if not api_key:
        print("  BIZINFO_API_KEY 없음, 스킵")
        return []

    results = []
    existing = get_existing()
    ai_strong = ['AI', '인공지능', 'AI바우처', '데이터바우처', '스마트상점', '키오스크',
                 '챗봇', '디지털커머스', '스마트공장']
    ai_weak = ['디지털전환', '디지털', '스마트', '빅데이터', '클라우드', '자동화',
               '로봇', 'DX', 'ICT', '온라인', '플랫폼']
    biz_words = ['소상공인', '소기업', '소공인', '자영업', '영세', '골목상권', '전통시장']

    try:
        url = 'https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do'
        params = f'crtfcKey={api_key}&dataType=json&searchCnt=200&pageUnit=200&pageIndex=1'
        full_url = f'{url}?{params}'

        req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8')
            data = json.loads(raw)

        items = data.get('jsonArray', [])
        total = items[0].get('totCnt', '?') if items else 0
        print(f"  기업마당 전체 공고: {total}건, 가져온 건: {len(items)}건")

        count = 0
        for item in items:
            title = clean(item.get('pblancNm', ''))
            desc = clean(item.get('bsnsSumryCn', ''))
            target = item.get('trgetNm', '')
            org = item.get('jrsdInsttNm', '')
            exc_org = item.get('excInsttNm', '')
            hashtags = item.get('hashtags', '')
            period = item.get('reqstBeginEndDe', '')
            purl = item.get('pblancUrl', '')
            link = f'https://www.bizinfo.go.kr{purl}' if purl and not purl.startswith('http') else purl

            full_text = f'{title} {desc} {target} {hashtags}'
            has_strong = any(kw.lower() in full_text.lower() for kw in ai_strong)
            has_weak = any(kw.lower() in full_text.lower() for kw in ai_weak)
            has_biz = any(w in full_text for w in biz_words)

            if (has_strong and has_biz) or (has_strong and '중소기업' in target) or (has_weak and has_biz):
                if title and title_hash(title) not in existing:
                    summary = desc[:300] if desc else ''
                    info_parts = []
                    if org: info_parts.append(f'소관: {org}')
                    if exc_org: info_parts.append(f'수행: {exc_org}')
                    if target: info_parts.append(f'대상: {target}')
                    if period: info_parts.append(f'신청기간: {period}')
                    info_line = ' | '.join(info_parts)
                    final_desc = f'{info_line}\n{summary}' if summary else info_line

                    results.append({
                        'title': title[:200],
                        'link': link,
                        'description': final_desc[:500],
                        'source': org or '기업마당',
                        'category': 'grant',
                        'pub_date': period.split('~')[0].strip() if '~' in period else datetime.now().strftime('%Y-%m-%d')
                    })
                    count += 1

        print(f"  AI/디지털/소상공인 필터 통과: {count}건")
    except Exception as e:
        print(f"  기업마당 실패: {e}")
        import traceback
        traceback.print_exc()

    return results



# ============================================
# GPT-4o-mini 번역 함수
# ============================================
def translate_to_korean(title, description=''):
    """영문 제목+설명을 한국어로 번역 (GPT-4o-mini)"""
    try:
        import openai
        client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))
        text = f"Title: {title}"
        if description:
            text += f"\nDescription: {description[:300]}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a Korean tech news translator. Translate the following English AI/tech news into natural Korean. Return ONLY a JSON object with keys \"title\" and \"description\". No markdown, no explanation."},
                {"role": "user", "content": text}
            ],
            temperature=0.3,
            max_tokens=500
        )
        import json
        result = json.loads(resp.choices[0].message.content.strip())
        return result.get('title', title), result.get('description', description)
    except Exception as e:
        print(f"  번역 실패: {e}")
        return title, description


# ============================================
# 해외 AI 뉴스 RSS 수집
# ============================================
def fetch_rss_global(url, source_name, category='global', country='us', limit=10):
    """해외 RSS 피드 수집 + 번역"""
    items = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'aikorea24-bot/2.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        for item in root.iter('item'):
            title_el = item.find('title')
            link_el = item.find('link')
            desc_el = item.find('description')
            pub_el = item.find('pubDate')
            if title_el is None or link_el is None:
                continue
            orig_title = (title_el.text or '').strip()
            orig_desc = clean(desc_el.text or '') if desc_el is not None else ''
            link = (link_el.text or '').strip()
            pub = (pub_el.text or '')[:25] if pub_el is not None else ''
            # AI 관련성 체크 (해외 소스는 AI 전문 피드이므로 가벼운 필터)
            ai_terms = ['AI', 'ARTIFICIAL INTELLIGENCE', 'MACHINE LEARNING', 'LLM', 'GPT',
                        'NEURAL', 'DEEPSEEK', 'OPENAI', 'ANTHROPIC', 'GEMINI', 'CLAUDE',
                        'ROBOT', 'AUTONOMOUS', 'DEEP LEARNING', 'GENERATIVE']
            text_upper = (orig_title + ' ' + orig_desc).upper()
            if not any(t in text_upper for t in ai_terms):
                continue
            # 영어 원문 그대로 저장 (번역은 --source translate에서 별도 수행)
            items.append({
                'title': orig_title,
                'link': link,
                'description': orig_desc,
                'source': source_name,
                'category': category,
                'pub_date': pub,
                'source_url': url,
                'original_title': orig_title,
                'country': country,
            })
            if len(items) >= limit:
                break
        print(f"  {source_name}: {len(items)}건 수집")
    except Exception as e:
        print(f"  {source_name} 수집 실패: {e}")
    return items


def fetch_hackernews_ai(limit=10):
    """Hacker News Algolia API로 AI 관련 스토리 수집 + 번역"""
    items = []
    try:
        url = 'https://hn.algolia.com/api/v1/search?query=AI&tags=story&hitsPerPage=20'
        req = urllib.request.Request(url, headers={'User-Agent': 'aikorea24-bot/2.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        data = json.loads(raw)
        for hit in data.get('hits', []):
            orig_title = hit.get('title', '').strip()
            link = hit.get('url') or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
            if not orig_title:
                continue
            items.append({
                'title': orig_title,
                'link': link,
                'description': '',
                'source': 'Hacker News',
                'category': 'global',
                'pub_date': hit.get('created_at', '')[:10],
                'source_url': 'https://hn.algolia.com',
                'original_title': orig_title,
                'country': 'us',
            })
            if len(items) >= limit:
                break
        print(f"  Hacker News: {len(items)}건 수집")
    except Exception as e:
        print(f"  Hacker News 수집 실패: {e}")
    return items


# 해외 소스 목록
GLOBAL_RSS_FEEDS = [
    ('https://techcrunch.com/category/artificial-intelligence/feed/', 'TechCrunch AI', 'us'),
    ('https://www.technologyreview.com/topic/artificial-intelligence/feed', 'MIT Tech Review', 'us'),
    ('https://www.scmp.com/rss/320663/feed', 'SCMP China Tech', 'cn'),
]


def fetch_global_news():
    """해외 AI 뉴스 전체 수집"""
    all_items = []
    for url, name, country in GLOBAL_RSS_FEEDS:
        items = fetch_rss_global(url, name, category='global', country=country, limit=7)
        all_items.extend(items)
    # Hacker News
    all_items.extend(fetch_hackernews_ai(limit=7))
    return all_items


# ============================================
# 공식 AI 기업 블로그 수집
# ============================================
def fetch_official_news():
    """공식 AI 기업 블로그 수집 (HTML 스크래핑)"""
    all_items = []
    # ByteDance Seed 블로그
    all_items.extend(fetch_bytedance_seed(limit=5))
    return all_items


def fetch_bytedance_seed(limit=5):
    """ByteDance Seed 블로그 스크래핑"""
    items = []
    try:
        url = 'https://seed.bytedance.com/en/blog'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        # 블로그 항목 파싱: 제목과 날짜 추출
        # 패턴: 제목\n날짜\n카테고리
        import re
        # 날짜 패턴으로 블로그 항목 찾기
        pattern = r'([A-Z][a-z]+ \d{1,2}, \d{4})'
        dates = re.findall(pattern, html)
        # 제목 추출 - 날짜 앞에 오는 텍스트 블록
        blocks = re.split(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}, \d{4}', html)
        titles_found = []
        for i, block in enumerate(blocks[:-1]):
            lines = [l.strip() for l in block.strip().split('\n') if l.strip() and len(l.strip()) > 10]
            if lines:
                title = lines[-1]
                if i < len(dates):
                    titles_found.append((title, dates[i]))
        for title, date_str in titles_found[:limit]:
            items.append({
                'title': title,
                'link': 'https://seed.bytedance.com/en/blog',
                'description': f'ByteDance Seed blog post: {title}',
                'source': 'ByteDance Seed',
                'category': 'official',
                'pub_date': date_str,
                'source_url': url,
                'original_title': title,
                'country': 'cn',
            })
        print(f"  ByteDance Seed: {len(items)}건 수집")
    except Exception as e:
        print(f"  ByteDance Seed 수집 실패: {e}")
    return items



# ============================================
# GPT 큐레이팅 + 번역 배치
# ============================================
def curate_and_translate(max_pick=10):
    """미번역 해외 뉴스를 GPT로 큐레이팅 후 번역"""
    import openai
    client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))

    # 1. 미번역 항목 조회 (title == original_title이고 country != kr)
    print("  미번역 항목 조회 중...")
    try:
        sql = "SELECT id, title, description, original_title FROM news WHERE country != 'kr' AND title = original_title ORDER BY created_at DESC LIMIT 50"
        r = subprocess.run(
            ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote', '--json', '--command', sql],
            capture_output=True, text=True, cwd=PROJECT_DIR, timeout=30)
        if r.returncode != 0:
            print(f"  DB 조회 실패: {r.stderr[:200]}")
            return
        data = json.loads(r.stdout)
        rows = data[0]['results'] if data and data[0].get('results') else []
    except Exception as e:
        print(f"  DB 조회 에러: {e}")
        return

    if not rows:
        print("  번역할 항목 없음")
        return

    print(f"  미번역 항목: {len(rows)}건")

    # 2. GPT 큐레이팅 - 제목 목록 보내서 상위 N건 선택
    title_list = ""
    for i, row in enumerate(rows):
        title_list += f"{i+1}. [ID:{row['id']}] {row['title']}\n"

    print(f"  GPT 큐레이팅 중 (상위 {max_pick}건 선별)...")
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"""You are a Korean AI news curator for aikorea24.kr.
From the following list of AI news titles, select the top {max_pick} most valuable items for Korean AI news readers.

Criteria for HIGH value:
- New AI model launches (GPT, Gemini, Claude, Qwen, DeepSeek etc.)
- Major investment/acquisition/partnership
- AI regulation/policy changes
- Security incidents or controversies
- Open-source releases
- Korea-related AI news
- Breakthrough research

Criteria for LOW value (exclude):
- Event/conference promotions
- Gaming/entertainment gossip
- Country-specific local news with no global impact
- Duplicate topics

Return ONLY a JSON array of the selected ID numbers. Example: [42, 15, 78, 3]
No explanation, no markdown."""},
                {"role": "user", "content": title_list}
            ],
            temperature=0.2,
            max_tokens=200
        )
        selected_ids = json.loads(resp.choices[0].message.content.strip())
        print(f"  선별된 항목: {len(selected_ids)}건 - IDs: {selected_ids}")
    except Exception as e:
        print(f"  큐레이팅 실패: {e}")
        return

    # 3. 선별된 항목만 번역
    selected_rows = [r for r in rows if r['id'] in selected_ids]
    translated = 0
    sql_updates = []

    for row in selected_rows:
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a Korean tech news translator. Translate the following English AI/tech news into natural Korean. Return ONLY a JSON object with keys \"title\" and \"description\". No markdown, no explanation."},
                    {"role": "user", "content": f"Title: {row['title']}\nDescription: {row['description'][:300]}"}
                ],
                temperature=0.3,
                max_tokens=500
            )
            result = json.loads(resp.choices[0].message.content.strip())
            kr_title = result.get('title', row['title']).replace("'", "''")
            kr_desc = result.get('description', row['description']).replace("'", "''")
            sql_updates.append(f"UPDATE news SET title='{kr_title}', description='{kr_desc}' WHERE id={row['id']};")
            translated += 1
            print(f"  번역 {translated}/{len(selected_rows)}: {kr_title[:40]}...")
        except Exception as e:
            print(f"  번역 실패 (ID:{row['id']}): {e}")

    # 4. DB 업데이트
    if sql_updates:
        sql_path = os.path.join(PROJECT_DIR, 'api_test', '_translate_update.sql')
        with open(sql_path, 'w') as f:
            f.write('\n'.join(sql_updates))
        try:
            r = subprocess.run(
                ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote', '--file', sql_path],
                capture_output=True, text=True, cwd=PROJECT_DIR, timeout=60)
            os.remove(sql_path)
            if r.returncode == 0:
                print(f"  DB 업데이트 완료: {translated}건 번역 저장")
            else:
                print(f"  DB 업데이트 실패: {r.stderr[:200]}")
        except Exception as e:
            print(f"  DB 업데이트 에러: {e}")
    else:
        print("  번역된 항목 없음")


def dedup_similar(articles):
    """동일 주제 다른 언론사 기사 제거"""
    seen = []
    result = []
    for a in articles:
        normalized = re.sub(r'[^가-힣a-zA-Z0-9]', '', a['title'])
        is_dup = False
        for s in seen:
            shorter = min(len(normalized), len(s))
            if shorter == 0:
                continue
            check_len = max(int(shorter * 0.7), 5)
            if normalized[:check_len] == s[:check_len]:
                is_dup = True
                break
        if not is_dup:
            seen.append(normalized)
            result.append(a)
    removed = len(articles) - len(result)
    if removed > 0:
        print(f"  유사 중복 제거: {removed}건")
    return result


def save_to_d1(articles):
    existing = get_existing()
    sql_lines = []
    skipped = 0
    for a in articles:
        h = title_hash(a['title'])
        if h in existing: skipped += 1; continue
        t = a['title'].replace("'", "''")[:200]
        l = a['link'].replace("'", "''")[:500]
        d = a['description'].replace("'", "''")[:500]
        s = a['source'].replace("'", "''")
        c = a['category']
        p = a.get('pub_date', datetime.now().strftime('%Y-%m-%d'))
        su = a.get('source_url', '').replace("'", "''")[:500]
        ot = a.get('original_title', '').replace("'", "''")[:200]
        co = a.get('country', 'kr').replace("'", "''")
        sql_lines.append(f"INSERT OR IGNORE INTO news (title, link, description, source, category, pub_date, source_url, original_title, country) VALUES ('{t}', '{l}', '{d}', '{s}', '{c}', '{p}', '{su}', '{ot}', '{co}');")
    if not sql_lines:
        print("  저장할 신규 항목 없음")
        return 0, skipped
    # SQL 파일로 저장 후 한번에 실행
    sql_path = os.path.join(PROJECT_DIR, 'api_test', '_batch_insert.sql')
    # 50개씩 나눠서 실행 (D1 제한 대응)
    saved = 0
    batch_size = 50
    for i in range(0, len(sql_lines), batch_size):
        batch = sql_lines[i:i+batch_size]
        with open(sql_path, 'w') as f:
            f.write('\n'.join(batch))
        try:
            r = subprocess.run(
                ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote', '--file', sql_path],
                capture_output=True, text=True, cwd=PROJECT_DIR, timeout=60)
            if r.returncode == 0:
                saved += len(batch)
                print(f"  배치 {i//batch_size+1}: {len(batch)}건 저장")
            else:
                print(f"  배치 {i//batch_size+1} 실패: {r.stderr[:200]}")
        except Exception as e:
            print(f"  배치 에러: {e}")
    # 정리
    try: os.remove(sql_path)
    except: pass
    return saved, skipped

# ============================================
# 정부 공문서 AI 학습데이터 API 연동
# ============================================
GOV_DOC_BASE = 'http://apis.data.go.kr/1741000/publicDoc'
GOV_DOC_ENDPOINTS = {
    'getDocPress': '보도자료',
    'getDocReport': '정책보고서',
    'getDocSpeech': '연설문',
}
GOV_DOC_KEYWORDS = ['AI', '인공지능', '디지털', '데이터', '클라우드', '스마트', '자율주행', '로봇', '반도체', '소프트웨어']

def fetch_gov_docs():
    """정부 공문서 AI 학습데이터에서 AI 관련 문서 수집"""
    api_key = os.environ.get('DATA_GO_KR_KEY', '')
    if not api_key:
        print('  DATA_GO_KR_KEY 없음 - 건너뜀')
        return []

    items = []
    for endpoint, doc_type in GOV_DOC_ENDPOINTS.items():
        for kw in GOV_DOC_KEYWORDS:
            try:
                params = urllib.parse.urlencode({'serviceKey': api_key, 'format': 'json', 'numOfRows': 10, 'pageNo': 1, 'title': kw})
                req = urllib.request.Request(f'{GOV_DOC_BASE}/{endpoint}?{params}', headers={'User-Agent': 'Mozilla/5.0'})
                data = json.loads(urllib.request.urlopen(req, timeout=15).read())
                body = data.get('response', {}).get('body', {})
                results = body.get('resultList', [])
                if isinstance(results, dict):
                    results = [results]
                for item in results:
                    meta = item.get('meta', item) if isinstance(item, dict) else {}
                    text_data = ''
                    if isinstance(item, dict) and 'data' in item:
                        text_data = item['data'].get('text', '')
                    title = meta.get('title', '')
                    if not title:
                        continue
                    combined = title.upper()
                    strong = any(w.upper() in combined for w in ['AI', '인공지능', 'GPT', '딥러닝', '머신러닝', 'LLM', '생성형', '챗봇'])
                    weak_cnt = sum(1 for w in ['디지털', '데이터', '클라우드', '스마트', '로봇', '반도체', '소프트웨어'] if w.upper() in combined)
                    if not strong and weak_cnt < 2:
                        continue
                    preview = text_data[:300] if text_data else f'{doc_type} - {meta.get("ministry", "")} ({meta.get("date", "")})'
                    items.append({
                        'title': title,
                        'link': 'https://www.data.go.kr/data/15125451/openapi.do',
                        'description': preview,
                        'source': f'정부공문서({doc_type})',
                        'category': 'policy',
                        'pub_date': meta.get('date', '')
                    })
            except Exception as e:
                pass
    # 제목 기준 중복 제거
    seen = set()
    unique = []
    for item in items:
        if item['title'] not in seen:
            seen.add(item['title'])
            unique.append(item)
    print(f'  정부공문서 AI관련: {len(unique)}건')
    return unique

# ===== 메인 =====
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=['kr', 'global', 'translate', 'all'], default='all')
    args = parser.parse_args()

    print('=' * 60)
    print(f"aikorea24 뉴스 수집 v2.0 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"소스: {args.source}")
    print('=' * 60)
    all_items = []

    if args.source in ('global', 'all'):
        print('\n[G1] 해외 AI 뉴스 (TechCrunch, MIT, SCMP)')
        all_items.extend(fetch_global_news())

    if args.source not in ('global', 'translate'):
        # 기존 국내 수집 (kr 또는 all)
        print('\n[1] 과기부 사업공고')
        all_items.extend(fetch_msit_announce())

        print('\n[2] 과기부 보도자료')
        all_items.extend(fetch_msit_press())

        print('\n[3] 정부24 혜택')
        all_items.extend(fetch_gov_benefits())

        print('\n[4] 네이버 뉴스')
        for q in QUERIES:
            r = fetch_naver(q)
            all_items.extend(r)
            print(f"  '{q}': {len(r)}건")

        print('\n[5] RSS')
        for url, name in RSS_FEEDS:
            r = fetch_rss(url, name)
            all_items.extend(r)
            print(f"  {name}: {len(r)}건")

        print('\n[6] 정부 AI 정책 뉴스')
        all_items.extend(fetch_naver_policy())

        print('\n[7] 행안부 보도자료')
        all_items.extend(fetch_mois_press())

        print('\n[8] 모두의 창업 프로젝트 뉴스')
        all_items.extend(fetch_startup_news())

        print('\n[9] AI 복지/접근성 뉴스')
        all_items.extend(fetch_welfare_news())

        print('\n[10] 정부 공문서')
        all_items.extend(fetch_gov_docs())

        print("\n[11] 기업마당 소상공인 AI 지원사업")
        all_items.extend(fetch_bizinfo_grants())

        print('\n[12] AI 노인복지 뉴스')
        all_items.extend(fetch_senior_news())

    if args.source == 'translate':
        print('\n[T1] GPT 큐레이팅 + 번역')
        curate_and_translate(max_pick=10)
        print('=' * 60)
        return

    print(f"\n총 수집: {len(all_items)}건")
    print('\nD1 저장 중...')
    saved, skipped = save_to_d1(all_items)
    print(f"  신규: {saved}건, 중복 스킵: {skipped}건")
    print('=' * 60)

    # [13] 노인복지 브리핑 자동 생성 (kr일 때만)
    if args.source in ('kr', 'all'):
      try:
        import subprocess as _sp
        print('\n[13] 노인복지 브리핑 생성...')
        _r = _sp.run(['python3', os.path.join(PROJECT_DIR, 'api_test', 'senior_briefing.py')],
                     capture_output=True, text=True, timeout=120)
        if _r.returncode == 0:
            print('  브리핑 생성 완료')
        else:
            print(f'  브리핑 생성 실패: {_r.stderr[:200]}')
      except Exception as _e:
        print(f'  브리핑 생성 에러: {_e}')

if __name__ == '__main__':
    main()
