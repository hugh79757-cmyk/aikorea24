"""tests/test_pipe15_fallback_source_relax.py

AIK24-PIPE-15 회귀 테스트 — 폴백 (c) 단계: 출처 제약 완화.

2026-11-02 07:00 실측 (`scripts/pipeline_runner.log:93900-93912`):
    [폴백 후보 1/9] 6점 … [폴백 후보 9/9] 9점 …
    [폴백 a 점수순] [12점] AI챗봇 생활정보 검색 … (네이버뉴스)
    [폴백 a 점수순] [10점] 399달러 오리 로봇 … (전자신문)
    [폴백] 일반 뉴스 2건으로 슬롯 충원
    선정 2건 (요청 3건, 무료 풀·폴백 부족 — 재충원에서 추가 충원 시도)
    …
    [재충원] [폴백] 출처 이미 사용 (7건 채점 제외): 네이버뉴스, 전자신문
    ⚠️ 폴백 후에도 후보 부족 — 슬롯 1개 미충원 → 브리핑 0건

9개 후보 중 7개가 이미 쓴 2개 출처(네이버뉴스·전자신문)여서 (a)(b)가 2건에서 멈췄고,
빈 브리핑이 됐다. (c) 단계는 그 7건에서 남은 슬롯을 **점수순**(동점은 최신순)으로 채운다 —
"빈 브리핑(0건)보다는 같은 출처 2건이 낫다".

계약:
  1. (a) 점수 ≥ SCORE_MIN → (b) 최신순 → **그래도 부족하면 (c) blocked_by_source 에서 점수순**.
  2. (c) 는 오직 `len(picked) < needed` 일 때만 동작한다 — (a)/(b)로 충분하면 출처 제약은 유지된다.
  3. (c) 도 3차 방어선(배치 내부 중복, is_duplicate_article_strict)을 그대로 통과해야 한다.
  4. 점수 없는 후보(실제 운영: 폴백 풀은 D1 에서 새로 읽어 _score=None)는 0점으로 정렬되고
     동점 처리(pub_date DESC)로 최신이 먼저 온다 — 11-02 재충원 호출의 실제 동작.

오프라인 보장: D1 은 SQL 마커로 라우팅하는 스텁, local 이력은 tmp 파일. LLM 채점은
사전 점수(_score)로 대체해 호출되지 않는다 (scorer 스텁이 호출되면 기록만 남긴다).
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import briefing_dedup  # noqa: E402
import auto_news_selector as sel  # noqa: E402

NAVER = '네이버뉴스'      # 11-02 이미 사용된 출처 1
ETNEWS = '전자신문'       # 11-02 이미 사용된 출처 2
MISC1 = 'AI타임스'
MISC2 = 'ZDNet Korea'
DAY = '2026-11-02'


def _his(nid, title, link=''):
    """D1 이력 행 (get_history_articles 컬럼: id/title/original_title/description/link)."""
    return {'id': str(nid), 'title': title, 'original_title': '',
            'description': '', 'link': link}


def _row(nid, source, pub, score=None, title=None):
    """폴백 풀 행 — 판정에 필요한 키 + 선택적 _score."""
    title = title or f'{source} {nid} 기사'
    return {'id': str(nid), 'title': title, 'original_title': '',
            'description': title, 'link': f'https://example.com/{nid}',
            'source': source, 'pub_date': pub, 'v2_tag': None, 'v2_pass': None,
            '_score': score}


def _fake_d1(history_rows, pool_rows):
    """이력 조회(DISTINCT n.id)와 폴백 풀 조회를 라우팅하는 D1 스텁."""
    def _query(sql):
        if 'DISTINCT n.id' in sql:
            return [dict(r) for r in history_rows]
        if "v2_tag IS NULL OR v2_tag = ''" in sql:
            return [dict(r) for r in pool_rows]
        return []
    return _query


@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    """sleep·D1·local 이력 차단 (실제 파일·네트워크 무관)."""
    monkeypatch.setattr(sel.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(sel, 'd1_query', lambda sql: [])
    monkeypatch.setattr(sel, 'score_helpfulness', lambda art: art.get('_score') or 0)
    hist = tmp_path / 'briefing_dedup.json'
    hist.write_text(json.dumps({'briefings': [], 'articles': []}, ensure_ascii=False),
                    encoding='utf-8')
    monkeypatch.setattr(briefing_dedup, 'HISTORY_PATH', hist)


# --------------------------------------------------------------- 11-02 재현 (검증 b)


def test_c_stage_fills_third_slot_from_blocked_sources_by_score():
    """11-02 재현 — 9개 후보 · 2개 출처 이미 사용 · (a)(b) 2건 → (c)가 3번째를 점수순으로.

    후보 구성(실측 로그의 점수 분포를 따름):
      - 다른 출처 2건: AI타임스 9점 / ZDNet Korea 4점  → (a) 1건 + (b) 1건
      - 이미 쓴 출처 7건: 네이버뉴스·전자신문 (점수 8·7·6·6·5·3·2) → (c) 점수순 1건
    """
    pool = [
        # (a)(b) 대상 — 아직 안 쓴 출처
        _row('misc-a', MISC1, f'{DAY} 06:00:00', 9, title='AI 반도체 수출 규제 완화 발표'),
        _row('misc-b', MISC2, f'{DAY} 05:00:00', 4, title='로봇 물류 자동화 투자 확대'),   # < SCORE_MIN → (b) 최신순
        # 이미 쓴 출처 — 출처당 1건 규칙으로 (a)(b) 에서 제외된다
        _row('nv-1', NAVER, f'{DAY} 06:30:00', 8, title='의료 AI 진단 보험 적용 논의'),
        _row('nv-2', NAVER, f'{DAY} 04:00:00', 7, title='교육 현장 생성형 AI 도입 시범'),
        _row('nv-3', NAVER, f'{DAY} 03:00:00', 6, title='금융권 이상거래 탐지 고도화'),
        _row('nv-4', NAVER, f'{DAY} 02:00:00', 5, title='스마트팜 수확 예측 정확도 개선'),
        _row('et-1', ETNEWS, f'{DAY} 01:00:00', 6, title='전기차 배터리 재활용 설비 증설'),
        _row('et-2', ETNEWS, f'{DAY} 00:30:00', 3, title='항공우주 부품 국산화 성과'),
        _row('et-3', ETNEWS, f'{DAY} 00:00:00', 2, title='조선 LNG 운반선 수주 확대'),
    ]
    picked = sel.fallback_fill_general(
        3, set(), {NAVER, ETNEWS}, set(), _fake_d1([], pool), lambda art: 0)

    ids = [a['id'] for a in picked]
    # (a) 9점 → (b) 남은 후보 최신순(4점) → (c) 출처완화 점수순(8점)
    assert ids == ['misc-a', 'misc-b', 'nv-1'], ids
    assert len(picked) == 3, len(picked)
    assert picked[-1]['source'] == NAVER, picked[-1]['source']   # 이미 쓴 출처에서 채움
    # (c) 가 최고 점수를 골랐는지 — 7점(nv-2)이 아니라 8점(nv-1)
    assert picked[-1]['_score'] == 8, picked[-1]['_score']


def test_c_stage_uses_latest_when_blocked_rows_have_no_score():
    """11-02 재충원 호출의 실제 조건 — 폴백 풀은 _score 가 없어 0점 동점 → 최신순.

    실측 로그: "[폴백] 출처 이미 사용 (7건 채점 제외): 네이버뉴스, 전자신문" 뒤
    채점 로그가 없고 슬롯 1개가 미충원이었다. (c) 는 이 7건에서 최신 1건을 채운다.
    """
    pool = [
        _row('nv-old', NAVER, f'{DAY} 01:00:00'),          # _score=None
        _row('nv-new', NAVER, f'{DAY} 06:40:00'),          # 가장 최신
        _row('et-mid', ETNEWS, f'{DAY} 05:00:00'),
        _row('et-old', ETNEWS, f'{DAY} 00:10:00'),
        _row('nv-mid', NAVER, f'{DAY} 03:20:00'),
        _row('et-mid2', ETNEWS, f'{DAY} 04:00:00'),
        _row('nv-2nd', NAVER, f'{DAY} 06:10:00'),
    ]
    picked = sel.fallback_fill_general(
        1, set(), {NAVER, ETNEWS}, set(), _fake_d1([], pool), lambda art: 0)

    assert [a['id'] for a in picked] == ['nv-new'], [a['id'] for a in picked]


def test_c_stage_still_respects_batch_dedup():
    """(c) 도 3차 방어선을 유지한다 — 배치에서 이미 다룬 사건은 출처를 풀어도 반입하지 않는다."""
    dup_title = 'AI챗봇 생활정보 검색, 질문법이 답이다'
    batch = [_row('kept-1', NAVER, f'{DAY} 06:00:00', 12, title=dup_title)]
    batch[0]['link'] = 'https://example.com/nv-top'      # 아래 nv-top 과 같은 링크
    pool = [
        _row('nv-top', NAVER, f'{DAY} 07:00:00', 9, title=dup_title),   # 최고점이지만 배치 중복
        _row('nv-ok', NAVER, f'{DAY} 02:00:00', 3),
        _row('et-ok', ETNEWS, f'{DAY} 01:00:00', 2),
    ]
    pool[0]['link'] = 'https://example.com/nv-top'

    picked = sel.fallback_fill_general(
        1, set(), {NAVER, ETNEWS}, set(), _fake_d1([], pool),
        lambda art: 0, batch_history=batch)

    assert [a['id'] for a in picked] == ['nv-ok'], [a['id'] for a in picked]
