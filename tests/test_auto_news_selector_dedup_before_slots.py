"""tests/test_auto_news_selector_dedup_before_slots.py

AIK24-PIPE-DEDUP-01 회귀 테스트 — 슬롯 배정 전에 이미 브리핑된 기사를 빼야 한다.

2026-10-15 사고: LLM 평가 상위 4건이 전부 과거 브리핑된 모델 카드였고,
auto_briefing 이 그 뒤에 dedup 을 걸면서 슬롯이 0건이 됐다. 신선한 2건은
슬롯 밖으로 밀려나면서 그날 브리핑이 0건이었다.
"""
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import auto_news_selector as sel  # noqa: E402
import briefing_dedup  # noqa: E402

TODAY = datetime.now(sel.KST).strftime('%Y-%m-%d')
MODEL_SRC = sel.MODEL_SOURCES[0]
NEWS_SRC = 'HuggingFace Blog'


def _art(nid, score, source):
    return {'id': nid, 'title': f'{source} {nid}', 'original_title': f'orig-{nid}',
            'source': source, 'pub_date': f'{TODAY} 10:00:00', 'v2_tag': 'free-llm' if source == MODEL_SRC else 'opensource',
            '_score': score, '_detail': '테스트'}


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """LLM 호출과 sleep, D1 조회를 전부 막는다."""
    monkeypatch.setattr(sel.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(sel, 'score_helpfulness', lambda art: art.get('_score', 0))


def _pool(monkeypatch, pool):
    counts = {t: 0 for t in sel.TAG_ORDER}
    for a in pool:
        counts[a['v2_tag']] += 1
    monkeypatch.setattr(sel, 'interleave_candidates', lambda limit: (pool, counts))


def _stub_dedup(monkeypatch, dupe_ids):
    monkeypatch.setattr(briefing_dedup, 'get_history_articles', lambda d1_query: [])
    monkeypatch.setattr(
        briefing_dedup, 'is_duplicate_article',
        lambda art, history: (True, 'exact_id') if art['id'] in dupe_ids else (False, None))


def test_dupes_do_not_consume_slots(monkeypatch):
    """과거 브리핑분이 슬롯을 다 먹으면 신선한 기사가 밀린다 — 밀리면 안 된다."""
    pool = ([_art(f'd{i}', s, MODEL_SRC) for i, s in zip((1, 2, 3, 4), (14, 12, 11, 11))]
            + [_art(f'n{i}', s, sel.MODEL_SOURCES[i]) for i, s in zip((0, 1), (10, 9))])
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch, {'d1', 'd2', 'd3', 'd4'})

    assert [a['id'] for a in sel.main()] == ['n0', 'n1']


def test_all_duplicates_yields_empty(monkeypatch):
    """전부 중복이면 조용히 빈 리스트(브리핑 0건) — 예외를 던지지 않는다."""
    pool = [_art(f'd{i}', s, MODEL_SRC) for i, s in zip((1, 2, 3, 4), (14, 12, 11, 11))]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch, {'d1', 'd2', 'd3', 'd4'})

    assert sel.main() == []


def test_history_query_failure_fails_open(monkeypatch):
    """D1 조회가 빈 리스트를 주면(fail-open) 이전처럼 통과시켜 브리핑을 막지 않는다."""
    pool = [_art('n1', 10, sel.MODEL_SOURCES[0]), _art('n2', 9, sel.MODEL_SOURCES[1])]
    _pool(monkeypatch, pool)
    monkeypatch.setattr(briefing_dedup, 'get_history_articles', lambda d1_query: None)
    monkeypatch.setattr(briefing_dedup, 'is_duplicate_article', lambda art, h: (False, None))

    assert len(sel.main()) == 2