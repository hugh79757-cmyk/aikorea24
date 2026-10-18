"""tests/test_auto_news_selector_zen_slot_limit.py

2026-10-18 대표님 지시 회귀 테스트 — "나오지 말아야 할 것이 나왔고, 나올 게 없다면
그 자리를 뉴스가 채워야 한다".

사고 실측(2026-10-18 09:00 KST 실행 로그, scripts/pipeline_runner.log):
    [selector] v2_pass=1 후보: 8건 (기회=3, zen=3, free-llm=3, opensource=0, tool=0)
    [selector]   ⓘ Zen 변경 3건 우선 배정
    [selector] 선정 3건
→ Zen 제공 중단 알림 2건이 카드로 나가고, 실제 뉴스 3건(free-llm)은 슬롯을 못 받았다.

계약:
  1. Zen 슬롯은 최대 1건 (ZEN_SLOT_LIMIT) — 남은 슬롯은 일반 뉴스가 점수순으로 채운다.
  2. 제공 중단 알림(`[제외] ...`)은 슬롯 후보가 아니다 (SQL 1차 + 배정 2차 방어).
  3. 재충원(refill) 단계에서도 같은 상한이 적용된다.
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


def _art(nid, score, source, v2_tag=None, title=None):
    return {'id': nid, 'title': title or f'{source} {nid}', 'original_title': f'orig-{nid}',
            'source': source, 'pub_date': f'{TODAY} 10:00:00',
            'v2_tag': v2_tag or ('free-llm' if source == ZEN_SRC else 'opensource'),
            '_score': score, '_detail': '테스트'}


def _removed(nid):
    return _art(nid, None, ZEN_SRC,
                title=f'[제외] {nid} — OpenCode Zen 무료 목록에서 제외')


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """LLM 호출과 sleep 을 막는다."""
    monkeypatch.setattr(sel.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(sel, 'score_helpfulness', lambda art: art.get('_score', 0))


def _pool(monkeypatch, pool):
    counts = {t: 0 for t in sel.TAG_ORDER}
    counts['opportunity'] = sum(1 for a in pool if a['v2_tag'] == 'free-opportunity')
    counts['zen'] = sum(1 for a in pool if a['source'] == ZEN_SRC)
    for a in pool:
        counts[a['v2_tag']] = counts.get(a['v2_tag'], 0) + 1
    monkeypatch.setattr(sel, 'interleave_candidates', lambda limit: (pool, counts))


def _stub_dedup(monkeypatch, dupe_ids=()):
    monkeypatch.setattr(briefing_dedup, 'get_history_articles', lambda d1_query: [])
    monkeypatch.setattr(
        briefing_dedup, 'is_duplicate_article',
        lambda art, history: (True, 'exact_id') if art['id'] in dupe_ids else (False, None))


# ------------------------------------------------------------------ 슬롯 상한


def test_zen_slot_is_capped_at_one(monkeypatch):
    """Zen 변경 3건이 슬롯을 독식하면 실제 뉴스가 밀린다 — 1건만 배정한다."""
    pool = [_art('z1', None, ZEN_SRC), _art('z2', None, ZEN_SRC), _art('z3', None, ZEN_SRC),
            _art('g1', 15, NEWS_SRC), _art('g2', 14, NEWS_SRC2)]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch)

    assert [a['id'] for a in sel.main()] == ['z1', 'g1', 'g2']


def test_removed_notice_never_takes_a_slot(monkeypatch):
    """제공 중단 알림([제외])은 후보가 아니다 — 그 자리는 뉴스가 채운다."""
    pool = [_removed('cat-jam-free'), _removed('muse-spark-1.3-contributor-free'),
            _art('g1', 15, NEWS_SRC), _art('g2', 14, NEWS_SRC2)]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch)

    assert [a['id'] for a in sel.main()] == ['g1', 'g2']


def test_added_rows_still_get_a_slot(monkeypatch):
    """신규 추가([신규 무료])는 여전히 슬롯 대상이다 — 제외만 빼는 것이지 전부 빼는 게 아니다."""
    pool = [_art('a1', None, ZEN_SRC, title='[신규 무료] new-free — OpenCode Zen 무료 목록에 추가'),
            _art('g1', 15, NEWS_SRC)]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch)

    assert [a['id'] for a in sel.main()] == ['a1', 'g1']


# ------------------------------------------------------------------ 방어선


def test_zen_query_excludes_removed_notices(monkeypatch):
    """SQL 1차 방어 — 후보 조회 단계에서 [제외] 행을 걸러낸다."""
    seen = []

    def _fake_query(sql):
        seen.append(sql)
        return []

    monkeypatch.setattr(sel, 'd1_query', _fake_query)
    sel.get_zen_changes(3)

    assert len(seen) == 1, seen
    assert "title NOT LIKE '[제외]%'" in seen[0]


def test_is_excluded_notice_matches_prefix_only():
    """접두 판정 — 제목 중간에 우연히 들어간 대괄호는 걸리지 않는다."""
    assert sel._is_excluded_notice({'title': '[제외] x — OpenCode Zen 무료 목록에서 제외'})
    assert not sel._is_excluded_notice({'title': '[신규 무료] y — OpenCode Zen 무료 목록에 추가'})
    assert not sel._is_excluded_notice({'title': 'AI 업계 [제외] 논쟁'})
    assert not sel._is_excluded_notice({})


def test_refill_zen_respects_slot_limit(monkeypatch):
    """재충원 단계도 같은 상한 — Zen 을 여러 건 채우지 않는다."""
    monkeypatch.setattr(briefing_dedup, 'filter_duplicates',
                        lambda articles, d1_query_func: (list(articles), []))
    pool = [_art('z1', None, ZEN_SRC), _art('z2', None, ZEN_SRC), _art('z3', None, ZEN_SRC),
            _art('g1', 15, NEWS_SRC)]
    out = sel.refill_after_dedup([_art('k1', 12, NEWS_SRC2)], dropped=(), max_count=3,
                                 d1_query_func=lambda sql: [], pool=pool,
                                 scorer=lambda art: 0)
    ids = [a['id'] for a in out]

    assert ids[0] == 'k1'
    assert len(ids) <= 3, ids
    assert sum(1 for i in ids if i.startswith('z')) == sel.ZEN_SLOT_LIMIT, ids


def test_refill_skips_removed_notices(monkeypatch):
    """재충원에서도 [제외] 는 슬롯을 받지 않는다."""
    monkeypatch.setattr(briefing_dedup, 'filter_duplicates',
                        lambda articles, d1_query_func: (list(articles), []))
    pool = [_removed('cat-jam-free'), _removed('muse-spark-1.3-contributor-free')]
    out = sel.refill_after_dedup([_art('k1', 12, NEWS_SRC2)], dropped=(), max_count=3,
                                 d1_query_func=lambda sql: [], pool=pool,
                                 scorer=lambda art: 0)

    assert [a['id'] for a in out] == ['k1']
