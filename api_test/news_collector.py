#!/usr/bin/env python3
"""
aikorea24 뉴스 수집기 v4.0
- 해외 50% : 국내 50% 비율
- 전체 AI 필터 적용
- 네이버 의존도 최소화
- 통합 중복 제거
- 수집 → 번역 1단계 통합
"""
import os, json, subprocess, urllib.request, urllib.parse, hashlib, re
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET
from html import unescape


# ============================================
# 환경 설정
# ============================================
def load_env(path):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    if line.startswith('export '):
                        line = line[7:]
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
load_env(os.path.join(PROJECT_DIR, 'api_test', '.env.sh'))
load_env(os.path.join(PROJECT_DIR, '.env'))

NAVER_ID = os.environ.get('NAVER_CLIENT_ID', '')
NAVER_SECRET = os.environ.get('NAVER_CLIENT_SECRET', '')
DATA_KEY = os.environ.get('DATA_GO_KR_KEY', '')
OPENAI_KEY = os.environ.get('OPENAI_API_KEY', '')


# ============================================
# 유틸리티
# ============================================
def clean(text):
    if not text: return ''
    text = unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ============================================
# AI 필터 (국내 + 해외 공용)
# ============================================
STRONG = ['AI', 'A.I', '인공지능', 'GPT', 'ChatGPT', '챗GPT', 'LLM',
    '생성형', '딥러닝', '머신러닝', '딥페이크', '자연어처리',
    '앤트로픽', 'Anthropic', '오픈AI', 'OpenAI', '클로드', 'Claude',
    'Gemini', '제미나이', 'Copilot', '코파일럿', '코덱스',
    'Midjourney', '미드저니', 'Stable Diffusion', 'DALL-E', 'Sora',
    'AI 바우처', 'AI바우처', 'AI 스타트업', '휴머노이드',
    '피지컬 AI', 'AI 서비스', 'AI 기반', 'AI 모드',
    # 영문 STRONG (해외용)
    'ARTIFICIAL INTELLIGENCE', 'MACHINE LEARNING', 'DEEP LEARNING',
    'NEURAL NETWORK', 'GENERATIVE AI', 'LARGE LANGUAGE MODEL',
    'DEEPSEEK', 'MISTRAL', 'LLAMA', 'DIFFUSION MODEL',
    'AGI', 'SUPERINTELLIGENCE', 'AGENTIC']

WEAK = ['데이터센터', '클라우드', '반도체', '엔비디아', 'GPU',
    '자율주행', '로봇', '알고리즘', '빅데이터', '테크', '4차 산업',
    '디지털 전환', '소프트웨어', '스타트업',
    # 영문 WEAK (해외용)
    'NVIDIA', 'SEMICONDUCTOR', 'DATA CENTER', 'CLOUD', 'AUTONOMOUS',
    'ROBOT', 'ALGORITHM', 'STARTUP', 'TECH']

EXCLUDE = ['귀촌', '귀어', '귀농', '축산', '양식', '어업',
    '교복', '생리대', '시승', '전시장 이벤트', '부동산', '아파트',
    '야구', '축구', '농구', '올림픽', '날씨', '태풍', '폭설',
    '결혼', '출산', '장례', '과학관', '과학특강', '마약',
    '행정통합', '통합특별', '도서관', '연휴 이벤트', '르노',
    '교육청', '임대', '재건축',
    # 해외 EXCLUDE
    'RECIPE', 'SPORTS', 'FASHION', 'CELEBRITY', 'GOSSIP']

SOFT_EXCLUDE = ['배터리', '전기차', '완성차', '희망퇴직', '위로금',
    '구조조정', '파업', '노조', '주가', '시가총액', '배당',
    '공모주', '상장폐지', '부채', '적자', '감원']


def is_ai(title, desc=''):
    """통합 AI 필터 - 국내/해외 모두 사용"""
    title_up = title.upper()
    desc_up = desc.upper()
    text = title_up + ' ' + desc_up

    for kw in EXCLUDE:
        if kw.upper() in text:
            return False

    for kw in SOFT_EXCLUDE:
        if kw.upper() in text:
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

    def has_strong(s):
        for kw in STRONG:
            ku = kw.upper()
            if len(ku) <= 3:
                if re.search(r'(?<![A-Z])' + re.escape(ku) + r'(?![A-Z])', s):
                    return True
            else:
                if ku in s:
                    return True
        return False

    if has_strong(title_up):
        return True
    if has_strong(desc_up):
        weak_count = sum(1 for kw in WEAK if kw.upper() in text)
        if weak_count >= 2:
            return True
    return False


# ============================================
# 중복 체크
# ============================================
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
            data = json.loads(r.stdout)
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


def dedup_similar(articles):
    """통합 중복 제거 - category 무관, 제목 기준"""
    seen = []
    result = []
    for a in articles:
        normalized = re.sub(r'[^가-힣a-zA-Z0-9]', '', a['title'])
        keywords = set(re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', a['title']))
        is_dup = False
        for s_norm, s_kw in seen:
            shorter = min(len(normalized), len(s_norm))
            if shorter == 0:
                continue
            check_len = max(int(shorter * 0.5), 5)
            if normalized[:check_len] == s_norm[:check_len]:
                is_dup = True; break
            if keywords and s_kw:
                overlap = len(keywords & s_kw) / max(min(len(keywords), len(s_kw)), 1)
                if overlap >= 0.65:
                    is_dup = True; break
        if not is_dup:
            seen.append((normalized, keywords))
            result.append(a)
    removed = len(articles) - len(result)
    if removed > 0:
        print(f"  유사 중복 제거: {removed}건")
    return result


# ============================================
# 번역
# ============================================
def translate_to_korean(title, description=""):
    """영문 → 한국어 번역 (타이틀만, GPT-4o-mini)"""
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Translate the following English AI/tech news title into natural Korean. Return ONLY the translated title text. No quotes, no explanation."},
                {"role": "user", "content": title}
            ],
            temperature=0.3, max_tokens=100)
        kr_title = resp.choices[0].message.content.strip().strip(chr(34)).strip(chr(39))
        return kr_title, description
    except Exception as e:
        print(f"    번역 실패: {e}")
        return title, description

def batch_translate(articles):
    """해외 기사 배치 번역 (10건씩 묶어서 1회 API 호출)"""
    if not OPENAI_KEY:
        print("  OPENAI_API_KEY 없음 - 번역 건너뜀")
        return articles
    import openai
    client = openai.OpenAI(api_key=OPENAI_KEY)
    # 번역 대상 추출
    targets = []
    for i, a in enumerate(articles):
        if a.get("country", "kr") == "kr":
            continue
        if a.get("original_title") and a["title"] != a["original_title"]:
            continue
        targets.append(i)
    if not targets:
        print("  번역할 항목 없음")
        return articles
    print(f"  번역 대상: {len(targets)}건 (10건씩 배치)")
    BATCH = 10
    translated = 0
    for b in range(0, len(targets), BATCH):
        batch_idx = targets[b:b+BATCH]
        titles = [articles[i]["title"] for i in batch_idx]
        numbered = chr(10).join(f"{j+1}. {t}" for j, t in enumerate(titles))
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Translate each numbered English AI/tech news title into natural Korean. Return ONLY the numbered list with Korean translations. Keep the same numbering. No explanation."},
                    {"role": "user", "content": numbered}
                ],
                temperature=0.3, max_tokens=len(batch_idx) * 80)
            lines = resp.choices[0].message.content.strip().split(chr(10))
            kr_titles = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                cleaned = line.lstrip("0123456789").lstrip(".").lstrip(")").strip()
                if cleaned:
                    kr_titles.append(cleaned)
            for k, idx in enumerate(batch_idx):
                articles[idx]["original_title"] = articles[idx]["title"]
                if k < len(kr_titles):
                    articles[idx]["title"] = kr_titles[k]
                translated += 1
            print(f"    배치 {b//BATCH+1}: {len(batch_idx)}건 번역")
        except Exception as e:
            print(f"    배치 {b//BATCH+1} 실패: {e}")
            for idx in batch_idx:
                articles[idx]["original_title"] = articles[idx]["title"]
    print(f"  번역 완료: {translated}건 ({(len(targets)-1)//BATCH+1}회 API 호출)")
    return articles

# 해외 뉴스 수집 (목표: 전체의 50%)
# ============================================
GLOBAL_RSS_FEEDS = [
    # 미국 주요
    ('https://techcrunch.com/category/artificial-intelligence/feed/', 'TechCrunch AI', 'us'),
    ('https://www.technologyreview.com/topic/artificial-intelligence/feed', 'MIT Tech Review', 'us'),
    ('https://www.theverge.com/rss/ai-artificial-intelligence/index.xml', 'The Verge AI', 'us'),
    ('https://arstechnica.com/tag/ai/feed/', 'Ars Technica AI', 'us'),
    ('https://venturebeat.com/category/ai/feed/', 'VentureBeat AI', 'us'),
    # 유럽
    ('https://www.artificialintelligence-news.com/feed/', 'AI News EU', 'eu'),
    ('https://www.euronews.com/rss?level=theme&name=ai', 'Euronews AI', 'eu'),
    # 아시아
    ('https://www.scmp.com/rss/320663/feed', 'SCMP China Tech', 'cn'),
    ('https://asia.nikkei.com/rss/feed/nar', 'Nikkei Asia', 'jp'),
    # AI 전문
    ('https://the-decoder.com/feed/', 'The Decoder', 'us'),
    ('https://www.marktechpost.com/feed/', 'MarkTechPost', 'us'),
]


def fetch_rss_global(url, source_name, country='us', limit=12):
    """해외 RSS 수집 + AI 필터"""
    items = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'aikorea24-bot/4.0'})
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
            if not is_ai(orig_title, orig_desc):
                continue
            items.append({
                'title': orig_title,
                'link': link,
                'description': orig_desc[:300],
                'source': source_name,
                'category': 'global',
                'pub_date': pub,
                'source_url': url,
                'original_title': orig_title,
                'country': country,
            })
            if len(items) >= limit:
                break
        print(f"  {source_name}: {len(items)}건")
    except Exception as e:
        print(f"  {source_name} 실패: {e}")
    return items


def fetch_hackernews_ai(limit=15):
    """Hacker News AI 뉴스 (최근 7일만)"""
    items = []
    cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%dT00:00:00')
    try:
        url = f'https://hn.algolia.com/api/v1/search?query=AI+artificial+intelligence&tags=story&hitsPerPage=30&numericFilters=created_at_i>{int((datetime.now() - timedelta(days=7)).timestamp())}'
        req = urllib.request.Request(url, headers={'User-Agent': 'aikorea24-bot/4.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        data = json.loads(raw)
        for hit in data.get('hits', []):
            orig_title = hit.get('title', '').strip()
            link = hit.get('url') or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
            if not orig_title or not is_ai(orig_title):
                continue
            items.append({
                'title': orig_title,
                'link': link,
                'description': '',
                'source': 'Hacker News',
                'category': 'global',
                'pub_date': hit.get('created_at', '')[:10],
                'source_url': 'https://news.ycombinator.com',
                'original_title': orig_title,
                'country': 'us',
            })
            if len(items) >= limit:
                break
        print(f"  Hacker News: {len(items)}건")
    except Exception as e:
        print(f"  Hacker News 실패: {e}")
    return items


def collect_global():
    """해외 뉴스 전체 수집"""
    all_items = []
    for url, name, country in GLOBAL_RSS_FEEDS:
        all_items.extend(fetch_rss_global(url, name, country, limit=12))
    all_items.extend(fetch_hackernews_ai(limit=15))
    return all_items


# ============================================
# 국내 뉴스 수집 (목표: 전체의 50%)
# ============================================

# 국내 RSS (AI 전문 매체 - 네이버 대체 핵심)
KR_RSS_FEEDS = [
    ('https://www.aitimes.com/rss/allArticle.xml', 'AI타임스'),
    ('http://rss.etnews.com/Section901.xml', '전자신문'),
    ('https://it.chosun.com/rss/allArticle.xml', 'IT조선'),
]

# 네이버 검색 (보조 역할, 최소화)
NAVER_QUERIES = ['인공지능 AI 최신', 'AI 스타트업']


def fetch_rss_kr(url, source_name, limit=15):
    """국내 RSS 수집 + AI 필터"""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        xml = urllib.request.urlopen(req, timeout=10).read()
        tree = ET.fromstring(xml)
        results = []
        for item in tree.findall('.//item')[:50]:  # 많이 읽고 필터링
            title = clean(item.findtext('title', ''))
            desc = clean(item.findtext('description', ''))
            if not is_ai(title, desc):
                continue
            results.append({
                'title': title,
                'link': item.findtext('link', ''),
                'description': desc[:200],
                'source': source_name,
                'category': 'news',
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'country': 'kr',
            })
            if len(results) >= limit:
                break
        print(f"  {source_name}: {len(results)}건")
        return results
    except Exception as e:
        print(f"  {source_name} 실패: {e}")
        return []


def fetch_naver(query, display=5):
    """네이버 뉴스 (보조 - display=5로 축소)"""
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
            if not is_ai(title, desc):
                continue
            results.append({
                'title': title, 'link': item['link'],
                'description': desc[:200], 'source': '네이버뉴스',
                'category': 'news',
                'pub_date': datetime.now().strftime('%Y-%m-%d'),
                'country': 'kr',
            })
        return results
    except Exception as e:
        print(f"  네이버 '{query}' 실패: {e}")
        return []


def fetch_msit_announce(limit=20):
    """과기부 사업공고"""
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
                    'category': 'grant', 'pub_date': item.get('pressDt', ''),
                    'country': 'kr'})
        print(f"  과기부 사업공고: {len(results)}건")
        return results
    except Exception as e:
        print(f"  과기부 사업공고 실패: {e}")
        return []


def fetch_msit_press(limit=15):
    """과기부 보도자료"""
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
                    'category': 'policy', 'pub_date': item.get('pressDt', ''),
                    'country': 'kr'})
        print(f"  과기부 보도자료: {len(results)}건")
        return results
    except Exception as e:
        print(f"  과기부 보도자료 실패: {e}")
        return []


def collect_kr():
    """국내 뉴스 전체 수집"""
    all_items = []

    # 핵심: 국내 AI 전문 매체 RSS (AI타임스 + 전자신문 + IT조선)
    print('\n  [KR-1] 국내 AI 매체 RSS')
    for url, name in KR_RSS_FEEDS:
        all_items.extend(fetch_rss_kr(url, name, limit=15))

    # 보조: 네이버 뉴스 (2개 쿼리 × 5건 = 최대 10건)
    print('\n  [KR-2] 네이버 뉴스 (보조)')
    for q in NAVER_QUERIES:
        r = fetch_naver(q, display=5)
        all_items.extend(r)
        print(f"    '{q}': {len(r)}건")

    # 정부 소스 (AI 정책/지원사업)
    print('\n  [KR-3] 과기부 사업공고')
    all_items.extend(fetch_msit_announce(limit=20))

    print('\n  [KR-4] 과기부 보도자료')
    all_items.extend(fetch_msit_press(limit=15))

    return all_items


# ============================================
# D1 저장
# ============================================
def save_to_d1(articles):
    existing = get_existing()
    sql_lines = []
    skipped = 0
    for a in articles:
        h = title_hash(a['title'])
        if h in existing:
            skipped += 1; continue
        t = a['title'].replace("'", "''")[:200]
        l = a['link'].replace("'", "''")[:500]
        d = a.get('description', '').replace("'", "''")[:500]
        s = a['source'].replace("'", "''")
        c = a['category']
        p = a.get('pub_date', datetime.now().strftime('%Y-%m-%d'))
        su = a.get('source_url', '').replace("'", "''")[:500]
        ot = a.get('original_title', '').replace("'", "''")[:200]
        co = a.get('country', 'kr').replace("'", "''")
        sql_lines.append(
            f"INSERT OR IGNORE INTO news (title, link, description, source, category, pub_date, source_url, original_title, country) "
            f"VALUES ('{t}', '{l}', '{d}', '{s}', '{c}', '{p}', '{su}', '{ot}', '{co}');")
    if not sql_lines:
        print("  저장할 신규 항목 없음")
        return 0, skipped
    sql_path = os.path.join(PROJECT_DIR, 'api_test', '_batch_insert.sql')
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
    try:
        os.remove(sql_path)
    except:
        pass
    return saved, skipped


# ============================================
# 메인
# ============================================
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=['kr', 'global', 'all'], default='all')
    args = parser.parse_args()

    print('=' * 60)
    print(f"aikorea24 뉴스 수집 v4.0 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"소스: {args.source} | 목표: 해외50% 국내50% | 전체 AI필터")
    print('=' * 60)

    global_items = []
    kr_items = []

    # === 해외 수집 ===
    if args.source in ('global', 'all'):
        print('\n[해외 뉴스 수집]')
        global_items = collect_global()
        global_items = dedup_similar(global_items)
        print(f"  해외 중복제거 후: {len(global_items)}건")

    # === 국내 수집 ===
    if args.source in ('kr', 'all'):
        print('\n[국내 뉴스 수집]')
        kr_items = collect_kr()
        kr_items = dedup_similar(kr_items)
        print(f"  국내 중복제거 후: {len(kr_items)}건")

    # === 비율 리포트 ===
    total = len(global_items) + len(kr_items)
    if total > 0:
        g_pct = len(global_items) / total * 100
        k_pct = len(kr_items) / total * 100
        print(f"\n[비율] 해외: {len(global_items)}건({g_pct:.0f}%) | 국내: {len(kr_items)}건({k_pct:.0f}%)")

    # === 통합 후 최종 중복 제거 ===
    all_items = global_items + kr_items
    all_items = dedup_similar(all_items)
    print(f"\n[최종] 통합 중복제거 후: {len(all_items)}건")

    # === 해외 뉴스 번역 ===
    if global_items:
        print('\n[번역] 해외 뉴스 한국어 번역...')
        all_items = batch_translate(all_items)

    # === D1 저장 ===
    print('\n[저장] D1 저장 중...')
    saved, skipped = save_to_d1(all_items)
    print(f"  신규: {saved}건 | 중복 스킵: {skipped}건")

    print('\n' + '=' * 60)
    print(f"완료! 총 {saved}건 저장")
    print('=' * 60)


if __name__ == '__main__':
    main()
