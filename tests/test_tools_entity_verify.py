#!/usr/bin/env python3
"""AIK24-TOOLS-ENTITY-01 — 실체 검증 필터 단위 테스트 (네트워크 0회).

검증 대상: scripts/entity_verify.py + scripts/tools_collector.py 의 필터 결선
  · 0단계 하드 실패 — URL 없음/형식 오류, 접속 불가, 4xx/5xx, 파킹, 수집원 도메인
  · 1단계 실체 확인 — 법인명 / 개인명+연락처 / (연락처만·저작권자만) 보류 / 신호 없음
  · 대체 경로 — App Store 판매자, GitHub 저장소 최근 활동
  · 수집기 결선 — 불통과는 LLM 호출 없이 스킵, 보류는 md 생성 없이 hold jsonl 기록

주의: 실제 URL 대신 픽스처 HTML/JSON 을 주입한다. 네트워크·LLM·D1·git 호출 0회.
사용: pytest tests/test_tools_entity_verify.py -q
"""
import importlib.util
import json
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITY_PATH = os.path.join(REPO_ROOT, 'scripts', 'entity_verify.py')
COLLECTOR_PATH = os.path.join(REPO_ROOT, 'scripts', 'tools_collector.py')


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='module')
def ev():
    mod = _load('aik24_entity_verify', ENTITY_PATH)
    mod.clear_cache()
    return mod


@pytest.fixture()
def tc(ev):
    return _load('aik24_tools_collector_entity', COLLECTOR_PATH)


class FakeFetcher:
    """URL → 픽스처 매핑. 정의되지 않은 URL 은 404."""

    def __init__(self, pages, missing_status=404):
        self.pages = pages
        self.missing_status = missing_status
        self.calls = []

    def __call__(self, url, timeout=15):
        self.calls.append(url)
        if url in self.pages:
            val = self.pages[url]
            if isinstance(val, Exception):
                return {'status': None, 'final_url': url, 'text': '', 'error': repr(val)}
            return {'status': 200, 'final_url': url, 'text': val, 'error': None}
        return {'status': self.missing_status, 'final_url': url, 'text': '', 'error': 'HTTP 404'}


LEGAL_HTML = """
<html><body><footer>
<p>Acme Labs, Inc. — 123 Main Street, San Francisco, CA 94105</p>
<p>Contact: hello@acmelabs.com</p>
<p>&copy; 2026 Acme Labs, Inc. All rights reserved.</p>
</footer></body></html>
"""

NO_SIGNAL_HTML = """
<html><body><h1>SuperTool</h1>
<p>The fastest way to summarize anything. Try it free today!</p>
<a href="/pricing">Pricing</a><a href="/login">Log in</a>
</body></html>
"""

PARKED_HTML = """
<html><body><h1>this domain is for sale</h1>
<p>Buy this domain today. Inquire at broker@sedo.com</p></body></html>
"""

PERSON_HTML = """
<html><body><h1>Paper Pilot</h1>
<p>Contact person: Jane Doe</p>
<p>Email: jane@paperpilot.io</p></body></html>
"""

CONTACT_ONLY_HTML = """
<html><body><h1>Widgetly</h1>
<p>Need help? Email support@widgetly.app</p></body></html>
"""

COPYRIGHT_ONLY_HTML = """
<html><body><h1>Widgetly</h1>
<p>&copy; 2026 Widgetly Studio</p></body></html>
"""


# ══════════════════════════════════════════════════════════════════════
# 0단계 — 하드 실패
# ══════════════════════════════════════════════════════════════════════
def test_empty_url_fails(ev):
    r = ev.verify_entity('', fetcher=FakeFetcher({}))
    assert r['verdict'] == ev.FAIL
    assert r['stage'] == 'reachability'
    assert 'URL 없음' in r['reason']


def test_non_http_url_fails(ev):
    r = ev.verify_entity('acme.com', fetcher=FakeFetcher({}))
    assert r['verdict'] == ev.FAIL
    assert '형식' in r['reason']


@pytest.mark.parametrize('url', [
    'https://topai.tools/tool/acme',
    'https://www.futurepedia.io/tool/acme',
    'https://huggingface.co/papers/2410.12345',
    'https://www.producthunt.com/products/acme',
    'https://theresanaiforthat.com/ai/acme',
])
def test_collector_source_domains_fail(ev, url):
    f = FakeFetcher({})
    r = ev.verify_entity(url, fetcher=f)
    assert r['verdict'] == ev.FAIL
    assert '수집원' in r['reason']
    assert f.calls == []  # 도메인 판정은 요청 전에 끝난다


def test_unreachable_fails_after_one_retry(ev):
    f = FakeFetcher({'https://dead.example-tool.com': OSError('dns failure')})
    r = ev.verify_entity('https://dead.example-tool.com', fetcher=f)
    assert r['verdict'] == ev.FAIL
    assert '접속 불가' in r['reason']
    assert f.calls.count('https://dead.example-tool.com') == 2  # 1회 재시도


def test_http_4xx_fails(ev):
    r = ev.verify_entity('https://gone.example-tool.com', fetcher=FakeFetcher({}, missing_status=404))
    assert r['verdict'] == ev.FAIL
    assert 'HTTP 404' in r['reason']


def test_http_5xx_fails(ev):
    r = ev.verify_entity('https://boom.example-tool.com', fetcher=FakeFetcher({}, missing_status=503))
    assert r['verdict'] == ev.FAIL
    assert 'HTTP 503' in r['reason']


def test_parked_page_fails(ev):
    r = ev.verify_entity('https://parked.example-tool.com',
                         fetcher=FakeFetcher({'https://parked.example-tool.com': PARKED_HTML}))
    assert r['verdict'] == ev.FAIL
    assert '파킹' in r['reason']


# ══════════════════════════════════════════════════════════════════════
# 1단계 — 실체 확인
# ══════════════════════════════════════════════════════════════════════
def test_legal_entity_on_home_passes(ev):
    url = 'https://acmelabs.com'
    r = ev.verify_entity(url, fetcher=FakeFetcher({url: LEGAL_HTML}))
    assert r['verdict'] == ev.PASS
    assert r['stage'] == 'entity'
    assert 'Acme Labs, Inc' in r['evidence']['legal_entity']


def test_legal_entity_only_on_privacy_page_passes(ev):
    url = 'https://quietlabs.io'
    f = FakeFetcher({
        url: NO_SIGNAL_HTML,
        'https://quietlabs.io/privacy': '<html><body>' + LEGAL_HTML + '</body></html>',
    })
    r = ev.verify_entity(url, fetcher=f)
    assert r['verdict'] == ev.PASS
    assert '/privacy' in r['evidence']['pages_checked']


def test_korean_legal_form_passes(ev):
    url = 'https://hangul-tool.kr'
    html = '<html><body><footer>주식회사 한글툴 | 서울특별시 강남구 테헤란로 123</footer></body></html>'
    r = ev.verify_entity(url, fetcher=FakeFetcher({url: html}))
    assert r['verdict'] == ev.PASS
    assert '주식회사' in r['evidence']['legal_entity']


def test_person_with_contact_passes(ev):
    url = 'https://paperpilot.io'
    r = ev.verify_entity(url, fetcher=FakeFetcher({url: PERSON_HTML}))
    assert r['verdict'] == ev.PASS
    assert 'Jane Doe' in r['reason']


def test_contact_only_holds(ev):
    url = 'https://widgetly.app'
    r = ev.verify_entity(url, fetcher=FakeFetcher({url: CONTACT_ONLY_HTML}))
    assert r['verdict'] == ev.HOLD
    assert '연락처만' in r['reason']


def test_copyright_only_holds(ev):
    url = 'https://widgetly-studio.app'
    r = ev.verify_entity(url, fetcher=FakeFetcher({url: COPYRIGHT_ONLY_HTML}))
    assert r['verdict'] == ev.HOLD
    assert '저작권자' in r['reason']


def test_no_signal_holds(ev):
    """실체 stage 는 불통과를 만들지 않는다 — 확실한 근거 없이 게재를 내리지 않는다.

    2026-11-24 캘리브레이션: 본문 길이만으로 불통과가 된 4건(imagefx·ninjo.ai·
    oreate·jev-wrapped)이 전부 실제 서비스였다(오탐 4/8).
    """
    url = 'https://supertool.example-tool.com'
    r = ev.verify_entity(url, fetcher=FakeFetcher({url: NO_SIGNAL_HTML}))
    assert r['verdict'] == ev.HOLD
    assert '운영 주체 신호' in r['reason']


def test_js_shell_page_holds(ev):
    """서버 HTML 이 껍데기(텍스트 <60자)면 fail 이 아니라 hold — 판정 불가."""
    url = 'https://spa.example-tool.com'
    r = ev.verify_entity(url, fetcher=FakeFetcher({url: '<html><body><div id="root"></div><script>app()</script></body></html>'}))
    assert r['verdict'] == ev.HOLD
    assert '판정 불가' in r['reason']


def test_thin_policy_page_is_not_evidence(ev):
    """정책 페이지가 열려도 내용이 껍데기(<80자)면 증거로 쓰지 않는다."""
    url = 'https://thintool.example-tool.com'
    f = FakeFetcher({
        url: NO_SIGNAL_HTML,
        'https://thintool.example-tool.com/privacy': '<html><body>Privacy</body></html>',
    })
    r = ev.verify_entity(url, fetcher=f)
    assert r['verdict'] == ev.HOLD       # 실체 stage 는 불통과를 만들지 않는다
    assert '/privacy' not in r['evidence']['pages_checked']


def test_fixed_response_classification_of_20_fixtures(ev):
    """분류 함수가 픽스처 20건을 통과/불통과/보류 3분류로 정확히 나눈다(합계 일치)."""
    cases = [
        ('https://a1.com', LEGAL_HTML, ev.PASS),
        ('https://a2.com', LEGAL_HTML, ev.PASS),
        ('https://a3.com', PERSON_HTML, ev.PASS),
        ('https://a4.com', PERSON_HTML, ev.PASS),
        ('https://a5.com', LEGAL_HTML, ev.PASS),
        ('https://a6.com', CONTACT_ONLY_HTML, ev.HOLD),
        ('https://a7.com', CONTACT_ONLY_HTML, ev.HOLD),
        ('https://a8.com', COPYRIGHT_ONLY_HTML, ev.HOLD),
        ('https://a9.com', COPYRIGHT_ONLY_HTML, ev.HOLD),
        ('https://a10.com', CONTACT_ONLY_HTML, ev.HOLD),
        ('https://a11.com', NO_SIGNAL_HTML, ev.HOLD),
        ('https://a12.com', NO_SIGNAL_HTML, ev.HOLD),
        ('https://a13.com', PARKED_HTML, ev.FAIL),
        ('https://a14.com', NO_SIGNAL_HTML, ev.HOLD),
        ('https://a15.com', LEGAL_HTML, ev.PASS),
        ('https://a16.com', PERSON_HTML, ev.PASS),
        ('https://a17.com', NO_SIGNAL_HTML, ev.HOLD),
        ('https://a18.com', CONTACT_ONLY_HTML, ev.HOLD),
        ('https://a19.com', LEGAL_HTML, ev.PASS),
        ('https://a20.com', NO_SIGNAL_HTML, ev.HOLD),
    ]
    pages = {u: h for u, h, _ in cases}
    f = FakeFetcher(pages)
    got = [ev.verify_entity(u, fetcher=f)['verdict'] for u, _, _ in cases]
    assert got == [v for _, _, v in cases]
    assert len(got) == 20
    assert got.count(ev.PASS) + got.count(ev.FAIL) + got.count(ev.HOLD) == 20


# ══════════════════════════════════════════════════════════════════════
# 대체 경로 — 스토어 / GitHub
# ══════════════════════════════════════════════════════════════════════
def test_app_store_seller_passes(ev):
    url = 'https://apps.apple.com/app/id1234567890'
    html = '<html><body><dt>Seller</dt><dd>Morphiqo Labs, Inc.</dd></body></html>'
    r = ev.verify_entity(url, fetcher=FakeFetcher({url: html}))
    assert r['verdict'] == ev.PASS
    assert r['stage'] == 'store'
    assert 'Morphiqo Labs' in r['evidence']['seller']


def test_app_store_without_seller_holds(ev):
    url = 'https://apps.apple.com/app/id999'
    r = ev.verify_entity(url, fetcher=FakeFetcher({url: '<html><body>App</body></html>'}))
    assert r['verdict'] == ev.HOLD
    assert '판매자' in r['reason']


def test_play_store_developer_passes(ev):
    url = 'https://play.google.com/store/apps/details?id=com.acme.tool'
    html = '<html><body>Offered by <a href="/store/apps/dev?id=x">Acme Studio</a></body></html>'
    r = ev.verify_entity(url, fetcher=FakeFetcher({url: html}))
    assert r['verdict'] == ev.PASS
    assert r['evidence']['seller'] == 'Acme Studio'


def test_github_recent_activity_passes(ev):
    url = 'https://github.com/acme/pipeline'
    api = 'https://api.github.com/repos/acme/pipeline'
    payload = json.dumps({'pushed_at': '2026-11-01T10:00:00Z'})
    # now = 2026-11-24 (고정)
    now = 1795000000
    r = ev.verify_entity(url, fetcher=FakeFetcher({api: payload}), now=now)
    assert r['verdict'] == ev.PASS
    assert r['stage'] == 'github'


def test_github_stale_fails(ev):
    url = 'https://github.com/acme/oldpipeline'
    api = 'https://api.github.com/repos/acme/oldpipeline'
    payload = json.dumps({'pushed_at': '2022-01-01T10:00:00Z'})
    now = 1795000000
    r = ev.verify_entity(url, fetcher=FakeFetcher({api: payload}), now=now)
    assert r['verdict'] == ev.FAIL
    assert '최근 활동 없음' in r['reason']


def test_github_api_blocked_holds(ev):
    url = 'https://github.com/acme/tool'
    f = FakeFetcher({url: '<html><body>repo</body></html>'}, missing_status=403)
    r = ev.verify_entity(url, fetcher=f)
    assert r['verdict'] == ev.HOLD


# ══════════════════════════════════════════════════════════════════════
# 캐시
# ══════════════════════════════════════════════════════════════════════
def test_same_url_fetched_once(ev):
    ev.clear_cache()
    url = 'https://cached.example-tool.com'
    f = FakeFetcher({url: LEGAL_HTML})
    ev.verify_entity(url, fetcher=f)
    ev.verify_entity(url, fetcher=f)
    assert f.calls.count(url) == 1


# ══════════════════════════════════════════════════════════════════════
# 수집기 결선 — process_batch 가 LLM 호출 전에 거른다
# ══════════════════════════════════════════════════════════════════════
def test_process_batch_skips_fail_and_records_hold(tc, monkeypatch, tmp_path):
    hold_path = tmp_path / 'entity_hold.jsonl'
    monkeypatch.setattr(tc, 'ENTITY_HOLD_PATH', str(hold_path))
    monkeypatch.setattr(tc, 'get_existing_tool_names', lambda: (set(), set()))

    verdicts = {
        'pass-tool': {'verdict': 'pass', 'stage': 'entity', 'reason': '법인명 확인: Acme Inc',
                      'evidence': {'legal_entity': 'Acme Inc'}},
        'fail-tool': {'verdict': 'fail', 'stage': 'entity', 'reason': '운영 주체 신호 없음',
                      'evidence': {}},
        'hold-tool': {'verdict': 'hold', 'stage': 'entity', 'reason': '연락처만 있음',
                      'evidence': {}},
    }

    def fake_verify(url, **_kw):
        for key, val in verdicts.items():
            if key in url:
                return dict(val, url=url)
        return {'verdict': 'fail', 'stage': 'reachability', 'reason': 'URL 없음',
                'evidence': {}, 'url': url}

    monkeypatch.setattr(tc, 'verify_entity', fake_verify)

    llm_calls = []

    def fake_generate(tool_info):
        llm_calls.append(tool_info['name'])
        return None

    monkeypatch.setattr(tc, 'generate_metadata', fake_generate)

    tools = [
        {'name': 'PassTool', 'url': 'https://pass-tool.com', 'description': 'x'},
        {'name': 'FailTool', 'url': 'https://fail-tool.com', 'description': 'x'},
        {'name': 'HoldTool', 'url': 'https://hold-tool.com', 'description': 'x'},
    ]
    created = tc.process_batch(tools, batch_size=5, max_workers=1)

    # 불통과·보류는 LLM(비용) 단계로 가지 않는다
    assert llm_calls == ['PassTool']
    assert created == []
    held = [json.loads(line) for line in hold_path.read_text(encoding='utf-8').splitlines() if line]
    assert len(held) == 1
    assert held[0]['name'] == 'HoldTool'
    assert held[0]['verdict'] == 'hold'
    assert held[0]['reason'] == '연락처만 있음'


def test_filter_entities_summary_counts(tc, monkeypatch):
    def fake_verify(url, **_kw):
        verdict = {'https://ok.com': 'pass', 'https://no.com': 'fail'}.get(url, 'hold')
        return {'url': url, 'verdict': verdict, 'stage': 'entity', 'reason': verdict,
                'evidence': {}}

    monkeypatch.setattr(tc, 'verify_entity', fake_verify)
    tools = [{'name': 'A', 'url': 'https://ok.com'},
             {'name': 'B', 'url': 'https://no.com'},
             {'name': 'C', 'url': 'https://meh.com'}]
    kept, skipped = tc.filter_entities(tools, write_hold=False)
    assert [t['name'] for t in kept] == ['A']
    assert {s['name']: s['verdict'] for s in skipped} == {'B': 'fail', 'C': 'hold'}
