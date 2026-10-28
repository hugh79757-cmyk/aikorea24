"""tests/test_pipe12_general_fallback.py

AIK24-PIPE-12 회귀 테스트 — 무료 태그 풀로 3건이 안 되면 일반 뉴스 폴백으로 채운다.

2026-10-28 사고 재현: 선정 풀 7건 중 6건이 이력 중복으로 제외되고 재충원 풀 8건도
전부 중복 → 빈 슬롯 2개가 그대로 발행됐다(브리핑 1건). 폴백 규칙:
  (a) LLM 도움 점수 ≥6 후보를 점수순으로, (b) 부족하면 점수 무관 최신순(pub_date DESC).
제외 조건(이미 브리핑된 기사, [제외] 알림, 프로바이더 4종, 지원사업 공고, 출처당 1건)
은 무료 풀과 동일하게 유지된다.

오프라인 보장: D1 조회는 SQL 마커로 라우팅하는 스텁을 주입하고
(DISTINCT n.id → 이력 조회 / FROM briefing_items bi → 폴백 풀 조회),
filter_duplicates 는 **실제 함수**를 통과시킨다(중복 차단이 진짜로 걸리는지 본다).
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import briefing_dedup  # noqa: E402
import auto_news_selector as sel  # noqa: E402

NEWS1 = '전자신문'
NEWS2 = 'ZDNet Korea'


def _his(nid, title, link=''):
    """D1 이력 행 (get_history_articles 컬럼: id/title/original_title/description/link)."""
    return {'id': str(nid), 'title': title, 'original_title': '',
            'description': '', 'link': link}


def _pool(nid, title, source, pub, v2_tag=None, link=''):
    """폴백 풀 행 (news 테이블 _COLS 중 판정에 필요한 키)."""
    return {'id': str(nid), 'title': title, 'original_title': '',
            'description': title, 'link': link or f'https://example.com/{nid}',
            'source': source, 'pub_date': pub, 'v2_tag': v2_tag,
            'v2_pass': None, '_score': None}


def _scorer(pts):
    """실제 score_helpfulness 규약을 따르는 가짜 스코어 — art['_score'] 를 직접 기록한다."""
    calls = []

    def _score(art):
        v = pts.get(art['id'], 0)
        art['_score'] = v
        calls.append(art['id'])
        return v
    return _score, calls


def _fake_d1(history_rows, pool_rows):
    def _query(sql):
        if 'DISTINCT n.id' in sql:            # get_history_articles (2차 D1 이력)
            return [dict(r) for r in history_rows]
        if "v2_tag IS NULL OR v2_tag = ''" in sql:   # 폴백 풀 조회 (1차 SQL)
            return [dict(r) for r in pool_rows]
        return []
    return _query


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    """sleep·D1 차단 + local 이력 파일을 tmp 로 — 실제 파일·네트워크를 만지지 않는다.

    sel.d1_query 를 안전값으로 고정한다: 재충원 1~3단계는 모듈 전역 d1_query 를
    쓰므로(주입 d1_query_func 는 2차·폴백 풀에만 쓰인다), 패치가 없으면 실제 D1
    조회가 나간다. 폴백 풀이 필요한 테스트는 _fake_d1 로 다시 패치한다.
    """
    monkeypatch.setattr(sel.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(sel, 'd1_query', lambda sql: [])
    hist = tmp_path / 'briefing_dedup.json'
    hist.write_text(json.dumps({'briefings': [], 'articles': []}, ensure_ascii=False),
                    encoding='utf-8')
    monkeypatch.setattr(briefing_dedup, 'HISTORY_PATH', hist)


# --------------------------------------------------------------- 2026-10-28 재현


def test_fallback_reproduces_20261028_case():
    """오늘 케이스 재현 — 신선 1건 이후 남은 2슬롯을 일반 뉴스 폴백으로 채운다.

    풀에 섞인 제외 대상(어제 Reddit 사건 재보도·프로바이더 행·기업마당 공고·
    [제외] 알림·같은 출처 중복)이 슬롯을 먹지 않는지 함께 본다.
    """
    history = [
        _his(57426, '엔타이어, AI 데이터 정리 도구 무료 공개',
             link='https://entata.com/news'),                      # 오늘 이미 실린 1건
        _his(57163, 'r/opensource bans AI generated content reviews',
             link='https://reddit.com/r/opensource'),              # 어제 Reddit 사건
    ]
    pool = [
        _pool(801, 'r/opensource bans AI generated content reviews',
              'Hacker News', '2026-10-28 06:00:00',
              link='https://reddit.com/r/opensource'),             # 재보도 → 2차 중복
        _pool(802, 'OpenRouter 무료 목록 갱신 — geminiexp 추가',
              'OpenRouter Free Models', '2026-10-28 06:30:00'),    # 프로바이더 행
        _pool(803, '2026년 AI 소기업 연구개발 지원사업 공고',
              '기업마당', '2026-10-28 05:00:00'),                   # 지원사업 공고
        _pool(804, '[제외] cat-jam-free — OpenCode Zen 무료 목록에서 제외',
              'OpenCode Zen', '2026-10-28 04:00:00'),              # [제외] 알림
        _pool(805, '조선업도 AI 도입 확산 — 표준 계약서 배포',
              NEWS1, '2026-10-27 20:00:00'),                       # 일반 뉴스 (7점)
        _pool(806, '국내 증권사 3곳, AI 리서치 어시스턴트 서비스 개시',
              NEWS2, '2026-10-28 01:00:00'),                       # 일반 뉴스 (9점)
        _pool(807, '교육(에듀테크) 스타트업 AI 과외 서비스 출시',
              NEWS1, '2026-10-28 03:00:00'),                       # 같은 출처 재등장
        _pool(808, 'AI 반도체 수주 증가 보도',
              'TechCrunch', '2026-10-28 07:00:00'),                # 5점 → (b) 후보
    ]
    score, calls = _scorer({'805': 7, '806': 9, '807': 6, '808': 5})
    picked = sel.fallback_fill_general(
        2, {'id:57426'}, {'인공지능신문'}, set(),
        _fake_d1(history, pool), score)

    ids = [a['id'] for a in picked]
    assert ids == ['806', '805'], ids          # (a) 점수순: 9점 → 7점
    assert '801' not in ids and '804' not in ids   # 재보도·[제외] 미반입
    assert '802' not in ids and '803' not in ids   # 프로바이더·공고 미반입
    assert '807' not in ids, ids               # 출처당 1건 — 805 가 NEWS1 슬롯을 씀
    assert set(calls) == {'805', '806', '807', '808'}, calls  # 차단분(801-804)은 채점 안 함


def test_fallback_fills_latest_when_scores_insufficient():
    """(b) 최신순 — 점수 후보가 부족하면 점수 무관 pub_date DESC 로 채운다.

    808(5점, 어제)보다 809(1점, 오늘)가 최신이므로 809 가 간다.
    """
    history = [_his(57426, '엔타이어, AI 데이터 정리 도구 무료 공개')]
    pool = [
        _pool(805, '조선업 AI 도입 확산 — 표준 계약서 배포',
              NEWS1, '2026-10-26 09:00:00'),   # 9점 → (a)에서 선정
        _pool(808, 'AI 반도체 수주 증가 보도',
              'TechCrunch', '2026-10-27 07:00:00'),  # 5점
        _pool(809, '로봇 청소년 시범 사업 시작 보도',
              NEWS2, '2026-10-28 07:00:00'),   # 1점
    ]
    score, _ = _scorer({'805': 9, '808': 5, '809': 1})
    picked = sel.fallback_fill_general(
        2, set(), set(), set(), _fake_d1(history, pool), score)

    ids = [a['id'] for a in picked]
    assert ids == ['805', '809'], ids   # (a) 9점 → (b) 최신순(809 > 808)


def test_fallback_dedups_same_event_within_batch():
    """3차 방어선 — 같은 사건(다른 매체)이 폴백 내에서 두 슬롯을 먹지 않는다.

    2차 filter_duplicates 는 '과거 이력'만 보고 배치 내부를 보지 않으므로,
    이 방어선은 fallback_fill_general 자체의 is_duplicate_article_strict 대조다.
    """
    history = []
    pool = [
        _pool(811, 'Kimi K2 joins OpenCode Zen free model list today',
              NEWS1, '2026-10-28 06:00:00'),
        _pool(812, 'Kimi K2 joins OpenCode Zen free model list for users',
              NEWS2, '2026-10-28 06:10:00'),   # 같은 사건 재보도
    ]
    score, _ = _scorer({'811': 9, '812': 8})
    picked = sel.fallback_fill_general(
        2, set(), set(), set(), _fake_d1(history, pool), score)

    ids = [a['id'] for a in picked]
    assert ids == ['811'], ids   # 같은 사건은 1건만


# ---------------------------------------------------------------- 1차 방어선 SQL


def test_get_general_fallback_news_sql_filters(monkeypatch):
    """SQL 1차 방어선 — 무료 태그 없음·프로바이더·공고·[제외]·브리핑 이력 제외."""
    seen = []
    monkeypatch.setattr(sel, 'd1_query', lambda sql: seen.append(sql) or [])
    rows = sel.get_general_fallback_news(sel.d1_query, exclude_ids=(57426,))
    sql = seen[0]
    assert rows == []

    assert "(v2_tag IS NULL OR v2_tag = '')" in sql
    assert "'OpenCode Zen'" in sql and "'NVIDIA NIM Free'" in sql      # 프로바이더 4종
    assert "'기업마당'" in sql and "'지식재산처'" in sql               # 공고 소스 명시 목록
    assert "title NOT LIKE '[제외]%'" in sql
    assert 'FROM briefing_items bi' in sql
    assert "b.status IN ('published', 'superseded')" in sql           # 브리핑 전체 이력
    assert 'id NOT IN (57426)' in sql                                  # 호출자 지정 제외
    assert 'ORDER BY id DESC' in sql and 'LIMIT 40' in sql             # 최신순 풀 상한


def test_is_announcement_source_suffix_guard():
    """2차 방어선 — 명시 목록 외 부처·자치단체 표기도 막는다."""
    assert sel._is_announcement_source('기업마당')
    assert sel._is_announcement_source('과학기술정보통신부')      # 접미 '부'
    assert sel._is_announcement_source('중소벤처기업부')
    assert sel._is_announcement_source('경기도')
    assert not sel._is_announcement_source(NEWS1)
    assert not sel._is_announcement_source('Hacker News')
    assert not sel._is_announcement_source('')
    assert not sel._is_announcement_source(None)


# ------------------------------------------------------------- select_top_articles


def test_select_top_articles_fallback_fills_three():
    """통합 — 클러스터에 신선 1건뿐이어도 allow_fallback=True 로 3건이 나온다.

    2026-10-28 실행과 동일 구조: 무료 태그 뉴스 1건(엔타이어) + 폴백 풀.
    """
    fresh = {'id': '57426', 'title': '엔타이어, AI 데이터 정리 도구 무료 공개',
             'original_title': '', 'description': '엔타이어 무료 공개',
             'link': 'https://entata.com/news', 'source': '인공지능신문',
             'pub_date': '2026-10-28 02:00:00', 'v2_tag': 'tool',
             'v2_pass': 1, '_score': 12}
    history = [_his(57426, '엔타이어, AI 데이터 정리 도구 무료 공개',
                    link='https://entata.com/news')]
    pool = [_pool(806, '국내 증권사 3곳, AI 리서치 어시스턴트 서비스 개시', NEWS2, '2026-10-28 01:00:00'),
            _pool(805, '조선업 AI 도입 확산 — 표준 계약서 배포', NEWS1, '2026-10-27 20:00:00')]
    score, _ = _scorer({'805': 7, '806': 9})

    picked = sel.select_top_articles({'v2': [fresh]}, 3, allow_fallback=True,
                                     d1_query_func=_fake_d1(history, pool),
                                     scorer=score)

    ids = [a['id'] for a in picked]
    assert ids == ['57426', '806', '805'], ids   # 3건 채움 + (a) 점수순


def test_select_top_articles_without_fallback_stays_short():
    """기본값(False) 회귀 — 기존 경로는 폴백 없이 있는 만큼만 선정한다."""
    fresh = {'id': '57426', 'title': '엔타이어, AI 데이터 정리 도구 무료 공개',
             'original_title': '', 'description': '', 'link': 'https://entata.com/news',
             'source': '인공지능신문', 'pub_date': '2026-10-28 02:00:00',
             'v2_tag': 'tool', 'v2_pass': 1, '_score': 12}

    picked = sel.select_top_articles({'v2': [fresh]}, 3)   # d1 쿼리 없음 — 네트워크 X

    assert [a['id'] for a in picked] == ['57426']          # 폴백 미동작 → 1건 (강제 없음)


# ------------------------------------------------------------------- 재충원 4단계


def test_fallback_skips_scoring_for_used_sources():
    """채점 전 출처 제외 — kept 출처와 같은 풀 행은 LLM 채점조차 하지 않는다.

    출처당 1건 규칙상 선정될 수 없는 행을 10건 채점 상한(FALLBACK_SCORE_LIMIT)에
    넣으면 살아있는 후보 볼륨이 줄어든다. 2026-10-28 소급 채우기 실측: 기존 1건
    출처(인공지능신문)와 같은 풀 행 13건이 채점 상한을 집어삼았다.
    """
    history = []
    pool = [
        _pool(820, 'AI 데이터 센터 수주 확대 보도', '인공지능신문', '2026-10-28 02:00:00'),
        _pool(821, '볼트, 온디바이스 AI 엔진 출시', '전자신문', '2026-10-28 01:30:00'),
    ]
    score, calls = _scorer({'820': 10, '821': 10})
    picked = sel.fallback_fill_general(
        1, set(), {'인공지능신문'}, set(), _fake_d1(history, pool), score)

    ids = [a['id'] for a in picked]
    assert ids == ['821'], ids
    assert calls == ['821'], calls   # 820(kept와 같은 출처)은 채점 안 함


def test_refill_tier4_fills_from_general_pool():
    """재충원 4단계 — 무료 풀 후보가 0건이어도 일반 뉴스 폴백으로 채운다.

    kept(이미 선정된 1건)는 batch_history 로 넘겨 폴백분과 배치 중복을 막는다.
    """
    kept = {'id': '57426', 'title': '엔타이어, AI 데이터 정리 도구 무료 공개',
            'original_title': '', 'description': '엔타이어 무료 공개',
            'link': 'https://entata.com/news', 'source': '인공지능신문',
            'pub_date': '2026-10-28 02:00:00', 'v2_tag': 'tool',
            'v2_pass': 1, '_score': 12}
    history = [_his(57426, '엔타이어, AI 데이터 정리 도구 무료 공개',
                    link='https://entata.com/news')]
    pool = [_pool(806, '국내 증권사 3곳, AI 리서치 어시스턴트 서비스 개시', NEWS2, '2026-10-28 01:00:00'),
            _pool(805, '조선업 AI 도입 확산 — 표준 계약서 배포', NEWS1, '2026-10-27 20:00:00'),
            _pool(801, 'r/opensource bans AI generated content reviews',
                  'Hacker News', '2026-10-28 06:00:00',
                  link='https://reddit.com/r/opensource')]      # 어제 재보도 → 차단
    score, _ = _scorer({'805': 7, '806': 9})

    out = sel.refill_after_dedup([kept], dropped=(), max_count=3,
                                 d1_query_func=_fake_d1(history, pool),
                                 pool=[], scorer=score)

    ids = [a['id'] for a in out]
    assert ids == ['57426', '806', '805'], ids   # 1건 + 폴백 2건 = 3건


# ----------------------------------------------------------------------- 유틸


def test_pub_ts_handles_mixed_formats():
    """RFC-2822(영문 매체)와 'YYYY-MM-DD HH:MM:SS'(국문 매체)가 같은 순간이면 같은 값."""
    rfc = sel._pub_ts({'pub_date': 'Tue, 27 Oct 2026 09:00:00 +0900'})
    kst = sel._pub_ts({'pub_date': '2026-10-27 09:00:00'})
    assert rfc == kst                       # 같은 순간 → 같은 epoch (형식 혼재 비교 가능)
    assert sel._pub_ts({'pub_date': '미정'}) == 0.0   # 파싱 불가 → 0 (최후순위)
    assert sel._pub_ts({}) == 0.0
    assert sel._pub_ts({'pub_date': '2026-10-28'}) > 0
