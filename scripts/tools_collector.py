#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 AI 툴 대량 확충기 v2.1
- Product Hunt RSS / GitHub awesome-ai-tools → 실시간 수집
- GPT-4o-mini 한국어 메타데이터 생성
- im-not-ai 3단계 한국어 품질 보강
- MD 파일 생성 → git commit → 텔레그램 알림 → Cloudflare 배포

재사용: news_collector.py의 fetch_rss_global 패턴, batch_translate, load_env, send_telegram
"""
import os, sys, json, re, hashlib, subprocess, urllib.request, urllib.parse, random, time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET
from html import unescape
from concurrent.futures import ThreadPoolExecutor, as_completed

# 프로젝트 루트 먼저 path에 추가 (pipeline import 전에 필요)
_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'scripts'))
sys.path.insert(0, os.path.join(_PROJECT_DIR, 'api_test'))

from pipeline.infra.logger import get_scrubbed_logger
from pipeline.infra.utils import slugify
logger = get_scrubbed_logger(__name__)

from pipeline.infra.env_loader import EnvConfig
_config = EnvConfig()
_config.load_to_environ()
from pipeline.infra import project_root; PROJECT_DIR = project_root()

# model_router (무료 LLM 폴백 체인) 경로 추가
sys.path.insert(0, os.path.join(PROJECT_DIR, 'scripts', 'threads', 'v3'))
from model_router import chat_completion

# 신규 도구 후처리(URL 승격·심화 v2·썸네일) 시간 예산 — 초과 시 남은 항목은 다음 실행이 처리
POSTPROCESS_BUDGET = 1200

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

# ~/.env.common fallback (프로젝트 .env에 없는 값만 채움)
import sys
sys.path.insert(0, '/Users/twinssn/Projects')
from common_env_loader import load_env_with_fallback
load_env_with_fallback(os.path.join(PROJECT_DIR, '.env'))

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

# === 신규 소스 URL ===
FUTUREPEDIA_SITEMAP = "https://www.futurepedia.io/sitemap.xml"
HUGGINGFACE_PAPERS_RSS = "https://huggingface.co/papers"
TOOLPILOT_API = "https://www.toolpilot.ai/api/tools"
AIXPLORIA_SITEMAP = "https://aixploria.com/sitemap.xml"
TOPAI_TOOLS_URL = "https://topai.tools"

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
    # 플랫폼/서비스가 아닌 항목
    'marketplace', 'community', 'forum', 'blog', 'newsletter',
    'podcast', 'youtube channel', 'discord server',
    # 너무 단순하거나 불완전한 프로젝트
    'work in progress', 'coming soon', 'beta', 'prototype',
    'demo', 'proof of concept', 'poc',
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
    """Product Hunt/HN 아이템이 AI 툴인지 판별 (제목 + 설명 기준)"""
    title_lower = title.lower()
    desc_lower = description.lower()
    combined = title_lower + ' ' + desc_lower

    # === 최소 설명 길이 체크 (너무 짧으면 스킵) ===
    if len(description.strip()) < 20:
        return False

    # === REJECT: AI 툴이 아닌 항목 먼저 차단 ===
    for kw in PH_REJECT_KEYWORDS:
        if kw.lower() in combined:
            return False

    # === AI 키워드 매칭 (제목에 있으면 바로 통과) ===
    for kw in PH_AI_KEYWORDS:
        if kw.lower() in title_lower:
            return True

    # === 제목에 'tool'/'app' + 설명에 AI 키워드 ===
    if 'tool' in title_lower or 'app' in title_lower:
        for kw in ['ai', 'intelligence', 'neural', 'deep learning', 'machine learning']:
            if kw in desc_lower:
                return True

    # === 설명에 AI 키워드 2개 이상 포함 시 통과 ===
    ai_desc_keywords = ['ai', 'artificial intelligence', 'machine learning', 'deep learning',
                        'neural network', 'language model', 'llm', 'gpt', 'generative']
    desc_ai_count = sum(1 for kw in ai_desc_keywords if kw in desc_lower)
    if desc_ai_count >= 2:
        return True

    return False


NS_ATOM = '{http://www.w3.org/2005/Atom}'

def resolve_product_hunt_url(ph_url: str) -> str:
    """Product Hunt 리다이렉트 URL → 실제 툴 URL 해석"""
    try:
        req = urllib.request.Request(
            ph_url,
            headers={'User-Agent': 'aikorea24-bot/2.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.url
    except Exception:
        return ph_url


def extract_real_url_from_content(content: str) -> str:
    """Product Hunt 콘텐츠에서 실제 툴 URL 추출"""
    # <a href="...">Link</a> 패턴에서 리다이렉트 URL 추출
    link_match = re.search(r'href="(https://www\.producthunt\.com/r/p/\d+\?app_id=\d+)"', content)
    if link_match:
        return link_match.group(1)
    return ''


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

            # 실제 툴 URL 추출 (리다이렉트 따라가기)
            redirect_url = extract_real_url_from_content(desc_raw)
            if redirect_url:
                real_url = resolve_product_hunt_url(redirect_url)
            else:
                real_url = href

            items.append({
                'name': title,
                'description': desc,
                'price': price,
                'url': real_url,
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
# ============================================
# 수집 함수: GitHub awesome-ai-tools
# ============================================
GITHUB_AWESOME_URL = 'https://raw.githubusercontent.com/mahseema/awesome-ai-tools/main/README.md'

# 수집할 섹션만 명시적 지정 (allow-list)
# README 구조: ## 상위섹션 → ### 하위섹션
ALLOW_SECTIONS = [
    'writing assistants',
    'productivity',
    'meeting assistants',
    'customer support',
    'generative ai images', 'image', 'graphic design',
    'generative ai video', 'video',
    'generative ai audio', 'audio', 'voice cloning', 'music generation',
    'ai tools for marketing', 'marketing',
    'phone call', 'phone calls',
    'editor\'s choice',
    'other ai tools', 'other',
]

# 이미 우리 디렉토리에 있거나 툴이 아닌 URL 패턴
GITHUB_REJECT_URLS = [
    'github.com/', 'github.com/mahseema', 'altern.ai', 'theresanai.com',
    # 어필리에이트/트래킹 URL 패턴
    '://try.', '://get.', 'affiliate.', 'ref=', 'utm_',
]

# 이미 있는 툴명 (대소문자 무시) — README엔 있지만 우리 기준에 안 맞는 항목
GITHUB_REJECT_NAMES = [
    'openai api', 'gopher', 'opt', 'bloom', 'llama', 'vicuna',
    'stable beluga', 'chatgpt', 'gemini', 'perplexity ai', 'phind',
    'notion ai', 'otter.ai', 'elicit', 'notebooklm',
    'claude 3', 'bard',
]


def fetch_github_awesome(limit=50) -> list:
    """GitHub awesome-ai-tools README.md → AI 툴 목록"""
    items = []
    try:
        req = urllib.request.Request(
            GITHUB_AWESOME_URL,
            headers={'User-Agent': 'aikorea24-bot/2.0'}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode('utf-8')

        lines = raw.split('\n')
        current_section = ''

        for line in lines:
            # 섹션 감지 (## 제목)
            section_match = re.match(r'^##+\s+(.+)', line)
            if section_match:
                current_section = section_match.group(1).lower().strip()

            # 섹션이 설정되기 전(## 상단)은 Editor's Choice로 간주
            if not current_section:
                continue

            # Markdown 링크 패턴: [텍스트](URL) - 설명
            # 앞에 - 또는 * 가 있을 수 있음
            link_match = re.match(r'\s*[-*]\s*\[([^\]]+)\]\(([^)]+)\)\s*(?:[-–—]\s*(.*))?', line)
            if not link_match:
                # 들여쓰기 없는 형태도 체크
                link_match = re.match(r'\s*\[([^\]]+)\]\(([^)]+)\)\s*(?:[-–—]\s*(.*))?', line)

            if not link_match:
                continue

            name = link_match.group(1).strip()
            url = link_match.group(2).strip()
            desc = (link_match.group(3) or '').strip()

            # 섹션 allow-list 필터 (수집할 섹션만 통과)
            if not any(allowed in current_section for allowed in ALLOW_SECTIONS):
                continue

            # 이름 필터
            name_lower = name.lower()
            if any(reject in name_lower for reject in GITHUB_REJECT_NAMES):
                continue

            # URL 필터 (reviews, affiliate 링크 제외)
            if '*reviews*' in desc.lower() or '[reviews]' in desc.lower():
                continue
            if any(reject in url for reject in GITHUB_REJECT_URLS):
                continue
            if 'affiliate.' in url or 'referral=' in url:
                continue

            # 설명 클리닝
            desc = re.sub(r'\*.*?\*', '', desc)  # *italic* 제거
            desc = re.sub(r'\[.*?\]\(.*?\)', '', desc)  # 인라인 링크 제거
            desc = re.sub(r'\s+', ' ', desc).strip()
            desc = desc[:300]

            # 가격 정보 (README에는 없으므로 빈 값)
            price = ''

            # 너무 짧거나 광고성 항목 제외
            if len(name) < 2:
                continue

            # 이미 수집한 항목과 중복 체크 (목록 내)
            dup = False
            for existing in items:
                if existing['name'].lower() == name_lower:
                    dup = True
                    break
                # 같은 URL
                if existing.get('url', '').rstrip('/') == url.rstrip('/'):
                    dup = True
                    break
            if dup:
                continue

            items.append({
                'name': name,
                'description': desc,
                'price': price,
                'url': url,
                'source': 'GitHub Awesome AI Tools',
            })

            if len(items) >= limit:
                break

        print(f"  GitHub Awesome AI Tools: {len(items)}개 수집")
    except Exception as e:
        print(f"  GitHub Awesome AI Tools 수집 실패: {e}")
    return items


# ============================================
# 수집 함수: Futurepedia
# ============================================
def extract_futurepedia_price(card):
    """Futurepedia 카드에서 가격 정보 추출"""
    text = card.get_text()
    if 'Free' in text or '무료' in text:
        return '무료'
    elif 'Freemium' in text:
        return '무료/유료'
    elif '$' in text:
        import re as re_m
        prices = re_m.findall(r'\$\d+', text)
        return prices[0] + '/월' if prices else '유료'
    return '유료'


def _fetch_html(url, timeout=15):
    """urllib를 사용한 HTML fetch 헬퍼"""
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'aikorea24-bot/2.0 (Tool collector)'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  ⚠️ fetch 실패 ({url[:50]}): {e}")
        return None


def collect_futurepedia(limit=10):
    """Futurepedia sitemap → 카테고리 페이지 → 툴 정보 추출"""
    tools = []

    html = _fetch_html(FUTUREPEDIA_SITEMAP)
    if not html:
        return tools

    try:
        root = ET.fromstring(html.encode())
    except Exception as e:
        print(f"  ⚠️ Futurepedia sitemap 파싱 오류: {e}")
        return tools

    ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    tool_urls = []
    for loc in root.findall('.//ns:loc', ns):
        url = loc.text
        if url and '/ai-tools/' in url and url.count('/') <= 6:
            tool_urls.append(url)

    random.shuffle(tool_urls)
    for cat_url in tool_urls[:limit]:
        try:
            html_page = _fetch_html(cat_url)
            if not html_page:
                continue
            soup = BeautifulSoup(html_page, 'html.parser')
            for card in soup.select('[class*="tool"], [class*="card"], article')[:5]:
                name_el = card.select_one('h2, h3, [class*="title"]')
                desc_el = card.select_one('p, [class*="desc"]')
                link_el = card.select_one('a[href*="/tool/"]')
                if not name_el or not link_el:
                    continue
                href = link_el['href']
                tools.append({
                    'name': name_el.get_text(strip=True),
                    'description': desc_el.get_text(strip=True) if desc_el else '',
                    'url': href if href.startswith('http') else 'https://www.futurepedia.io' + href,
                    'price': extract_futurepedia_price(card),
                    'source': 'futurepedia',
                    'pub_date': datetime.now().strftime('%Y-%m-%d')
                })
        except Exception as e:
            print(f"  ⚠️ Futurepedia 오류: {e}")
            continue

    return tools[:limit]


# ============================================
# 수집 함수: Hugging Face Daily Papers
# ============================================
def collect_huggingface_papers(limit=5):
    """Hugging Face Daily Papers → AI 연구/도구 정보 추출"""
    tools = []

    html = _fetch_html(HUGGINGFACE_PAPERS_RSS)
    if not html:
        return tools

    soup = BeautifulSoup(html, 'html.parser')
    articles = soup.select('article, [class*="paper"], .paper-card')[:limit]

    for article in articles:
        title_el = article.select_one('h2, h3, [class*="title"]')
        link_el = article.select_one('a[href*="arxiv"]') or article.select_one('a[href*="hf.co"]') or article.select_one('a[href*="huggingface"]')
        desc_el = article.select_one('p, [class*="desc"], [class*="abstract"]')

        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        if not any(kw in title.lower() for kw in ['tool', 'agent', 'model', 'framework', 'llm', 'gpt', 'diffusion', 'transformer']):
            continue

        tools.append({
            'name': title[:50],
            'description': desc_el.get_text(strip=True)[:200] if desc_el else title,
            'url': link_el['href'] if link_el else 'https://huggingface.co/papers',
            'price': '무료' if 'open source' in title.lower() else '유료',
            'source': 'huggingface',
            'pub_date': datetime.now().strftime('%Y-%m-%d')
        })

    return tools


# ============================================
# 수집 함수: TopAI.tools
# ============================================
def collect_topai_tools(limit=20) -> list:
    """TopAI.tools에서 AI 도구 목록 수집"""
    tools = []
    html = _fetch_html(TOPAI_TOOLS_URL)
    if not html:
        return tools
    soup = BeautifulSoup(html, 'html.parser')
    # 카드 형태의 도구 목록 파싱
    for card in soup.select('[class*="tool-card"], [class*="tool-item"], article, .card')[:limit]:
        name_el = card.select_one('h2, h3, h4, [class*="title"], [class*="name"]')
        desc_el = card.select_one('p, [class*="desc"], [class*="description"]')
        link_el = card.select_one('a[href]')
        if not name_el or not link_el:
            continue
        name = name_el.get_text(strip=True)
        desc = desc_el.get_text(strip=True)[:300] if desc_el else ''
        url = link_el.get('href', '')
        if url and not url.startswith('http'):
            url = 'https://topai.tools' + url
        # AI 툴 필터
        if not is_ai_tool(name, desc):
            continue
        tools.append({
            'name': name,
            'description': desc,
            'url': url,
            'price': '',
            'source': 'topai.tools',
            'pub_date': datetime.now().strftime('%Y-%m-%d'),
        })
    print(f"  TopAI.tools: {len(tools)}개 수집")
    return tools


def collect_theresanaiforthat(limit=10) -> list:
    """There's An AI For That (TAAFT) 에서 도구 수집 (Playwright)"""
    tools = []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  There's An AI For That: Playwright 미설치 → 스킵")
        return tools

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 800},
            )
            page = context.new_page()
            page.goto('https://theresanaiforthat.com/tools/', timeout=30000)
            time.sleep(5)

            # Scroll to trigger lazy-load
            for _ in range(3):
                page.evaluate('window.scrollBy(0, 1000)')
                time.sleep(1)

            rows = page.evaluate('''() => {
                const results = [];
                const rows = document.querySelectorAll('.tools-table-row');
                for (const row of rows) {
                    const nameLink = row.querySelector('.home-today-name-link') || row.querySelector('.tools-name-main-link');
                    const nameEl = row.querySelector('.home-today-name-text') || row.querySelector('.tools-name-heading-cluster');
                    const taskEl = row.querySelector('.home-today-topic-link');
                    const authorEl = row.querySelector('.home-today-author-name-row');
                    const savesEl = row.querySelector('.home-today-save');
                    const viewsEl = row.querySelector('.home-today-views-value');
                    const descEl = row.querySelector('.tools-name-tagline');

                    const name = nameEl?.innerText?.trim() || '';
                    const url = nameLink?.href || '';
                    const task = taskEl?.innerText?.trim() || '';
                    const author = authorEl?.innerText?.trim() || '';
                    const saves = savesEl?.innerText?.trim() || viewsEl?.innerText?.trim() || '0';
                    const desc = descEl?.innerText?.trim() || '';

                    if (name && url && url.includes('/ai/')) {
                        results.push({ name, url, description: desc, task, author, saves });
                    }
                }
                return results;
            }''')

            browser.close()

            seen = set()
            for tool in rows:
                if len(tools) >= limit:
                    break
                url = tool['url'].strip()
                if url in seen:
                    continue
                seen.add(url)
                tools.append({
                    'name': tool['name'],
                    'description': tool['description'][:300],
                    'url': url,
                    'price': '',
                    'source': 'theresanaiforthat',
                    'pub_date': datetime.now().strftime('%Y-%m-%d'),
                })
    except Exception as e:
        print(f"  There's An AI For That: 수집 실패 ({e})")

    print(f"  There's An AI For That: {len(tools)}개 수집")
    return tools


# ============================================
# D1 가드 — 3구간 폴백 + 상태 파일 + 알림 (AIK24-PIPE-09 B-1/B-7)
#
# 2026-10-21 실측: 같은 날 06:00 tools-collector 도 D1 가드로 죽었다
#   scripts/tools_collector_error.log:447
#   cfnew.QuotaExceededError: [D1-GUARD] 일일 읽기 4,113,239/5,000,000 (82.3%) — 작업 중단
# → 하루를 통째로 버렸다. 상태 파일도 알림도 없어 **조용히 죽었다**.
#
# 뉴스 수집기(api_test/news_collector.py)와 **같은 3구간 정책**을 쓴다:
#   < 80%      : 정상 수집 (기존 동작과 완전 동일)
#   80% ~ 95%  : 축소 수집 (핵심 소스만 + 행 상한) + 1회 알림
#   ≥ 95%      : 전면 중단 + 1회 알림 + 원본 예외 재발
# 한도를 못 읽으면 fail-open(수집을 죽이지 않는다).
#
# 상태 파일은 뉴스 수집기와 **다른 파일**을 쓴다:
#   scripts/.collector_state.json        ← 뉴스 수집기 (07:00 파이프라인이 읽는다)
#   scripts/.tools_collector_state.json  ← 이 수집기 (운영자 가시성 전용)
# ============================================

# --- 상수 ---
TOOLS_COLLECTOR_STATE_PATH = os.path.join(PROJECT_DIR, 'scripts', '.tools_collector_state.json')
TOOLS_SOFT_RATIO = 0.80   # 소프트 한계 — 여기부터 축소 수집
TOOLS_HARD_RATIO = 0.95   # 하드 한계 — 여기부터 전면 중단 (cfnew.READONLY_RATIO 와 동일)
REDUCED_ROW_CAP = 8       # 축소 수집 행 상한 (정상 1일 수집량 중앙값 6 · 평균 8.5)
REDUCED_EST_READ_COST = 1_000  # 축소 수집 1회 추정 D1 읽기 비용(행)

# 수집 소스 목록 — 수집 결과 row 의 'source' 필드 값 기준
TOOL_SOURCES = (
    'Product Hunt',
    'GitHub Awesome AI Tools',
    'futurepedia',
    'huggingface',
    'topai.tools',
    'theresanaiforthat',
)

# 축소 수집 핵심 소스 — 2026-10-21 기준 로그 19회 실행 실측에서 골랐다.
#   Product Hunt      : 19/19회 실행 · 2~9건 (매일 실질 기여)      → 유지
#   huggingface       : 19/19회 실행 · 0~5건 (브라우저 불필요)      → 유지
#   GitHub Awesome    : 10건이지만 **주 1회(월) 전용**이라 일일 세트가 아님 → 제외
#   futurepedia       : 19/19회 **0건** (HTML 크롤링 비용 대비 무효) → 제외
#   topai.tools       : 19/19회 **0건**                              → 제외
#   theresanaiforthat : Playwright 브라우저 필요 · 현재 미설치로 17/19회 0건
#                       (가장 느린 소스 — 브라우저 기동 + 스크롤)      → 제외
REDUCED_SOURCES = ('Product Hunt', 'huggingface')

# 상태 파일 status → 알림 표시 라벨
_TOOLS_STATUS_LABEL = {
    'ok': '정상', 'reduced': '축소 수집', 'aborted': '중단', 'error': '오류 종료',
}


def decide_collection_mode(rows_read, limit, soft=TOOLS_SOFT_RATIO, hard=TOOLS_HARD_RATIO,
                           reduced_read_cost=REDUCED_EST_READ_COST, row_cap=REDUCED_ROW_CAP):
    """D1 일일 읽기 사용량 → 수집 모드 결정. 순수 함수(D1·네트워크 무관).

    반환 dict: mode(normal|reduced|abort) · used · limit · pct · headroom · reason
    """
    limit = int(limit or 0)
    used = max(int(rows_read or 0), 0)
    pct = (used / limit) if limit else 1.0
    headroom = max(limit - used, 0)
    base = {'used': used, 'limit': limit, 'pct': pct, 'headroom': headroom,
            'soft': soft, 'hard': hard, 'row_cap': row_cap}
    if limit <= 0:
        # 한도를 못 봤으면 fail-open — 수집을 죽이지 않는다.
        return {**base, 'mode': 'normal', 'reason': 'D1 한도 미확인(fail-open) — 정상 수집'}
    if pct >= hard:
        return {**base, 'mode': 'abort',
                'reason': f'D1 읽기 {used:,}/{limit:,} ({pct:.1%}) — 하드 한계 {hard:.0%} 초과, 수집 중단'}
    if pct < soft:
        return {**base, 'mode': 'normal',
                'reason': f'D1 읽기 {used:,}/{limit:,} ({pct:.1%}) — 정상 수집'}
    # 소프트 이상 하드 미만 → 축소 수집. 단 축소 수집이 하드 한계를 넘기면 중단.
    if used + int(reduced_read_cost or 0) >= hard * limit:
        return {**base, 'mode': 'abort',
                'reason': (f'D1 읽기 {used:,}/{limit:,} ({pct:.1%}) — 축소 수집 비용'
                           f'(≈{int(reduced_read_cost or 0):,}행)까지 쓰면 하드 한계 {hard:.0%} 를 넘는다, 수집 중단')}
    return {**base, 'mode': 'reduced',
            'reason': (f'D1 읽기 {used:,}/{limit:,} ({pct:.1%}) — 소프트 한계 {soft:.0%} 초과, '
                       f'축소 수집(핵심 소스만 · {row_cap}행 상한)')}


def select_reduced_sources(items, core_sources):
    """수집 결과 → 축소 수집 핵심 소스만 남긴 부분집합. 순수 함수.

    items: 수집 row(dict) 목록 · core_sources: 유지할 'source' 필드 값.
    원래 순서를 유지한 부분집합을 돌려준다(전체 목록의 strict subset).
    """
    core = set(core_sources or ())
    return [t for t in (items or []) if t.get('source') in core]


def apply_row_cap(items, cap):
    """행 상한 적용. 순수 함수 — cap 을 넘지 않는 목록을 돌려준다."""
    items = list(items or [])
    cap = int(cap or 0)
    if cap <= 0:
        return []
    return items[:cap]


def _kst_now_iso():
    """현재 KST 시각 ISO8601 문자열 (상태 파일 'at' 필드)."""
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')


def write_tools_collector_state(status, reason, collected=0, path=None, at=None):
    """툴 수집 상태 파일 기록 — 원자적 쓰기(tmp 파일 → os.replace).

    같은 디렉터리에 tmp 를 쓰고 os.replace 로 교체한다(같은 파일시스템 내 rename 은
    원자적). 실패 시 tmp 를 지우고 기존 파일은 그대로 둔다.
    """
    path = path or TOOLS_COLLECTOR_STATE_PATH
    payload = {
        'status': status,
        'reason': str(reason or '')[:300],
        'at': at or _kst_now_iso(),
        'collected': int(collected or 0),
    }
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        # 쓰기 실패 시 tmp 를 지운다 — 대상 파일은 os.replace 전까지 손대지 않았다.
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return payload


def _default_alert_sender(text):
    """기본 알림 채널 — cfnew.muse_send (muse.ai 기본채팅).

    D1 가드 경보(3단계 50/70/90%)와 같은 채널(scripts/cfnew.py 관례)이다.
    muse_send 는 예외를 던지지 않고 bool 을 돌려준다(전달 실패 시 False).
    """
    import cfnew
    return cfnew.muse_send(text)


class ToolsCollectorReporter:
    """툴 수집 상태 기록 + 알림 1회 보장 (AIK24-PIPE-09 B-1).

    · report() 은 첫 호출만 반영 — 가드 중단 뒤 예외 핸들러가 'error' 로 덮어쓰지 않는다.
    · 알림은 런당 최대 1회만 시도한다. 알림 실패는 원본 예외를 절대 가리지 않는다.
    """

    def __init__(self, state_path=None, sender=None, state_writer=None):
        self.state_path = state_path or TOOLS_COLLECTOR_STATE_PATH
        self.sender = sender or _default_alert_sender
        self.state_writer = state_writer or write_tools_collector_state
        self.reported = False
        self.alert_attempts = 0
        self.alert_ok = None
        self.state = None

    def report(self, status, reason, collected=0, alert=True):
        """상태 파일 기록 + (필요 시) 알림 1회. 첫 호출만 반영된다."""
        if self.reported:
            return self.state
        self.reported = True
        try:
            self.state = self.state_writer(status=status, reason=reason,
                                           collected=collected, path=self.state_path)
            print(f"  ℹ 툴 수집 상태 기록: {self.state_path} "
                  f"({status} · {int(collected or 0)}건)", flush=True)
        except Exception as e:
            print(f'  ⚠ 툴 수집 상태 파일 기록 실패(무시): {e}', flush=True)
            self.state = None
        if alert:
            self._alert(status, reason, collected)
        return self.state

    def _alert(self, status, reason, collected):
        if self.alert_attempts >= 1:
            return False
        self.alert_attempts += 1
        label = _TOOLS_STATUS_LABEL.get(status, status)
        text = (f'[AIK24-PIPE-09] aikorea24 툴 수집 {label} — {reason} '
                f'(수집 {int(collected or 0)}건, {_kst_now_iso()})')
        try:
            ok = bool(self.sender(text))
        except Exception as e:
            # 알림 실패가 원본 예외를 가리면 안 된다 — 예외를 삼키고 로그만 남긴다.
            print(f'  ⚠ 툴 수집 알림 전송 실패(무시 — 원본 오류 유지): {e}', flush=True)
            return False
        self.alert_ok = ok
        print(f"  {'✅' if ok else '⚠'} 툴 수집 알림 발송 {'성공' if ok else '실패'}", flush=True)
        return ok


def apply_guard(cfnew, reporter, soft=TOOLS_SOFT_RATIO, hard=TOOLS_HARD_RATIO,
                reduced_read_cost=REDUCED_EST_READ_COST):
    """수집 진입 가드 — 모드를 결정하고, 중단이면 상태 기록·알림 후 예외를 던진다.

    3구간 판정이 필요하므로 cfnew.check_quota 를 raise_on_exceed=False 로 호출해
    사용량을 dict 로 받는다. 중단 시 던지는 예외는 cfnew.QuotaExceededError —
    메시지 형식이 기존과 같아서 tools_collector_error.log 의 오류 줄이 그대로 남는다.
    """
    quota = cfnew.check_quota(threshold=soft, raise_on_exceed=False)
    used = int(quota.get('used') or 0)
    limit = int(quota.get('limit') or 0)
    decision = decide_collection_mode(used, limit, soft=soft, hard=hard,
                                      reduced_read_cost=reduced_read_cost)
    mode = decision['mode']
    if mode == 'abort':
        print(f"[D1-GUARD] {decision['reason']}", flush=True)
        reporter.report('aborted', decision['reason'], collected=0)
        raise cfnew.QuotaExceededError(
            f"[D1-GUARD] 일일 읽기 {used:,}/{limit:,} ({decision['pct']:.1%}) — 작업 중단")
    if mode == 'reduced':
        print(f"[D1-GUARD] {decision['reason']}", flush=True)
    return decision


# ============================================
# 통합 수집
# ============================================
def should_run_github_today():
    """GitHub Awesome AI Tools는 주 1회(월요일)만 실행"""
    return datetime.now().weekday() == 0


def collect_tools(limit_per_source=15, reduced=False) -> list:
    """모든 소스에서 툴 수집 → 중복 제거된 리스트

    AIK24-PIPE-09: reduced=True 면 핵심 소스(REDUCED_SOURCES)만 수집하고
    행 상한(REDUCED_ROW_CAP)을 적용한다. 축소 모드의 실질 이득은 D1 읽기 절감이
    아니라 **하루를 통째로 버리지 않는 연속성**과 쓰기(LLM·후처리·배포) 절감이다.
    """
    all_tools = []
    all_tools.extend(fetch_product_hunt(limit=limit_per_source))

    if reduced:
        print("  GitHub Awesome AI Tools: 축소 수집 — 제외")
    elif should_run_github_today():
        gh_tools = fetch_github_awesome(limit=limit_per_source)
        all_tools.extend(gh_tools)
        print(f"  GitHub Awesome AI Tools: {len(gh_tools)}개 (주간 업데이트)")
    else:
        print(f"  GitHub Awesome AI Tools: 오늘 스킵 (주 1회 실행)")

    if reduced:
        print("  Futurepedia: 축소 수집 — 제외")
    else:
        fp_tools = collect_futurepedia(limit_per_source)
        all_tools.extend(fp_tools)
        print(f"  Futurepedia: {len(fp_tools)}개")

    hf_tools = collect_huggingface_papers(5)
    all_tools.extend(hf_tools)
    print(f"  Hugging Face Papers: {len(hf_tools)}개")

    # 추가 소스
    if reduced:
        print("  TopAI.tools: 축소 수집 — 제외")
    else:
        topai_tools = collect_topai_tools(limit_per_source)
        all_tools.extend(topai_tools)

    if reduced:
        print("  There's An AI For That: 축소 수집 — 제외")
    else:
        taft_tools = collect_theresanaiforthat(limit=min(limit_per_source, 10))
        all_tools.extend(taft_tools)

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

    # 축소 수집 행 상한 — LLM 메타 생성·후처리·배포 비용을 통제한다.
    if reduced:
        before = len(unique_tools)
        unique_tools = apply_row_cap(unique_tools, REDUCED_ROW_CAP)
        print(f"  [축소 수집] 행 상한 적용: {before}건 → {len(unique_tools)}건 "
              f"(상한 {REDUCED_ROW_CAP}건)")

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
• **모든 문장은 "~습니다/~합니다" 체**로 통일 (비즈니스 정중체)
• "입니다/습니다/합니다/있습니다/없습니다" 종결 형태 유지
• "매우/정말/많은" 대신 구체 수치·사례로
• 문장 길이 다양화 (짧은 문장 1~2개 섞기)

❌ 금지 서술체 (반드시 제거):
• "~할 수 있다" → "~할 수 있습니다" (가능성이 아닌 서술은 단언)
• "~수 있다" → "~수 있습니다" ("제공할 수 있다" ❌ → "제공할 수 있습니다" ✅)
• "~ㄴ다/~는다/~었다/~다" → "~니다/~습니다/~했습니다"
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

        # E-2: ~고 있다 → ~합니다
        (r'([가-힣]+)고 있다\b', lambda m: m.group(1) + '니다'),

        # 평서체(~다) → 정중체(~니다) 변환 (문장 끝에서만)
        (r'([가-힣]+)니다\.', lambda m: m.group(0)),  # 이미 정중체면 유지
        (r'([가-힣]+)합니다\.', lambda m: m.group(0)),  # 이미 정중체면 유지
        (r'([가-힣]+)습니다\.', lambda m: m.group(0)),  # 이미 정중체면 유지
        (r'([가-힣]+)이다\.', lambda m: m.group(1) + '입니다.'),
        (r'([가-힣]+)한다\.', lambda m: m.group(1) + '합니다.'),
        (r'툴이다\.', '툴입니다.'),
        (r'도구다\.', '도구입니다.'),
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


from pipeline.infra.telegram import send_telegram


# ============================================
# GPT 한국어 메타데이터 생성 (with im-not-ai 1단계)
# ============================================
SYSTEM_PROMPT = """당신은 한국어 AI 툴 큐레이터입니다.
한국 일반 사용자(직장인·학생·소상공인) 관점에서 실용적으로 설명합니다.
전문용어 대신 쉬운 표현, 한국 실생활 예시를 반드시 포함합니다.
예시: "영어 이메일 작성", "유튜브 썸네일 제작", "사업계획서 초안 작성"

문체 규칙:
- 모든 설명은 "~합니다/~습니다/~입니다" 체의 정중한 비즈니스 한국어로 작성.
- "~다/~ㄴ다/~는다" 체(반말/평서체)는 절대 사용 금지.

JSON 외 다른 텍스트는 절대 출력하지 마세요.
{HUMANIZE_RULES}"""

USER_PROMPT_TEMPLATE = """다음 AI 툴 정보를 분석해 JSON으로 응답하세요.

툴명: __NAME__
영문설명: __DESCRIPTION__
가격: __PRICE__
URL: __URL__

[실제 웹사이트에서 크롤링한 정보]
__CRAWLED_PRICING__

반환 형식 (이 JSON 구조만 출력. 빈 배열/빈 문자열 절대 금지):
{
  "description_kr": "한줄 설명 (80자 이내, 핵심 기능 + 한국 사용자 관점)",
  "category": "글쓰기·챗봇 또는 이미지 생성 또는 영상·음성 또는 업무·생산성 또는 코딩·개발 또는 디자인 또는 번역·학습",
  "koreanSupport": true 또는 false,
  "difficulty": "초보자 OK 또는 중급 또는 고급",
  "useCases": [
    {"title": "영어 이메일 작성", "prompt": "실제 한국어 프롬프트 예시 1문장"},
    {"title": "유튜브 썸네일 제작", "prompt": "실제 한국어 프롬프트 예시 1문장"},
    {"title": "사업계획서 초안", "prompt": "실제 한국어 프롬프트 예시 1문장"}
  ],
  "tags": ["태그1", "태그2", "태그3"],
  "tasks": ["태스크 슬러그 1~3개 — 아래 목록에서 선택"],
  "tool_detail": {
    "summary": "2~3문장. 이 툴이 무엇인지, 어떤 문제를 해결하는지 한국 사용자 관점으로.",
    "features": [
      {"name": "기능명 (10자 이내)", "desc": "이 기능이 왜 유용한지 한국 사용자 관점 (40자 이내)"},
      {"name": "기능명", "desc": "설명"},
      {"name": "기능명", "desc": "설명"}
    ],
    "pricing": {
      "free": "무료 플랜 내용 1문장",
      "paid": "유료 플랜 이름 + 가격(원화 반드시 병기) + 주요 혜택 1~2문장",
      "tip": "비용 절약 팁 1문장"
    },
    "korean_detail": "한국어 지원 수준 상세 설명 1~2문장.",
    "recommend_for": "이런 분에게 추천합니다. 구체적인 페르소나 2~3개, 각 1문장.",
    "real_examples": [
      {"persona": "직장인", "example": "구체적 상황 + 어떻게 사용하는지 2문장"},
      {"persona": "학생", "example": "구체적 상황 + 어떻게 사용하는지 2문장"},
      {"persona": "소상공인", "example": "구체적 상황 + 어떻게 사용하는지 2문장"}
    ],
    "vs_similar": {
      "pros": ["장점1 (구체적)", "장점2"],
      "cons": ["단점1 (구체적)"],
      "best_for": "이 툴이 가장 적합한 상황 1문장"
    },
    "faq": [
      {"q": "실제 사용자가 검색할 법한 구체적 질문", "a": "답변 2~3문장. 단답형 금지."},
      {"q": "질문2", "a": "답변"},
      {"q": "질문3", "a": "답변"}
    ]
  }
}

태스크 슬러그 목록 (아래에서 툴 성격에 맞는 1~3개 선택):
문서: pdf-요약, 유튜브-요약, 글쓰기, 이메일-작성, 번역, 요약, 맞춤법-교정, 보고서-작성, 이력서, 카피라이팅, 문서-번역, 자기소개서, 기획서, 회의록, 프레젠테이션
이미지: 이미지-생성-무료, 이미지-생성, 배경-제거, 썸네일-제작, 로고-디자인, ppt-발표, 인포그래픽, 아이콘-디자인, 일러스트, UI-디자인, 웹디자인
영상: 영상-제작, 영상-편집, 자막-생성, 음성-변환, 더빙, 음악-생성, 텍스트-음성, 음성-녹음, 팟캐스트, 배경음악
업무: 회의-요약, 일정-관리, 데이터-분석, 엑셀-자동화, 업무-자동화, 챗봇-구축, 메모-정리, 프로젝트-관리, 자동화-워크플로우, CRM
코딩: 코딩, 코드-리뷰, 노코드, 바이브코딩, API-개발, 디버깅, 테스트
학습: 논문-요약, 영어-학습, 리서치, 자격증-학습, 면접-준비, 제2외국어
마케팅: sns-콘텐츠, seo-최적화, 광고-카피, 블로그-작성, 유튜브-편집, 마케팅-자동화, 콘텐츠-기획, 브랜드-네이밍
전문: 의료-상담, 법률-검토, 부동산-분석, 투자-분석, 회계-경리, 고객-상담

"""

def crawl_tool_page(url: str) -> dict:
    """도구 웹사이트에서 실제 정보 크롤링"""
    result = {
        'title': '',
        'description': '',
        'pricing_text': '',
        'features_text': '',
        'korean_text': '',
    }
    if not url or not url.startswith('http'):
        return result

    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9,ko;q=0.8',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')

        soup = BeautifulSoup(html, 'html.parser')

        # 타이틀
        title_el = soup.find('title')
        result['title'] = title_el.get_text(strip=True)[:200] if title_el else ''

        # 메타 설명
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        result['description'] = (meta_desc.get('content', '') or '')[:500] if meta_desc else ''

        # OG 설명
        if not result['description']:
            og_desc = soup.find('meta', attrs={'property': 'og:description'})
            result['description'] = (og_desc.get('content', '') or '')[:500] if og_desc else ''

        # 본문 텍스트 (가격, 기능 정보 추출용)
        body_text = soup.get_text(separator=' ', strip=True)[:3000]
        result['pricing_text'] = body_text
        result['features_text'] = body_text
        result['korean_text'] = body_text

        print(f"  크롤링 성공: {url[:50]}... (설명 {len(result['description'])}자)")
    except Exception as e:
        print(f"  크롤링 실패 ({url[:30]}): {e}")

    return result


def generate_metadata(tool_info: dict) -> dict:
    """무료 LLM 폴백 체인(model_router) → 한국어 메타데이터"""
    # URL 크롤링
    crawled = crawl_tool_page(tool_info.get('url', ''))
    crawled_desc = crawled.get('description', '') or tool_info.get('description', '')[:500]
    crawled_pricing = crawled.get('pricing_text', '')[:1000]

    prompt = USER_PROMPT_TEMPLATE \
        .replace('__NAME__', tool_info.get('name', '')) \
        .replace('__DESCRIPTION__', crawled_desc) \
        .replace('__PRICE__', tool_info.get('price', '')) \
        .replace('__URL__', tool_info.get('url', '')) \
        .replace('__CRAWLED_PRICING__', crawled_pricing)
    try:
        raw = chat_completion(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=SYSTEM_PROMPT,
            temperature=0.5,
            max_tokens=3000,
            model_override=None,  # 무료 LLM 폴백 체인 사용
        )
        if not raw:
            print("  LLM 호출 실패 (모든 모델 시도 후 None 반환)")
            return None
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
        print(f"    LLM 호출 실패: {e}")
        return None


# ============================================
# MD 파일 생성
# ============================================
def slugify(name: str) -> str:
    return title_to_slug(name)


def strip_tracking_params(url: str) -> str:
    """URL에서 트래킹 파라미터(ref, utm_*)만 제거. 나머지 쿼리는 보존."""
    if not url or '?' not in url:
        return url
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    parts = urlsplit(url)
    if not parts.query:
        return url
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not (k == 'ref' or k.startswith('utm_'))]
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(kept), parts.fragment))


def validate_tool_url(url: str) -> bool:
    """툴 URL이 유효한지 검증 (Product Hunt 리스팅/리다이렉트, GitHub 저장소 직접 링크 제외)"""
    if not url:
        return False
    # 쿼리스트링(트래킹 파라미터)은 판정에서 무시 — 실제 툴 도메인은 유지되어야 함
    base = url.split('?', 1)[0]
    # Product Hunt 리스팅/리다이렉트 URL 제외 (툴 자체 URL이 아님)
    if 'producthunt.com/products/' in base or 'producthunt.com/r/p/' in base:
        return False
    # GitHub 저장소 직접 링크 제외 (실제 툴이 아님)
    if base.startswith('https://github.com/') and '/blob/' not in base:
        return False
    return True


def _extract_price_label(text: str, has_free: bool) -> str:
    """문장 형태의 가격에서 짧은 라벨 추출 (예: '프리미엄 플랜 5만원/월' → '무료/월 5만원')"""
    if not text:
        return '유료'
    # 무료인 경우
    if '없음' in text or '무료' in text:
        return '무료'
    # 사용량 기반
    if '사용량' in text:
        return '사용량 기반'
    # 가격 숫자 + 단위 패턴 추출
    m = re.search(r'(\d[\d,.]*\s*(?:만원|원|달러|€|\$))', text)
    if m:
        price_unit = m.group(1).strip()
        prefix = '무료/월 ' if has_free else '월 '
        return f'{prefix}{price_unit}'
    return '유료'


def build_frontmatter(name: str, meta: dict, order: int, tool_url: str = '') -> str:
    """MD frontmatter 생성 (description은 humanize 적용)"""
    desc = humanize_md(meta.get('description_kr', ''))
    tasks_str = json.dumps(meta.get('tasks', []), ensure_ascii=False)
    tags_str = json.dumps(meta.get('tags', []), ensure_ascii=False)
    use_cases_raw = meta.get('useCases', [])
    if use_cases_raw and isinstance(use_cases_raw[0], dict):
        use_cases_raw = [uc.get('title', '') for uc in use_cases_raw]
    use_cases_str = json.dumps(use_cases_raw, ensure_ascii=False)
    today = datetime.now().strftime('%Y-%m-%d')
    # price: price_kr (구 구조) 또는 pricing.free/paid에서 생성
    price_str = meta.get('price_kr', '')
    if not price_str:
        pricing = meta.get('tool_detail', {}).get('pricing', {})
        if isinstance(pricing, dict):
            paid = pricing.get('paid', '')
            free_text = pricing.get('free', '')
            if paid:
                price_str = _extract_price_label(paid, bool(free_text))
            else:
                price_str = pricing.get('free', '무료')
    # url: tool_info에서 전달받은 원본 URL 우선, 없으면 meta에서
    url = tool_url or meta.get('url', '')
    # URL 검증
    if not validate_tool_url(url):
        url = meta.get('url', '')
    # 저장 전 트래킹 파라미터 제거 (ref=producthunt, utm_*)
    url = strip_tracking_params(url)

    return f"""---
name: "{name}"
description: "{desc}"
category: "{meta.get('category', '')}"
price: "{price_str}"
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
    """MD 본문 생성 (tool_detail 구조) — 새 JSON 구조 지원"""
    td = meta.get('tool_detail', {})
    lines = []

    # 한줄 요약
    summary = td.get('summary', '')
    if summary:
        lines.append('## 한줄 요약')
        lines.append('')
        lines.append(summary)
        lines.append('')

    # 핵심 기능 (객체 배열 또는 문자열 배열 지원)
    features = td.get('features', [])
    if features:
        lines.append('## 핵심 기능')
        lines.append('')
        for feat in features:
            if isinstance(feat, dict):
                name = feat.get("name", "")
                desc = feat.get("desc", "")
                if isinstance(desc, list):
                    desc = ' '.join(str(x) for x in desc)
                lines.append(f'- **{name}**: {desc}')
            elif isinstance(feat, list):
                lines.append(f'- {" ".join(str(x) for x in feat)}')
            else:
                lines.append(f'- {feat}')
        lines.append('')

    # 가격 정책 (새 구조: pricing / 구 구조: price_detail)
    pricing = td.get('pricing', td.get('price_detail', ''))
    if pricing:
        lines.append('## 가격 정책')
        lines.append('')
        if isinstance(pricing, dict):
            if pricing.get('free'):
                lines.append(f'- **무료 플랜**: {pricing["free"]}')
            if pricing.get('paid'):
                lines.append(f'- **유료 플랜**: {pricing["paid"]}')
            if pricing.get('tip'):
                lines.append(f'\n비용 절약 팁: {pricing["tip"]}')
        elif isinstance(pricing, str):
            lines.append(pricing)
        lines.append('')

    # 한국어 지원
    korean = td.get('korean_detail', '')
    if korean:
        lines.append('## 한국어 지원')
        lines.append('')
        lines.append(korean)
        lines.append('')

    # 이런 분에게 추천
    recommend = td.get('recommend_for', '')
    if recommend:
        lines.append('## 이런 분에게 추천합니다')
        lines.append('')
        lines.append(recommend)
        lines.append('')

    # 실제 활용 예시 (객체 배열 또는 문자열 배열 지원)
    examples = td.get('real_examples', [])
    if examples:
        lines.append('## 실제 활용 예시')
        lines.append('')
        for ex in examples:
            if isinstance(ex, dict):
                persona = ex.get("persona", "")
                example = ex.get("example", "")
                if isinstance(example, list):
                    example = ' '.join(str(x) for x in example)
                lines.append(f'- **{persona}**: {example}')
            elif isinstance(ex, list):
                lines.append(f'- {" ".join(str(x) for x in ex)}')
            else:
                lines.append(f'- {ex}')
        lines.append('')

    # 유사 툴과 비교 (새 구조: 객체 / 구 구조: 문자열)
    vs = td.get('vs_similar', '')
    if vs:
        lines.append('## 유사 툴과 비교')
        lines.append('')
        if isinstance(vs, dict):
            pros = vs.get('pros', [])
            cons = vs.get('cons', [])
            best = vs.get('best_for', '')
            if pros:
                lines.append('**장점:**')
                for p in pros:
                    if isinstance(p, list):
                        p = ' '.join(str(x) for x in p)
                    lines.append(f'- {p}')
                lines.append('')
            if cons:
                lines.append('**단점:**')
                for c in cons:
                    if isinstance(c, list):
                        c = ' '.join(str(x) for x in c)
                    lines.append(f'- {c}')
                lines.append('')
            if best:
                lines.append(f'**이런 분에게 가장 적합합니다:** {best}')
        elif isinstance(vs, str):
            lines.append(vs)
        lines.append('')

    # 자주 묻는 질문
    faqs = td.get('faq', [])
    if faqs:
        lines.append('## 자주 묻는 질문')
        lines.append('')
        for faq in faqs:
            q = faq.get("q", "") if isinstance(faq, dict) else str(faq)
            a = faq.get("a", "") if isinstance(faq, dict) else ""
            if isinstance(a, list):
                a = ' '.join(str(x) for x in a)
            lines.append(f'**{q}**')
            lines.append('')
            lines.append(f'{a}')
            lines.append('')

    # 일부 LLM 출력이 list를 섞어 넣어 TypeError로 전체 실행이 크래시 → sync_tools_to_d1 도달 불가 방어
    return '\n'.join(x if isinstance(x, str) else '\n'.join(str(i) for i in x) for x in lines)


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
# D1 tools 테이블 동기화
# ============================================
def sync_tools_to_d1() -> bool:
    """src/content/tools/*.md → D1 tools 테이블 동기화 (sync_tools_to_d1.mjs + wrangler d1 execute)"""
    sync_script = os.path.join(PROJECT_DIR, 'scripts', 'sync_tools_to_d1.mjs')
    if not os.path.exists(sync_script):
        print("  sync_tools_to_d1.mjs 없음, D1 동기화 스킵")
        return False

    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False, dir='/tmp')
    try:
        r = subprocess.run(['node', sync_script], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            print(f"  SQL 생성 실패: {r.stderr[:200]}")
            os.unlink(tmp.name)
            return False
        tmp.write(r.stdout)
        tmp.close()
        count_line = [l for l in r.stderr.split('\n') if 'INSERT' in l]
        if count_line:
            print(f"  SQL 생성: {count_line[0].strip()}")

        # wrangler d1 execute does not support BEGIN TRANSACTION/COMMIT; strip wrappers
        lines = r.stdout.splitlines()
        clean_lines = [l for l in lines if l.strip() not in ('BEGIN TRANSACTION;', 'COMMIT;')]
        with open(tmp.name, 'w') as f:
            f.write('\n'.join(clean_lines))

        r2 = subprocess.run(
            ['npx', 'wrangler', 'd1', 'execute', 'aikorea24-db', '--remote', '--file', tmp.name],
            capture_output=True, text=True, timeout=120
        )
        if r2.returncode == 0:
            print("  D1 tools 테이블 동기화 완료 ✅")
            return True
        else:
            print(f"  D1 execute 실패 ({r2.returncode}): {r2.stderr[:300]}")
            return False
    except subprocess.TimeoutExpired:
        print("  D1 동기화 타임아웃")
        return False
    except Exception as e:
        print(f"  D1 동기화 오류: {e}")
        return False
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


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
    """엔트리포인트 — 상태 기록·알림 1회 보장을 위해 예외를 감싼다 (AIK24-PIPE-09 B-1)."""
    import cfnew
    reporter = ToolsCollectorReporter()
    try:
        _run(cfnew, reporter)
    except Exception as e:
        # B-1: 예외 종료 — 상태 파일(error) + 알림 1회.
        # 가드 중단으로 이미 보고했다면 report() 가 덮어쓰지 않는다(알림 1회 보장),
        # 원본 예외는 그대로 재발시켜 스택 트레이스·exit code 를 보존한다.
        reporter.report('error', f'{type(e).__name__}: {e}', collected=0)
        raise


def _run(cfnew, reporter):
    import argparse
    # [D1-GUARD] 3구간 가드 — 80% 미만 정상 / 80~95% 축소 수집 / 95% 이상 중단.
    #   기존에는 cfnew.check_quota(threshold=0.8) 한 줄이 80% 에서 곧바로 죽였다.
    decision = apply_guard(cfnew, reporter)
    reduced = (decision['mode'] == 'reduced')

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
    parser.add_argument('--no-postprocess', action='store_true',
                       help='신규 도구 후처리(URL 승격·심화 v2·썸네일) 건너뛰기')
    parser.add_argument('--postprocess-budget', type=int, default=POSTPROCESS_BUDGET,
                       help=f'후처리 시간 예산(초, 기본 {POSTPROCESS_BUDGET})')
    args = parser.parse_args()

    # 툴 목록 로드
    tools = []
    if args.collect:
        mode_note = ' — [축소 수집] 핵심 소스만' if reduced else ''
        print(f"[수집 모드] Product Hunt + Futurepedia + HuggingFace (소스당 {args.limit}개){mode_note}")
        tools = collect_tools(limit_per_source=args.limit, reduced=reduced)
        if not tools:
            print("수집된 툴 없음")
            reporter.report('reduced' if reduced else 'ok', decision['reason'],
                            collected=0, alert=reduced)
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
        print("  python3 tools_collector.py --collect --batch 5        # PH + Futurepedia + HuggingFace 수집 + 처리")
        print("  python3 tools_collector.py --collect --dry-run       # 수집만 미리보기")
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
        # ── 신규 도구 자동 후처리 (URL 승격 → 심화 스키마 v2 → 썸네일) ──────────
        # 커밋·배포 **전에** 수행한다. 그래야 새 도구가 8섹션 스텁·썸네일 없음 상태로
        # 배포되지 않는다. 실패해도 수집 결과는 그대로 커밋·배포된다(비차단).
        try:
            if args.no_postprocess:
                print("\n[후처리] --no-postprocess 지정 — 건너뜀")
            else:
                import tools_postprocess
                print("\n[후처리] 신규 도구 상세페이지 심화·썸네일·URL 승격")
                tools_postprocess.postprocess(created, budget=args.postprocess_budget)
        except Exception as e:
            print(f"  후처리 실패(수집 결과는 유지): {type(e).__name__}: {e}")

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
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                r = subprocess.run(['bash', deploy_script],
                                 capture_output=True, text=True, timeout=300)
                if r.returncode == 0:
                    print("  배포 완료 ✅")
                    break
                else:
                    err_msg = (r.stderr[:300] or r.stdout[:300] or '알 수 없는 오류').strip()
                    print(f"  배포 실패 (시도 {attempt}/{max_retries}): {err_msg}")
                    if attempt < max_retries:
                        print("  5초 후 재시도...")
                        import time
                        time.sleep(5)
            except subprocess.TimeoutExpired:
                print(f"  배포 타임아웃 (시도 {attempt}/{max_retries})")
                if attempt < max_retries:
                    print("  5초 후 재시도...")
                    import time
                    time.sleep(5)
            except Exception as e:
                print(f"  배포 오류 (시도 {attempt}/{max_retries}): {e}")
                break

        # D1 tools 테이블 동기화
        print("\n[D1 동기화] tools 테이블 업데이트 중...")
        sync_tools_to_d1()

    # === 수집 상태 기록 (AIK24-PIPE-09 B-1) ===
    # 운영자 가시성용 상태 파일. 07:00 파이프라인이 읽는 뉴스 수집기의
    # scripts/.collector_state.json 과는 **다른 파일**이다.
    # 정상 수집은 알림을 보내지 않는다(하루 1회 성공을 알릴 이유가 없다).
    reporter.report('reduced' if reduced else 'ok', decision['reason'],
                    collected=len(created), alert=reduced)


if __name__ == '__main__':
    main()
