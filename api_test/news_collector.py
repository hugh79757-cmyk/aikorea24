#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
import sys
import os
# stdout/stderr 안전 처리 (대시보드 원격 실행 시 fd 없을 수 있음)
try:
    sys.stdout.fileno()
except (OSError, AttributeError):
    import io as _io
    _fallback_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fallback.log")
    _fh = open(_fallback_log, "a", encoding="utf-8")
    sys.stdout = _fh
    sys.stderr = _fh


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
# 날짜 필터 (최근 3일 이내만 수집)
# ============================================
def parse_pub_date(pub_str):
    """RSS pub_date 문자열 → datetime 변환"""
    if not pub_str:
        return None
    formats = [
        '%a, %d %b %Y %H:%M:%S %z',   # RSS 표준: Wed, 29 Apr 2026 10:00:00 +0000
        '%a, %d %b %Y %H:%M:%S GMT',   # Wed, 29 Apr 2026 10:00:00 GMT
        '%a, %d %b %Y %H:%M:%S +0000', # Wed, 29 Apr 2026 10:00:00 +0000
        '%Y-%m-%dT%H:%M:%S%z',         # ISO 8601
        '%Y-%m-%dT%H:%M:%SZ',          # ISO 8601 UTC
        '%Y-%m-%d %H:%M:%S',           # 단순 datetime
        '%Y-%m-%d',                    # 날짜만
        '%Y%m%d',                      # 숫자형
    ]
    for fmt in formats:
        try:
            pub_clean = pub_str.strip()[:31].replace(' GMT', ' +0000')
            return datetime.strptime(pub_clean, fmt)
        except Exception:
            continue
    return None


def is_recent(pub_str, days=3):
    """최근 N일 이내 기사인지 확인. 날짜 파싱 실패 시 True(허용)"""
    dt = parse_pub_date(pub_str)
    if dt is None:
        return True  # 날짜 불명 → 일단 수집
    # timezone-aware 비교
    try:
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        return (now - dt).days <= days
    except Exception:
        return True




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
# 강화된 AI 필터 (신규 해외 소스 전용)
# ============================================
# 1차 키워드 (고신뢰, 단독으로 통과)
_PRIMARY_AI = [
    'AI', 'A.I.',
    'ARTIFICIAL INTELLIGENCE',
    'MACHINE LEARNING', 'DEEP LEARNING',
    'LARGE LANGUAGE MODEL', 'LLM', 'LLMS',
    'CHATGPT', 'GPT-4', 'GPT-5', 'CLAUDE', 'GEMINI', 'GROK', 'LLAMA', 'MISTRAL',
    'OPENAI', 'ANTHROPIC', 'DEEPMIND', 'HUGGING FACE',
    'GENERATIVE AI', 'GEN AI', 'GENAI',
    'NEURAL NETWORK', 'NEURAL NETWORKS',
    'NATURAL LANGUAGE PROCESSING', 'NLP',
    'COMPUTER VISION',
    'AUTONOMOUS', 'SELF-DRIVING',
]

# 2차 키워드 (복합 조건 — 2개 이상 포함 시 통과)
_SECONDARY_AI = [
    'ROBOT', 'ROBOTICS',
    'AUTOMATION',
    'ALGORITHM', 'ALGORITHMS',
    'DATA MODEL', 'FOUNDATION MODEL', 'FOUNDATION MODELS',
    'TRANSFORMER', 'DIFFUSION MODEL', 'DIFFUSION MODELS',
    'PROMPT', 'INFERENCE', 'FINE-TUNING', 'FINETUNING',
]

# REJECT: 순수 주가/실적 키워드 (AI 결합 없는 경우 제외)
_STOCK_KEYWORDS = ['STOCK', 'EARNINGS', 'REVENUE', 'PROFIT']


def _has_primary(text_up):
    """1차 키워드 매칭 (경계 조건 처리)"""
    for kw in _PRIMARY_AI:
        if kw == 'AI':
            if re.search(r'\bAI\b', text_up) or 'A.I.' in text_up:
                return True
        elif kw == 'A.I.':
            if 'A.I.' in text_up:
                return True
        elif kw == 'GPT-4' or kw == 'GPT-5' or kw == 'LLM' or kw == 'LLMS' or kw == 'NLP':
            if re.search(r'\b' + re.escape(kw) + r'\b', text_up):
                return True
        else:
            if kw in text_up:
                return True
    return False


def is_ai_related(title: str, summary: str = "") -> bool:
    """강화된 AI 필터 — 신규 'AI 키워드 필터링 필수' 해외 소스용"""
    title_up = title.upper().strip()
    summary_up = summary.upper().strip()
    text_up = title_up + ' ' + summary_up

    # === REJECT: self-driving car / autonomous vehicle 단독 (AI 언급 없음) ===
    if re.search(r'\bSELF-DRIVING CARS?\b', title_up) and not re.search(r'\bAI\b', title_up) and 'A.I.' not in title_up and 'ARTIFICIAL' not in title_up:
        return False
    if re.search(r'\bAUTONOMOUS VEHICLES?\b', title_up) and not re.search(r'\bAI\b', title_up) and 'A.I.' not in title_up and 'ARTIFICIAL' not in title_up:
        return False

    # === REJECT: 순수 주가/실적 (AI 결합 없는 경우) ===
    stock_count = sum(1 for kw in _STOCK_KEYWORDS if kw in text_up)
    if stock_count >= 2:
        has_ai_ref = any(kw in text_up for kw in
            ['AI ', ' A.I.', 'ARTIFICIAL INTELLIGENCE', 'CHATGPT', 'OPENAI',
             'ANTHROPIC', 'LLM', 'GPT-4', 'GPT-5', 'CLAUDE', 'GEMINI'])
        if not has_ai_ref:
            return False

    # === 1차 키워드 체크 (title 또는 summary에 하나라도 있으면 통과) ===
    if _has_primary(title_up) or _has_primary(summary_up):
        return True

    # === 2차 키워드 체크 (2개 이상 포함 시 통과) ===
    secondary_count = sum(1 for kw in _SECONDARY_AI if kw in text_up)
    if secondary_count >= 2:
        return True

    return False


def is_ai_related_relaxed(title: str, summary: str = "") -> bool:
    """완화된 AI 필터 — AI 전용 피드용 (1차 키워드만 체크 + REJECT 동일)"""
    title_up = title.upper().strip()
    summary_up = summary.upper().strip()
    text_up = title_up + ' ' + summary_up

    # REJECT 조건 (is_ai_related와 동일)
    if re.search(r'\bSELF-DRIVING CARS?\b', title_up) and not re.search(r'\bAI\b', title_up) and 'A.I.' not in title_up and 'ARTIFICIAL' not in title_up:
        return False
    if re.search(r'\bAUTONOMOUS VEHICLES?\b', title_up) and not re.search(r'\bAI\b', title_up) and 'A.I.' not in title_up and 'ARTIFICIAL' not in title_up:
        return False
    stock_count = sum(1 for kw in _STOCK_KEYWORDS if kw in text_up)
    if stock_count >= 2:
        has_ai_ref = any(kw in text_up for kw in
            ['AI ', ' A.I.', 'ARTIFICIAL INTELLIGENCE', 'CHATGPT', 'OPENAI',
             'ANTHROPIC', 'LLM', 'GPT-4', 'GPT-5', 'CLAUDE', 'GEMINI'])
        if not has_ai_ref:
            return False

    # 1차 키워드만 체크 (2차 키워드는 미적용)
    return _has_primary(title_up) or _has_primary(summary_up)


# ============================================
# 링크 유효성 검사 + Fallback
# ============================================
# HEAD 요청으로 링크 유효성 검사가 필요한 소스 (성능 이슈로 특정 소스만)
_VALIDATE_SOURCES = {'TechCrunch AI', 'CNBC Tech', 'BBC Technology', 'Business Insider AI'}

def validate_link(url, timeout=8):
    """HEAD 요청으로 URL이 유효한지 확인 (2xx/3xx면 True)"""
    if not url.startswith('http'):
        return False
    try:
        req = urllib.request.Request(url, method='HEAD',
            headers={'User-Agent': 'aikorea24-bot/4.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400
    except Exception:
        return False

def find_fallback_url(title, max_title_chars=80):
    """Google News RSS로 동일 기사 검색 → 첫 번째 결과 URL 반환"""
    import urllib.parse
    query = urllib.parse.quote(title[:max_title_chars])
    url = f'https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'aikorea24-bot/4.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        for item in root.iter('item'):
            link_el = item.find('link')
            if link_el is not None and link_el.text:
                found = link_el.text.strip()
                if found.startswith('http'):
                    return found
    except Exception:
        pass
    return None


# ============================================
# 중복 체크
# ============================================
def title_hash(title):
    normalized = re.sub(r'[^가-힣a-zA-Z0-9]', '', title)
    return hashlib.md5(normalized.encode()).hexdigest()


def get_existing():
    try:
        r = subprocess.run(
            ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote', '--yes',
             '--command', "SELECT title FROM news WHERE created_at >= datetime('now', '-7 days')", '--json'],
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
    """통합 중복 제거 - prefix + 키워드 + 고유명사 3단계"""
    seen = []
    result = []
    for a in articles:
        normalized = re.sub(r'[^가-힣a-zA-Z0-9]', '', a['title'])
        keywords = set(re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', a['title']))
        # 고유명사 추출 (영문 대문자 시작 단어 + 한글 2-4자 연속)
        proper_nouns = set(re.findall(r'[A-Z][a-zA-Z]{2,}', a['title']))
        proper_nouns |= set(re.findall(r'[가-힣]{2,4}(?=\s|,|$|\.|·)', a['title']))
        is_dup = False
        for s_norm, s_kw, s_pn in seen:
            shorter = min(len(normalized), len(s_norm))
            if shorter == 0:
                continue
            # 1단계: prefix 40% 일치
            check_len = max(int(shorter * 0.4), 5)
            if normalized[:check_len] == s_norm[:check_len]:
                is_dup = True; break
            # 2단계: 키워드 60% 이상 겹침
            if keywords and s_kw:
                overlap = len(keywords & s_kw) / max(min(len(keywords), len(s_kw)), 1)
                if overlap >= 0.6:
                    is_dup = True; break
            # 3단계: 고유명사 2개 이상 + 키워드 40% 겹침 (같은 이슈 다른 매체)
            if proper_nouns and s_pn:
                pn_match = len(proper_nouns & s_pn)
                kw_overlap = len(keywords & s_kw) / max(min(len(keywords), len(s_kw)), 1) if keywords and s_kw else 0
                if pn_match >= 2 and kw_overlap >= 0.4:
                    is_dup = True; break
        if not is_dup:
            seen.append((normalized, keywords, proper_nouns))
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
            max_completion_tokens=100)
        kr_title = resp.choices[0].message.content.strip().strip(chr(34)).strip(chr(39))
        return kr_title, description
    except Exception as e:
        print(f"    번역 실패: {e}")
        return title, description

def batch_translate(articles):
    """해외 기사 병렬 배치 번역 (10건/배치, 5스레드 동시)"""
    if not OPENAI_KEY:
        print("  OPENAI_API_KEY 없음 - 번역 건너뜀")
        return articles
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import openai
    client = openai.OpenAI(api_key=OPENAI_KEY)
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
    BATCH = 10
    batches = [targets[b:b+BATCH] for b in range(0, len(targets), BATCH)]
    print(f"  번역 대상: {len(targets)}건 → {len(batches)}배치 (5스레드 병렬)")
    def translate_batch(batch_idx, batch_num):
        items = []
        for j, i in enumerate(batch_idx):
            t = articles[i]["title"]
            d = articles[i].get("description", "")[:300]
            items.append(f"{j+1}. TITLE: {t}")
            items.append(f"   DESC: {d}")
        numbered = chr(10).join(items)
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Translate each numbered English AI/tech news item (TITLE and DESC) into natural Korean. Return the result in this exact format for each item:\n1. TITLE: 번역된 제목\n   DESC: 번역된 설명(2-3문장 자연스러운 한국어)\nKeep the same numbering. No explanation."},
                    {"role": "user", "content": numbered}
                ],
                max_completion_tokens=len(batch_idx) * 200)
            text = resp.choices[0].message.content.strip()
            kr_titles = []
            kr_descs = []
            for line in text.split(chr(10)):
                line = line.strip()
                if not line:
                    continue
                if "TITLE:" in line:
                    cleaned = line.split("TITLE:", 1)[1].strip()
                    cleaned = cleaned.lstrip("0123456789").lstrip(".").lstrip(")").strip()
                    kr_titles.append(cleaned)
                elif "DESC:" in line:
                    cleaned = line.split("DESC:", 1)[1].strip()
                    kr_descs.append(cleaned)
            return batch_num, batch_idx, kr_titles, kr_descs
        except Exception as e:
            print(f"    배치 {batch_num} 실패: {e}")
            return batch_num, batch_idx, [], []
    translated = 0
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(translate_batch, b, i+1) for i, b in enumerate(batches)]
        for future in as_completed(futures):
            batch_num, batch_idx, kr_titles, kr_descs = future.result()
            for k, idx in enumerate(batch_idx):
                articles[idx]["original_title"] = articles[idx]["title"]
                if k < len(kr_titles):
                    articles[idx]["title"] = kr_titles[k]
                if k < len(kr_descs) and kr_descs[k]:
                    articles[idx]["description"] = kr_descs[k]
                translated += 1
            print(f"    배치 {batch_num}: {len(batch_idx)}건 완료")
    print(f"  번역 완료: {translated}건 ({len(batches)}배치 병렬처리)")
    return articles

# ============================================
# 신규 해외 소스 분류 상수
# ============================================
REUTERS_URL = 'https://feeds.reuters.com/reuters/technologyNews'
REUTERS_FALLBACK_URL = 'https://news.google.com/rss/search?q=site:reuters.com+artificial+intelligence&hl=en&gl=US&ceid=US:en'

# AI 전용 피드 URL 목록 (1차 키워드만 필터링, REJECT 조건 동일)
AI_FEED_URLS = {
    'https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/spotlight/artificial-intelligence/rss.xml',
    'https://www.theguardian.com/technology/artificialintelligenceai/rss',
    'https://www.ft.com/artificial-intelligence?format=rss',
    'https://www.fastcompany.com/section/artificial-intelligence/rss',
}

# 신규 강화 필터 적용 소스 전체 URL 목록 (AI_FEED_URLS 포함)
ENHANCED_FILTER_URLS = {
    # 일반 테크 소스는 is_ai(기존 필터)로 처리 → 여기서 제거
    # AI 전용 피드만 강화 필터 적용
    'https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/spotlight/artificial-intelligence/rss.xml',
    'https://www.theguardian.com/technology/artificialintelligenceai/rss',
    'https://www.ft.com/artificial-intelligence?format=rss',
    'https://www.fastcompany.com/section/artificial-intelligence/rss',
    # 2026-06 추가 소스
    'https://thenextweb.com/feed',
    'https://www.cityam.com/feed/',
    'https://www.cnbc.com/id/19854910/device/rss/rss.html',
    'https://www.thenationalnews.com/arc/outboundfeeds/rss/?outputType=xml',
    'https://nltimes.nl/rssfeed2',
    # 2026-06 추가 소스 (AI 필터 필수)
    'https://www.heraldscotland.com/news/rss/',
    'https://www.theguardian.com/us-news/rss',
    'https://www.axios.com/feeds/feed.rss',
    'https://www.politico.eu/section/technology/feed/rss/',
    'https://nvidianews.nvidia.com/rss',
    'https://www.sec.gov/news/pressreleases.rss',
    'https://www.nature.com/subjects/machine-learning.rss',
    'https://news.google.com/rss/search?q=site:aljazeera.com+artificial+intelligence&hl=en&gl=US&ceid=US:en',
    'https://news.google.com/rss/search?q=site:anthropic.com+news&hl=en&gl=US&ceid=US:en',
    'https://www.memphisflyer.com/feed',
}


# ============================================
GLOBAL_RSS_FEEDS = [
    # 미국 주요
    ('https://techcrunch.com/category/artificial-intelligence/feed/', 'TechCrunch AI', 'us'),
    ('https://www.technologyreview.com/topic/artificial-intelligence/feed', 'MIT Tech Review', 'us'),
    ('https://arstechnica.com/tag/ai/feed/', 'Ars Technica AI', 'us'),
    ('https://venturebeat.com/category/ai/feed/', 'VentureBeat AI', 'us'),
    # 유럽
    # ('https://www.artificialintelligence-news.com/feed/', 'AI News EU', 'eu'),  # 403 차단
    # 아시아
    ('https://www.scmp.com/rss/320663/feed', 'SCMP China Tech', 'cn'),
    # AI 전문
    ('https://the-decoder.com/feed/', 'The Decoder', 'us'),
    # ('https://www.marktechpost.com/feed/', 'MarkTechPost', 'us'),  # 403 차단
    # 빅테크 블로그 + 뉴스레터
    ('https://www.theverge.com/rss/ai-artificial-intelligence/index.xml', 'The Verge AI', 'us'),
    ('https://www.wired.com/feed/tag/ai/latest/rss', 'Wired AI', 'us'),
    ('https://www.zdnet.com/topic/artificial-intelligence/rss.xml', 'ZDNET AI', 'us'),
    ('https://openai.com/blog/rss.xml', 'OpenAI Blog', 'us'),
    ('https://blog.google/technology/ai/rss/', 'Google AI Blog', 'us'),
    ('https://www.bensbites.com/feed', "Ben's Bites", 'us'),        # beehiiv -> 자체도메인
    # 바이브코딩 / AI 개발
    ('https://github.blog/feed/', 'GitHub Blog', 'us'),
    ('https://simonwillison.net/atom/everything/', 'Simon Willison', 'us'),
    # 추가 양질 피드 (기존 dead 피드 대체)
    ('https://huggingface.co/blog/feed.xml', 'HuggingFace Blog', 'us'),
    ('https://www.interconnects.ai/feed', 'Interconnects AI', 'us'),
    # === 신규 해외 RSS 소스 (2026-05 추가) ===
    # AI 키워드 필터링 필수 (is_ai_related 적용)
    ('http://rss.cnn.com/rss/cnn_tech.rss', 'CNN Technology', 'us'),
    (REUTERS_FALLBACK_URL, 'Reuters Technology (via Google News)', 'us'),
    ('https://feeds.businessinsider.com/custom/all', 'Business Insider AI', 'us'),
    ('https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml', 'NYT Technology', 'us'),
    ('https://feeds.washingtonpost.com/rss/business/technology', 'Washington Post Technology', 'us'),
    ('https://feeds.bbci.co.uk/news/technology/rss.xml', 'BBC Technology', 'us'),
    # AI 전용 피드 (is_ai_related_relaxed 적용 — 1차 키워드만)
    ('https://www.nytimes.com/svc/collections/v1/publish/https://www.nytimes.com/spotlight/artificial-intelligence/rss.xml', 'NYT AI Spotlight', 'us'),
    ('https://www.theguardian.com/technology/artificialintelligenceai/rss', 'The Guardian AI', 'us'),
    ('https://www.ft.com/artificial-intelligence?format=rss', 'Financial Times AI', 'us'),
    ('https://www.fastcompany.com/section/artificial-intelligence/rss', 'Fast Company AI', 'us'),
    # === 신규 해외 RSS 소스 (2026-06 추가) ===
    # AI 키워드 필터링 필수 (is_ai_related 적용)
    ('https://thenextweb.com/feed', 'The Next Web', 'eu'),
    ('https://www.cityam.com/feed/', 'City AM', 'eu'),
    ('https://www.cnbc.com/id/19854910/device/rss/rss.html', 'CNBC Tech', 'us'),
    ('https://www.thenationalnews.com/arc/outboundfeeds/rss/?outputType=xml', 'The National News', 'eu'),
    ('https://nltimes.nl/rssfeed2', 'NL Times', 'eu'),
    # === 신규 해외 RSS 소스 (2026-06-14 추가) ===
    # AI 키워드 필터링 필수 (is_ai_related 적용)
    ('https://www.heraldscotland.com/news/rss/', 'Herald Scotland', 'eu'),
    ('https://www.theguardian.com/us-news/rss', 'Guardian US News', 'us'),
    ('https://www.axios.com/feeds/feed.rss', 'Axios', 'us'),
    ('https://www.politico.eu/section/technology/feed/rss/', 'Politico EU Tech', 'eu'),
    ('https://nvidianews.nvidia.com/rss', 'NVIDIA Newsroom', 'us'),
    ('https://www.sec.gov/news/pressreleases.rss', 'SEC Press Releases', 'us'),
    ('https://www.nature.com/subjects/machine-learning.rss', 'Nature ML', 'us'),
    ('https://news.google.com/rss/search?q=site:aljazeera.com+artificial+intelligence&hl=en&gl=US&ceid=US:en', 'Al Jazeera AI (via Google News)', 'us'),
    ('https://news.google.com/rss/search?q=site:anthropic.com+news&hl=en&gl=US&ceid=US:en', 'Anthropic News (via Google News)', 'us'),
    ('https://www.memphisflyer.com/feed', 'Memphis Flyer', 'us'),
]


def fetch_rss_global(url, source, country='us', limit=12, filter_fn=None):
    """해외 RSS 수집 + AI 필터 (filter_fn 지정 시 해당 필터 사용, 기본 is_ai)"""
    if filter_fn is None:
        filter_fn = is_ai
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
            if not filter_fn(orig_title, orig_desc):
                continue
            if not is_recent(pub, days=3):
                continue

            # 링크 유효성 검사 (지정된 소스만, 성능 보호)
            if source in _VALIDATE_SOURCES:
                if not validate_link(link):
                    print(f"    ⚠ 링크 유효성 실패: {link[:60]}... → fallback 시도")
                    fallback = find_fallback_url(orig_title)
                    if fallback:
                        print(f"    ✅ fallback URL 발견: {fallback[:60]}...")
                        link = fallback
                    else:
                        print(f"    ❌ fallback 실패 — 해당 기사 skip")
                        continue

            items.append({
                'title': orig_title,
                'link': link,
                'description': orig_desc[:300],
                'source': source,
                'category': 'global',
                'pub_date': pub,
                'source_url': url,
                'original_title': orig_title,
                'country': country,
            })
            if len(items) >= limit:
                break
        print(f"  {source}: {len(items)}건")
    except Exception as e:
        print(f"  {source} 실패: {e}")
        # Reuters fallback: 실패 시 Google News 우회 URL 재시도
        if url == REUTERS_URL:
            print(f"  → Reuters fallback 시도 중...")
            try:
                fallback_req = urllib.request.Request(REUTERS_FALLBACK_URL, headers={'User-Agent': 'aikorea24-bot/4.0'})
                with urllib.request.urlopen(fallback_req, timeout=15) as resp:
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
                    if not filter_fn(orig_title, orig_desc):
                        continue
                    if not is_recent(pub, days=3):
                        continue
                    items.append({
                        'title': orig_title,
                        'link': link,
                        'description': orig_desc[:300],
                        'source': 'Reuters Technology (via Google News)',
                        'category': 'global',
                        'pub_date': pub,
                        'source_url': REUTERS_FALLBACK_URL,
                        'original_title': orig_title,
                        'country': country,
                    })
                    if len(items) >= limit:
                        break
                print(f"  Reuters (Google News fallback): {len(items)}건")
            except Exception as e2:
                print(f"  Reuters fallback도 실패: {e2}")
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
    """해외 뉴스 전체 수집 (소스별 필터 자동 분기)"""
    all_items = []
    for url, name, country in GLOBAL_RSS_FEEDS:
        if url in ENHANCED_FILTER_URLS:
            if url in AI_FEED_URLS:
                # AI 전용 피드: 1차 키워드만 + REJECT
                all_items.extend(fetch_rss_global(url, name, country, limit=7, filter_fn=is_ai_related_relaxed))
            else:
                # 일반 테크 뉴스: 강화 필터 적용
                all_items.extend(fetch_rss_global(url, name, country, limit=7, filter_fn=is_ai_related))
        else:
            # 기존 소스: 기존 is_ai 필터 유지
            all_items.extend(fetch_rss_global(url, name, country, limit=7))
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
    ('https://www.aitimes.kr/rss/allArticle.xml', '인공지능신문'),
    ('https://www.digitaltoday.co.kr/rss/allArticle.xml', '디지털투데이'),
    # ('https://www.bloter.net/feed', '블로터'),  # 404 dead
    # ('https://zdnet.co.kr/rss/allArticle.xml', 'ZDNet Korea'),  # 404 dead
    ('https://www.itchosun.com/rss/allArticle.xml', 'IT조선 RSS'),
    ('https://news.hada.io/rss/news', 'GeekNews'),
]

# 네이버 검색 (보조 역할, 최소화)
NAVER_QUERIES = ['인공지능 AI 최신', 'AI 스타트업']


def fetch_rss_kr(url, source, limit=15):
    """국내 RSS 수집 + AI 필터"""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        xml = urllib.request.urlopen(req, timeout=10).read()
        tree = ET.fromstring(xml)
        results = []
        for item in tree.findall('.//item')[:50]:  # 많이 읽고 필터링
            title = clean(item.findtext('title', ''))
            desc = clean(item.findtext('description', ''))
            pub_date_raw = item.findtext('pubDate', '')
            if not is_recent(pub_date_raw, days=3):
                continue
            if not is_ai(title, desc):
                continue
            results.append({
                'title': title,
                'link': item.findtext('link', ''),
                'description': desc[:200],
                'source': source,
                'category': 'news',
                'pub_date': pub_date_raw or datetime.now().strftime('%Y-%m-%d'),
                'country': 'kr',
            })
            if len(results) >= limit:
                break
        print(f"  {source}: {len(results)}건")
        return results
    except Exception as e:
        print(f"  {source} 실패: {e}")
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
    saved = 0
    batch_size = 50
    for i in range(0, len(sql_lines), batch_size):
        batch = sql_lines[i:i+batch_size]
        batch_num = i // batch_size + 1
        sql_path = os.path.join(PROJECT_DIR, 'api_test', f'_batch_{batch_num}.sql')
        try:
            with open(sql_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(batch))
                f.flush()
                os.fsync(f.fileno())
            r = subprocess.run(
                ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote', '--yes', '--file', sql_path],
                capture_output=True, text=True, cwd=PROJECT_DIR, timeout=90)
            if r.returncode == 0:
                saved += len(batch)
                print(f"  배치 {batch_num}: {len(batch)}건 저장")
            else:
                print(f"  배치 {batch_num} 실패: {r.stderr[:200]}")
        except Exception as e:
            print(f"  배치 {batch_num} 에러: {e}")
        finally:
            try:
                os.remove(sql_path)
            except:
                pass
    return saved, skipped


# ============================================
# 메인
# ============================================

# ============================================
# Cloudflare Cache Purge (수집 완료 후 즉시 반영)
# ============================================
def purge_cloudflare_cache():
    """수집 완료 후 뉴스 관련 Cloudflare 엣지 캐시 즉시 무효화"""
    import urllib.request, json
    token   = os.environ.get('CLOUDFLARE_API_TOKEN', '')
    zone_id = os.environ.get('CLOUDFLARE_ZONE_ID', '')

    if not token or not zone_id:
        print("  ⚠ CLOUDFLARE_API_TOKEN 또는 ZONE_ID 미설정 — purge 스킵")
        return

    urls = [
        'https://aikorea24.kr/api/news/latest',
        'https://aikorea24.kr/api/news/global',
        'https://aikorea24.kr/api/news/senior',
        'https://aikorea24.kr/api/news/policy',
        'https://aikorea24.kr/',
        'https://aikorea24.kr/news',
        'https://aikorea24.kr/global',
    ]

    payload = json.dumps({'files': urls}).encode()
    req = urllib.request.Request(
        f'https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache',
        data=payload,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        method='POST'
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get('success'):
            print(f"  ✅ Cloudflare 캐시 purge 완료 ({len(urls)}개 URL)")
        else:
            print(f"  ❌ purge 실패: {result.get('errors')}")
    except Exception as e:
        print(f"  ❌ purge 요청 실패: {e}")

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
    purge_cloudflare_cache()
    print('=' * 60)


if __name__ == '__main__':
    main()
