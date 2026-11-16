"""tests/test_brief17_ai_relevance_recency.py

AIK24-BRIEF-17 회귀 테스트 — 브리핑 선정 기준 3종 보강 (2026-11-16 대표님 지시).

사고: 2026-11-16 07:00 브리핑에서 슬롯 1·2 후보가 비어 4순위 일반 뉴스 폴백이
최신순으로 3건을 채웠고, 아래 3건이 그대로 카드가 됐다.

    [단독] 한국형 인큐텔 초대 대표에 윤효환 한국벤처투자 본부장 '유력'   ← 인사 단신
    SK하이닉스 HBM4 증설                                              ← 일반 설비
    젠슨 황 악재                                                      ← 인물 단신

원인: 폴백 (b) 단계가 점수도, AI 관련성도 보지 않고 발행 시각만 봤다.
계약(이 파일이 고정하는 것):
  1. 인사·주가/실적·거시경제 단신은 슬롯에 들이지 않는다 (_is_briefing_misfit).
     단, 제품 출시·오픈소스·도구 기사가 인사 표현을 곁들인 경우는 오탐으로 막지 않는다.
  2. AI 직접 관련성(2 직접 / 1 인접 / 0 무관)을 점수와 폴백 정렬에 반영한다.
  3. 24h 이내 +3 · 48h +2 · 72h +1 최신성 가점 — 같은 점수·같은 관련성이면 새 기사가 먼저다.
  4. AI 후보가 모자라도 브리핑은 3건을 채운다 (AIK24-PIPE-12/14 유지).

오프라인 보장: D1 은 SQL 마커로 라우팅하는 스텁, local 이력은 tmp 파일, LLM·sleep 은
스텁/차단이다. 실제 네트워크·실제 이력 파일을 만지지 않는다.
"""
import json
import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import auto_news_selector as sel  # noqa: E402
import briefing_dedup  # noqa: E402

NEWS1 = '전자신문'
NEWS2 = 'ZDNet Korea'
NEWS3 = 'IT조선'


def _pub(hours_ago=1, source=None):
    """지금으로부터 hours_ago 시간 전 발행 시각(KST, 'YYYY-MM-DD HH:MM:SS')."""
    return (datetime.now(sel.KST) - timedelta(hours=hours_ago)).strftime('%Y-%m-%d %H:%M:%S')


def _row(nid, title, source=NEWS1, pub=None, score=None, v2_tag=None, desc=None):
    return {'id': str(nid), 'title': title, 'original_title': '',
            'description': desc if desc is not None else title,
            'link': f'https://example.com/{nid}', 'source': source,
            'pub_date': pub or _pub(), 'v2_tag': v2_tag, 'v2_pass': None,
            '_score': score}


def _fake_d1(pool_rows, history_rows=()):
    def _query(sql):
        if 'DISTINCT n.id' in sql:
            return [dict(r) for r in history_rows]
        if "v2_tag IS NULL OR v2_tag = ''" in sql:
            return [dict(r) for r in pool_rows]
        return []
    return _query


def _scorer(points):
    calls = []

    def _score(art):
        v = points.get(str(art['id']), 0)
        art['_score'] = v
        calls.append(str(art['id']))
        return v
    return _score, calls


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    monkeypatch.setattr(sel.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(sel, 'd1_query', lambda sql: [])
    hist = tmp_path / 'briefing_dedup.json'
    hist.write_text(json.dumps({'briefings': [], 'articles': []}, ensure_ascii=False),
                    encoding='utf-8')
    monkeypatch.setattr(briefing_dedup, 'HISTORY_PATH', hist)


# ------------------------------------------------- 1) 인사·비AI 단신 필터 (방어선 1)

def test_personnel_guard_blocks_appointment_and_obituary():
    """대표 선임·인사 발령·내정·부고 단신은 슬롯 대상이 아니다."""
    incumbents = [
        ('[단독] 한국형 인큐텔 초대 대표에 윤효환 한국벤처투자 본부장 \'유력\'', NEWS1),
        ('엔비디아, 신임 CTO 선임', NEWS2),
        ('카카오, 조직 개편 인사 발령 단행', NEWS1),
        ('전직 장관, AI 기업 고문으로 부고', NEWS3),
    ]
    for title, src in incumbents:
        art = _row(1, title, src)
        assert sel._is_personnel_news(art) is True, title
        assert sel._is_briefing_misfit(art) is True, title


def test_personnel_guard_spares_product_and_tool_news():
    """AI 기업/제품·오픈소스·도구 기사는 인사 표현이 섞여도 막지 않는다 (오탐 방지)."""
    keep = [
        ('OpenAI, GPT-5.1 공개 — 추론 성능 2배', 'TechCrunch'),
        ('앤트로픽, 신임 연구책임자 영입과 함께 Claude 신모델 공개', NEWS2),
        ('삼성전자, AI 반도체 라인 책임자 임명… HBM4 양산 시작', NEWS1),
        ('오픈소스 LLM 도구 3종 무료 배포', NEWS3),
    ]
    for title, src in keep:
        art = _row(2, title, src)
        assert sel._is_personnel_news(art) is False, title
        assert sel._is_briefing_misfit(art) is False, title


def test_offtopic_guard_blocks_macro_and_stock_declines_but_keeps_ai():
    """주가·실적·거시경제 단신은 제외하되, AI 직접 기사는 예외로 둔다."""
    assert sel._is_briefing_misfit(_row(3, '코스피 3000 돌파, 외국인 순매수 행진', '연합뉴스'))
    assert sel._is_briefing_misfit(
        _row(4, 'SK하이닉스, 3분기 영업이익 발표… 시장 기대치 상회', NEWS1))
    # AI 직접 관련 기사는 주가·실적 표현이 있어도 남긴다.
    assert sel._is_briefing_misfit(
        _row(5, '엔비디아 실적 발표 — AI 데이터센터 매출 3배', NEWS2)) is False


# --------------------------------------------------- 2) AI 직접 관련성 (방어선 2)

def test_ai_relevance_levels():
    assert sel._ai_relevance(_row(10, 'OpenAI, GPT-5.1 공개')) == 2         # 직접
    assert sel._ai_relevance(_row(11, '국내 증권사, AI 리서치 어시스턴트 출시')) == 2
    assert sel._ai_relevance(_row(12, 'SK하이닉스, HBM4 증설 투자 확대')) in (1, 2)  # 인접
    assert sel._ai_relevance(_row(13, '조선소 수주 확대')) == 0              # 무관


def test_ai_relevance_does_not_use_outlet_name():
    """출처명(인공지능신문·AI타임스)이 제목·설명에 섞여도 관련성으로 치지 않는다."""
    art = _row(14, '지역 축제 개최 안내', '인공지능신문',
               desc='인공지능신문 제공 — 지역 축제 개최 안내')
    assert sel._ai_relevance(art) == 0
    ai_art = _row(15, '지역 축제 개최 안내', 'AI타임스',
                  desc='AI타임스 제공 — 지역 축제 개최 안내')
    assert sel._ai_relevance(ai_art) == 0


# ------------------------------------------------------- 3) 최신성 가점 (방어선 3)

def test_recency_bonus_tiers():
    assert sel._recency_bonus(_row(20, 'AI 신모델 공개', pub=_pub(1))) == 3
    assert sel._recency_bonus(_row(21, 'AI 신모델 공개', pub=_pub(30))) == 2
    assert sel._recency_bonus(_row(22, 'AI 신모델 공개', pub=_pub(60))) == 1
    assert sel._recency_bonus(_row(23, 'AI 신모델 공개', pub=_pub(120))) == 0
    assert sel._recency_bonus({'pub_date': '미정'}) == 0        # 파싱 불가
    assert sel._recency_bonus({}) == 0


def test_rank_score_combines_score_relevance_and_recency():
    """종합 점수 = LLM 점수 + AI 관련성 가점 + 최신성 가점."""
    direct_fresh = _row(30, 'OpenAI 신모델 공개', pub=_pub(1), score=6)
    dull_fresh = _row(31, '조선소 수주 확대', source=NEWS2, pub=_pub(1), score=6)
    direct_stale = _row(32, 'OpenAI 신모델 공개', source=NEWS3, pub=_pub(120), score=6)

    assert sel._rank_score(direct_fresh) == 6 + 4 + 3
    assert sel._rank_score(dull_fresh) == 6 + 0 + 3
    assert sel._rank_score(direct_stale) == 6 + 4 + 0
    assert sel._rank_score(direct_fresh) > sel._rank_score(direct_stale)


# ------------------------------------- 폴백: 2026-11-16 사고 재현과 3건 불변식

def test_fallback_skips_personnel_and_prefers_ai_news():
    """오늘 사고 재현 — 최신 인사 단신·설비 단신보다 AI 직접 기사를 먼저 쓴다."""
    pool = [
        _row(901, "[단독] 한국형 인큐텔 초대 대표에 윤효환 한국벤처투자 본부장 '유력'",
             NEWS1, pub=_pub(1)),                                   # 인사 → 제외
        _row(902, 'SK하이닉스, HBM4 증설 투자 확대', NEWS2, pub=_pub(2)),   # 설비(인접)
        _row(903, '젠슨 황 악재', NEWS3, pub=_pub(3)),                   # 무관 단신
        _row(904, 'OpenAI, GPT-5.1 공개 — 추론 성능 2배', 'TechCrunch', pub=_pub(10)),
        _row(905, '앤트로픽, Claude 신모델 공개', 'AI타임스', pub=_pub(30)),
    ]
    score, calls = _scorer({'901': 9, '902': 4, '903': 2, '904': 7, '905': 6})

    picked = sel.fallback_fill_general(
        3, set(), set(), set(), _fake_d1(pool), score)

    ids = [a['id'] for a in picked]
    # (a) AI 직접 + 점수 통과분(904·905) → (b) AI 인접 최신(902) 순.
    assert ids == ['904', '905', '902'], ids
    assert '901' not in ids, '인사 단신이 폴백에 들어왔다'
    assert '903' not in ids, '무관 단신이 AI 후보보다 먼저 들어왔다'
    assert '901' not in calls, '제외 대상은 LLM 채점도 하지 않는다'


def test_fallback_prefers_ai_news_over_newer_irrelevant():
    """(b) 점수 무관 단계 — 최신 무관 기사보다 하루 지난 AI 기사를 먼저 쓴다."""
    pool = [
        _row(910, '지역 축제 개최 안내', NEWS1, pub=_pub(1)),        # 무관 · 최신
        _row(911, 'OpenAI, 새 에이전트 기능 공개', NEWS2, pub=_pub(26)),  # AI · 하루 전
    ]
    score, _ = _scorer({})
    picked = sel.fallback_fill_general(1, set(), set(), set(), _fake_d1(pool), score)

    assert [a['id'] for a in picked] == ['911'], [a['id'] for a in picked]


def test_fallback_uses_latest_among_equally_relevant():
    """같은 AI 관련성끼리는 최신순 — 최신성 가점 규칙이 정렬에 실제로 걸린다."""
    pool = [
        _row(920, '앤트로픽, Claude 신모델 공개', NEWS1, pub=_pub(20)),
        _row(921, 'AI 챗봇 신기능 업데이트', NEWS2, pub=_pub(2)),      # 더 최신
    ]
    score, _ = _scorer({})
    picked = sel.fallback_fill_general(1, set(), set(), set(), _fake_d1(pool), score)

    assert [a['id'] for a in picked] == ['921'], [a['id'] for a in picked]


def test_fallback_still_fills_three_when_ai_pool_is_short():
    """AI 후보가 모자라도 브리핑은 3건 — 무관 기사는 폴백 (b) 의 맨 뒤에서 쓴다."""
    pool = [
        _row(930, '조선소 수주 확대', NEWS1, pub=_pub(1)),
        _row(931, '지역 축제 개최 안내', NEWS2, pub=_pub(2)),
        _row(932, '도로 정비 공사 완료', NEWS3, pub=_pub(3)),
    ]
    score, _ = _scorer({})
    picked = sel.fallback_fill_general(3, set(), set(), set(), _fake_d1(pool), score)

    assert len(picked) == 3, [a['id'] for a in picked]
    assert [a['id'] for a in picked] == ['930', '931', '932']   # 같은 관련성 → 최신순


# ------------------------------------------ 선정 슬롯(일반 뉴스) 정렬에도 같은 기준

def test_select_top_articles_slot3_prefers_ai_news_over_higher_raw_score():
    """일반 뉴스 슬롯(3) — 9점 무관 기사보다 6점 AI 기사가 먼저 온다 (관련성 가점 4)."""
    dull = _row(940, '조선소 수주 확대', NEWS1, pub=_pub(1), score=9)
    ai_news = _row(941, 'OpenAI, GPT-5.1 공개', NEWS2, pub=_pub(2), score=6)

    picked = sel.select_top_articles({'v2': [dull, ai_news]}, 2)

    assert [a['id'] for a in picked] == ['941', '940'], [a['id'] for a in picked]


def test_select_top_articles_skips_personnel_news():
    """선정 슬롯에서도 인사 단신은 빠진다 — 폴백을 켜지 않아도 카드가 되지 않는다."""
    personnel = _row(950, '카카오, 조직 개편 인사 발령 단행', NEWS1, pub=_pub(1), score=12)
    ai_news = _row(951, '앤트로픽, Claude 신모델 공개', NEWS2, pub=_pub(2), score=8)

    picked = sel.select_top_articles({'v2': [personnel, ai_news]}, 2)

    assert [a['id'] for a in picked] == ['951'], [a['id'] for a in picked]


def test_select_top_articles_prefers_recent_ai_news_on_equal_scores():
    """같은 점수·같은 관련성이면 최신 기사가 먼저 온다 (최신성 가점)."""
    fresh = _row(960, 'OpenAI 신모델 공개', NEWS1, pub=_pub(2), score=8)
    stale = _row(961, 'OpenAI 구모델 공개', NEWS2, pub=_pub(100), score=8)

    picked = sel.select_top_articles({'v2': [stale, fresh]}, 2)

    assert [a['id'] for a in picked] == ['960', '961'], [a['id'] for a in picked]
