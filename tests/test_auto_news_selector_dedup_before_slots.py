"""tests/test_auto_news_selector_dedup_before_slots.py

AIK24-PIPE-DEDUP-01 회귀 테스트 — 슬롯 배정 전에 이미 브리핑된 기사를 빼야 한다.

2026-10-15 사고: LLM 평가 상위 4건이 전부 과거 브리핑된 모델 카드였고,
auto_briefing 이 그 뒤에 dedup 을 걸면서 슬롯이 0건이 됐다. 신선한 2건은
슬롯 밖으로 밀려나면서 그날 브리핑이 0건이었다.

AIK24-PIPE-03(2026-10-16) v3 슬롯: 무료 기회 1 → Zen 변경 → 점수순 일반 뉴스.
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import auto_news_selector as sel  # noqa: E402
import briefing_dedup  # noqa: E402

TODAY = datetime.now(sel.KST).strftime('%Y-%m-%d')
ZEN_SRC = 'OpenCode Zen'
NEWS_SRC = 'HuggingFace Blog'
NEWS_SRC2 = 'GitHub Blog'


def _art(nid, score, source, v2_tag=None):
    return {'id': nid, 'title': f'{source} {nid}', 'original_title': f'orig-{nid}',
            'source': source, 'pub_date': f'{TODAY} 10:00:00',
            'v2_tag': v2_tag or ('free-llm' if source == ZEN_SRC else 'opensource'),
            '_score': score, '_detail': '테스트'}


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """LLM 호출과 sleep, D1 조회를 전부 막는다."""
    monkeypatch.setattr(sel.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(sel, 'score_helpfulness', lambda art: art.get('_score', 0))


def _pool(monkeypatch, pool):
    counts = {t: 0 for t in sel.TAG_ORDER}
    counts['opportunity'] = sum(1 for a in pool if a['v2_tag'] == 'free-opportunity')
    counts['zen'] = sum(1 for a in pool if a['source'] == ZEN_SRC)
    for a in pool:
        counts[a['v2_tag']] = counts.get(a['v2_tag'], 0) + 1
    monkeypatch.setattr(sel, 'interleave_candidates', lambda limit: (pool, counts))


def _stub_dedup(monkeypatch, dupe_ids):
    monkeypatch.setattr(briefing_dedup, 'get_history_articles', lambda d1_query: [])
    # AIK24-PIPE-09: filter_duplicates 가 D1 층·local 층 양쪽에서
    # is_duplicate_article_strict 를 쓴다 → 더블도 두 공개 진입점을 함께 막는다.
    stub = lambda art, history: (True, 'exact_id') if art['id'] in dupe_ids else (False, None)
    monkeypatch.setattr(briefing_dedup, 'is_duplicate_article', stub)
    monkeypatch.setattr(briefing_dedup, 'is_duplicate_article_strict', stub)


def test_dupes_do_not_consume_slots(monkeypatch):
    """과거 브리핑분이 슬롯을 다 먹으면 신선한 기사가 밀린다 — 밀리면 안 된다."""
    pool = ([_art(f'd{i}', s, ZEN_SRC) for i, s in zip((1, 2, 3, 4), (14, 12, 11, 11))]
            + [_art('n0', 10, NEWS_SRC), _art('n1', 9, NEWS_SRC2)])
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch, {'d1', 'd2', 'd3', 'd4'})

    assert [a['id'] for a in sel.main()] == ['n0', 'n1']


def test_all_duplicates_yields_empty(monkeypatch):
    """전부 중복이면 조용히 빈 리스트(브리핑 0건) — 예외를 던지지 않는다."""
    pool = [_art(f'd{i}', s, ZEN_SRC) for i, s in zip((1, 2, 3, 4), (14, 12, 11, 11))]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch, {'d1', 'd2', 'd3', 'd4'})

    assert sel.main() == []


def test_history_query_failure_fails_open(monkeypatch):
    """D1 조회가 빈 리스트를 주면(fail-open) 이전처럼 통과시켜 브리핑을 막지 않는다."""
    pool = [_art('n1', 10, NEWS_SRC), _art('n2', 9, NEWS_SRC2)]
    _pool(monkeypatch, pool)
    monkeypatch.setattr(briefing_dedup, 'get_history_articles', lambda d1_query: None)
    monkeypatch.setattr(briefing_dedup, 'is_duplicate_article', lambda art, h: (False, None))

    assert len(sel.main()) == 2


# ---------------------------------------------------------------- v3 (PIPE-03)


def test_opportunity_gets_first_slot(monkeypatch):
    """슬롯 1 은 무료 기회 — 점수와 무관하게 맨 앞."""
    pool = [_art('g1', 14, NEWS_SRC), _art('g2', 12, NEWS_SRC2),
            _art('o1', 0, '무료 기회', v2_tag='free-opportunity')]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch, set())

    assert [a['id'] for a in sel.main()][0] == 'o1'


def test_zen_change_beats_higher_scored_news(monkeypatch):
    """Zen 목록 변경은 LLM 점수와 무관하게 일반 뉴스보다 먼저 슬롯을 받는다."""
    pool = [_art('g1', 15, NEWS_SRC), _art('z1', None, ZEN_SRC),
            _art('g2', 14, NEWS_SRC2)]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch, set())

    picked = [a['id'] for a in sel.main()]
    assert picked[:2] == ['z1', 'g1'], picked


def test_third_slot_is_score_order_and_no_padding(monkeypatch):
    """일반 슬롯은 점수순, 후보가 모자라면 있는 만큼만 (물타기 금지)."""
    pool = [_art('g1', 9, NEWS_SRC), _art('g2', 12, NEWS_SRC2)]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch, set())

    assert [a['id'] for a in sel.main()] == ['g2', 'g1']
    assert sel.MAX_COUNT == 3


def test_mechanical_rows_skip_llm_scoring(monkeypatch):
    """기계 감지 행(Zen 변경·무료 기회)은 LLM 평가를 태우지 않는다."""
    calls = []

    def _score(art):
        calls.append(art['id'])
        return art.get('_score') or 0

    monkeypatch.setattr(sel.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(sel, 'score_helpfulness', _score)
    pool = [_art('z1', None, ZEN_SRC), _art('o1', 0, '무료 기회', v2_tag='free-opportunity'),
            _art('g1', 11, NEWS_SRC)]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch, set())

    sel.main()
    assert calls == ['g1']


# ------------------------------------------- 슬롯 1 소진 (2026-10-16 2차 개편)
# 배경: 큐레이션 8건은 pub_date 가 동일하고, 3.5단계 dedup 히스토리는 최근 3일만 본다.
# 슬롯 후보를 LIMIT 3 으로 뽑으면 4일째 슬롯이 비고 1일차 항목이 창을 벗어나 재등장한다
# (4~8번째 영구 미노출). 그래서 쿼리 자체가 브리핑 이력으로 제외한다.


def test_opportunity_query_excludes_briefed_rows(monkeypatch):
    """슬롯 1 쿼리는 브리핑 이력(briefing_items)으로 제외 + pub_date 동률 시 id 오름차순."""
    captured = {}

    def _fake_d1(sql):
        captured['sql'] = sql
        return []

    monkeypatch.setattr(sel, 'd1_query', _fake_d1)
    sel.get_opportunity_news(3)
    sql = captured['sql']

    assert 'id NOT IN (' in sql and 'briefing_items' in sql and 'JOIN briefings' in sql
    assert "b.status IN ('published', 'superseded')" in sql
    assert 'ORDER BY pub_date DESC, id ASC' in sql  # 동률 소진 순서 결정적
    assert 'LIMIT 3' in sql
    assert sel._opportunity_cutoff() in sql  # 21일 창 (7일이면 8건이 소진되기 전에 만료)


def test_opportunity_window_is_21_days_but_zen_stays_7():
    """슬롯 1 은 21일, Zen 은 7일 — 두 창의 차이는 정확히 14일."""
    fmt = '%Y-%m-%d %H:%M:%S'
    zen = datetime.strptime(sel._slot_cutoff(), fmt)
    opp = datetime.strptime(sel._opportunity_cutoff(), fmt)
    assert (zen - opp).days == 14


def test_opportunity_slot_drains_queue_one_per_day(monkeypatch):
    """제외가 SQL 로 끝나므로 슬롯은 매일 '아직 안 실린 가장 최신 1건'을 뽑는다.

    day1 → o1, day2(o1 이 SQL 로 제외돼 pool 에 없음) → o2, day3 → o3.
    """
    def _run(pool_ids):
        pool = [_art(i, 0, '무료 기회', v2_tag='free-opportunity') for i in pool_ids]
        _pool(monkeypatch, pool)
        _stub_dedup(monkeypatch, set())
        picked = sel.main()
        return picked[0]['id'] if picked else None

    assert _run(['o1', 'o2', 'o3']) == 'o1'
    assert _run(['o2', 'o3']) == 'o2'
    assert _run(['o3']) == 'o3'
    assert _run([]) is None  # 큐 소진 → 슬롯 비움 (강제 충전 금지)
