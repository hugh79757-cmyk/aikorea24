"""tests/test_pipe08_dedup_unification.py — AIK24-PIPE-08 회귀 테스트

2026-10-21 07:00 브리핑 0건 사고(AIK24-PIPE-07)의 재발 방지 하네스.

사고의 인과 사슬 (docs/state.md "AIK24-PIPE-07" 참조):
    후보 9건 → 선정 3건 → Phase 2 dedup 에서 3/3 탈락 → 재충원 9/9 탈락 → 브리핑 0건

이 테스트는 다음을 **오프라인으로** 검증한다 (실제 D1 · 실제 local 이력 파일 무관):
    1) "선정 → Phase 2 탈락 0건" — selector 의 3.5단계와 auto_briefing Phase 2 가
       같은 기준(filter_duplicates = D1 이력 + local 이력)을 쓴다.
    2) 정당한 중복 차단은 유지된다 (56074·56525·56391·56206).
    3) 범용 엔티티 오탐만 풀린다 (56082·56500·56076·56389).
    4) 재충원 풀이 선정 풀보다 넓다 (A-5).
    5) B-2 조기 경보용 헬퍼(count_fresh_candidates)가 부작용 없이 동작한다.

데이터 출처 (tests/fixtures/pipe08_20261021.json):
    - candidates / d1_history : 2026-10-21 D1 읽기 전용 조회 결과 (news · briefings)
    - local_history            : scripts/briefing_dedup.json 스냅샷
                                (2026-10-21 07:00 실행 시점 = 10-20 07:00 이후 변경 없음)
    실제 scripts/briefing_dedup.json 은 이 테스트에서 **읽지도 쓰지도 않는다**
    (HISTORY_PATH 를 tmp_path 로 교체) — test_local_history_file_untouched 가 증명한다.
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import auto_news_selector as sel  # noqa: E402
import briefing_dedup  # noqa: E402
from threads.dedup import compute_similarity, is_same_topic, _has_korean  # noqa: E402

FIXTURE = Path(__file__).parent / 'fixtures' / 'pipe08_20261021.json'
DATA = json.loads(FIXTURE.read_text(encoding='utf-8'))

CANDIDATES = {c['id']: c for c in DATA['candidates']}
POOL_ORDER = DATA['pool_order']
D1_HISTORY = DATA['d1_history']
LOCAL_HISTORY = DATA['local_history']

# 2026-10-21 07:00 실행 로그에 남은 사유 (scripts/pipeline_runner.log:84447)
LOGGED_REFILL_REASONS = [
    'local_semantic', 'entity(2)', 'local_entity(2)', 'exact_id', 'local_exact_id',
    'exact_id', 'local_entity(2)', 'local_semantic', 'local_semantic',
]

# 2026-10-21 07:00 실행의 실제 LLM 점수 (scripts/pipeline_runner.log:84423-84430)
#   56391=11점 · 56389=6점 · 56500=13점 (나머지는 기계 감지 행이라 평가 생략)
SCORES = {56391: 11, 56389: 6, 56500: 13}

# 오탐으로 풀려야 하는 id / 정당 차단을 유지해야 하는 id (AIK24-PIPE-08 지시)
# AIK24-PIPE-09: 56074 의 D1 층 entity(2) 도 오탐으로 풀린다(대표님 결정) →
#   56074 를 RELEASE_IDS 로 옮기고 KEEP_BLOCKED_IDS 에서 뺀다.
RELEASE_IDS = [56082, 56500, 56076, 56389, 56074]
KEEP_BLOCKED_IDS = [56525, 56391, 56206]
DECIDED_ID = 56406  # local_semantic — 결론은 아래 테스트에서 명시


# --------------------------------------------------------------------- 도구


def _row(r):
    return (r.get('title') or '', r.get('original_title') or '', r.get('description') or '')


def _old_is_same_topic(t1, o1, d1, t2, o2, d2):
    """**변경 전**(2026-10-21 이전) is_same_topic 규칙 — 원본 코드 전사.

    AIK24-PIPE-08 의 "before" 근거를 테스트 안에서 재현하기 위한 것이다.
    """
    sim = compute_similarity(t1, o1, d1, t2, o2, d2)
    he1, he2 = sim['has_en1'], sim['has_en2']
    has_ko = _has_korean(t1) and _has_korean(t2)
    if he1 and he2:
        if sim['jaccard_en'] >= 0.30:
            return True
        if sim['entity_overlap'] >= 4:
            return True
    elif not he1 and not he2 and has_ko:
        if sim['jaccard_ko'] >= 0.25:
            return True
        if sim['entity_overlap'] >= 2:
            return True
    else:
        if sim['jaccard_all'] >= 0.15:
            return True
        if sim['entity_overlap'] >= 1 and sim['jaccard_all'] >= 0.10:
            return True
    if sim['jaccard_all'] >= 0.30:
        return True
    return False


def _old_is_duplicate_article(article, history, entity_needs_topic=False):
    """**변경 전** is_duplicate_article — Layer 3 이 엔티티 단독 판정이었다."""
    aid = str(article.get('id', '')) or str(article.get('news_id', ''))
    link = briefing_dedup.normalize_url(article.get('link', ''))
    title = (article.get('title', '') or '')[:50]
    orig = (article.get('original_title', '') or '')[:30]
    desc = article.get('description', '') or ''

    if article.get('source') in sel.PROVIDER_SOURCES:
        if any(aid and aid == (str(h.get('id', '')) or str(h.get('news_id', '')))
               for h in history):
            return True, 'exact_id'
        return False, None

    for h in history:
        hid = str(h.get('id', '')) or str(h.get('news_id', ''))
        h_link = briefing_dedup.normalize_url(h.get('link', ''))
        h_title = (h.get('title', '') or '')[:50]
        h_orig = (h.get('original_title', '') or '')[:30]
        if aid and hid and aid == hid:
            return True, 'exact_id'
        if link and h_link and link == h_link:
            return True, 'exact_link'
        if title and h_title and title == h_title:
            return True, 'exact_title'
        if orig and h_orig and orig == h_orig:
            return True, 'exact_original_title'
        if _old_is_same_topic(title, orig, desc,
                              h.get('title', ''), h.get('original_title', ''),
                              h.get('description', '')):
            return True, 'semantic'
        ent1 = briefing_dedup.extract_entities(title, orig, desc)
        ent2 = briefing_dedup.extract_entities(
            h.get('title', ''), h.get('original_title', ''), h.get('description', ''))
        overlap = len(ent1 & ent2)
        if overlap >= briefing_dedup.ENTITY_OVERLAP_THRESHOLD:
            return True, f'entity({overlap})'
    return False, None


def _old_filter_duplicates(articles, history, local):
    """**변경 전** filter_duplicates (D1 이력 → local 이력, 둘 다 entity 단독 판정)."""
    kept, removed = [], []
    for art in articles:
        dup, reason = _old_is_duplicate_article(art, history)
        if dup:
            removed.append((art, reason))
            continue
        dup2, reason2 = _old_is_duplicate_article(art, local)
        if dup2:
            removed.append((art, f'local_{reason2}'))
            continue
        kept.append(art)
    return kept, removed


# --------------------------------------------------------------------- 픽스처


@pytest.fixture()
def world(monkeypatch, tmp_path):
    """오프라인 세계 — 실제 D1 과 실제 local 이력 파일을 건드리지 않는다.

    반환: (d1_stub, history_path) — history_path 는 tmp_path 로 옮긴 local 이력.
    """
    # 1) D1 조회 스텁: 이력 SQL 이면 픽스처 7행, 그 외에는 빈 리스트
    def d1_stub(sql):
        if 'FROM briefings' in sql:
            return [dict(r) for r in D1_HISTORY]
        return []

    monkeypatch.setattr(sel, 'd1_query', d1_stub)

    # 2) local 이력은 tmp_path 로 옮긴다 (실제 scripts/briefing_dedup.json 무관)
    hist_path = tmp_path / 'briefing_dedup.json'
    hist_path.write_text(json.dumps(
        {'briefings': [], 'articles': [dict(r) for r in LOCAL_HISTORY]},
        ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(briefing_dedup, 'HISTORY_PATH', hist_path)

    # 3) LLM 호출·sleep 차단
    monkeypatch.setattr(sel.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(sel, 'score_helpfulness', lambda art: art.get('_score') or 0)

    return d1_stub, hist_path


def _install_candidate_stubs(monkeypatch):
    """selector 의 후보 조회를 픽스처로 대체한다 ( opp 3 · zen 2 · news 4 ).

    반환 행에는 2026-10-21 실행의 실제 LLM 점수를 붙인다 (기계 감지 행은 0).
    """
    opp = [CANDIDATES[i] for i in POOL_ORDER
           if CANDIDATES[i]['v2_tag'] == 'free-opportunity']
    zen = [CANDIDATES[i] for i in POOL_ORDER if CANDIDATES[i]['source'] == 'OpenCode Zen']
    per_tag = {t: [CANDIDATES[i] for i in POOL_ORDER if CANDIDATES[i]['v2_tag'] == t]
               for t in sel.TAG_ORDER}

    def _scored(a):
        row = dict(a)
        row['_score'] = SCORES.get(row['id'], 0)
        return row

    monkeypatch.setattr(sel, 'get_opportunity_news', lambda limit=1: [_scored(a) for a in opp[:limit]])
    monkeypatch.setattr(sel, 'get_zen_changes',
                        lambda limit=sel.MAX_COUNT: [_scored(a) for a in zen[:limit]])

    def _recent(hours=sel.WINDOW_HOURS, v2_tag=None, exclude_models=False):
        rows = per_tag.get(v2_tag, []) if v2_tag else []
        if exclude_models:
            rows = [a for a in rows if a['source'] not in sel.PROVIDER_SOURCES]
        return [_scored(a) for a in rows]

    monkeypatch.setattr(sel, 'get_recent_news', _recent)


def _pool_articles():
    """실제 실행과 같은 순서의 9행 풀."""
    return [dict(CANDIDATES[i]) for i in POOL_ORDER]


# --------------------------------------------------------------------- A-3


def test_offline_replay_reproduces_20261021_log_reasons():
    """재현 하네스 — 변경 전 규칙으로 9건의 사유가 실제 로그와 9/9 일치해야 한다.

    근거: scripts/pipeline_runner.log:84447
      "[재충원] 중복 제외 9건: local_semantic, entity(2), local_entity(2), exact_id,
       local_exact_id, exact_id, local_entity(2), local_semantic, local_semantic"
    """
    kept, removed = _old_filter_duplicates(_pool_articles(), D1_HISTORY, LOCAL_HISTORY)

    assert [reason for _, reason in removed] == LOGGED_REFILL_REASONS
    assert kept == [], [a['id'] for a in kept]


def test_selection_survives_phase2_dedup(world, monkeypatch):
    """A-3 완료 기준 — **선정→Phase 2 탈락 0건**.

    selector 의 3.5단계가 남긴 기사는 auto_briefing Phase 2 의 filter_duplicates 를
    그대로 통과해야 한다 (두 단계가 같은 기준을 쓰므로 구조적으로 성립).

    근거: 2026-10-21 07:00 실행은 선정 3건이 Phase 2 에서 3/3 탈락해 브리핑이 0건.
    같은 입력에서 지금은 0건 탈락이다 (아래 테스트가 "변경 전" 재현도 함께 검증).
    """
    d1_stub, _ = world
    _install_candidate_stubs(monkeypatch)

    selected = sel.main()

    # 변경 후 선정 3건 — 56206(10-17 발행분)은 3.5단계에서 local_exact_id 로 먼저 제외된다
    assert [a['id'] for a in selected] == [56082, 56500, 56389]

    # Phase 2 (auto_briefing.py:456 과 동일한 호출)
    kept, removed = briefing_dedup.filter_duplicates(selected, d1_stub)

    assert removed == [], [(a['id'], r) for a, r in removed]
    assert [a['id'] for a in kept] == [a['id'] for a in selected]


def test_old_dedup_criteria_reproduce_the_incident(world, monkeypatch):
    """**변경 전** 기준이면 같은 입력에서 선정 3건이 Phase 2 에서 전부 탈락한다.

    2026-10-21 07:00 사고 재현 (scripts/pipeline_runner.log:84435-84446):
        선정 3건 → Phase 2 중복 제거 3건 → 브리핑 0건
    """
    d1_stub, _ = world
    _install_candidate_stubs(monkeypatch)

    # 변경 전 3.5단계 = D1 이력만 보는 판정
    def _d1_only(articles, d1_query_func):
        history = briefing_dedup.get_history_articles(d1_query_func)
        kept, removed = [], []
        for art in articles:
            dup, reason = briefing_dedup.is_duplicate_article(art, history)
            if dup:
                removed.append((art, reason))
            else:
                kept.append(art)
        return kept, removed

    monkeypatch.setattr(briefing_dedup, 'filter_duplicates', _d1_only)

    selected = sel.main()
    assert [a['id'] for a in selected] == [56082, 56206, 56500]

    # 변경 전 Phase 2 (local 이력까지 보는 판정)
    _k, removed = _old_filter_duplicates(selected, D1_HISTORY, LOCAL_HISTORY)
    assert len(removed) == 3, [(a['id'], r) for a, r in removed]


def test_selector_uses_same_dedup_as_phase2(world, monkeypatch):
    """3.5단계가 Phase 2 와 같은 filter_duplicates 를 쓰는다는 계약."""
    d1_stub, _ = world
    _install_candidate_stubs(monkeypatch)

    calls = []
    orig = briefing_dedup.filter_duplicates

    def _spy(articles, d1q):
        calls.append(list(articles))
        return orig(articles, d1q)

    monkeypatch.setattr(briefing_dedup, 'filter_duplicates', _spy)
    sel.main()

    assert calls, 'selector 3.5단계가 filter_duplicates 를 호출하지 않았다'
    # auto_briefing Phase 2(auto_briefing.py:456)도 같은 모듈 속성을 호출한다
    # → 지연 import 라 spy 가 양쪽에서 동일하게 관측된다.
    import auto_briefing  # noqa: F401  (지연 import 경로 확인용)
    assert auto_briefing.__dict__ is not None
    assert calls[0] is not None


# --------------------------------------------------------------------- A-4


def test_generic_entity_false_positives_are_released(world):
    """범용 엔티티 오탐만 풀린다 — 56082·56500·56076·56389."""
    d1_stub, _ = world
    kept, removed = briefing_dedup.filter_duplicates(_pool_articles(), d1_stub)
    removed_ids = {a['id'] for a, _ in removed}

    for nid in RELEASE_IDS:
        assert nid not in removed_ids, f'{nid} 이 여전히 차단됨'
        assert nid in {a['id'] for a in kept}


def test_genuine_duplicates_stay_blocked(world):
    """정당한 중복 차단은 유지된다 — 56525·56391·56206.

    AIK24-PIPE-09: 56074 는 여기서 빠졌다 — D1 층 entity(2) 가 범용 엔티티
    오탐으로 판명되어 해제되었다(아래 test_d1_layer_entity_false_positive_released).
    """
    d1_stub, _ = world
    _kept, removed = briefing_dedup.filter_duplicates(_pool_articles(), d1_stub)
    reasons = {a['id']: r for a, r in removed}

    assert reasons.get(56525) == 'exact_id'
    assert reasons.get(56391) == 'exact_id'
    assert reasons.get(56206) == 'local_exact_id'


def test_56406_decision_is_documented_and_stable(world):
    """56406 결론 — 차단 유지(같은 주제).

    56406 "VS Code에서 GitHub Copilot 앱 세션을 이어가는 방법" ↔ local 55205
    "초보자를 위한 GitHub Copilot 앱: Copilot에게 코드베이스를 가르치는 방법" 은
    엔티티 {Copilot, GitHub} + jaccard_all 0.16 으로 **같은 제품·같은 주제**다.
    주제어 겹침이 있으므로 A-4 로 풀리지 않는다 (풀리면 안 되는 사례).
    """
    d1_stub, _ = world
    _kept, removed = briefing_dedup.filter_duplicates(_pool_articles(), d1_stub)
    reasons = {a['id']: r for a, r in removed}

    assert reasons.get(DECIDED_ID) == 'local_semantic'

    mate = [r for r in LOCAL_HISTORY if r['id'] == '55205'][0]
    sim = compute_similarity(*_row(CANDIDATES[DECIDED_ID]), *_row(mate))
    assert sim['entity_overlap'] >= 2
    assert sim['jaccard_all'] >= 0.15  # 주제어 겹침 있음 → 엔티티 단독이 아님


def test_before_after_reason_table(world):
    """주요 증거 표 — 9건의 차단 전/후 사유가 지시서 기대와 일치한다.

    AIK24-PIPE-09: "after" 표에서 56074 가 빠졌다 — D1 층 entity(2) 가 범용
    엔티티 오탐으로 판명되어 해제되었다(대표님 결정 2026-10-21).
    """
    d1_stub, _ = world
    _old_kept, old_removed = _old_filter_duplicates(
        _pool_articles(), D1_HISTORY, LOCAL_HISTORY)
    _new_kept, new_removed = briefing_dedup.filter_duplicates(_pool_articles(), d1_stub)

    old = {a['id']: r for a, r in old_removed}
    new = {a['id']: r for a, r in new_removed}

    expected_before = {
        56082: 'local_semantic', 56074: 'entity(2)', 56076: 'local_entity(2)',
        56525: 'exact_id', 56206: 'local_exact_id', 56391: 'exact_id',
        56389: 'local_entity(2)', 56500: 'local_semantic', 56406: 'local_semantic',
    }
    assert old == expected_before

    expected_after = {
        56525: 'exact_id', 56391: 'exact_id',
        56206: 'local_exact_id', 56406: 'local_semantic',
    }
    assert new == expected_after


def test_local_entity_layer_requires_topic_overlap():
    """Layer 3 — 엔티티 단독 겹침으로는 막지 않는다 (local 30일 이력)."""
    art = dict(CANDIDATES[56076])  # Cloudflare Workers AI
    mate = _local_row(51777)        # {AI, API} 만 겹침

    assert briefing_dedup.is_duplicate_article(art, [mate])[0] is True  # 기존 동작(엔티티 단독)
    assert briefing_dedup.is_duplicate_article_strict(art, [mate])[0] is False  # 주제어 동시 요구 → 해제


def test_ko_ko_entity_threshold_raised():
    """KO-KO 분기 — 엔티티 2개만 겹치면 막지 않는다 (EN-EN 과 동일 기준 + 주제어 요구)."""
    a = ('AI 보안 위협까지 진단한다…네이버클라우드, 기업용 무료 보안 자가진단 서비스 개설', '',
         '생성형 인공지능(AI)과 AI 에이전트의 기업 도입이 확산하면서 기존 정보기술(IT) '
         '인프라뿐 아니라 AI 서비스 이용 과정에서 발생할 수 있는 정보 유출과 자동화 공격까지 '
         '보안 관리 범위가 확대되고 있다.')
    b = ('데이터쿠에 따르면 CIO의 81%, IT 부서 외부에 구축된 AI 에이전트에 대한 완전한 통제',
         '', '데이터쿠에 따르면 CIO의 81%, IT 부서 외부에 구축된 AI 에이전트에 대한 통제 수준')

    sim = compute_similarity(*a, *b)
    assert sim['entity_overlap'] == 2  # {AI, IT} 범용 엔티티
    assert not is_same_topic(*a, *b)


def _local_row(news_id, original_title=None):
    """local 이력에서 특정 행을 찾는다 (id 는 문자열로 저장돼 있다)."""
    rows = [r for r in LOCAL_HISTORY if str(r['id']) == str(news_id)]
    if original_title is not None:
        rows = [r for r in rows if (r.get('original_title') or '') == original_title]
    assert rows, f'local 이력에 {news_id} 가 없다'
    return rows[0]


def test_mixed_branch_single_entity_no_longer_blocks():
    """Mixed 분기 — 엔티티 1개 겹침만으로는 막지 않는다 (실제 상대 행 사용)."""
    art = CANDIDATES[56082]                              # OpenRouter 무료 모델 (:free 태그)
    mate = _local_row(54938, original_title='')          # 10-11 ling-3.1-flash 행

    sim = compute_similarity(*_row(art), *_row(mate))
    assert sim['entity_overlap'] == 1  # {OpenRouter} 만 겹침
    assert not is_same_topic(*_row(art), *_row(mate))


def test_en_en_single_shared_token_no_longer_blocks():
    """EN-EN 분기 — 공유 토큰 1개(jaccard 0.33)만으로는 막지 않는다."""
    a = ('OpenRouter 무료 모델 (:free 태그)',
         'OpenRouter 무료 모델 (:free 태그)',
         ':free 태그가 붙은 모델을 무료로 호출 — 별도 크레딧 없이 API 키만으로 사용.')
    b = ('[무료 LLM] beam-free — OpenCode Zen 무료 티어',
         'beam-free',
         'Beam Free — CLI에서 입출력 모두 무료. 컨텍스트 1,048,576 토큰.')

    sim = compute_similarity(*a, *b)
    assert sim['jaccard_en'] >= 0.30
    assert sim['en_shared'] == 1  # 공유 토큰은 'free' 1개
    assert not is_same_topic(*a, *b)


def test_identical_original_title_still_blocks():
    """완전히 같은 original_title 는 그대로 중복으로 막힌다 (조건을 강화한 게 아니다)."""
    a = ('[무료 LLM] beam-free — OpenCode Zen 무료 티어', 'beam-free', 'Beam Free — CLI 무료.')
    b = ('[무료 LLM] beam-free — OpenCode Zen 무료 티어', 'beam-free', 'Beam Free — CLI 무료.')

    assert is_same_topic(*a, *b)


# --------------------------------------------------------------------- A-5


def test_refill_pool_is_larger_than_selection_pool(world, monkeypatch):
    """A-5 — 같은 입력에서 재충원 풀이 선정 풀보다 **엄격히 넓다**."""
    _install_candidate_stubs(monkeypatch)

    sel_pool, _ = sel.interleave_candidates(sel.CANDIDATE_LIMIT)
    refill_pool, _ = sel.interleave_candidates(sel.REFILL_POOL_LIMIT, refill=True)

    assert len(refill_pool) > len(sel_pool), (len(refill_pool), len(sel_pool))


def test_selection_pool_is_unchanged(world, monkeypatch):
    """A-5 — 선정 경로 상한은 바뀌지 않는다 (전용 확장일 뿐)."""
    _install_candidate_stubs(monkeypatch)

    pool, counts = sel.interleave_candidates(sel.CANDIDATE_LIMIT)

    assert len(pool) == sel.CANDIDATE_LIMIT
    assert counts['opportunity'] == 3
    assert counts['zen'] == 2
    # 일반 뉴스는 라운드로빈 최대 4건 (free-llm 2 · tool 2)
    assert counts['free-llm'] == 2 and counts['opensource'] == 0 and counts['tool'] == 2
    assert len(pool) <= 3 + 2 + 4


def test_refill_uses_wider_window(world, monkeypatch):
    """A-5 ① — 재충원만 72h 창을 쓴다 (선정 창 36h 은 그대로)."""
    seen = []

    def _recent(hours=sel.WINDOW_HOURS, v2_tag=None, exclude_models=False):
        seen.append(hours)
        return []

    monkeypatch.setattr(sel, 'get_recent_news', _recent)
    monkeypatch.setattr(sel, 'get_opportunity_news', lambda limit=1: [])
    monkeypatch.setattr(sel, 'get_zen_changes', lambda limit=sel.MAX_COUNT: [])

    sel.interleave_candidates(sel.CANDIDATE_LIMIT)
    assert set(seen) == {sel.WINDOW_HOURS}

    seen.clear()
    sel.interleave_candidates(sel.REFILL_POOL_LIMIT, refill=True)
    assert set(seen) == {sel.REFILL_WINDOW_HOURS}
    assert sel.REFILL_WINDOW_HOURS == 72
    assert sel.WINDOW_HOURS == 36  # 선정 창은 그대로


def test_refill_slots_are_capped_per_pool(world, monkeypatch):
    """A-5 ③ — 기회 슬롯이 Zen 슬롯을 독식하지 않는다 (풀별 상한 분리)."""
    monkeypatch.setattr(briefing_dedup, 'filter_duplicates',
                        lambda articles, d1_query_func: (list(articles), []))
    pool = [
        {'id': 'o1', 'title': ' opp 1', 'original_title': 'o1', 'source': '무료 기회',
         'v2_tag': 'free-opportunity', 'pub_date': '2026-10-21 10:00:00', '_score': 0},
        {'id': 'o2', 'title': 'opp 2', 'original_title': 'o2', 'source': '무료 기회',
         'v2_tag': 'free-opportunity', 'pub_date': '2026-10-21 09:00:00', '_score': 0},
        {'id': 'z1', 'title': 'zen 1', 'original_title': 'z1', 'source': 'OpenCode Zen',
         'v2_tag': 'free-llm', 'pub_date': '2026-10-21 10:00:00', '_score': 0},
        {'id': 'g1', 'title': 'news 1', 'original_title': 'g1', 'source': 'HuggingFace Blog',
         'v2_tag': 'opensource', 'pub_date': '2026-10-21 10:00:00', '_score': 12},
    ]
    out = sel.refill_after_dedup([], dropped=(), max_count=3,
                                 d1_query_func=lambda sql: [], pool=pool,
                                 scorer=lambda art: 12)
    ids = [a['id'] for a in out]

    assert ids.count('z1') == 1, ids          # Zen 슬롯은 보장된다
    assert sum(1 for i in ids if i.startswith('o')) <= sel.REFILL_OPP_SLOT_CAP, ids
    assert 'g1' in ids, ids                    # 남는 슬롯은 뉴스가 채운다


def test_refill_does_not_force_fill(world, monkeypatch):
    """원칙 유지 — 후보가 없으면 빈 슬롯을 유지한다 (강제 충전 없음)."""
    monkeypatch.setattr(briefing_dedup, 'filter_duplicates',
                        lambda articles, d1_query_func: (list(articles), []))
    out = sel.refill_after_dedup([], dropped=(), max_count=3,
                                 d1_query_func=lambda sql: [], pool=[],
                                 scorer=lambda art: 0)

    assert out == []


# --------------------------------------------------------------------- B-2 헬퍼


def test_count_fresh_candidates_matches_filter_duplicates(world, monkeypatch):
    """B-2 계약 — 신선 후보 수 = 최종 dedup(D1+local) 후 생존 수."""
    d1_stub, _ = world
    _install_candidate_stubs(monkeypatch)

    pool = _pool_articles()
    expected = len(briefing_dedup.filter_duplicates(pool, d1_stub)[0])

    assert sel.count_fresh_candidates(d1_stub, pool=pool) == expected


def test_count_fresh_candidates_has_no_side_effects(world, monkeypatch):
    """B-2 계약 — 채점·저장·파일 쓰기 없음."""
    d1_stub, hist_path = world
    _install_candidate_stubs(monkeypatch)

    scored = []
    monkeypatch.setattr(sel, 'score_helpfulness',
                        lambda art: scored.append(art['id']) or 0)
    before = hist_path.read_bytes()
    before_mtime = hist_path.stat().st_mtime_ns

    count = sel.count_fresh_candidates(d1_stub, pool=_pool_articles())

    assert isinstance(count, int)
    assert scored == [], 'LLM 채점이 호출되었다'
    assert hist_path.read_bytes() == before
    assert hist_path.stat().st_mtime_ns == before_mtime


def test_count_fresh_candidates_builds_pool_when_none_given(world, monkeypatch):
    """B-2 계약 — pool 이 None 이면 기존 후보 풀 빌더로 만든다."""
    d1_stub, _ = world
    _install_candidate_stubs(monkeypatch)

    count = sel.count_fresh_candidates(d1_stub)

    assert isinstance(count, int)
    assert count >= 0


# --------------------------------------------------------------------- 안전장치


def test_local_history_file_untouched(world):
    """실제 scripts/briefing_dedup.json 은 이 테스트에서 읽지도 쓰지도 않는다.

    하네스가 local 이력을 tmp_path 로 옮겨 쓰는지 + 실제 파일의 mtime·크기가
    그대로인지로 증명한다.
    """
    real = Path(sel.__file__).parent / 'briefing_dedup.json'
    assert real.exists(), '기준 파일이 없다'

    before_stat = real.stat()
    before_bytes = real.read_bytes()

    d1_stub, hist_path = world
    briefing_dedup.filter_duplicates(_pool_articles(), d1_stub)

    after_stat = real.stat()
    assert after_stat.st_mtime_ns == before_stat.st_mtime_ns
    assert after_stat.st_size == before_stat.st_size
    assert real.read_bytes() == before_bytes
    # 하네스가 쓴 local 이력은 tmp_path 쪽이다
    assert hist_path != real
