#!/usr/bin/env python3
"""AIK24-PIPE-09 B-1/B-7 — 툴 수집기 가드 정책·상태 파일·알림 테스트 (D1·네트워크 0회)

배경 (2026-10-21 실측):
    같은 날 06:00 tools-collector 도 D1 가드로 죽었다 —
    scripts/tools_collector_error.log:447
    cfnew.QuotaExceededError: [D1-GUARD] 일일 읽기 4,113,239/5,000,000 (82.3%) — 작업 중단
    상태 파일도 알림도 없어 **조용히 죽었다**.

검증 대상: scripts/tools_collector.py
  · decide_collection_mode()   — 3구간 판정 (정상 / 축소 수집 / 중단)
  · select_reduced_sources()   — 축소 소스 집합이 전체의 strict subset 인지
  · apply_row_cap()            — 행 상한
  · write_tools_collector_state() — 상태 파일 스키마 + 원자적 쓰기
  · apply_guard()/ToolsCollectorReporter — 중단 시 알림 1회 · 알림 실패가 원본 예외를 가리지 않음
  · collect_tools(reduced=True) — 축소 모드가 실제로 핵심 소스만 부르고 상한을 적용하는지

주의: 실제 scripts/.tools_collector_state.json 은 절대 건드리지 않는다(전 테스트 tmp 격리).
      실제 네트워크·LLM·D1·Telegram·메일은 전부 스텁이다.
사용: pytest tests/test_pipe09_tools_collector_guard.py -q
"""
import importlib.util
import json
import os
import sys
from datetime import datetime

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECTOR_PATH = os.path.join(REPO_ROOT, 'scripts', 'tools_collector.py')

D1_LIMIT = 5_000_000

# 2026-10-21 실측 지점 — tools_collector_error.log:447
TODAY_USED = 4_113_239  # 82.3%


@pytest.fixture(scope='module')
def tc():
    """툴 수집기 모듈 로드 (경로 기반 import — scripts 는 패키지가 아니다)."""
    spec = importlib.util.spec_from_file_location('aik24_tools_collector', COLLECTOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _isolate(tc, tmp_path, monkeypatch):
    """① 상태 파일 경로 격리 — 실제 scripts/.tools_collector_state.json 은 절대 쓰지 않는다.
    ② 기본 알림 센더 스텁 — 실제 muse 발송이 나가지 않는다."""
    monkeypatch.setattr(tc, 'TOOLS_COLLECTOR_STATE_PATH',
                        str(tmp_path / '.tools_collector_state.json'))
    sent = []

    def stub(text):
        sent.append(text)
        return True

    monkeypatch.setattr(tc, '_default_alert_sender', stub)
    return sent


class _FakeCfnew:
    """cfnew 스텁 — check_quota 만 흉내 낸다(D1/GraphQL 호출 0회)."""

    class QuotaExceededError(RuntimeError):
        pass

    def __init__(self, used, limit=D1_LIMIT):
        self.used = used
        self.limit = limit
        self.calls = []

    def check_quota(self, threshold=0.8, tok=None, raise_on_exceed=True):
        self.calls.append({'threshold': threshold, 'raise_on_exceed': raise_on_exceed})
        return {'readonly': False, 'used': self.used, 'limit': self.limit,
                'pct': self.used / self.limit}


def _read_state(path):
    return json.loads(open(path, encoding='utf-8').read())


# ============================================================
# ① 소프트 미만 → 정상 수집
# ============================================================
def test_below_soft_is_normal(tc):
    """2026-10-21 실측 22.1%(1,106,085행) → 정상 수집."""
    d = tc.decide_collection_mode(1_106_085, D1_LIMIT)
    assert d['mode'] == 'normal'
    assert d['pct'] == pytest.approx(0.221217, abs=1e-5)
    assert '축소' not in d['reason']
    assert '정상 수집' in d['reason']


def test_soft_boundary_exactly_is_reduced(tc):
    """정확히 80%(4,000,000행)부터 축소 수집(기존 중단선 80%)."""
    assert tc.decide_collection_mode(4_000_000, D1_LIMIT)['mode'] == 'reduced'
    assert tc.decide_collection_mode(3_999_999, D1_LIMIT)['mode'] == 'normal'


def test_unknown_limit_is_fail_open(tc):
    """한도를 못 보면 수집을 죽이지 않는다(fail-open)."""
    assert tc.decide_collection_mode(0, 0)['mode'] == 'normal'


# ============================================================
# ② 소프트 이상·하드 미만 → 축소 수집
# ============================================================
def test_between_soft_and_hard_is_reduced(tc):
    """오늘 사고 지점 82.3%(4,113,239행) → 축소 수집(전면 중단 아님)."""
    d = tc.decide_collection_mode(TODAY_USED, D1_LIMIT)
    assert d['mode'] == 'reduced'
    assert '축소 수집' in d['reason']
    assert '소프트 한계' in d['reason']


def test_reduced_cost_breaching_hard_limit_aborts(tc):
    """축소 수집 비용까지 더하면 하드 한계를 넘는 경우 → 중단.

    하드 한계 = 95% × 5,000,000 = 4,750,000행 · 축소 수집 추정 비용 1,000행.
    """
    d = tc.decide_collection_mode(4_749_000, D1_LIMIT, reduced_read_cost=1_000)
    assert d['mode'] == 'abort'
    assert '축소 수집 비용' in d['reason']
    ok = tc.decide_collection_mode(4_748_000, D1_LIMIT, reduced_read_cost=1_000)
    assert ok['mode'] == 'reduced'


def test_reduced_sources_are_strict_subset(tc):
    """축소 소스 집합은 전체 소스의 strict subset 이고 순서를 유지한다."""
    assert set(tc.REDUCED_SOURCES) < set(tc.TOOL_SOURCES)
    assert 0 < len(tc.REDUCED_SOURCES) < len(tc.TOOL_SOURCES)
    # 지정한 핵심 소스가 실제 목록에 존재한다(없는 이름을 조용히 버리지 않는다)
    assert set(tc.REDUCED_SOURCES) <= set(tc.TOOL_SOURCES)


def test_reduced_sources_keep_the_two_daily_producers(tc):
    """실측 근거 — 매일 실질 기여한 2개 소스만 축소 세트에 남는다.

    2026-10-21 로그 19회 실행: Product Hunt 19/19회·2~9건, huggingface 19/19회·0~5건.
    futurepedia·topai.tools 는 19/19회 0건, theresanaiforthat 는 브라우저 미설치로
    17/19회 0건, GitHub Awesome 는 주 1회 전용이다.
    """
    assert 'Product Hunt' in tc.REDUCED_SOURCES
    assert 'huggingface' in tc.REDUCED_SOURCES
    for excluded in ('futurepedia', 'topai.tools', 'theresanaiforthat',
                     'GitHub Awesome AI Tools'):
        assert excluded not in tc.REDUCED_SOURCES


def test_select_reduced_sources_filters_and_keeps_order(tc):
    """select_reduced_sources — 핵심 소스만 남기고 원래 순서를 유지한다."""
    items = [
        {'name': 'a', 'source': 'Product Hunt'},
        {'name': 'b', 'source': 'futurepedia'},
        {'name': 'c', 'source': 'huggingface'},
        {'name': 'd', 'source': 'topai.tools'},
        {'name': 'e', 'source': 'Product Hunt'},
    ]
    reduced = tc.select_reduced_sources(items, tc.REDUCED_SOURCES)
    assert [t['name'] for t in reduced] == ['a', 'c', 'e']
    assert 0 < len(reduced) < len(items)


def test_row_cap_applies(tc):
    """행 상한 — 정상 1일 수집량(중앙값 6 · 평균 8.5 · 최대 20)보다 작다."""
    items = list(range(30))
    capped = tc.apply_row_cap(items, tc.REDUCED_ROW_CAP)
    assert len(capped) == tc.REDUCED_ROW_CAP
    assert capped == items[:tc.REDUCED_ROW_CAP]
    assert tc.REDUCED_ROW_CAP == 8
    assert tc.REDUCED_ROW_CAP < 20   # 로그 최대 수집량
    assert tc.REDUCED_ROW_CAP >= 6   # 로그 중앙값 수집량은 온전히 확보된다
    assert tc.apply_row_cap(items, 0) == []


# ============================================================
# ③ 하드 이상 → 전면 중단
# ============================================================
def test_at_or_above_hard_is_abort(tc):
    """95%(4,750,000행) 이상 → 전면 중단. cfnew.READONLY_RATIO 와 같은 선."""
    assert tc.decide_collection_mode(4_750_000, D1_LIMIT)['mode'] == 'abort'
    assert tc.decide_collection_mode(4_999_999, D1_LIMIT)['mode'] == 'abort'


def test_abort_raises_quota_exceeded_with_original_message_format(tc, tmp_path):
    """중단 시 예외 타입·메시지 형식은 기존과 동일(로그 원본이 가려지지 않는다)."""
    reporter = tc.ToolsCollectorReporter(state_path=str(tmp_path / '.tools_collector_state.json'))
    fake = _FakeCfnew(4_900_000)
    with pytest.raises(fake.QuotaExceededError) as ei:
        tc.apply_guard(fake, reporter)
    msg = str(ei.value)
    assert 'D1-GUARD' in msg
    assert '4,900,000/5,000,000' in msg
    assert '98.0%' in msg
    assert '작업 중단' in msg
    # check_quota 는 예외를 내지 않도록(raise_on_exceed=False) 호출되어 사용량을 먼저 읽는다
    assert fake.calls == [{'threshold': tc.TOOLS_SOFT_RATIO, 'raise_on_exceed': False}]


# ============================================================
# ④ 상태 파일 — 스키마 · 상태별 값 · 원자적 쓰기
# ============================================================
def test_state_file_schema(tc, tmp_path):
    """스키마: status · reason · at(ISO8601 KST) · collected."""
    path = tmp_path / '.tools_collector_state.json'
    payload = tc.write_tools_collector_state('reduced', 'D1 읽기 82.3% — 축소 수집', 5, path=str(path))
    assert set(payload) == {'status', 'reason', 'at', 'collected'}
    assert payload['status'] == 'reduced'
    assert payload['collected'] == 5
    on_disk = _read_state(path)
    assert on_disk == payload
    # at 은 ISO8601 + KST(+09:00)
    dt = datetime.fromisoformat(on_disk['at'])
    assert dt.utcoffset().total_seconds() == 9 * 3600


def test_state_file_written_for_each_status(tc, tmp_path):
    """상태별 status/reason/collected 가 정확히 기록된다."""
    path = tmp_path / '.tools_collector_state.json'
    cases = [
        ('ok', '정상 수집', 5, False),
        ('reduced', '소프트 한계 초과 — 축소 수집', 3, True),
        ('aborted', '하드 한계 초과 — 수집 중단', 0, True),
        ('error', 'RuntimeError:boom', 0, True),
    ]
    for status, reason, collected, _alert in cases:
        reporter = tc.ToolsCollectorReporter(state_path=str(path))
        reporter.report(status, reason, collected=collected, alert=_alert)
        st = _read_state(path)
        assert st['status'] == status
        assert st['collected'] == collected
        assert reason.split(':')[0] in st['reason']


def test_state_write_uses_atomic_replace(tc, tmp_path, monkeypatch):
    """원자적 교체 — 대상 파일은 os.replace 로만 바뀐다(교체 전까지 이전 내용 유지)."""
    path = tmp_path / '.tools_collector_state.json'
    path.write_text(json.dumps({'status': 'ok', 'reason': '이전 값', 'at': 'x', 'collected': 1},
                                ensure_ascii=False), encoding='utf-8')
    seen = {}
    real_replace = os.replace

    def spy(src, dst):
        seen['src'] = str(src)
        seen['dst'] = str(dst)
        seen['before'] = path.read_text(encoding='utf-8')  # 교체 직전 대상은 아직 이전 내용
        return real_replace(src, dst)

    monkeypatch.setattr(tc.os, 'replace', spy)
    tc.write_tools_collector_state('ok', '새 값', 2, path=str(path))
    assert seen['dst'] == str(path)
    assert seen['src'] == str(path) + '.tmp'
    assert '이전 값' in seen['before']
    assert _read_state(path)['reason'] == '새 값'
    # tmp 는 남지 않는다
    assert not (tmp_path / '.tools_collector_state.json.tmp').exists()


def test_state_write_failure_leaves_previous_file_intact(tc, tmp_path, monkeypatch):
    """쓰기 중 실패해도 기존 상태 파일은 손상되지 않는다(반만 쓰인 파일이 남지 않는다)."""
    path = tmp_path / '.tools_collector_state.json'
    path.write_text(json.dumps({'status': 'ok', 'reason': '이전 값', 'at': 'x', 'collected': 1},
                                ensure_ascii=False), encoding='utf-8')

    def boom(*a, **kw):
        raise OSError('디스크 오류')

    monkeypatch.setattr(tc.json, 'dump', boom)
    with pytest.raises(OSError):
        tc.write_tools_collector_state('ok', '새 값', 2, path=str(path))
    assert _read_state(path)['reason'] == '이전 값'
    assert not (tmp_path / '.tools_collector_state.json.tmp').exists()


def test_state_file_is_separate_from_news_collector(tc):
    """뉴스 수집기 상태 파일과 **다른 파일**을 쓴다 (07:00 파이프라인은 뉴스 것만 읽는다)."""
    assert tc.TOOLS_COLLECTOR_STATE_PATH.endswith('.tools_collector_state.json')
    assert 'collector_state.json' not in tc.TOOLS_COLLECTOR_STATE_PATH.replace(
        '.tools_collector_state.json', '')
    news_state = os.path.join(REPO_ROOT, 'scripts', '.collector_state.json')
    assert tc.TOOLS_COLLECTOR_STATE_PATH != news_state


# ============================================================
# ⑤ 알림 — 1회만 · 실패해도 원본 예외를 가리지 않음
# ============================================================
def test_alert_sent_exactly_once_on_abort(tc, tmp_path):
    """중단 시 알림은 정확히 1회."""
    sent = []
    path = tmp_path / '.tools_collector_state.json'
    reporter = tc.ToolsCollectorReporter(state_path=str(path), sender=lambda t: sent.append(t) or True)
    fake = _FakeCfnew(4_900_000)
    with pytest.raises(fake.QuotaExceededError):
        tc.apply_guard(fake, reporter)
    assert len(sent) == 1
    assert '중단' in sent[0]
    assert 'AIK24-PIPE-09' in sent[0]
    assert reporter.alert_attempts == 1
    # 상태 파일은 중단으로 기록된다
    st = _read_state(path)
    assert st['status'] == 'aborted' and st['collected'] == 0


def test_alert_failure_never_masks_original_error(tc, tmp_path):
    """알림 채널이 죽어도 원본 D1-GUARD 예외가 그대로 올라온다."""

    def boom(text):
        raise RuntimeError('muse 채널 장애')

    path = tmp_path / '.tools_collector_state.json'
    reporter = tc.ToolsCollectorReporter(state_path=str(path), sender=boom)
    fake = _FakeCfnew(4_900_000)
    with pytest.raises(fake.QuotaExceededError) as ei:
        tc.apply_guard(fake, reporter)
    assert 'muse 채널 장애' not in str(ei.value)
    assert 'D1-GUARD' in str(ei.value)
    assert reporter.alert_attempts == 1
    # 상태 파일은 알림 실패와 무관하게 기록된다
    assert _read_state(path)['status'] == 'aborted'


def test_main_alerts_once_and_keeps_aborted_status(tc, tmp_path, monkeypatch):
    """main() 경로 — 가드 중단 뒤 예외 핸들러가 status 를 덮어쓰지 않고 알림도 1회."""
    sent = []
    monkeypatch.setattr(tc, '_default_alert_sender', lambda t: sent.append(t) or True)
    fake = _FakeCfnew(4_900_000)
    monkeypatch.setitem(sys.modules, 'cfnew', fake)
    with pytest.raises(fake.QuotaExceededError):
        tc.main()
    assert len(sent) == 1
    st = _read_state(tc.TOOLS_COLLECTOR_STATE_PATH)
    assert st['status'] == 'aborted'
    assert st['collected'] == 0


def test_unexpected_exception_writes_error_state_and_alerts_once(tc, monkeypatch):
    """수집 중 예외 → status 'error' + 알림 1회, 원본 예외 재발."""
    sent = []
    monkeypatch.setattr(tc, '_default_alert_sender', lambda t: sent.append(t) or True)

    def boom(cfnew, reporter):
        raise RuntimeError('수집 중 예외')

    monkeypatch.setattr(tc, '_run', boom)
    with pytest.raises(RuntimeError, match='수집 중 예외'):
        tc.main()
    assert len(sent) == 1
    st = _read_state(tc.TOOLS_COLLECTOR_STATE_PATH)
    assert st['status'] == 'error'
    assert st['collected'] == 0
    assert 'RuntimeError' in st['reason']


def test_ok_run_writes_state_without_alert(tc, tmp_path):
    """정상 수집은 상태 파일만 남기고 알림은 보내지 않는다."""
    sent = []
    path = tmp_path / '.tools_collector_state.json'
    reporter = tc.ToolsCollectorReporter(state_path=str(path), sender=lambda t: sent.append(t) or True)
    reporter.report('ok', 'D1 읽기 22.1% — 정상 수집', collected=5, alert=False)
    assert sent == []
    assert reporter.alert_attempts == 0
    st = _read_state(path)
    assert st['status'] == 'ok' and st['collected'] == 5


def test_reduced_run_writes_reduced_state_and_alerts_once(tc, tmp_path):
    """축소 수집은 'reduced' 상태를 기록하고 1회 알린다."""
    sent = []
    path = tmp_path / '.tools_collector_state.json'
    reporter = tc.ToolsCollectorReporter(state_path=str(path), sender=lambda t: sent.append(t) or True)
    fake = _FakeCfnew(TODAY_USED)
    decision = tc.apply_guard(fake, reporter)
    assert decision['mode'] == 'reduced'
    reporter.report('reduced', decision['reason'], collected=3, alert=True)
    assert len(sent) == 1
    assert '축소 수집' in sent[0]
    st = _read_state(path)
    assert st['status'] == 'reduced' and st['collected'] == 3


# ============================================================
# 축소 수집 분기 통합 — 소스 선택 · 행 상한 (네트워크 0회)
# ============================================================
def _stub_sources(tc, monkeypatch):
    """6개 수집 소스를 전부 스텁으로 교체(네트워크 0회). 호출 소스를 기록한다."""
    calls = []

    def _mk(source, n):
        def _fn(*a, **kw):
            calls.append(source)
            return [{'name': f'{source}-{i}', 'description': '', 'url': f'https://x/{source}/{i}',
                     'source': source, 'price': '', 'pub_date': ''} for i in range(n)]
        return _fn

    monkeypatch.setattr(tc, 'fetch_product_hunt', _mk('Product Hunt', 6))
    monkeypatch.setattr(tc, 'fetch_github_awesome', _mk('GitHub Awesome AI Tools', 10))
    monkeypatch.setattr(tc, 'collect_futurepedia', _mk('futurepedia', 5))
    monkeypatch.setattr(tc, 'collect_huggingface_papers', _mk('huggingface', 5))
    monkeypatch.setattr(tc, 'collect_topai_tools', _mk('topai.tools', 5))
    monkeypatch.setattr(tc, 'collect_theresanaiforthat', _mk('theresanaiforthat', 5))
    monkeypatch.setattr(tc, 'should_run_github_today', lambda: True)
    return calls


def test_collect_tools_reduced_uses_only_core_sources(tc, monkeypatch):
    """축소 모드는 핵심 소스(Product Hunt·huggingface)만 부른다(네트워크 0회)."""
    calls = _stub_sources(tc, monkeypatch)
    tools = tc.collect_tools(limit_per_source=10, reduced=True)
    assert set(calls) == set(tc.REDUCED_SOURCES)
    assert 'futurepedia' not in calls
    assert 'topai.tools' not in calls
    assert 'theresanaiforthat' not in calls
    assert 'GitHub Awesome AI Tools' not in calls
    assert len(calls) < len(tc.TOOL_SOURCES)


def test_collect_tools_normal_uses_all_sources(tc, monkeypatch):
    """정상 모드는 기존과 동일 — 6개 소스를 모두 부른다(네트워크 0회)."""
    calls = _stub_sources(tc, monkeypatch)
    tc.collect_tools(limit_per_source=10, reduced=False)
    assert set(calls) == set(tc.TOOL_SOURCES)
    assert len(calls) == len(tc.TOOL_SOURCES)


def test_collect_tools_reduced_applies_row_cap(tc, monkeypatch):
    """축소 모드는 행 상한을 적용한다(LLM·후처리·배포 비용 통제)."""
    calls = _stub_sources(tc, monkeypatch)
    tools = tc.collect_tools(limit_per_source=10, reduced=True)
    assert len(tools) == tc.REDUCED_ROW_CAP
    # 상한 적용 후에도 핵심 소스만 남아 있다
    assert {t['source'] for t in tools} <= set(tc.REDUCED_SOURCES)


def test_collect_tools_normal_does_not_cap_rows(tc, monkeypatch):
    """정상 모드는 상한이 적용되지 않는다(기존 동작 유지)."""
    calls = _stub_sources(tc, monkeypatch)
    tools = tc.collect_tools(limit_per_source=10, reduced=False)
    assert len(tools) == 36  # 6+10+5+5+5+5
    assert len(tools) > tc.REDUCED_ROW_CAP


# ============================================================
# _run 통합 — 축소 분기가 실제로 전파되는지 (네트워크·LLM·배포 0회)
# ============================================================
def _stub_run_pipeline(tc, monkeypatch):
    """_run 의 외부 호출을 전부 스텁으로 교체(네트워크·LLM·MD 저장·git·배포 0회)."""
    seen = {}

    def fake_collect(limit_per_source=15, reduced=False):
        seen['reduced'] = reduced
        seen['limit_per_source'] = limit_per_source
        return [{'name': 'Tool A', 'description': '', 'url': 'https://x/a',
                 'source': 'Product Hunt', 'price': '', 'pub_date': ''}]

    def fake_process_batch(tools, batch_size=5, max_workers=3, translate=False):
        seen['processed'] = len(tools)
        return []  # 신규 생성 0건 → 후처리·git·배포·Telegram 블록을 건너뛴다

    monkeypatch.setattr(tc, 'collect_tools', fake_collect)
    monkeypatch.setattr(tc, 'process_batch', fake_process_batch)
    monkeypatch.setattr(tc.sys, 'argv', ['tools_collector.py', '--collect', '--batch', '10'])
    return seen


def test_run_reduced_branch_reaches_collect_tools_and_reports(tc, monkeypatch):
    """82.3% → 축소 수집이 실제로 전파되고 상태가 'reduced' 로 기록된다."""
    sent = []
    monkeypatch.setattr(tc, '_default_alert_sender', lambda t: sent.append(t) or True)
    fake = _FakeCfnew(TODAY_USED)
    monkeypatch.setitem(sys.modules, 'cfnew', fake)
    seen = _stub_run_pipeline(tc, monkeypatch)

    tc.main()

    assert seen['reduced'] is True
    st = _read_state(tc.TOOLS_COLLECTOR_STATE_PATH)
    assert st['status'] == 'reduced'
    assert '축소 수집' in st['reason']
    assert len(sent) == 1  # 축소 수집은 1회 알림


def test_run_normal_branch_reports_ok_without_alert(tc, monkeypatch):
    """22.1% → 정상 수집(축소 아님) + 상태 'ok' + 알림 없음."""
    sent = []
    monkeypatch.setattr(tc, '_default_alert_sender', lambda t: sent.append(t) or True)
    fake = _FakeCfnew(1_106_085)
    monkeypatch.setitem(sys.modules, 'cfnew', fake)
    seen = _stub_run_pipeline(tc, monkeypatch)

    tc.main()

    assert seen['reduced'] is False
    st = _read_state(tc.TOOLS_COLLECTOR_STATE_PATH)
    assert st['status'] == 'ok'
    assert sent == []  # 정상 수집은 알림을 보내지 않는다
