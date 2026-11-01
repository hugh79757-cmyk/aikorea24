"""tests/test_pipe14_selector_fallback_reachability.py

AIK24-PIPE-14 회귀 테스트 — 선정기 main() 의 조기 리턴이 PIPE-12 폴백을 우회하던 버그.

2026-11-01 07:00 사고: 수집기는 05:30 에 105건을 저장했고 파이프라인도 정상 실행됐지만,
선정 단계에서 v2 풀 4건(기회 2 · tool 2)이 LLM 점수를 통과한 뒤 dedup 에서 **전부**
"이미 브리핑됨" 으로 제외됐다. 그런데 main() 이 `if not passed: return []` 로 조기
리턴해 select_top_articles 의 일반 뉴스 폴백(④)에 도달하지 못했다 — 폴백 코드는
존재했지만 도달 불가능한 상태였다. 결과: 브리핑 0건 · 이메일 미발송.

계약(PIPE-14):
  1. passed 가 비어도(점수 미달 · 이력 중복) 조기 리턴하지 않고 슬롯 4 폴백으로 이어간다.
  2. main() 은 select_top_articles(..., allow_fallback=True) 로 호출한다 — v2 풀이
     일부만 있어도 남은 슬롯을 일반 뉴스로 채운다.
  3. 폴백 선정분의 점수는 fallback_fill_general 내부 규칙
     ((a) 점수 ≥ SCORE_MIN 점수순 → (b) 점수 무관 최신순)을 그대로 따르며 재평가하지 않는다.
  4. 폴백에서도 0건일 때만 "브리핑 건너뜀" 으로 끝난다.

오프라인 보장: LLM(sleep·score_helpfulness)·D1 은 스텁이고 local 이력은 tmp 파일이다.
D1 스텁은 폴백 풀 SQL 마커로 라우팅하고(`v2_tag IS NULL OR v2_tag = ''`),
dedup 판정은 briefing_dedup 의 공개 진입점 스텁으로 고정한다 — 테스트가 실제
네트워크·실제 이력 파일을 만지지 않는다.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import auto_news_selector as sel  # noqa: E402
import briefing_dedup  # noqa: E402

# 2026-11-01 실행일 (실제 사고 날짜의 창 안 — 36h 창 계산과 무관하게 스텁이라 고정값)
D1 = '2026-11-01'
NEWS1 = '인공지능신문'
NEWS2 = '전자신문'
NEWS3 = 'ZDNet Korea'


def _v2(nid, score, source, v2_tag, pub=f'{D1} 06:00:00'):
    """v2 풀 행 (선정 후보) — 기회·Zen·무료 뉴스."""
    return {'id': nid, 'title': f'{source} {nid} 기사', 'original_title': f'orig-{nid}',
            'description': f'{source} {nid} 설명', 'link': f'https://example.com/{nid}',
            'source': source, 'pub_date': pub, 'v2_tag': v2_tag, 'v2_pass': 1,
            '_score': score}


def _fb(nid, source, pub, score):
    """폴백 풀 행 (무료 태그 없는 일반 뉴스). _score 를 미리 넣어 LLM 재평가를 막는다."""
    return {'id': nid, 'title': f'{source} 일반뉴스 {nid}', 'original_title': '',
            'description': f'{source} 일반뉴스 {nid} 설명',
            'link': f'https://example.com/{nid}', 'source': source,
            'pub_date': pub, 'v2_tag': None, 'v2_pass': None, '_score': score}


def _fake_d1(pool_rows):
    """폴백 풀 조회만 응답하는 D1 스텁 — 이력 조회는 빈 리스트."""
    def _query(sql):
        if "v2_tag IS NULL OR v2_tag = ''" in sql:   # get_general_fallback_news
            return [dict(r) for r in pool_rows]
        return []
    return _query


def _stub_dedup(monkeypatch, dupe_ids):
    """dedup 판정 고정 — dupe_ids 만 '이미 브리핑됨'으로 본다 (D1·local 이력 무관)."""
    monkeypatch.setattr(briefing_dedup, 'get_history_articles', lambda d1_query: [])
    stub = lambda art, history: (True, 'exact_id') if art['id'] in dupe_ids else (False, None)
    monkeypatch.setattr(briefing_dedup, 'is_duplicate_article', stub)
    monkeypatch.setattr(briefing_dedup, 'is_duplicate_article_strict', stub)


def _pool(monkeypatch, pool):
    """interleave_candidates 를 고정하고 main() 의 후보 풀을 대체한다."""
    counts = {t: 0 for t in sel.TAG_ORDER}
    counts['opportunity'] = sum(1 for a in pool if a['v2_tag'] == 'free-opportunity')
    counts['zen'] = sum(1 for a in pool if a['source'] == 'OpenCode Zen')
    for a in pool:
        counts[a['v2_tag']] = counts.get(a['v2_tag'], 0) + 1
    monkeypatch.setattr(sel, 'interleave_candidates', lambda limit: (pool, counts))


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    """LLM·sleep·D1 차단 + local 이력 tmp 격리.

    sel.d1_query 기본값을 빈 풀로 고정한다 — 폴백 풀이 필요한 테스트는 _fake_d1 로
    다시 패치한다. 패치가 없으면 폴백이 실제 D1 을 조회한다(오프라인 위반).
    """
    monkeypatch.setattr(sel.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(sel, 'score_helpfulness', lambda art: art.get('_score') or 0)
    monkeypatch.setattr(sel, 'd1_query', lambda sql: [])
    hist = tmp_path / 'briefing_dedup.json'
    hist.write_text(json.dumps({'briefings': [], 'articles': []}, ensure_ascii=False),
                    encoding='utf-8')
    monkeypatch.setattr(briefing_dedup, 'HISTORY_PATH', hist)


# 폴백 풀 — (a) 점수 ≥ SCORE_MIN 2건 + (a) 미달 2건.
# f3 이 f4 보다 최신이므로 (b) 단계는 f3 를 고른다 (점수 3 < 6 이지만 최신).
FALLBACK_POOL = [
    _fb('f1', NEWS1, f'{D1} 06:10:00', 9),
    _fb('f2', NEWS3, f'{D1} 05:30:00', 7),
    _fb('f3', NEWS2, f'{D1} 06:40:00', 3),
    _fb('f4', 'AI타임스', f'{D1} 02:00:00', 2),
]


# ------------------------------------------------- 2026-11-01 사고 재현 (검증 ①)


def test_20261101_dedup_wipes_v2_pool_then_fallback_fills_three(monkeypatch):
    """사고 재현 — v2 풀 4건 전원 '이미 브리핑됨' → 폴백이 일반 뉴스 3건을 채운다.

    수정 전에는 main() 이 "신선 후보 없음 — 브리핑 건너뜀" 으로 조기 리턴해 [] 였다
    (브리핑 0건). 지금은 슬롯 4 폴백이 (a) 점수순 → (b) 최신순으로 3건을 채운다.
    """
    pool = [
        _v2('o1', 0, '무료 기회', 'free-opportunity', pub=f'{D1} 05:00:00'),
        _v2('o2', 0, '무료 기회', 'free-opportunity', pub=f'{D1} 04:00:00'),
        _v2('t1', 8, NEWS1, 'tool', pub=f'{D1} 06:00:00'),
        _v2('t2', 7, NEWS2, 'tool', pub=f'{D1} 03:00:00'),
    ]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch, {'o1', 'o2', 't1', 't2'})   # 4건 전멸 (2026-11-01 실측)
    monkeypatch.setattr(sel, 'd1_query', _fake_d1(FALLBACK_POOL))

    selected = sel.main()

    ids = [a['id'] for a in selected]
    assert ids == ['f1', 'f2', 'f3'], ids          # (a) 9점·7점 → (b) 최신(f3)
    assert len(selected) == sel.MAX_COUNT, len(selected)
    assert set(ids).isdisjoint({'o1', 'o2', 't1', 't2'}), ids   # 전멸분 미반입
    assert {a['v2_tag'] for a in selected} == {None}, '폴백분은 무료 태그가 없다'


def test_main_falls_back_when_all_scores_below_min(monkeypatch):
    """점수 미달로 통과 0건이어도 조기 리턴하지 않는다 — 같은 폴백으로 3건을 채운다.

    수정 전에는 "통과 후보 없음 — 브리핑 건너뜀" 으로 끝났다 (같은 버그 클래스).
    """
    pool = [
        _v2('g1', 3, NEWS1, 'free-llm', pub=f'{D1} 06:00:00'),
        _v2('g2', 2, NEWS2, 'opensource', pub=f'{D1} 05:00:00'),
    ]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch, set())                      # 중복 아님 — 점수만 미달
    monkeypatch.setattr(sel, 'd1_query', _fake_d1(FALLBACK_POOL))

    ids = [a['id'] for a in sel.main()]

    assert ids == ['f1', 'f2', 'f3'], ids


def test_main_pads_partial_v2_pool_with_general_news(monkeypatch):
    """v2 풀이 일부만 신선해도 남은 슬롯을 일반 뉴스로 채운다 (allow_fallback=True).

    수정 전에는 main() 이 allow_fallback 을 넘기지 않아 v2 1건으로 끝났다.
    """
    pool = [
        # 신선 1건 — 출처를 폴백 풀과 겹치지 않게 둔다 (출처당 1건 규칙 때문에 폴백이 줄면
        # (a) 점수순 검증이 흐려진다).
        _v2('g1', 9, 'IT조선', 'free-llm', pub=f'{D1} 06:00:00'),   # 신선 — 슬롯 차지
        _v2('g2', 8, NEWS2, 'opensource', pub=f'{D1} 05:00:00'),  # 이미 브리핑됨
        _v2('g3', 7, NEWS3, 'tool', pub=f'{D1} 04:00:00'),        # 이미 브리핑됨
    ]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch, {'g2', 'g3'})
    monkeypatch.setattr(sel, 'd1_query', _fake_d1(FALLBACK_POOL))

    ids = [a['id'] for a in sel.main()]

    assert ids == ['g1', 'f1', 'f2'], ids    # v2 신선 1 + 폴백 (a) 점수순 2
    assert len(ids) == sel.MAX_COUNT, ids


def test_main_returns_empty_only_after_fallback_empty(monkeypatch):
    """폴백에서도 0건일 때만 브리핑을 건너뛴다 — 그 전에는 [] 를 반환하지 않는다."""
    pool = [
        _v2('t1', 8, NEWS1, 'tool', pub=f'{D1} 06:00:00'),
        _v2('t2', 7, NEWS2, 'tool', pub=f'{D1} 05:00:00'),
    ]
    _pool(monkeypatch, pool)
    _stub_dedup(monkeypatch, {'t1', 't2'})
    monkeypatch.setattr(sel, 'd1_query', _fake_d1([]))   # 폴백 풀도 비어 있음

    assert sel.main() == []
