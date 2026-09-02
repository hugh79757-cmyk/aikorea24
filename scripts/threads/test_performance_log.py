#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""test_performance_log.py — Phase 38 성과 로그 단위 테스트 (네트워크 mock, 발행 무관)

실행: .venv/bin/python3 scripts/threads/test_performance_log.py
"""
import os
import sys
import json
import tempfile
import urllib.request
from datetime import datetime, timedelta
from unittest import mock

_here = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_here))
sys.path.insert(0, _project_root)
sys.path.insert(0, _here)

import performance_log as pl


def _fresh_env():
    """PERF_LOG/REPORT를 임시 파일로 리다이렉트."""
    tmpdir = tempfile.mkdtemp(prefix='perf_test_')
    pl.PERF_LOG = os.path.join(tmpdir, 'performance_log.json')
    pl.REPORT = os.path.join(tmpdir, 'insights_report.json')
    return tmpdir


def test_record_publish():
    _fresh_env()
    pl.record_publish('111', '2026-09-01T18:00:00', 'D', '47319', '테스트 제목', '네이버뉴스')
    pl.record_publish('222', '2026-09-01T20:00:00', 'D', '47400', '테스트 제목2', '블로터')
    data = pl._load()
    assert len(data['posts']) == 2, f'posts 2건 필요: {len(data["posts"])}'
    p = data['posts'][0]
    for field in ('root_id', 'posted_at', 'format', 'article_id', 'title', 'source', 'topic_tags', 'metrics'):
        assert field in p, f'스키마 필드 누락: {field}'
    assert p['metrics'] is None
    # 지속성: 재로드 후에도 유지
    data2 = pl._load()
    assert len(data2['posts']) == 2
    print('✅ test_record_publish: 2건 기록, 스키마 완비, 지속성 확인')


def _insights_response(views=311, likes=2, replies=5, reposts=0, quotes=0):
    body = {'data': [
        {'name': 'views', 'values': [{'value': views}]},
        {'name': 'likes', 'values': [{'value': likes}]},
        {'name': 'thread_replies', 'values': [{'value': replies}]},
        {'name': 'reposts', 'values': [{'value': reposts}]},
        {'name': 'quotes', 'values': [{'value': quotes}]},
    ]}
    return json.dumps(body).encode()


def test_collect_insights_net_replies():
    _fresh_env()
    pl.record_publish('111', datetime.now().isoformat(), 'D', '1', 't', 's')

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if '/insights' in url:
            return mock.MagicMock(name='resp', **{'read.return_value': _insights_response(),
                                                  '__enter__': lambda s: s,
                                                  '__exit__': lambda s, *a: False})
        if '/replies' in url:
            # root 직접 답글: 자기 링크 1 + 자기 카드2 1 + 외부 1 → net_replies=1
            # (insights replies=5는 체인 하위 자기 답글 포함 — 무시)
            body = json.dumps({'data': [
                {'id': 'x1', 'text': '🔗 https://aikorea24.kr/x', 'username': 'aikorea24'},
                {'id': 'x2', 'text': '카드2 본문', 'username': 'aikorea24'},
                {'id': 'x3', 'text': '외부 답글', 'username': 'someone'},
            ]}).encode()
            return mock.MagicMock(name='resp', **{'read.return_value': body,
                                                  '__enter__': lambda s: s,
                                                  '__exit__': lambda s, *a: False})
        raise AssertionError(f'unexpected url: {url}')

    with mock.patch.object(urllib.request, 'urlopen', fake_urlopen), \
         mock.patch('publisher.load_env', return_value={'THREADS_ACCESS_TOKEN': 'TOK', 'THREADS_USER_ID': 'U'}):
        n = pl.collect_insights(days=2)
    assert n == 1
    m = pl._load()['posts'][0]['metrics']
    # 기준선 모델: 외부(root 직접 답글 중 username≠aikorea24)만 카운트 → 1
    assert m['replies'] == 5 and m['net_replies'] == 1, f'net_replies 산출 실패: {m}'
    assert m['views'] == 311
    print('✅ test_collect_insights_net_replies: replies 5 → net_replies 1 (외부 직접 카운트)')


def test_collect_insights_error_continues():
    _fresh_env()
    pl.record_publish('111', datetime.now().isoformat(), 'D', '1', 't', 's')
    pl.record_publish('222', datetime.now().isoformat(), 'D', '2', 't2', 's2')

    calls = {'n': 0}
    def fake_urlopen(req, timeout=None):
        calls['n'] += 1
        if '/111/' in req.full_url:
            raise urllib.error.HTTPError(req.full_url, 500, 'boom', {}, None)
        return mock.MagicMock(name='resp', **{'read.return_value': _insights_response(views=194, likes=1, replies=0),
                                              '__enter__': lambda s: s,
                                              '__exit__': lambda s, *a: False})

    with mock.patch.object(urllib.request, 'urlopen', fake_urlopen), \
         mock.patch('publisher.load_env', return_value={'THREADS_ACCESS_TOKEN': 'TOK', 'THREADS_USER_ID': 'U'}):
        n = pl.collect_insights(days=2)
    assert n == 2
    posts = {p['root_id']: p['metrics'] for p in pl._load()['posts']}
    assert 'error' in posts['111'], f'실패 건에 error 기록 필요: {posts["111"]}'
    assert posts['222']['views'] == 194 and posts['222']['net_replies'] == 0
    print('✅ test_collect_insights_error_continues: error 기록 후 계속, 성공 건은 정상 수집')


def test_analyze_threshold():
    _fresh_env()
    # 29건 → report 없음
    for i in range(29):
        pl.record_publish(f'r{i}', (datetime.now() - timedelta(days=1)).isoformat(), 'D', str(i), f't{i}', 'src')
    data = pl._load()
    for p in data['posts']:
        p['metrics'] = {'views': 100, 'likes': 1, 'replies': 0, 'reposts': 0, 'quotes': 0, 'net_replies': 0}
    pl._atomic_save(data)
    assert pl.analyze() is None
    assert not os.path.exists(pl.REPORT), '29건에 report 생성되면 안 됨'

    # 30건 → report 생성
    pl.record_publish('r30', (datetime.now() - timedelta(days=1)).isoformat(), 'D', '30', 't30', 'src2')
    data = pl._load()
    data['posts'][-1]['metrics'] = {'views': 200, 'likes': 2, 'replies': 2, 'reposts': 0, 'quotes': 0, 'net_replies': 1}
    pl._atomic_save(data)
    report = pl.analyze()
    assert report is not None and os.path.exists(pl.REPORT)
    assert report['n_posts'] == 30
    assert report['by_format']['D']['n'] == 30
    assert report['by_source']['src']['n'] == 29 and report['by_source']['src2']['n'] == 1
    assert len(report['top_topics']) >= 1
    # by_source fallback: top_topic이 source명
    assert report['top_topics'][0]['topic'] in ('src', 'src2')
    print('✅ test_analyze_threshold: 29건 → 없음, 30건 → 생성 (by_source fallback 동작)')


def test_analyze_topic_tags():
    _fresh_env()
    for i in range(30):
        tags = ['반도체'] if i % 2 == 0 else ['로봇']
        pl.record_publish(f'r{i}', (datetime.now() - timedelta(days=1)).isoformat(), 'D', str(i), f't{i}', 's', topic_tags=tags)
    data = pl._load()
    for i, p in enumerate(data['posts']):
        p['metrics'] = {'views': 300 if i % 2 == 0 else 100, 'likes': 3, 'replies': 1, 'reposts': 0, 'quotes': 0, 'net_replies': 0}
    pl._atomic_save(data)
    report = pl.analyze()
    assert report['by_topic']['반도체']['avg_views'] == 300
    assert report['by_topic']['로봇']['avg_views'] == 100
    assert report['top_topics'][0]['topic'] == '반도체'
    print('✅ test_analyze_topic_tags: by_topic 집계 + top_topics 정렬 확인')


if __name__ == '__main__':
    test_record_publish()
    test_collect_insights_net_replies()
    test_collect_insights_error_continues()
    test_analyze_threshold()
    test_analyze_topic_tags()
    print('\n전체 통과: 5/5')
