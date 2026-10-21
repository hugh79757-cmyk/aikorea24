#!/usr/bin/env python3
"""tests/test_pipe09_d1_entity_relaxation.py — AIK24-PIPE-09 결정 1 회귀 테스트

배경 (대표님 결정 2026-10-21):
    AIK24-PIPE-08 이 "56074 의 D1 층 entity(2) 는 fail-safe 로 유지" 로 남긴
    잔여 항목 1건을 닫는다 — D1 층도 local 층과 **같은 기준**으로 완화한다.

    근거: 56074 "Google Cloud 신규 가입 $300 크레딧" 의 D1 상대는
    56152 "구글, 유료 구독자에 비해 픽셀 등 무료 AI Pro 체험 사용자의 기능 제한".
    공통 엔티티는 {AI, Google} 뿐이고 jaccard_all 0.04 — **다른 주제**다.
    즉 entity(2) 는 범용 엔티티 오탐이었다.

검증 대상: scripts/briefing_dedup.py
    · filter_duplicates 의 D1 층이 is_duplicate_article_strict 를 쓰는가
    · D1 이력 7행 × 후보 9건 = 63쌍의 판정에서 **변경은 엔티티 단독 쌍뿐**인가
    · Layer 1(exact)·Layer 2(semantic) 판정은 **전부 불변**인가
    · 진짜 엔티티 중복은 사유 라벨 entity(2) 로 계속 막히는가

주의: 실제 D1 · 실제 scripts/briefing_dedup.json 은 건드리지 않는다.
사용: pytest tests/test_pipe09_d1_entity_relaxation.py -q
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import briefing_dedup  # noqa: E402
from threads.dedup import compute_similarity, is_same_topic, is_topic_related  # noqa: E402

FIXTURE = Path(__file__).parent / 'fixtures' / 'pipe08_20261021.json'
DATA = json.loads(FIXTURE.read_text(encoding='utf-8'))

CANDIDATES = {c['id']: c for c in DATA['candidates']}
D1_HISTORY = DATA['d1_history']
LOCAL_HISTORY = DATA['local_history']

# 결정의 핵심 사례 — D1 층에서 풀리는 유일한 쌍
RELEASED_ID = 56074
D1_COUNTERPART = 56152


def _row(r):
    return (r.get('title') or '', r.get('original_title') or '', r.get('description') or '')


@pytest.fixture()
def world(monkeypatch, tmp_path):
    """오프라인 세계 — 실제 D1 · 실제 local 이력 파일 무관."""
    def d1_stub(sql):
        if 'FROM briefings' in sql:
            return [dict(r) for r in D1_HISTORY]
        return []

    hist_path = tmp_path / 'briefing_dedup.json'
    hist_path.write_text(json.dumps(
        {'briefings': [], 'articles': [dict(r) for r in LOCAL_HISTORY]},
        ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(briefing_dedup, 'HISTORY_PATH', hist_path)
    return d1_stub, hist_path


def _pairs():
    """D1 이력 7행 × 후보 9건 = 63쌍."""
    return [(c, h) for c in DATA['candidates'] for h in D1_HISTORY]


# --------------------------------------------------------------------- 쌍 단위


def test_d1_pair_count_is_7x9():
    """픽스처 D1 이력 7행 × 후보 9건 = 63쌍 (전수 순회 대상)."""
    assert len(D1_HISTORY) == 7
    assert len(DATA['candidates']) == 9
    assert len(_pairs()) == 63


def test_d1_layer_delta_is_entity_only():
    """**핵심 증거** — 63쌍 중 판정이 바뀐 쌍은 엔티티 단독 쌍뿐이다.

    Layer 1(exact_*)·Layer 2(semantic) 사유가 바뀐 쌍은 0건이어야 한다.
    """
    changed = []
    for c, h in _pairs():
        before = briefing_dedup.is_duplicate_article(c, [h])
        after = briefing_dedup.is_duplicate_article_strict(c, [h])
        if before != after:
            changed.append((c['id'], h['id'], before, after))

    assert len(changed) == 1, changed
    cid, hid, before, after = changed[0]
    # 바뀐 쌍은 오탐으로 판명된 56074 × 56152
    assert (cid, hid) == (RELEASED_ID, D1_COUNTERPART)
    # 변경 전 사유는 엔티티 단독이고, 변경 후에는 통과한다
    assert before == (True, 'entity(2)')
    assert after == (False, None)


def test_d1_layer_exact_and_semantic_reasons_unchanged():
    """Layer 1/2 사유(exact_*·semantic)는 어느 쌍에서도 바뀌지 않는다."""
    for c, h in _pairs():
        before = briefing_dedup.is_duplicate_article(c, [h])
        after = briefing_dedup.is_duplicate_article_strict(c, [h])
        if before[0] and before[1] and (before[1].startswith('exact_')
                                       or before[1] == 'semantic'):
            assert after == before, (c['id'], h['id'], before, after)


def test_layer1_layer2_outcomes_identical_when_entity_layer_disabled(monkeypatch):
    """Layer 3 을 통째로 끄면 loose·strict 판정이 **모든 쌍에서 동일**하다.

    → Layer 1/2 구현은 두 경로가 같은 코드를 공유한다는 직접 증거.
    """
    monkeypatch.setattr(briefing_dedup, 'ENTITY_OVERLAP_THRESHOLD', 10 ** 6)
    for c, h in _pairs():
        before = briefing_dedup.is_duplicate_article(c, [h])
        after = briefing_dedup.is_duplicate_article_strict(c, [h])
        assert before == after, (c['id'], h['id'], before, after)


def test_d1_layer_decision_table_before_after():
    """후보 9건 × D1 이력 7행 판정표 — before/after 표를 그대로 고정한다."""
    before_table = {}
    after_table = {}
    for c in DATA['candidates']:
        before_table[c['id']] = briefing_dedup.is_duplicate_article(c, D1_HISTORY)
        after_table[c['id']] = briefing_dedup.is_duplicate_article_strict(c, D1_HISTORY)

    # before — entity(2) 로 막던 것이 56074 하나
    assert before_table[56074] == (True, 'entity(2)')
    assert before_table[56525] == (True, 'exact_id')
    assert before_table[56391] == (True, 'exact_id')

    # after — 56074 만 풀리고 나머지는 동일
    assert after_table[56074] == (False, None)
    assert after_table[56525] == (True, 'exact_id')
    assert after_table[56391] == (True, 'exact_id')
    for cid in (56076, 56082, 56206, 56389, 56406, 56500):
        assert after_table[cid] == before_table[cid] == (False, None), cid


def test_56074_counterpart_is_generic_entity_false_positive():
    """56074 × 56152 가 오탐인 근거 — 주제어 겹침이 거의 없다."""
    c = CANDIDATES[56074]
    h = [r for r in D1_HISTORY if r['id'] == D1_COUNTERPART][0]

    ent_c = briefing_dedup.extract_entities(*_row(c))
    ent_h = briefing_dedup.extract_entities(*_row(h))
    assert sorted(ent_c & ent_h) == ['AI', 'Google']

    sim = compute_similarity(*_row(c), *_row(h))
    assert sim['jaccard_all'] < 0.15  # 주제어 겹침 기준 미달
    assert not is_same_topic(*_row(c), *_row(h))
    assert not is_topic_related(*_row(c), *_row(h))


# --------------------------------------------------------------------- 전 구간


def test_filter_duplicates_uses_strict_for_d1_layer(world):
    """filter_duplicates 의 D1 층이 strict 판정이다 (엔티티 단독으로 막지 않는다)."""
    d1_stub, _ = world
    kept, removed = briefing_dedup.filter_duplicates([dict(CANDIDATES[56074])], d1_stub)

    assert removed == []
    assert [a['id'] for a in kept] == [56074]


def test_filter_duplicates_keeps_genuine_blocks(world):
    """정당한 차단은 그대로 — 56525·56391(exact_id) · 56206(local_exact_id) · 56406(local_semantic)."""
    d1_stub, _ = world
    pool = [dict(CANDIDATES[i]) for i in (56525, 56391, 56206, 56406, 56074)]
    _kept, removed = briefing_dedup.filter_duplicates(pool, d1_stub)
    reasons = {a['id']: r for a, r in removed}

    assert reasons == {56525: 'exact_id', 56391: 'exact_id',
                       56206: 'local_exact_id', 56406: 'local_semantic'}


def test_local_layer_decision_unchanged(world):
    """local 층 판정은 이번 변경의 영향 밖 — strict 로 그대로다.

    local 층은 변경 전에도 strict 경로였고, 변경 후에도 strict 경로다.
    아래 표는 9건 후보 × local 이력 272행의 strict 판정 결과(변경 전과 동일).
    """
    d1_stub, _ = world
    strict_table = {}
    for c in DATA['candidates']:
        strict_table[c['id']] = briefing_dedup.is_duplicate_article_strict(c, LOCAL_HISTORY)

    assert strict_table == {
        56074: (False, None),
        56076: (False, None),
        56082: (False, None),
        56206: (True, 'exact_id'),
        56389: (False, None),
        56391: (True, 'exact_id'),
        56406: (True, 'semantic'),
        56500: (False, None),
        56525: (True, 'exact_id'),
    }


def test_local_layer_is_never_looser_than_strict(world):
    """loose 경로가 막는 케이스가 strict 에서 통과하면 안 된다 (단조성)."""
    d1_stub, _ = world
    for c in DATA['candidates']:
        loose = briefing_dedup.is_duplicate_article(c, LOCAL_HISTORY)
        strict = briefing_dedup.is_duplicate_article_strict(c, LOCAL_HISTORY)
        assert not strict[0] or loose[0], (c['id'], loose, strict)


def test_entity_reason_label_kept_for_genuine_entity_match():
    """진짜 엔티티 중복은 **entity(2) 라벨로** 계속 막힌다 (로그 진단성 유지).

    EN-EN 분기: 공유 토큰 1개('free')로 jaccard_en 0.33 → Layer 2(semantic)는
    통과하지 않지만, 주제어 겹침(jaccard_en ≥ 0.30)은 있고 공통 엔티티는
    {API, Free} 2개 → Layer 3 이 entity(2) 로 막는다.
    """
    a = {'id': '90001', 'title': 'OpenRouter Free API Models', 'original_title': 'OpenRouter free',
         'description': 'OpenRouter free tier listing', 'link': 'https://example.com/a'}
    b = {'id': '90002', 'title': 'Perplexity Free API Guide', 'original_title': 'Perplexity free',
         'description': 'Perplexity free plan guide', 'link': 'https://example.com/b'}

    assert not is_same_topic(*_row(a), *_row(b))
    assert is_topic_related(*_row(a), *_row(b))
    assert briefing_dedup.is_duplicate_article(a, [b]) == (True, 'entity(2)')
    assert briefing_dedup.is_duplicate_article_strict(a, [b]) == (True, 'entity(2)')


def test_d1_layer_entity_label_in_filter_duplicates(world):
    """filter_duplicates 의 D1 층 엔티티 차단은 'entity(2)' (local_ 접두 없음)로 남는다."""
    d1_stub, _ = world
    a = {'id': '90001', 'title': 'OpenRouter Free API Models', 'original_title': 'OpenRouter free',
         'description': 'OpenRouter free tier listing', 'link': 'https://example.com/a'}
    b = {'id': '90002', 'title': 'Perplexity Free API Guide', 'original_title': 'Perplexity free',
         'description': 'Perplexity free plan guide', 'link': 'https://example.com/b'}

    def d1_with_pair(sql):
        if 'FROM briefings' in sql:
            return [dict(b)]
        return []

    _kept, removed = briefing_dedup.filter_duplicates([a], d1_with_pair)
    assert removed == [(a, 'entity(2)')]


def test_none_history_fails_open():
    """D1 조회가 None 을 주면 막지 않고 통과시킨다 (fail-open)."""
    a = {'id': '90001', 'title': 'OpenRouter Free API Models', 'original_title': 'OpenRouter free',
         'description': 'OpenRouter free tier listing', 'link': 'https://example.com/a'}
    b = {'id': '90002', 'title': 'Perplexity Free API Guide', 'original_title': 'Perplexity free',
         'description': 'Perplexity free plan guide', 'link': 'https://example.com/b'}

    assert briefing_dedup.is_duplicate_article_strict(a, None) == (False, None)
    assert briefing_dedup.is_duplicate_article_strict(a, []) == (False, None)


def test_loose_entry_point_still_available():
    """`is_duplicate_article`(loose)는 그대로 남아 "변경 전 규칙" 재현에 쓰인다."""
    c = CANDIDATES[56074]
    h = [r for r in D1_HISTORY if r['id'] == D1_COUNTERPART][0]
    assert briefing_dedup.is_duplicate_article(c, [h]) == (True, 'entity(2)')
