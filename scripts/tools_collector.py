#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 AI 툴 대량 확충기 v2.0
- Product Hunt RSS / Hacker News API → 실시간 수집
- GPT-4o-mini 한국어 메타데이터 생성
- im-not-ai 3단계 한국어 품질 보강
- MD 파일 생성 → git commit → 텔레그램 알림

재사용: news_collector.py의 fetch_rss_global 패턴, batch_translate, load_env, send_telegram
"""
import os, sys, json, re, hashlib, subprocess, urllib.request, urllib.parse
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET
from html import unescape
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts'))
sys.path.insert(0, os.path.join(PROJECT_DIR, 'api_test'))

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

load_env(os.path.join(PROJECT_DIR, '.env'))
load_env(os.path.join(PROJECT_DIR, 'api_test', '.env.sh'))

OPENAI_KEY = os.environ.get('OPENAI_API_KEY', '')

# ============================================
# news_collector.py에서 batch_translate import
# ============================================
try:
    # api_test 디렉토리에서 import
    sys.path.insert(0, os.path.join(PROJECT_DIR, 'api_test'))
    from news_collector import batch_translate, load_env as nc_load_env
except ImportError:
    batch_translate = None
    nc_load_env = None

# ============================================
# 수집 함수: Product Hunt RSS
# ============================================
PRODUCT_HUNT_FEED = 'https://www.producthunt.com/feed'

# AI 툴로 분류할 키워드 (Product Hunt: 제목 기준으로만 매칭)
PH_AI_KEYWORDS = [
    'AI', 'GPT', 'LLM', 'LLaMA', 'Mistral', 'Claude',
    'Gemini', 'Copilot', 'OpenAI', 'Anthropic', 'ChatGPT',
    'machine learning', 'deep learning', 'neural network',
    'artificial intelligence', 'generative',
    'no-code LLM', 'AI agent', 'AI tool', 'AI-powered',
]

# REJECT 키워드 — AI 툴이 아닌 항목 제외 (news_collector.py EXCLUDE 패턴 참고)
PH_REJECT_KEYWORDS = [
    'directory', 'list', 'curated', 'handpicked', 'collection of',
    'launcher', 'prompt launcher', 'ssh', 'server management',
    'product hunt analytics', 'radar for product hunt',
    'analytics beyond', 'leaderboard',
    # HN 개인 프로젝트 발표 (실제 툴 아님)
    'i built', 'i made', 'i created', 'i wrote',
]

# Product Hunt 설명에서 가격 정보 추출
PH_PRICE_PATTERNS = [
    (r'\$(0|)\s*free', 'Free'),
    (r'free', 'Free'),
    (r'\$(\d+)/month', r'$\1/month'),
    (r'\$(\d+)/mo', r'$\1/month'),
    (r'\$(\d+)\.?\d*\s*(one-time|one time|lifetime)', r'$\1 one-time'),
    (r'from\s*\$(\d+)', r'from $\1'),
]


def extract_price(description: str) -> str:
    """Product Hunt 설명에서 가격 정보 추출"""
    desc_lower = description.lower()
    for pattern, replacement in PH_PRICE_PATTERNS:
        m = re.search(pattern, desc_lower)
        if m:
            # replacement이 lambda가 아닌 문자열이면
            if isinstance(replacement, str):
                result = replacement
                for i, group in enumerate(m.groups()):
                    placeholder = f'\\{i+1}'
                    # 간단 치환
                return result
            return m.group(0)
    return ''


def is_ai_tool(title: str, description: str = '') -> bool:
    """Product Hunt/HN 아이템이 AI 툴인지 판별 (제목 기준)"""
    title_lower = title.lower()
    desc_lower = description.lower()
    combined = title_lower + ' ' + desc_lower

    # === REJECT: AI 툴이 아닌 항목 먼저 차단 ===
    for kw in PH_REJECT_KEYWORDS:
        if kw.lower() in combined:
            return False

    # === AI 키워드 매칭 ===
    for kw in PH_AI_KEYWORDS:
        if kw.lower() in title_lower:
            return True
    # description에도 ai 키워드가 포함된 경우 + 제목에도 'tool'이 있는 경우 완화
    if 'tool' in title_lower or 'app' in title_lower:
        for kw in ['ai', 'intelligence', 'neural', 'deep learning', 'machine learning']:
            if kw in desc_lower:
                return True
    return False


NS_ATOM = '{http://www.w3.org/2005/Atom}'

def fetch_product_hunt(limit=15) -> list:
    """Product Hunt Atom 피드 → AI 툴 목록"""
    items = []
    try:
        req = urllib.request.Request(
            PRODUCT_HUNT_FEED,
            headers={'User-Agent': 'aikorea24-bot/2.0 (RSS collector)'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        for entry in root.iter(f'{NS_ATOM}entry'):
            if len(items) >= limit:
                break
            title_el = entry.find(f'{NS_ATOM}title')
            link_el = entry.find(f'{NS_ATOM}link')
            content_el = entry.find(f'{NS_ATOM}content')
            pub_el = entry.find(f'{NS_ATOM}published')
            if title_el is None or link_el is None:
                continue
            title = (title_el.text or '').strip()
            # Atom link: <link rel="alternate" href="...">
            href = link_el.get('href', '')
            if not href:
                continue
            # content/description
            desc_raw = (content_el.text or '') if content_el is not None else ''
            desc = re.sub(r'<[^>]+>', ' ', desc_raw)
            desc = re.sub(r'\s+', ' ', desc).strip()
            # Product Hunt boilerplate 제거
            desc = re.sub(r'\s*Discussion\s*\|\s*Link\s*', '', desc)
            desc = desc[:500]

            # AI 툴 필터
            if not is_ai_tool(title, desc):
                continue

            # 가격 추출
            price = extract_price(desc)
            if not price:
                price = ''

            items.append({
                'name': title,
                'description': desc,
                'price': price,
                'url': href,
                'source': 'Product Hunt',
                'pub_date': (pub_el.text or '')[:10] if pub_el is not None else '',
            })
        print(f"  Product Hunt: {len(items)}개 수집 (AI 필터 후)")
    except Exception as e:
        print(f"  Product Hunt 수집 실패: {e}")
    return items


# ============================================
# 수집 함수: Hacker News (Show HN)
# ============================================
HN_API_URL = 'https://hn.algolia.com/api/v1/search'

HN_AI_KEYWORDS = [
    'ai', 'llm', 'gpt', 'chatgpt', 'claude', 'gemini', 'llama', 'mistral',
    'machine learning', 'deep learning', 'neural network', 'copilot',
    'openai', 'anthropic', 'generative', 'rag', 'agent',
    'vector database', 'embedding', 'transformer', 'diffusion',
]


def fetch_hacker_news_tools(limit=15) -> list:
    """Hacker News Show HN → AI 툴 목록"""
    items = []
    try:
        # 최근 30일 이내 Show HN + AI tool 검색어
        cutoff = int((datetime.now() - timedelta(days=30)).timestamp())
        params = urllib.parse.urlencode({
            'tags': 'show_hn',
            'query': 'AI tool',
            'hitsPerPage': 50,
            'numericFilters': f'created_at_i>{cutoff}',
        })
        url = f'{HN_API_URL}?{params}'
        req = urllib.request.Request(url, headers={'User-Agent': 'aikorea24-bot/2.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        data = json.loads(raw)
        for hit in data.get('hits', []):
            if len(items) >= limit:
                break
            title = hit.get('title', '').strip()
            # Show HN prefix 제거
            title = re.sub(r'^Show\s+HN:\s*', '', title, flags=re.IGNORECASE)
            # AI 관련 필터
            text_to_check = title.lower()
            if not any(kw in text_to_check for kw in HN_AI_KEYWORDS):
                continue
            # REJECT: AI 툴이 아닌 항목 제외
            combined = text_to_check + ' ' + (hit.get('story_text', '') or '').lower()
            if any(kw.lower() in combined for kw in PH_REJECT_KEYWORDS):
                continue
            # URL
            url = hit.get('url') or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
            # 포인트 (인기도)
            points = hit.get('points', 0)
            # 설명 (HN은 description이 없고 title에 모든 정보)
            desc = hit.get('story_text', '') or ''
            desc = re.sub(r'<[^>]+>', ' ', desc)
            desc = re.sub(r'\s+', ' ', desc).strip()[:300]

            items.append({
                'name': title,
                'description': desc if desc else f"Show HN: {title}",
                'price': '',
                'url': url,
                'source': 'Hacker News',
                'points': points,
                'pub_date': datetime.fromtimestamp(hit.get('created_at_i', 0)).strftime('%Y-%m-%d') if hit.get('created_at_i') else '',
            })
        print(f"  Hacker News: {len(items)}개 수집")
    except Exception as e:
        print(f"  Hacker News 수집 실패: {e}")
    return items


# ============================================
# 통합 수집
# ============================================
def collect_tools(limit_per_source=15) -> list:
    """모든 소스에서 툴 수집 → 중복 제거된 리스트"""
    all_tools = []
    all_tools.extend(fetch_product_hunt(limit=limit_per_source))
    all_tools.extend(fetch_hacker_news_tools(limit=limit_per_source))

    # 중복 제거 (URL 기준)
    seen_urls = set()
    unique_tools = []
    for t in all_tools:
        url = t.get('url', '').strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        unique_tools.append(t)

    print(f"  총 {len(unique_tools)}개 (중복 제거 후)")
    return unique_tools


# ============================================
# im-not-ai 1단계: GPT 프롬프트 금지 패턴 (예방)
# ============================================
# im-not-ai rewriting-playbook.md + ai-tell-taxonomy.md에서 추출
HUMANIZE_RULES = """
[필수 규칙 — AI 번역투·관용구 금지]
당신의 응답에서 아래 표현을 절대 사용하지 마세요:

❌ 금지 표현 (원문 패턴 → 올바른 표현):
• "~에 대해(서)" → "~를" (예: "PDF 변환에 대해" → "PDF 변환을")
• "~를 통해" → "~로", "~해서" (예: "AI를 통해" → "AI로")
• "~에 있어(서)" → "~에서", "~을 볼 때"
• "~에 의해" 피동 → "~가" 능동 (예: "AI에 의해 생성" → "AI가 만든")
• "가지고 있다" → "있다" (예: "강점을 가지고 있다" → "강점이 있다")
• "~할 수 있다" 남발 → 가능성 아니면 단언으로 (예: "제공할 수 있다" → "제공한다")
• "~에 기반하여/바탕으로" → "~로", "~을 보고"
• "~라는 점에서" 한 문서에 3회 이상 금지

❌ 금지 관용구 (전량 삭제):
• "결론적으로", "시사하는 바가 크다", "주목할 만하다"
• "혁신적인", "획기적인", "강력한", "파격적인"
• "본질적으로", "핵심적으로"
• "~의 지평을 열다", "~시대가 도래했다"
• "~라고 할 수 있다" (단언 가능하면 "~이다")

❌ 금지 구조:
• "첫째/둘째/셋째" 기계적 나열 금지 — 산문 흐름으로 녹일 것
• "또한/따라서/그러므로/즉," 문두 접속사 연속 금지 (2회 이상)

❌ 금지 시각 장식:
• 이모지 남용 금지 (제품명·가격표기 외 본문에 ❌)
• 영어 괄호 병기 금지 (첫 등장도 지양)
• "-성/-적/-화" 한자어 명사화 3회 이상 금지

✅ 지향:
• "~ㄴ다/~었다/~는다/~기 마련이다" 등 종결어미 다양화
• "매우/정말/많은" 대신 구체 수치·사례로
• 문장 길이 다양화 (짧은 문장 1~2개 섞기)

❌ 금지 약한 서술 (반드시 제거):
• "~할 수 있다"  → "~한다", "~입니다" (가능성이 아닌 서술은 단언)
• "~수 있다" (받침 없는 동사) → "~ㄴ다" ("제공할 수 있다" ❌ → "제공한다" ✅)
• "~도와준다" → "~에 도움이 된다" 또는 생략
• "~돕는다" → 구체적 효능으로 ("업무 효율을 높인다")
• "사용자가 ~할 수 있도록 돕는다" → "~할 수 있다" 자체가 불필요

✅ FAQ 작성 기준 (반드시 준수):
• 질문 3개 이상, 각 질문은 실제 사용자가 검색할 법한 구체적인 질문
• 각 답변은 2~3문장, 최소 50자 이상
• 단답형("네/아니요") 금지 — 이유와 예외를 함께 설명
• 단차 비교("A가 낫다")보다 사용자 상황별 조언("예산/목적에 따라 다릅니다")
• 좋은 FAQ 예: "무료로 쓸 수 있나요?" → 설명 + 무료 범위 + 유료 필요 시점
• 나쁜 FAQ 예: "이 도구가 좋은가요?" → 너무 추상적
"""

# ============================================
# im-not-ai 2단계: regex 후처리 (교정)
# ============================================
# im-not-ai rewriting-playbook.md §1 + quick-rules.md 기반
def humanize_md(text: str) -> str:
    """im-not-ai rewriting playbook 기반 경량 한국어 humanize (추가 비용 0)"""
    if not text:
        return text

    replacements = [
        # A-1: ~에 대해(서) → ~를
        (r'(?<=[가-힣])(\s*)에 대해(서)?(?=\s|[.。]|$)', r'\1를'),
        # A-2: ~를 통해 → ~로
        (r'(?<=[가-힣])(을|를) 통해', r'로'),
        # A-3: ~에 있어(서) → ~에서
        (r'(?<=[가-힣])(\s*)에 있어(서)?(?=\s|[.。]|$)', r'\1에서'),
        # A-5: ~와 관련하여 → ~에
        (r'(?<=[가-힣])(과|와) 관련하여', r''),
        # A-6: ~에 기반하여/바탕으로 → ~로
        (r'(?<=[가-힣])(\s*)에 기반하여', r'\1로'),
        (r'(?<=[가-힣])(\s*)을 바탕으로', r'\1을 보고'),
        # A-7: ~을/를 가지고 있다 → 있다
        (r'([가-힣]+)을/를 가지고 있다', r'\1이 있다'),
        (r'([가-힣]+)을/를 갖추고 있다', r'\1을 갖췄다'),
        # A-9: ~에 의해 → ~가
        (r'(?<=[가-힣])(\s*)에 의해 생성', r'\1가 만든'),
        (r'(?<=[가-힣])(\s*)에 의해 제공', r'\1가 제공'),
        # A-10: ~할 수 있다 남발 (가능성이 명확한 경우 단언)
        (r'을 제공할 수 있습니다', r'을 제공합니다'),
        (r'을 지원할 수 있습니다', r'을 지원합니다'),
        (r'을 사용할 수 있습니다', r'을 사용합니다'),
        (r'을 활용할 수 있습니다', r'을 활용합니다'),
        (r'을 찾아볼 수 있다', r'을 찾을 수 있다'),
        (r'를 찾아볼 수 있다', r'를 찾을 수 있다'),
        (r'할 수 있도록 돕', r'하는 데 도움이 되'),
        (r'도와준다', r'도움이 된다'),
        (r'돕는다', r'도움이 된다'),
        (r'수행할 수 있다', r'수행한다'),
        (r'처리할 수 있다', r'처리한다'),
        (r'제공할 수 있는', r'제공하는'),
        (r'지원할 수 있는', r'지원하는'),
        (r'활용할 수 있는', r'활용하는'),
        (r'사용할 수 있는', r'사용하는'),
        # A-11: ~을 위해 → ~려고
        (r'([가-힣]+)을 위해 ', r'\1하려고 '),
        (r'([가-힣]+)를 위해 ', r'\1하려고 '),

        # D-1: 결론적/시사/주목 삭제
        (r'결론적으로,?\s*', ''),
        (r'시사하는 바가 크(다|습니다)', '의미가 큽니다'),
        (r'주목할 만한 (점은|것은)\s*', ''),
        # D-4: hype 어휘
        (r'혁신적인', '새로운'),
        (r'획기적인', ''),
        (r'강력한 ', ''),
        (r'파격적인', ''),

        # C-11: 연결어미 뒤 쉼표 제거
        (r'(하고|하며|지만|면서|면서도|아서|어서),', lambda m: m.group(1) + ''),
        # C-5: 본문 이모지 제거 (💡⚠️📌✅❌ 등은 제품정보에만 허용)
        (r'(?<![💰🇰🇷📊🔗⭐📂])[💡⚠️📌✅❌🔍📱💻🎯🚀🔥💪🧠⚡🔧📈💬🎨📝✨],?', ''),

        # E-2: ~고 있다 단순 시제 환원
        (r'([가-힣]+)고 있다\b', lambda m: m.group(1) + '는다' if len(m.group(1)) <= 2 else m.group(1) + '니다'),
    ]

    for pattern, replacement in replacements:
        try:
            text = re.sub(pattern, replacement, text)
        except Exception:
            pass
    return text


# ============================================
# im-not-ai 3단계: AI tell 점수 검증 게이트
# ============================================
def ai_tell_score(text: str) -> float:
    """im-not-ai 10대 카테고리 기반 AI 티 점수 (높을수록 AI스러움, 임계: 15)"""
    score = 0
    patterns = {
        '번역투': 2.0,
        'AI관용구': 3.0,
        '접속사': 1.5,
        '형식명사': 1.0,
        'hedging': 2.5,
    }
    counters = {
        '번역투': [r'에 대해', r'를 통해', r'에 있어', r'가지고 있다', r'에 의해', r'기반하여', r'바탕으로'],
        'AI관용구': [r'결론적으로', r'시사하는 바', r'주목할 만', r'혁신적인', r'획기적인'],
        '접속사': [r'또한,?\s', r'따라서,?\s', r'그러므로,?\s', r'즉,?\s'],
        '형식명사': [r'것입니다', r'수 있습니다', r'필요가 있습니다'],
        'hedging': [r'~할 수 있을 것으로 보', r'~라고 할 수 있', r'~적인 측면'],
    }
    for category, patterns_list in counters.items():
        weight = patterns[category]
        for p in patterns_list:
            matches = re.findall(p, text)
            score += len(matches) * weight
    return score


# ============================================
# 중복 체크
# ============================================
def get_existing_tool_names():
    """기존 tools MD에서 name 목록 읽기 (slug + name 이중 체크)"""
    tools_dir = os.path.join(PROJECT_DIR, 'src/content/tools')
    if not os.path.isdir(tools_dir):
        return set(), set()
    slugs = set()
    names = set()
    for f in os.listdir(tools_dir):
        if not f.endswith('.md'):
            continue
        slug = f.replace('.md', '')
        slugs.add(slug)
        # frontmatter에서 name 읽기
        fpath = os.path.join(tools_dir, f)
        try:
            with open(fpath, 'r', encoding='utf-8') as fh:
                content = fh.read()
            m = re.search(r'^name:\s*"([^"]+)"', content, re.MULTILINE)
            if m:
                names.add(m.group(1).strip().lower())
        except Exception:
            pass
    return slugs, names


def title_to_slug(name: str) -> str:
    """툴명 → 파일명 slug"""
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9가-힣]', '-', s)
    s = re.sub(r'-+', '-', s)
    s = s.strip('-')
    return s


# ============================================
# GPT 한국어 메타데이터 생성 (with im-not-ai 1단계)
# ============================================
SYSTEM_PROMPT = f"""당신은 한국어 AI 툴 큐레이터입니다.
한국 일반 사용자(직장인·학생·소상공인) 관점에서 실용적으로 설명합니다.
전문용어 대신 쉬운 표현, 한국 실생활 예시를 반드시 포함합니다.
예시: "영어 이메일 작성", "유튜브 썸네일 제작", "사업계획서 초안 작성"
JSON 외 다른 텍스트는 절대 출력하지 마세요.
{HUMANIZE_RULES}"""

USER_PROMPT_TEMPLATE = """다음 AI 툴 정보를 분석해 JSON으로 응답하세요.

툴명: {name}
영문설명: {description}
가격: {price}
URL: {url}

반환 형식 (이 JSON 구조만 출력):
{{
  "description_kr": "한줄 설명 (80자 이내, 핵심 기능 + 한국 사용자 관점)",
  "category": "글쓰기·챗봇 또는 이미지 생성 또는 영상·음성 또는 업무·생산성 또는 코딩·개발 또는 디자인 또는 번역·학습",
  "koreanSupport": true 또는 false,
  "difficulty": "초보자 OK 또는 중급 또는 고급",
  "price_kr": "무료 또는 무료/월 N만원 또는 월 N만원~",
  "useCases": ["한국 직장인 맥락 활용사례", "학생 활용사례", "소상공인 활용사례"],
  "tags": ["태그1", "태그2", "태그3"],
  "tasks": ["pdf-요약", "글쓰기", "이미지-생성", "번역" 등 위 정의 태스크 슬러그 중 1~3개],
  "tool_detail": {{
    "summary": "2~3문장. 이 툴이 무엇인지, 어떤 문제를 해결하는지 한국 사용자 관점으로.",
    "features": ["핵심 기능1 (50자)", "핵심 기능2 (50자)", "핵심 기능3 (50자)"],
    "price_detail": "무료 플랜과 유료 플랜 차이점 2~3문장.",
    "korean_detail": "한국어 지원 수준 상세 설명 1~2문장.",
    "recommend_for": "이런 분에게 추천합니다. 구체적인 페르소나 2~3개, 각 1문장.",
    "real_examples": ["한국 맥락 실제 활용 예시1 (1문장)", "예시2", "예시3"],
    "vs_similar": "유사 툴 대비 이 툴의 장점·단점 2~3문장.",
    "faq": [
      {{"q": "자주 묻는 질문1", "a": "답변 (2~3문장)"}},
      {{"q": "자주 묻는 질문2", "a": "답변 (2~3문장)"}},
      {{"q": "자주 묻는 질문3", "a": "답변 (2~3문장)"}}
    ]
  }}
}}"""


def generate_metadata(tool_info: dict) -> dict:
    """GPT-4o-mini 호출 → 한국어 메타데이터 (im-not-ai 규칙 적용)"""
    if not OPENAI_KEY:
        print("  OPENAI_API_KEY 없음")
        return None
    import openai
    client = openai.OpenAI(api_key=OPENAI_KEY)
    prompt = USER_PROMPT_TEMPLATE.format(
        name=tool_info.get('name', ''),
        description=tool_info.get('description', '')[:500],
        price=tool_info.get('price', ''),
        url=tool_info.get('url', ''),
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=2000,
            temperature=0.5,
        )
        raw = resp.choices[0].message.content.strip()
        # JSON 파싱 (```json ... ``` 처리)
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
        if json_match:
            raw = json_match.group(1).strip()
        data = json.loads(raw)
        return data
    except json.JSONDecodeError as e:
        print(f"    JSON 파싱 실패: {e}")
        print(f"    원문: {raw[:300]}")
        return None
    except Exception as e:
        print(f"    GPT 호출 실패: {e}")
        return None


# ============================================
# MD 파일 생성
# ============================================
def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9가-힣]', '-', s)
    s = re.sub(r'-+', '-', s)
    s = s.strip('-')
    # 50자 제한 + trailing - 제거
    if len(s) > 50:
        s = s[:50].rstrip('-')
    return s


def build_frontmatter(name: str, meta: dict, order: int, tool_url: str = '') -> str:
    """MD frontmatter 생성"""
    tasks_str = json.dumps(meta.get('tasks', []), ensure_ascii=False)
    tags_str = json.dumps(meta.get('tags', []), ensure_ascii=False)
    use_cases_str = json.dumps(meta.get('useCases', []), ensure_ascii=False)
    today = datetime.now().strftime('%Y-%m-%d')
    # url: tool_info에서 전달받은 원본 URL 우선, 없으면 meta에서
    url = tool_url or meta.get('url', '')

    return f"""---
name: "{name}"
description: "{meta.get('description_kr', '')}"
category: "{meta.get('category', '')}"
price: "{meta.get('price_kr', '')}"
koreanSupport: {str(meta.get('koreanSupport', False)).lower()}
difficulty: "{meta.get('difficulty', '')}"
url: "{url}"
useCases: {use_cases_str}
tags: {tags_str}
featured: false
order: {order}
tasks: {tasks_str}
updated: "{today}"
---
"""


def build_body(meta: dict) -> str:
    """MD 본문 생성 (tool_detail 구조)"""
    td = meta.get('tool_detail', {})
    lines = []

    # 한줄 요약
    lines.append('## 한줄 요약')
    lines.append('')
    lines.append(td.get('summary', ''))
    lines.append('')

    # 핵심 기능
    lines.append('## 핵심 기능')
    lines.append('')
    for feat in td.get('features', []):
        lines.append(f'- {feat}')
    lines.append('')

    # 가격 정책
    lines.append('## 가격 정책')
    lines.append('')
    lines.append(td.get('price_detail', ''))
    lines.append('')

    # 한국어 지원
    lines.append('## 한국어 지원')
    lines.append('')
    lines.append(td.get('korean_detail', ''))
    lines.append('')

    # 이런 분에게 추천
    lines.append('## 이런 분에게 추천합니다')
    lines.append('')
    lines.append(td.get('recommend_for', ''))
    lines.append('')

    # 실제 활용 예시
    lines.append('## 실제 활용 예시')
    lines.append('')
    for ex in td.get('real_examples', []):
        lines.append(f'- {ex}')
    lines.append('')

    # 유사 툴과 비교
    lines.append('## 유사 툴과 비교')
    lines.append('')
    lines.append(td.get('vs_similar', ''))
    lines.append('')

    # 자주 묻는 질문
    lines.append('## 자주 묻는 질문')
    lines.append('')
    for faq in td.get('faq', []):
        lines.append(f'**{faq.get("q", "")}**')
        lines.append('')
        lines.append(f'{faq.get("a", "")}')
        lines.append('')

    return '\n'.join(lines)


def save_tool_md(name: str, meta: dict, order: int, tool_url: str = '') -> str:
    """MD 파일 저장 → 파일명 반환"""
    slug = slugify(name)
    tools_dir = os.path.join(PROJECT_DIR, 'src/content/tools')
    os.makedirs(tools_dir, exist_ok=True)
    filepath = os.path.join(tools_dir, f'{slug}.md')

    frontmatter = build_frontmatter(name, meta, order, tool_url=tool_url)

    # --- im-not-ai 2단계: 본문 humanize ---
    body_raw = build_body(meta)
    body = humanize_md(body_raw)

    content = frontmatter + '\n' + body + '\n'

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  저장: {filepath}")
    return slug


# ============================================
# 텔레그램 알림 (news_collector 패턴 재사용)
# ============================================
def send_telegram(message: str) -> None:
    import requests
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("  텔레그램 토큰/챗ID 없음, 알림 스킵")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
        print("  텔레그램 알림 전송 완료")
    except Exception as e:
        print(f"  텔레그램 전송 실패: {e}")


# ============================================
# Git 자동 커밋
# ============================================
def git_commit(message: str) -> bool:
    try:
        r = subprocess.run(['git', '-C', PROJECT_DIR, 'add', '-A'],
                         capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            print(f"  git add 실패: {r.stderr[:200]}")
            return False
        r = subprocess.run(['git', '-C', PROJECT_DIR, 'commit', '-m', message],
                         capture_output=True, text=True, timeout=30)
        if 'nothing to commit' in r.stdout:
            print("  커밋할 변경사항 없음")
            return False
        print(f"  git commit: {r.stdout[:200]}")
        r = subprocess.run(['git', '-C', PROJECT_DIR, 'push'],
                         capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            print("  git push 완료")
        else:
            print(f"  git push: {r.stderr[:200]}")
        return True
    except Exception as e:
        print(f"  git 오류: {e}")
        return False


# ============================================
# 배치 처리
# ============================================
def translate_tools(tools: list) -> list:
    """batch_translate()를 재사용해 툴명/설명 한국어 번역"""
    if batch_translate is None:
        print("  batch_translate import 실패, 번역 스킵")
        return tools
    if not OPENAI_KEY:
        print("  OPENAI_API_KEY 없음, 번역 스킵")
        return tools
    # tools → articles 포맷 변환
    articles = []
    for t in tools:
        articles.append({
            'title': t.get('name', ''),
            'description': t.get('description', ''),
            'country': 'us',  # 번역 대상으로 표시
            'link': t.get('url', ''),
            'source': t.get('source', ''),
            'category': 'global',
            'pub_date': t.get('pub_date', ''),
            'source_url': '',
            'original_title': t.get('name', ''),
        })
    print(f"  번역 시작: {len(articles)}건 (batch_translate 재사용)...")
    translated = batch_translate(articles)
    # articles → tools 포맷 복원
    for i, a in enumerate(translated):
        if i < len(tools):
            tools[i]['name'] = a.get('title', tools[i]['name'])
            tools[i]['description'] = a.get('description', tools[i]['description'])
            tools[i]['original_name'] = a.get('original_title', tools[i].get('original_name', ''))
    print(f"  번역 완료")
    return tools


def process_batch(tools: list, batch_size=5, max_workers=3, translate=False) -> list:
    """툴 목록을 배치로 처리 → 생성된 slug 목록 반환"""
    existing_slugs, existing_names = get_existing_tool_names()
    print(f"기존 툴: {len(existing_slugs)}개 (슬러그), {len(existing_names)}개 (이름)")
    
    # 중복 제거 (slug + name 이중 체크)
    new_tools = []
    for t in tools:
        name = t.get('name', '').strip()
        slug = title_to_slug(name)
        name_lower = name.lower()
        if slug in existing_slugs or name_lower in existing_names:
            print(f"  중복 스킵: {name}")
            continue
        new_tools.append(t)
    
    if not new_tools:
        print("새로운 툴 없음")
        return []
    
    # 번역 (옵션)
    if translate:
        print("\n[번역] batch_translate()로 한국어 번역...")
        new_tools = translate_tools(new_tools)
    
    if not new_tools:
        print("새로운 툴 없음")
        return []
    
    print(f"신규 툴: {len(new_tools)}개 (배치={batch_size}, 스레드={max_workers})")
    
    created = []
    # 배치로 나누기
    batches = [new_tools[i:i+batch_size] for i in range(0, len(new_tools), batch_size)]
    
    for batch_num, batch in enumerate(batches, 1):
        print(f"\n--- 배치 {batch_num}/{len(batches)} ({len(batch)}건) ---")
        
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {}
            for idx, tool in enumerate(batch):
                future = pool.submit(generate_metadata, tool)
                futures[future] = (idx, tool)
            
            for future in as_completed(futures):
                idx, tool = futures[future]
                meta = future.result()
                if meta is None:
                    print(f"  ❌ {tool.get('name', '')} — GPT 생성 실패")
                    continue
                
                # im-not-ai 3단계: AI tell 점수 검증
                body_raw = build_body(meta)
                score = ai_tell_score(body_raw)
                if score > 15:
                    print(f"  ⚠️ {tool.get('name', '')} — AI tell 점수 {score:.0f} (임계 15 초과), 후처리 강화")
                    body_raw = humanize_md(body_raw)
                    score2 = ai_tell_score(body_raw)
                    print(f"     후처리 후: {score2:.0f}")
                
                # MD 저장
                order_base = 100 + idx
                slug = save_tool_md(tool.get('name', ''), meta, order_base, tool_url=tool.get('url', ''))
                created.append(slug)
                print(f"  ✅ {tool.get('name', '')} → {slug}.md")
        
        # 배치 간 텀 (rate limit 방지)
        if batch_num < len(batches):
            import time
            time.sleep(2)
    
    return created


# ============================================
# 샘플 툴 데이터 (테스트용)
# ============================================
SAMPLE_TOOLS = [
    {
        "name": "Hailuo AI",
        "description": "AI video generation platform that creates high-quality videos from text prompts and images",
        "price": "Free / $15 per month",
        "url": "https://hailuoai.video",
    },
    {
        "name": "Napkin AI",
        "description": "Turn text into visual diagrams and infographics instantly",
        "price": "Free / $10 per month",
        "url": "https://napkin.ai",
    },
    {
        "name": "Trellis",
        "description": "AI-powered 3D model generation from images and text descriptions",
        "price": "Free / $20 per month",
        "url": "https://trellis3d.com",
    },
]


# ============================================
# 메인
# ============================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description='AI 툴 대량 확충기')
    parser.add_argument('--batch', type=int, default=5,
                       help='배치 크기 (초기: 50, 유지: 10)')
    parser.add_argument('--workers', type=int, default=3,
                       help='동시 스레드 수')
    parser.add_argument('--sample', action='store_true',
                       help='샘플 데이터로 테스트 실행')
    parser.add_argument('--json', type=str,
                       help='JSON 파일 경로 (툴 목록)')
    parser.add_argument('--collect', action='store_true',
                       help='Product Hunt + HN 실시간 수집 후 처리')
    parser.add_argument('--dry-run', action='store_true',
                       help='실제 저장 없이 수집 결과만 출력')
    parser.add_argument('--translate', action='store_true',
                       help='batch_translate()로 영문→한국어 번역')
    parser.add_argument('--limit', type=int, default=10,
                       help='소스당 수집 제한 개수')
    args = parser.parse_args()

    # 툴 목록 로드
    tools = []
    if args.collect:
        print(f"[수집 모드] Product Hunt + Hacker News (소스당 {args.limit}개)")
        tools = collect_tools(limit_per_source=args.limit)
        if not tools:
            print("수집된 툴 없음")
            sys.exit(0)
        print(f"수집 완료: {len(tools)}개")
    elif args.sample:
        tools = SAMPLE_TOOLS
        print(f"[샘플 모드] {len(tools)}개 툴 처리")
    elif args.json:
        with open(args.json, 'r', encoding='utf-8') as f:
            tools = json.load(f)
        print(f"[JSON 모드] {len(tools)}개 툴 로드")
    else:
        print("사용법:")
        print("  python3 tools_collector.py --collect --batch 5        # 실시간 수집 + 처리")
        print("  python3 tools_collector.py --collect --dry-run       # 수집만, 저장 안 함")
        print("  python3 tools_collector.py --collect --translate     # 수집 + 번역 + 처리")
        print("  python3 tools_collector.py --sample                  # 샘플 테스트")
        print("  python3 tools_collector.py --json tools.json --batch 50  # JSON 배치")
        sys.exit(0)

    # DRY RUN: 수집 결과만 출력
    if args.dry_run:
        print(f"\n{'='*55}")
        print(f"[DRY RUN] 수집된 툴 목록 ({len(tools)}개)")
        print(f"{'='*55}")
        for i, t in enumerate(tools, 1):
            name = t.get('name', '')
            desc = t.get('description', '')[:80]
            url = t.get('url', '')
            price = t.get('price', '')
            source = t.get('source', '')
            print(f"\n  {i:2d}. {name}")
            print(f"      설명: {desc}{'…' if len(t.get('description',''))>80 else ''}")
            print(f"      URL:   {url}")
            print(f"      가격:  {price or '없음'}")
            print(f"      출처:  {source}")
        existing_slugs, existing_names = get_existing_tool_names()
        dup_count = sum(1 for t in tools if title_to_slug(t.get('name','')) in existing_slugs or t.get('name','').lower() in existing_names)
        print(f"\n  → 총 {len(tools)}개 중 중복 예상: {dup_count}개")
        print(f"  → 신규 예상: {len(tools) - dup_count}개")
        sys.exit(0)

    start = datetime.now()
    created = process_batch(tools, batch_size=args.batch, max_workers=args.workers, translate=args.translate)
    elapsed = (datetime.now() - start).total_seconds()

    # 요약
    print(f"\n{'='*50}")
    print(f"처리 완료: {len(created)}/{len(tools)}개 생성 ({elapsed:.1f}초)")
    
    if created:
        # Git commit
        msg = f"feat: AI 툴 {len(created)}개 추가 ({datetime.now().strftime('%Y-%m-%d')})"
        git_commit(msg)
        
        # Telegram
        existing_slugs, _ = get_existing_tool_names()
        send_telegram(
            f"🤖 <b>AI 툴 수집 완료</b>\n"
            f"신규: {len(created)}개\n"
            f"총: {len(existing_slugs)}개\n"
            f"소요: {elapsed:.0f}초"
        )

        # 배포 (launchd 자동 실행 시)
        print("\n[배포] Cloudflare Pages 배포 중...")
        deploy_script = os.path.join(PROJECT_DIR, 'scripts/deploy.sh')
        try:
            r = subprocess.run(['bash', deploy_script],
                             capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                print("  배포 완료 ✅")
            else:
                print(f"  배포 실패: {r.stderr[:300]}")
        except Exception as e:
            print(f"  배포 오류: {e}")


if __name__ == '__main__':
    main()
