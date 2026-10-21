#!/usr/bin/env python3
"""AIK24-PIPE-08 B-1/B-7 — 수집기 가드 정책·상태 파일·알림 테스트 (D1·네트워크 0회)

검증 대상: api_test/news_collector.py
  · decide_collection_mode()  — 3구간 판정 (정상 / 축소 수집 / 중단)
  · select_reduced_sources()  — 축소 소스 집합이 전체의 strict subset 인지
  · apply_row_cap()/split_row_cap() — 행 상한
  · write_collector_state()   — 상태 파일 스키마 + 원자적 쓰기
  · apply_guard()/CollectorReporter — 중단 시 알림 1회 · 알림 실패가 원본 예외를 가리지 않음

주의: 실제 scripts/.collector_state.json 은 절대 건드리지 않는다(전 테스트 tmp 격리).
사용: pytest tests/test_collector_guard_policy.py -q
"""
import importlib.util
import json
import os
from datetime import datetime

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECTOR_PATH = os.path.join(REPO_ROOT, 'api_test', 'news_collector.py')

D1_LIMIT = 5_000_000


@pytest.fixture(scope='module')
def nc():
    """수집기 모듈 로드 (경로 기반 import — api_test 는 패키지가 아니다)."""
    spec = importlib.util.spec_from_file_location('aik24_news_collector', COLLECTOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _isolate(nc, tmp_path, monkeypatch):
    """① 상태 파일 경로 격리 — 실제 scripts/.collector_state.json 은 절대 쓰지 않는다.
    ② 기본 알림 센더 스텁 — 실제 muse 발송이 나가지 않는다(테스트 중 Telegram/메일도 없음)."""
    monkeypatch.setattr(nc, 'COLLECTOR_STATE_PATH', str(tmp_path / '.collector_state.json'))
    sent = []

    def stub(text):
        sent.append(text)
        return True

    monkeypatch.setattr(nc, '_default_alert_sender', stub)
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


# ============================================================
# ① 소프트 미만 → 정상 수집
# ============================================================
def test_below_soft_is_normal(nc):
    """2026-10-21 실측 22.1%(1,106,085행) → 정상 수집."""
    d = nc.decide_collection_mode(1_106_085, D1_LIMIT)
    assert d['mode'] == 'normal'
    assert d['pct'] == pytest.approx(0.221217, abs=1e-5)
    assert '축소' not in d['reason']
    assert '정상 수집' in d['reason']


def test_soft_boundary_exactly_is_reduced(nc):
    """정확히 80%(4,000,000행)부터 축소 수집(기존 중단선)."""
    assert nc.decide_collection_mode(4_000_000, D1_LIMIT)['mode'] == 'reduced'
    assert nc.decide_collection_mode(3_999_999, D1_LIMIT)['mode'] == 'normal'


def test_unknown_limit_is_fail_open(nc):
    """한도를 못 보면 수집을 죽이지 않는다(fail-open)."""
    assert nc.decide_collection_mode(0, 0)['mode'] == 'normal'


# ============================================================
# ② 소프트 이상·하드 미만 → 축소 수집
# ============================================================
def test_between_soft_and_hard_is_reduced(nc):
    """오늘 사고 지점 82.1%(4,107,355행) → 축소 수집(전면 중단 아님)."""
    d = nc.decide_collection_mode(4_107_355, D1_LIMIT)
    assert d['mode'] == 'reduced'
    assert '축소 수집' in d['reason']
    assert '소프트 한계' in d['reason']


def test_reduced_cost_breaching_hard_limit_aborts(nc):
    """축소 수집 비용까지 더하면 하드 한계를 넘는 경우 → 중단(축소 수집은 하드 한계를 존중)."""
    d = nc.decide_collection_mode(4_740_000, D1_LIMIT, reduced_read_cost=15_000)
    assert d['mode'] == 'abort'
    assert '축소 수집 비용' in d['reason']
    # 하드 한계 직전까지는 축소 수집 가능
    ok = nc.decide_collection_mode(4_730_000, D1_LIMIT, reduced_read_cost=15_000)
    assert ok['mode'] == 'reduced'


def test_reduced_sources_are_strict_subset(nc):
    """축소 소스 집합은 전체 소스의 strict subset 이고 순서를 유지한다."""
    for full, core in ((nc.GLOBAL_RSS_FEEDS, nc.REDUCED_GLOBAL_SOURCES),
                       (nc.KR_RSS_FEEDS, nc.REDUCED_KR_SOURCES)):
        reduced = nc.select_reduced_sources(full, core)
        assert 0 < len(reduced) < len(full), '축소 집합은 비어 있지도 전체와 같지도 않다'
        assert set(reduced).issubset(set(full))
        # 지정한 핵심 소스가 실제 목록에 존재한다(없는 이름을 조용히 버리지 않는다)
        assert set(core) <= {f[1] for f in full}
        # 원래 순서 유지
        assert reduced == [f for f in full if f[1] in set(core)]


def test_row_cap_applies(nc):
    """행 상한 — 정상 1일(≈130건)보다 크게 낮고, 해외/국내 반씩 나눈다."""
    items = list(range(200))
    capped = nc.apply_row_cap(items, nc.REDUCED_ROW_CAP)
    assert len(capped) == nc.REDUCED_ROW_CAP
    assert capped == items[:nc.REDUCED_ROW_CAP]
    assert nc.REDUCED_ROW_CAP < 130
    g, k = nc.split_row_cap(nc.REDUCED_ROW_CAP)
    assert g + k == nc.REDUCED_ROW_CAP


def test_collect_global_reduced_uses_only_core_sources(nc, monkeypatch):
    """축소 모드는 핵심 소스만 부르고 Hacker News 는 제외한다(네트워크 0회)."""
    calls = []
    monkeypatch.setattr(nc, 'fetch_rss_global',
                        lambda url, name, country='us', limit=12, filter_fn=None: calls.append(name) or [])
    monkeypatch.setattr(nc, 'fetch_hackernews_ai',
                        lambda limit=15: calls.append('HackerNews') or [])

    nc.collect_global(reduced=True)
    assert set(calls) == set(nc.REDUCED_GLOBAL_SOURCES)
    assert 'HackerNews' not in calls
    assert len(calls) < len(nc.GLOBAL_RSS_FEEDS)

    calls.clear()
    nc.collect_global(reduced=False)
    assert len(calls) == len(nc.GLOBAL_RSS_FEEDS) + 1  # 전체 소스 + HackerNews (기존 동작)


def test_collect_kr_reduced_uses_only_core_sources(nc, monkeypatch):
    """축소 모드는 국내 핵심 RSS 만 — 네이버·정부 소스는 제외(네트워크 0회)."""
    calls = []
    monkeypatch.setattr(nc, 'fetch_rss_kr', lambda url, source, limit=15: calls.append(source) or [])
    monkeypatch.setattr(nc, 'fetch_naver', lambda q, display=5: calls.append('naver') or [])

    nc.collect_kr(reduced=True)
    assert set(calls) == set(nc.REDUCED_KR_SOURCES)
    assert 'naver' not in calls
    assert len(calls) < len(nc.KR_RSS_FEEDS)


# ============================================================
# ③ 하드 이상 → 전면 중단
# ============================================================
def test_at_or_above_hard_is_abort(nc):
    """95%(4,750,000행) 이상 → 전면 중단. cfnew.READONLY_RATIO 와 같은 선."""
    assert nc.decide_collection_mode(4_750_000, D1_LIMIT)['mode'] == 'abort'
    assert nc.decide_collection_mode(4_999_999, D1_LIMIT)['mode'] == 'abort'
    # 하드 한계 직전이라도 '축소 수집 비용' 이 한계를 넘기면 중단이다
    assert nc.decide_collection_mode(4_734_999, D1_LIMIT)['mode'] == 'reduced'
    assert nc.decide_collection_mode(4_735_000, D1_LIMIT)['mode'] == 'abort'


def test_abort_raises_quota_exceeded_with_original_message_format(nc, tmp_path):
    """중단 시 예외类型·메시지 형식은 기존과 동일(로그 원본이 가려지지 않는다)."""
    reporter = nc.CollectorReporter(state_path=str(tmp_path / '.collector_state.json'))
    fake = _FakeCfnew(4_900_000)
    with pytest.raises(fake.QuotaExceededError) as ei:
        nc.apply_guard(fake, reporter)
    msg = str(ei.value)
    assert 'D1-GUARD' in msg
    assert '4,900,000/5,000,000' in msg
    assert '98.0%' in msg
    assert '작업 중단' in msg
    # check_quota 는 예외를 내지 않도록(raise_on_exceed=False) 호출되어 사용량을 먼저 읽는다
    assert fake.calls == [{'threshold': nc.COLLECTOR_SOFT_RATIO, 'raise_on_exceed': False}]


# ============================================================
# ④ 상태 파일 — 스키마 · 상태별 값 · 원자적 쓰기
# ============================================================
def _read_state(path):
    return json.loads(open(path, encoding='utf-8').read())


def test_state_file_schema(nc, tmp_path):
    """스키마: status · reason · at(ISO8601 KST) · collected."""
    path = tmp_path / '.collector_state.json'
    payload = nc.write_collector_state('reduced', 'D1 읽기 82.1% — 축소 수집', 17, path=str(path))
    assert set(payload) == {'status', 'reason', 'at', 'collected'}
    assert payload['status'] == 'reduced'
    assert payload['collected'] == 17
    on_disk = _read_state(path)
    assert on_disk == payload
    # at 은 ISO8601 + KST(+09:00)
    dt = datetime.fromisoformat(on_disk['at'])
    assert dt.utcoffset().total_seconds() == 9 * 3600


def test_state_file_written_for_each_status(nc, tmp_path):
    """상태별 status/reason/collected 가 정확히 기록된다."""
    path = tmp_path / '.collector_state.json'
    # reporter 는 첫 보고만 반영한다(런당 1회) — 상태별로 새 reporter 를 쓴다.
    cases = [
        ('ok', '정상 수집', 130, False),
        ('reduced', '소프트 한계 초과 — 축소 수집', 28, True),
        ('aborted', '하드 한계 초과 — 수집 중단', 0, True),
        ('error', 'RuntimeError:boom', 0, True),
    ]
    for status, reason, collected, _alert in cases:
        reporter = nc.CollectorReporter(state_path=str(path))
        reporter.report(status, reason, collected=collected, alert=_alert)
        st = _read_state(path)
        assert st['status'] == status
        assert st['collected'] == collected
        assert reason.split(':')[0] in st['reason']


def test_state_write_uses_atomic_replace(nc, tmp_path, monkeypatch):
    """원자적 교체 — 대상 파일은 os.replace 로만 바뀐다(교체 전까지 이전 내용 유지)."""
    path = tmp_path / '.collector_state.json'
    path.write_text(json.dumps({'status': 'ok', 'reason': '이전 값', 'at': 'x', 'collected': 1},
                                ensure_ascii=False), encoding='utf-8')
    seen = {}
    real_replace = os.replace

    def spy(src, dst):
        seen['src'] = str(src)
        seen['dst'] = str(dst)
        seen['before'] = path.read_text(encoding='utf-8')  # 교체 직전 대상은 아직 이전 내용
        return real_replace(src, dst)

    monkeypatch.setattr(nc.os, 'replace', spy)
    nc.write_collector_state('ok', '새 값', 2, path=str(path))
    assert seen['dst'] == str(path)
    assert seen['src'] == str(path) + '.tmp'
    assert '이전 값' in seen['before']
    assert _read_state(path)['reason'] == '새 값'
    # tmp 는 남지 않는다
    assert not (tmp_path / '.collector_state.json.tmp').exists()


def test_state_write_failure_leaves_previous_file_intact(nc, tmp_path, monkeypatch):
    """쓰기 중 실패해도 기존 상태 파일은 손상되지 않는다(반만 쓰인 파일이 남지 않는다)."""
    path = tmp_path / '.collector_state.json'
    path.write_text(json.dumps({'status': 'ok', 'reason': '이전 값', 'at': 'x', 'collected': 1},
                                ensure_ascii=False), encoding='utf-8')

    def boom(*a, **kw):
        raise OSError('디스크 오류')

    monkeypatch.setattr(nc.json, 'dump', boom)
    with pytest.raises(OSError):
        nc.write_collector_state('ok', '새 값', 2, path=str(path))
    assert _read_state(path)['reason'] == '이전 값'
    assert not (tmp_path / '.collector_state.json.tmp').exists()


# ============================================================
# ⑤ 알림 — 1회만 · 실패해도 원본 예외를 가리지 않음
# ============================================================
def test_alert_sent_exactly_once_on_abort(nc, tmp_path):
    """중단 시 알림은 정확히 1회."""
    sent = []
    path = tmp_path / '.collector_state.json'
    reporter = nc.CollectorReporter(state_path=str(path), sender=lambda t: sent.append(t) or True)
    fake = _FakeCfnew(4_900_000)
    with pytest.raises(fake.QuotaExceededError):
        nc.apply_guard(fake, reporter)
    assert len(sent) == 1
    assert '중단' in sent[0]
    assert reporter.alert_attempts == 1
    # 상태 파일은 중단으로 기록된다
    st = _read_state(path)
    assert st['status'] == 'aborted' and st['collected'] == 0


def test_alert_failure_never_masks_original_error(nc, tmp_path):
    """알림 채널이 죽어도 원본 D1-GUARD 예외가 그대로 올라온다."""

    def boom(text):
        raise RuntimeError('muse 채널 장애')

    path = tmp_path / '.collector_state.json'
    reporter = nc.CollectorReporter(state_path=str(path), sender=boom)
    fake = _FakeCfnew(4_900_000)
    with pytest.raises(fake.QuotaExceededError) as ei:
        nc.apply_guard(fake, reporter)
    assert 'muse 채널 장애' not in str(ei.value)
    assert 'D1-GUARD' in str(ei.value)
    assert reporter.alert_attempts == 1
    # 상태 파일은 알림 실패와 무관하게 기록된다
    assert _read_state(path)['status'] == 'aborted'


def test_main_alerts_once_and_keeps_aborted_status(nc, tmp_path, monkeypatch):
    """main() 경로 — 가드 중단 뒤 예외 핸들러가 status 를 덮어쓰지 않고 알림도 1회."""
    sent = []
    monkeypatch.setattr(nc, '_default_alert_sender', lambda t: sent.append(t) or True)
    fake = _FakeCfnew(4_900_000)
    monkeypatch.setattr(nc, '_collect',
                        lambda cfnew, reporter: nc.apply_guard(fake, reporter))
    with pytest.raises(fake.QuotaExceededError):
        nc.main()
    assert len(sent) == 1
    st = _read_state(nc.COLLECTOR_STATE_PATH)
    assert st['status'] == 'aborted'
    assert st['collected'] == 0


def test_unexpected_exception_writes_error_state_and_alerts_once(nc, monkeypatch):
    """수집 중 예외 → status 'error' + 알림 1회, 원본 예외 재발."""
    sent = []
    monkeypatch.setattr(nc, '_default_alert_sender', lambda t: sent.append(t) or True)

    def boom(cfnew, reporter):
        raise RuntimeError('수집 중 예외')

    monkeypatch.setattr(nc, '_collect', boom)
    with pytest.raises(RuntimeError, match='수집 중 예외'):
        nc.main()
    assert len(sent) == 1
    st = _read_state(nc.COLLECTOR_STATE_PATH)
    assert st['status'] == 'error'
    assert st['collected'] == 0
    assert 'RuntimeError' in st['reason']


def test_ok_run_writes_state_without_alert(nc, tmp_path):
    """정상 수집은 상태 파일만 남기고 알림은 보내지 않는다."""
    sent = []
    path = tmp_path / '.collector_state.json'
    reporter = nc.CollectorReporter(state_path=str(path), sender=lambda t: sent.append(t) or True)
    reporter.report('ok', 'D1 읽기 22.1% — 정상 수집', collected=130, alert=False)
    assert sent == []
    assert reporter.alert_attempts == 0
    st = _read_state(path)
    assert st['status'] == 'ok' and st['collected'] == 130


# ============================================================
# 축소 수집 분기 통합 — 행 상한이 실제로 적용되는지 (D1·네트워크 0회)
# ============================================================
def _fake_items(prefix, n):
    return [{'title': f'{prefix}{i}', 'link': f'{prefix.lower()}{i}', 'description': '',
             'source': 'S', 'category': 'global', 'pub_date': '', 'country': 'us',
             'original_title': f'{prefix}{i}'} for i in range(n)]


def _stub_collect_pipeline(nc, monkeypatch):
    """_collect 의 외부 호출을 전부 스텁으로 교체(D1·네트워크·LLM 0회)."""
    monkeypatch.setattr(nc.sys, 'argv', ['news_collector.py'])  # argparse 가 pytest 인자를 먹지 않게
    monkeypatch.setattr(nc, 'collect_global', lambda reduced=False: _fake_items('G', 40))
    monkeypatch.setattr(nc, 'collect_kr', lambda reduced=False: _fake_items('K', 40))
    monkeypatch.setattr(nc, 'dedup_similar', lambda items: list(items))
    monkeypatch.setattr(nc, 'batch_translate', lambda items: items)
    monkeypatch.setattr(nc, 'index_new_to_vectorize', lambda: None)
    monkeypatch.setattr(nc, 'purge_cloudflare_cache', lambda: None)
    monkeypatch.setattr(nc, 'parse_model_card_saved', lambda out: 0)
    monkeypatch.setattr(nc.subprocess, 'run', lambda *a, **k: type(
        'R', (), {'stdout': '', 'stderr': '', 'returncode': 0})())
    saved = {}

    def fake_save(items):
        saved['items'] = list(items)
        return len(saved['items']), 0

    monkeypatch.setattr(nc, 'save_to_d1', fake_save)
    return saved


def test_reduced_branch_caps_saved_rows(nc, tmp_path, monkeypatch):
    """축소 수집 분기 — 저장 행이 상한(30) 이하로 제한되고 상태가 'reduced' 로 기록된다."""
    sent = []
    path = tmp_path / '.collector_state.json'
    reporter = nc.CollectorReporter(state_path=str(path), sender=lambda t: sent.append(t) or True)
    saved = _stub_collect_pipeline(nc, monkeypatch)

    fake = _FakeCfnew(4_107_355)  # 82.1% → 축소 수집
    nc._collect(fake, reporter)

    assert len(saved['items']) == nc.REDUCED_ROW_CAP
    st = _read_state(path)
    assert st['status'] == 'reduced'
    assert st['collected'] == nc.REDUCED_ROW_CAP
    assert '축소' in st['reason']
    assert len(sent) == 1  # 축소 수집은 1회 알림


def test_normal_branch_keeps_all_rows(nc, tmp_path, monkeypatch):
    """정상 수집 분기 — 상한이 적용되지 않는다(기존 동작 유지)."""
    path = tmp_path / '.collector_state.json'
    reporter = nc.CollectorReporter(state_path=str(path))
    saved = _stub_collect_pipeline(nc, monkeypatch)

    fake = _FakeCfnew(1_106_085)  # 22.1% → 정상 수집
    nc._collect(fake, reporter)

    assert len(saved['items']) == 80  # 해외 40 + 국내 40 (기존과 동일)
    st = _read_state(path)
    assert st['status'] == 'ok'
    assert st['collected'] == 80
