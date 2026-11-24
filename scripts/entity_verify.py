#!/usr/bin/env python3
"""AIK24-TOOLS-ENTITY-01 — 도구 '실체(운영 주체)' 검증 모듈.

수집기(`scripts/tools_collector.py`)의 신규 등록 필터와 전수조사
(`scripts/audit_tool_entities.py`)가 **같은 기준**을 쓰도록 분리한 모듈이다.
한쪽만 바꾸면 두 판정이 어긋나므로 판정 기준은 이 파일에만 둔다.

판정 기준 (지시서 2026-11-24 §2)
  0단계 하드 실패
    · URL 접속 불가 (DNS·타임아웃·4xx·5xx — 1회 재시도 후에도 실패)
    · 파킹 페이지 (domain for sale / parked 등)
    · 수집원 도메인 (논문·디렉토리 링크 — topai.tools, huggingface.co/papers 등)
  1단계 실체 확인
    · 공식 홈페이지 + /privacy·/terms·/contact 계열 페이지에서 운영 주체 신호
    · 신호 = 법인명(Inc·Ltd·LLC·GmbH·Pte·(주)·주식회사 등)
             또는 개인명 + 연락처(이메일·주소·전화 중 1개 이상)
  대체 경로
    · App Store / Google Play URL → 스토어 판매자(seller/개발자) 정보
    · GitHub 저장소 → 저장소 실존 + 최근 1년 내 활동(커밋·릴리스)
  판정
    · pass  : 실체 신호 확인
    · fail  : 하드 실패 또는 실체 신호 없음
    · hold  : 신호가 애매해 사람이 직접 확인해야 함 (자동 통과 금지)

주의: 정책 페이지의 존재 자체는 증거가 아니다. 법인명·주소·연락처가
      실제로 적혀 있어야 한다. 애매하면 hold 로 내리고 pass 로 올리지 않는다.

사용:
    from entity_verify import verify_entity
    r = verify_entity('https://example.com')
    r['verdict']  # 'pass' | 'fail' | 'hold'
"""
from __future__ import annotations

import html as _html
import json
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit

PASS = 'pass'
FAIL = 'fail'
HOLD = 'hold'

TIMEOUT = 15
MAX_BODY_BYTES = 800_000
POLICY_PATHS = (
    '/privacy', '/privacy-policy', '/policies/privacy-policy', '/legal/privacy',
    '/terms', '/terms-of-service', '/terms-of-use', '/policies/terms-of-use',
    '/legal', '/legal/terms', '/imprint', '/impressum',
    '/contact', '/contact-us', '/about', '/about-us', '/company',
)
MAX_POLICY_FETCHES = 8

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

# ── 0단계: 수집원(디렉토리·논문) 도메인 ──────────────────────────────────
COLLECTOR_HOSTS = {
    'topai.tools', 'www.topai.tools',
    'futurepedia.io', 'www.futurepedia.io',
    'aixploria.com', 'www.aixploria.com',
    'toolpilot.ai', 'www.toolpilot.ai',
    'theresanaiforthat.com', 'www.theresanaiforthat.com',
    'producthunt.com', 'www.producthunt.com',
    'huggingface.co', 'www.huggingface.co',
    'github.com', 'www.github.com',  # GitHub 은 대체 경로에서만 허용
}

# ── 파킹 페이지 ─────────────────────────────────────────────────────────
PARKED_RE = re.compile(
    r'domain\s+(?:name\s+)?(?:is\s+)?for\s+sale|buy\s+this\s+domain|'
    r'this\s+domain\s+(?:is|may\s+be)\s+for\s+sale|domain\s+parking|'
    r'parked\s+(?:free|domain)|hugedomains|afternic|sedo\.com|'
    r'spaceship\.com|domain\s+is\s+available|make\s+an\s+offer\s+on\s+this\s+domain',
    re.I,
)

# ── 실체 신호 정규식 ────────────────────────────────────────────────────
_LEGAL_SUFFIX = (
    r'(?:Inc|Incorporated|LLC|L\.L\.C\.|Ltd|Limited|Corp|Corporation|GmbH|'
    r'Pty\.?\s*Ltd|Pte\.?\s*Ltd|Co\.,?\s*Ltd|S\.A\.|B\.V\.|K\.K\.)'
)
LEGAL_RE = re.compile(
    r'(?:\(주\)|㈜|주식회사|株式会社|有限公司)'
    r'|\b[A-Z][A-Za-z0-9&\'\-]{0,24}'
    r'(?:\s*,?\s+[A-Z][A-Za-z0-9&\'\-]{0,24}){0,3}\s*,?\s+' + _LEGAL_SUFFIX + r'\b\.?'
)

EMAIL_RE = re.compile(r'[A-Za-z0-9._%+\-]{2,64}@[A-Za-z0-9.\-]{2,64}\.[A-Za-z]{2,10}')
_EMAIL_BAD_DOMAINS = (
    'example.com', 'example.org', 'sentry.io', 'sentry-next.wixpress.com',
    'wixpress.com', 'domain.com', 'email.com', 'yourdomain.com', 'sentry.wixpress.com',
)
_EMAIL_BAD_TLDS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js')

PHONE_RE = re.compile(
    r'(?:\+\d{1,3}[\s.\-]?(?:\(?\d{1,4}\)?[\s.\-]?)?\d{2,4}[\s.\-]\d{3,4}[\s.\-]\d{3,4})'
    r'|(?:(?:tel|phone|전화|연락처|대표번호|고객센터)\s*[:：]?\s*'
    r'(?:\+\d{1,3}[\s\-]?)?(?:0\d{1,2}[\s.\-]?\d{3,4}[\s.\-]?\d{4}))',
    re.I,
)

ADDRESS_RE = re.compile(
    r'\b\d{1,6}[A-Za-z]?\s+[A-Z][A-Za-z0-9.\-]+'
    r'(?:\s+[A-Z0-9][A-Za-z0-9.\-]+){0,3}\s+'
    r'(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Lane|Ln\.?|'
    r'Drive|Dr\.?|Court|Ct\.?|Way|Place|Pl\.?|Suite|Floor|Building)\b'
    r'|(?:서울(?:특별시|특별자치시|시)?|부산(?:광역시|시)?|대구|인천|광주|대전|울산|세종|'
    r'경기(?:도)?|강원(?:특별자치도|도)?|충북|충남|전북|전남|경북|경남|제주(?:특별자치도)?)'
    r'[^\n]{0,40}?(?:로|길|대로)\s*\d+'
)

PERSON_CONTEXT_RE = re.compile(
    r'(?:CEO|Founder|Co-?Founder|Owner|Director|대표(?:자)?|운영자|'
    r'개인정보\s*보호\s*책임자|Contact\s*person|Contact|문의\s*담당)\s*[:：\-]?\s*'
    r'([A-Z][a-z]{1,19}(?:\s+[A-Z][a-z]{1,24}){1,2})'
)

COPYRIGHT_RE = re.compile(
    r'(?:©|\(c\)|Copyright)\s*(?:\d{4}(?:\s*[-–]\s*\d{4})?)?\s*'
    r'([A-Z][A-Za-z0-9&.\'\-]*(?:\s+[A-Z][A-Za-z0-9&.\'\-]*){0,4})',
    re.I,
)

_SCRIPT_STYLE_RE = re.compile(r'<(script|style|noscript)[^>]*>.*?</\1>', re.I | re.S)

# 법인명 문맥에서 '운영 주체가 아닌' 언급을 걸러내는 표지 (고객사·호스팅·투자자)
_NON_OPERATOR_MARKERS = (
    'customer stories', 'customers include', 'trusted by', 'used by', 'powered by',
    'hosted by', 'testimonial', 'case study', 'our customers', 'partnered with',
    'backed by', 'investors include', 'works with', 'as seen in', 'featured in',
    '고객사', '도입 사례', '파트너사',
    # 호스팅·인프라 사업자가 정책 페이지에 자기 이름을 남기는 경우
    'vercel inc', 'vercel.com', 'netlify', 'sentry', 'wix.com', 'shopify inc',
    'squarespace', 'godaddy', 'amazon web services', 'google cloud',
)

# 법인명 매치에 섞여 들어오면 안 되는 일반명사(추출 오류 방지)
_LEGAL_GENERIC_WORDS = (
    'purpose', 'location', 'compliance', 'privacy', 'terms', 'policy', 'cookie',
    'security', 'service', 'services', 'notice', 'statement', 'rights', 'reserved',
    'customer', 'customers', 'story', 'stories', 'company', 'provider', 'seller',
)
_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')


# ══════════════════════════════════════════════════════════════════════
# HTTP
# ══════════════════════════════════════════════════════════════════════
def default_fetch(url: str, timeout: int = TIMEOUT) -> dict:
    """URL 1회 요청. 예외를 던지지 않고 결과 dict 로 돌려준다.

    반환: {'status': int|None, 'final_url': str, 'text': str, 'error': str|None}
    """
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,ko;q=0.8',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(MAX_BODY_BYTES)
            charset = resp.headers.get_content_charset() or 'utf-8'
            try:
                text = raw.decode(charset, errors='replace')
            except LookupError:
                text = raw.decode('utf-8', errors='replace')
            return {'status': getattr(resp, 'status', 200), 'final_url': resp.geturl() or url,
                    'text': text, 'error': None}
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read(200_000).decode('utf-8', errors='replace')
        except Exception:  # noqa: BLE001
            pass
        return {'status': e.code, 'final_url': url, 'text': body, 'error': f'HTTP {e.code}'}
    except Exception as e:  # noqa: BLE001 — DNS·타임아웃·SSL 전부 같은 경로
        return {'status': None, 'final_url': url, 'text': '', 'error': f'{type(e).__name__}: {e}'}


_FETCH_CACHE: dict[str, dict] = {}
_CACHE_LOCK = threading.Lock()


def fetch_page(url: str, fetcher=None, timeout: int = TIMEOUT) -> dict:
    """1회 재시도 + 프로세스 내 캐시(전수조사에서 같은 도메인 반복 요청 방지)."""
    fetcher = fetcher or default_fetch
    key = (id(fetcher), url)
    with _CACHE_LOCK:
        if key in _FETCH_CACHE:
            return _FETCH_CACHE[key]
    res = fetcher(url, timeout) if _accepts_timeout(fetcher) else fetcher(url)
    if res.get('status') is None:            # 네트워크 실패만 1회 재시도
        time.sleep(1)
        res = fetcher(url, timeout) if _accepts_timeout(fetcher) else fetcher(url)
    with _CACHE_LOCK:
        _FETCH_CACHE[key] = res
    return res


def _accepts_timeout(fetcher) -> bool:
    try:
        import inspect
        return 'timeout' in inspect.signature(fetcher).parameters
    except (TypeError, ValueError):
        return False


def clear_cache() -> None:
    with _CACHE_LOCK:
        _FETCH_CACHE.clear()


# ══════════════════════════════════════════════════════════════════════
# 텍스트·신호
# ══════════════════════════════════════════════════════════════════════
_POLICY_LINK_RE = re.compile(
    r'href=["\']([^"\']{2,200})["\']', re.I)
_POLICY_WORD_RE = re.compile(
    r'privacy|terms|legal|about|contact|impressum|policy|company|회사|개인정보|약관|이용약관',
    re.I)


def _candidate_policy_urls(home_html: str, base: str, limit: int = 6) -> list[str]:
    """홈페이지 실제 링크에서 정책·회사 소개 페이지를 찾는다 (경로 추측보다 정확).

    2026-11-24 캘리브레이션: canva.com 은 /privacy 가 404 이고 실제 정책은
    /policies/privacy-policy/ 에 있다. 경로 추측만으로는 대형 서비스도 '신호 없음'이 됐다.
    """
    out, seen = [], set()
    for m in _POLICY_LINK_RE.finditer(home_html or ''):
        href = m.group(1)
        if not _POLICY_WORD_RE.search(href):
            continue
        target = urljoin(base, href)
        if not target.startswith('http'):
            continue
        if urlsplit(target).netloc != urlsplit(base).netloc:
            continue
        target = target.split('#', 1)[0]
        if target in seen or target.rstrip('/') == base.rstrip('/'):
            continue
        seen.add(target)
        out.append(target)
        if len(out) >= limit:
            break
    return out


def html_to_text(html: str) -> str:
    """태그·스크립트를 걷어낸 사람이 읽는 텍스트 (정규식 기반, 의존성 0)."""
    if not html:
        return ''
    s = _SCRIPT_STYLE_RE.sub(' ', html)
    s = _TAG_RE.sub(' ', s)
    s = _html.unescape(s)
    return _WS_RE.sub(' ', s).strip()


def _first_match(regex, text, flags=0):
    m = re.search(regex, text, flags)
    return m.group(0).strip() if m else None


def find_legal_entity(text: str, page_kind: str = 'home') -> str | None:
    """법인명 탐지 — '고객사 이름'을 운영 주체로 오인하지 않도록 문맥을 본다.

    page_kind='home'  : 홈페이지. 저작권 표기·연락처·사업자 표기 문맥에서만 인정한다.
    page_kind='policy': 개인정보·약관·연락처 페이지. 페이지 자체가 운영 주체를 밝히는
                        문서이므로 문맥 요건을 완화하되, 호스팅·고객사 언급은 제외한다.
    """
    if not text:
        return None
    for m in LEGAL_RE.finditer(text):
        snippet = m.group(0).strip().rstrip(',').strip()
        ctx = text[max(0, m.start() - 140):m.end() + 140]
        low = ctx.lower()
        if any(mark in low for mark in _NON_OPERATOR_MARKERS):
            continue
        name_only = snippet.lower()
        if any(w in name_only for w in _LEGAL_GENERIC_WORDS):
            continue
        if page_kind == 'policy':
            return snippet
        if re.search(r'©|\(c\)\s*\d{4}|copyright', low):
            return snippet
        if re.search(r'사업자|등록번호|대표자|대표\s*:|주소|개인정보\s*(?:보호\s*)?책임자', ctx):
            return snippet
        if re.search(r'\b(?:address|registered office|headquarter\w*|contact|email|tel|phone)\b',
                     low) or find_contact(ctx)['email'] or find_contact(ctx)['address']:
            return snippet
    return None


def find_contact(text: str) -> dict:
    out = {'email': None, 'phone': None, 'address': None}
    for m in EMAIL_RE.finditer(text or ''):
        cand = m.group(0)
        low = cand.lower()
        if any(bad in low for bad in _EMAIL_BAD_DOMAINS):
            continue
        if low.endswith(_EMAIL_BAD_TLDS):
            continue
        out['email'] = cand
        break
    out['phone'] = _first_match(PHONE_RE, text or '')
    out['address'] = _first_match(ADDRESS_RE, text or '')
    return out


_PERSON_STOPWORDS = {
    'support', 'legal', 'privacy', 'terms', 'contact', 'about', 'home', 'pricing',
    'blog', 'help', 'team', 'careers', 'press', 'security', 'cookies', 'cookie',
    'policy', 'login', 'sign', 'free', 'pro', 'features', 'product', 'company',
    'store', 'app', 'apps', 'api', 'docs', 'what', 'how', 'why', 'our', 'the',
    'more', 'read', 'learn', 'get', 'start', 'user', 'users', 'customer', 'email',
    'person', 'manager', 'director', 'founder', 'owner',
}


def find_person_with_contact(text: str) -> str | None:
    """'개인명 + 연락처' 경로. 이름만 있고 연락처가 없으면 신호가 아니다.

    탐색 메뉴('Contact Support Legal Privacy')를 사람 이름으로 오인하지 않도록
    일반명사 목록으로 걸러낸다.
    """
    if not text:
        return None
    contact = find_contact(text)
    if not any(contact.values()):
        return None
    for m in PERSON_CONTEXT_RE.finditer(text):
        words = m.group(1).split()
        kept = []
        for w in words:
            if w.lower().strip('.,') in _PERSON_STOPWORDS:
                break
            kept.append(w)
        if len(kept) < 2:
            continue
        name = ' '.join(kept)
        if LEGAL_RE.search(name):      # 법인명을 사람 이름으로 오인하지 않는다
            continue
        return name
    return None


def find_copyright_org(text: str) -> str | None:
    if not text:
        return None
    m = COPYRIGHT_RE.search(text)
    if not m:
        return None
    org = (m.group(1) or '').strip()
    # '© 2026 All rights reserved' 같은 상투구는 기관명이 아니다
    if len(org) < 2 or re.match(r'(?i)^(all|the|this|our)\b', org):
        return None
    return m.group(0).strip()


def is_parked(text: str, url: str = '') -> bool:
    blob = (text or '')[:20000] + ' ' + (url or '')
    return bool(PARKED_RE.search(blob))


def is_collector_source(url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or '').lower()
    except ValueError:
        return False
    if host in COLLECTOR_HOSTS:
        return True
    return any(host.endswith('.' + h) for h in COLLECTOR_HOSTS)


# ══════════════════════════════════════════════════════════════════════
# 대체 경로 — 스토어 / GitHub
# ══════════════════════════════════════════════════════════════════════
APPLE_STORE_RE = re.compile(r'^https?://apps\.apple\.com/', re.I)
PLAY_STORE_RE = re.compile(r'^https?://play\.google\.com/store/apps/details', re.I)
GITHUB_REPO_RE = re.compile(r'^https?://(?:www\.)?github\.com/([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+)')

_APPLE_SELLER_RES = (
    re.compile(r'"sellerName"\s*:\s*"([^"]{2,80})"'),
    re.compile(r'Seller</dt>\s*<dd[^>]*>(.{2,120}?)</dd>', re.I | re.S),
    re.compile(r'"seller"\s*:\s*"([^"]{2,80})"'),
    re.compile(r'Provider</dt>\s*<dd[^>]*>(.{2,120}?)</dd>', re.I | re.S),
)
_PLAY_DEV_RES = (
    re.compile(r'Offered by\s*</?[^>]*>?\s*([^<]{2,80})', re.I),
    re.compile(r'href="/store/apps/dev\?id=[^"]*"[^>]*>([^<]{2,80})<', re.I),
    re.compile(r'개발자\s*</?[^>]*>?\s*([^<]{2,80})'),
)


def _verify_store(url: str, fetcher) -> dict:
    res = fetch_page(url, fetcher)
    if res.get('status') is None:
        return _result(url, FAIL, 'store', '스토어 페이지 접속 불가', {'error': res.get('error')})
    if res.get('status', 0) >= 400:
        return _result(url, FAIL, 'store', f'스토어 페이지 HTTP {res["status"]}',
                       {'error': res.get('error')})
    patterns = _APPLE_SELLER_RES if APPLE_STORE_RE.match(url) else _PLAY_DEV_RES
    for pat in patterns:
        m = pat.search(res.get('text') or '')
        if m:
            name = html_to_text(m.group(1)).strip()
            if 2 <= len(name) <= 80:
                return _result(url, PASS, 'store', f'스토어 판매자 정보: {name}',
                               {'seller': name, 'final_url': res.get('final_url')})
    return _result(url, HOLD, 'store', '스토어 페이지는 열리지만 판매자 정보를 못 찾음',
                   {'final_url': res.get('final_url')})


def _verify_github(url: str, fetcher, now=None) -> dict:
    m = GITHUB_REPO_RE.match(url)
    if not m:
        return _result(url, HOLD, 'github', 'GitHub 저장소 URL 형식이 아님')
    owner, repo = m.group(1), m.group(2)
    if repo.endswith('.git'):
        repo = repo[:-4]
    api = f'https://api.github.com/repos/{owner}/{repo}'
    res = fetch_page(api, fetcher)
    pushed = None
    if res.get('status') == 200 and res.get('text'):
        try:
            data = json.loads(res['text'])
            pushed = data.get('pushed_at') or data.get('updated_at')
        except (json.JSONDecodeError, TypeError):
            pushed = None
    if not pushed:
        page = fetch_page(f'https://github.com/{owner}/{repo}', fetcher)
        if page.get('status') is None:
            return _result(url, FAIL, 'github', 'GitHub 저장소 접근 불가',
                           {'error': page.get('error')})
        if page.get('status', 0) >= 400:
            return _result(url, FAIL, 'github', f'GitHub 저장소 HTTP {page["status"]}')
        return _result(url, HOLD, 'github', '저장소는 있으나 최근 활동을 확인하지 못함',
                       {'repo': f'{owner}/{repo}'})
    # 최근 1년 내 활동
    now_ts = now or time.time()
    try:
        pushed_ts = time.mktime(time.strptime(pushed[:19], '%Y-%m-%dT%H:%M:%S'))
        pushed_ts -= time.timezone
    except (ValueError, TypeError):
        pushed_ts = None
    if pushed_ts is None:
        return _result(url, HOLD, 'github', f'저장소 활동 시각 해석 실패: {pushed}',
                       {'repo': f'{owner}/{repo}', 'pushed_at': pushed})
    days = (now_ts - pushed_ts) / 86400
    if days <= 365:
        return _result(url, PASS, 'github', f'GitHub 저장소 최근 활동 {int(days)}일 전',
                       {'repo': f'{owner}/{repo}', 'pushed_at': pushed})
    return _result(url, FAIL, 'github', f'GitHub 저장소 최근 활동 없음 ({int(days)}일 전)',
                   {'repo': f'{owner}/{repo}', 'pushed_at': pushed})


# ══════════════════════════════════════════════════════════════════════
# 본 판정
# ══════════════════════════════════════════════════════════════════════
def _result(url, verdict, stage, reason, evidence=None, extra=None) -> dict:
    out = {'url': url, 'verdict': verdict, 'stage': stage, 'reason': reason,
           'evidence': evidence or {}}
    if extra:
        out.update(extra)
    return out


def verify_entity(url: str, fetcher=None, now=None) -> dict:
    """도구 URL 1건의 실체 판정.

    Args:
        url: 도구 공식 URL (md frontmatter `url`)
        fetcher: 테스트 주입용 callable(url[, timeout]) -> fetch dict
        now: GitHub 활동 판정 기준 시각(epoch sec) — 테스트 고정용
    Returns:
        {'url','verdict','stage','reason','evidence'}
    """
    fetcher = fetcher or default_fetch
    url = (url or '').strip()

    # 0-a. URL 자체가 없음
    if not url:
        return _result(url, FAIL, 'reachability', 'URL 없음')
    if not re.match(r'^https?://', url, re.I):
        return _result(url, FAIL, 'reachability', 'URL 형식이 아님(http/https 아님)')

    # 0-b. 수집원(디렉토리·논문) 도메인 = 도구 자체 홈페이지가 아님
    if is_collector_source(url) and not GITHUB_REPO_RE.match(url):
        return _result(url, FAIL, 'reachability', '수집원(디렉토리·논문) 도메인 링크')

    # 대체 경로 1 — 앱 스토어
    if APPLE_STORE_RE.match(url) or PLAY_STORE_RE.match(url):
        return _verify_store(url, fetcher)

    # 대체 경로 2 — GitHub 저장소
    if GITHUB_REPO_RE.match(url):
        return _verify_github(url, fetcher, now=now)

    # 0-c. 접속 확인 (+1회 재시도는 fetch_page 안에서)
    home = fetch_page(url, fetcher)
    if home.get('status') is None:
        return _result(url, FAIL, 'reachability', f'URL 접속 불가 ({home.get("error")})',
                       {'error': home.get('error')})
    if home.get('status', 0) >= 400:
        status = home['status']
        # 봇 차단·요금 게이트는 '없는 사이트'가 아니라 '판정 불가'다 (2026-11-24 캘리브레이션:
        #   claude.ai·midjourney.com·perplexity.ai 등 실재 서비스가 403/400 을 돌려줬다).
        if status in (400, 401, 402, 403, 407, 418, 429):
            return _result(url, HOLD, 'reachability',
                           f'HTTP {status} — 접근 차단(봇 차단 추정), 판정 불가',
                           {'status': status})
        return _result(url, FAIL, 'reachability', f'HTTP {status}',
                       {'status': status})
    home_text = html_to_text(home.get('text') or '')
    if is_parked(home_text, home.get('final_url') or url):
        return _result(url, FAIL, 'reachability', '파킹 페이지',
                       {'final_url': home.get('final_url')})

    # 1단계. 실체 확인 — 홈 + 정책/연락 페이지
    base = home.get('final_url') or url
    pages = [('home', home_text)]
    legal = find_legal_entity(home_text, 'home')
    fetched = 0
    if not legal:
        # ① 홈페이지 실제 링크에서 정책·회사 페이지를 먼저 찾는다(경로 추측보다 정확).
        candidates = _candidate_policy_urls(home.get('text') or '', base, limit=MAX_POLICY_FETCHES)
        # ② 링크가 없으면 관례 경로로 보완한다.
        candidates += [urljoin(base, path) for path in POLICY_PATHS]
        seen = set()
        for target in candidates:
            if fetched >= MAX_POLICY_FETCHES:
                break
            if target in seen:
                continue
            seen.add(target)
            r = fetch_page(target, fetcher)
            fetched += 1
            if r.get('status') != 200:
                continue
            txt = html_to_text(r.get('text') or '')
            if len(txt) < 80:          # 껍데기 페이지는 증거가 아니다
                continue
            label = urlsplit(target).path or target
            pages.append((label, txt))
            legal = find_legal_entity(txt, 'policy')
            if legal:
                break

    blob = '\n'.join(t for _, t in pages)
    contact = find_contact(blob)
    person = find_person_with_contact(blob)
    copyright_org = find_copyright_org(blob)
    evidence = {
        'final_url': base,
        'pages_checked': [n for n, _ in pages],
        'legal_entity': legal,
        'person_with_contact': person,
        'contact': {k: v for k, v in contact.items() if v} or None,
        'copyright_holder': copyright_org,
    }

    if legal:
        return _result(url, PASS, 'entity', f'법인명 확인: {legal}', evidence)
    if person:
        return _result(url, PASS, 'entity', f'개인명 + 연락처 확인: {person}', evidence)
    if any(contact.values()) and copyright_org:
        return _result(url, HOLD, 'entity',
                       '연락처·저작권자 표기는 있으나 법인격 표기(Inc/Ltd 등)가 없어 사람 확인 필요',
                       evidence)
    if copyright_org:
        return _result(url, HOLD, 'entity',
                       '저작권자 표기만 있고 연락처가 없어 사람 확인 필요', evidence)
    if any(contact.values()):
        return _result(url, HOLD, 'entity',
                       '연락처만 있고 운영 주체 이름이 없어 사람 확인 필요', evidence)
    # 정책 페이지가 막혔거나 JS 로만 그려져 신호를 못 얻은 경우는 '주체 없음'이 아니라
    # '판정 불가'다 (2026-11-24 캘리브레이션: canva·gemini·grok 등 대형 서비스가
    #  경로 추측 실패만으로 불통과가 됐다). 내용이 빈약한 페이지만 불통과로 본다.
    if len(home_text) < 60:
        return _result(url, HOLD, 'entity',
                       '홈페이지 텍스트가 너무 적어(JS 렌더 추정) 판정 불가 — 사람 확인 필요',
                       evidence)
    # 2026-11-24 캘리브레이션 2차: 본문이 짧은 것도 '운영 주체 없음'이 아니라
    # '판정 불가'다(imagefx·ninjo.ai·oreate·jev-wrapped 이 본문 길이만으로 불통과가 됐다).
    # 실체 stage 에서는 불통과를 만들지 않는다 — 확실한 근거 없이 게재를 내리지 않는다.
    return _result(url, HOLD, 'entity',
                   '운영 주체 신호를 못 찾음(정책 페이지 접근 실패·JS 렌더 추정) — 사람 확인 필요',
                   evidence)


__all__ = [
    'PASS', 'FAIL', 'HOLD', 'verify_entity', 'default_fetch', 'fetch_page', 'clear_cache',
    'html_to_text', 'find_legal_entity', 'find_contact', 'find_person_with_contact',
    'is_parked', 'is_collector_source',
]
