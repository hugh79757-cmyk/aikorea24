#!/usr/bin/env python3
"""tests/test_dedup10_briefing_same_story.py — AIK24-DEDUP-10 회귀 테스트

배경 (2026-10-27 실측):
    브리핑 id=365(2026-10-27)가 어제 id=364(2026-10-26)와 **같은 사건**을 다시 게재했다.
    r/opensource 커뮤니티의 AI 금지 정책 뉴스로, 어제는 The Verge, 오늘은
    Hacker News(Tom's Hardware)·The Decoder 두 건이었다. 즉 오늘 브리핑 2건이
    모두 같은 사건이었고, 그 사건은 어제도 나왔다.

    원인 3개:
      ① 엔티티 추출을 title[:50]·original_title[:30] 절단값으로 수행해
         어제 기사의 'non-English speakers' 가 30자에서 잘려 'English' 가 소멸
         → 겹침 2 → 1, 임계값(2) 미달 → 통과.
      ② filter_duplicates 가 '과거 발행분'만 보고 **같은 배치 내부**를 보지 않아
         같은 사건 2건이 한 브리핑에 동시에 들어갔다.
      ③ Layer 2 가 1번째 기사만 절단하고 2번째는 원문을 넘기는 비대칭이었다.

검증 대상: scripts/briefing_dedup.py
    · Layer 3 엔티티·주제어 판정이 절단 전 원문을 쓰는가
    · Layer 2 가 양쪽을 같은 기준으로 비교하는가
    · dedupe_within_batch=True 일 때만 배치 내부 중복을 제거하는가
    · 기본값(False)에서 selector 동작(PIPE-08 로 풀린 56076 류)이 보존되는가

주의: 실제 D1 · 실제 scripts/briefing_dedup.json 은 건드리지 않는다.
사용: pytest tests/test_dedup10_briefing_same_story.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import briefing_dedup  # noqa: E402
from threads.dedup import extract_entities  # noqa: E402

# ---------------------------------------------------------------- 실제 사건 데이터
# 2026-10-26 발행분 (The Verge) — original_title 이 30자에서 잘리면 'English' 가 사라진다.
YESTERDAY = {
    'id': '57111',
    'title': "레딧의 'r/open source' 커뮤니티, AI 및 비영어권 사용자 등 금지",
    'original_title': 'r/open source just banned AI, non-English speakers and more',
    'description': ('레딧의 오픈소스 커뮤니티가 AI 콘텐츠와 비영어권 사용자의 게시물을 '
                    '금지하는 등 엄격한 규정을 도입했습니다.'),
    'link': 'https://www.theverge.com/ai-artificial-intelligence/1018217/reddit-opensource-ai-ban',
    'source': 'The Verge',
}

# 2026-10-27 발행분 1 (Tom's Hardware) — 어제 기사와 같은 사건.
TODAY_A = {
    'id': '57241',
    'title': '레딧(Reddit) r/opensource 커뮤니티, AI 생성 및 AI 중심 프로젝트와 비영어권 사용자 금지',
    'original_title': 'R/opensource bans AI-made and AI-focused projects and non-English speakers',
    'description': ('오픈소스 커뮤니티인 r/opensource가 AI로 생성된 프로젝트와 AI 관련 도구들을 '
                    '금지하는 새로운 정책을 도입했습니다.'),
    'link': ('https://www.tomshardware.com/tech-industry/artificial-intelligence/'
             'reddits-r-opensource-bans-ai-made-and-ai-focused-projects'),
    'source': 'Hacker News',
}

# 2026-10-27 발행분 2 (The Decoder) — 1과 같은 사건, 어제 기사와도 같은 사건.
TODAY_B = {
    'id': '57166',
    'title': "레딧의 'r/opensource', 모든 AI 관련 프로젝트 금지… 반발과 함께 대체 커뮤니티 등장",
    'original_title': ("Reddit's r/opensource bans all AI-related projects, "
                       'sparking backlash and a rival subreddit'),
    'description': ("레딧의 오픈소스 포럼인 'r/opensource'가 AI로 제작되었거나 AI 기반인 모든 "
                    '프로젝트 게시물을 금지했습니다.'),
    'link': ('https://the-decoder.com/reddits-r-opensource-bans-all-ai-related-projects-'
             'sparking-backlash-and-a-rival-subreddit/'),
    'source': 'The Decoder',
}

# 2026-10-26 발행분 1 (AI타임스) — 같은 날이지만 **다른 사건**. 오탐 방지 대조군.
YESTERDAY_OTHER = {
    'id': '57117',
    'title': "엔비디아, 로컬 에이전트·로봇 겨냥 4GB 모델 '네모트론 3.5 볼트' 출시",
    'original_title': '',
    'description': ('엔비디아가 로컬에서 적은 메모리로 자연스러운 대화와 작업 수행이 가능한 '
                    '경량 온디바이스 AI 모델을 선보였다.'),
    'link': 'https://www.aitimes.com/news/articleView.html?idxno=216625',
    'source': 'AI타임스',
}


@pytest.fixture()
def no_history(monkeypatch):
    """실제 local 이력 파일을 읽지 않게 한다."""
    monkeypatch.setattr(briefing_dedup, 'load_local_history', lambda: [])
    return lambda sql: []


def _empty_d1(sql):
    return []


# ---------------------------------------------------------------- ① 절단 회귀
def test_entity_extraction_uses_full_text_not_truncated():
    """어제 기사의 구별 토큰('English')이 30자 절단에서 사라지는 것을 재현한다.

    이 테스트가 고정하는 계약: Layer 3 는 **원문**으로 엔티티를 뽑는다.
    절단값을 쓰면 아래 overlap 이 1 로 떨어져 같은 사건이 통과한다.
    """
    truncated_orig = YESTERDAY['original_title'][:30]
    full = extract_entities(TODAY_A['title'], TODAY_A['original_title'], TODAY_A['description'])
    cut = extract_entities(YESTERDAY['title'], truncated_orig, YESTERDAY['description'])
    full_h = extract_entities(
        YESTERDAY['title'], YESTERDAY['original_title'], YESTERDAY['description'])

    # 절단하면 'English' 가 소멸한다 — 이것이 사고의 출발점이다.
    assert 'English' in full_h, '원문에는 English 엔티티가 있어야 한다'
    assert 'English' not in cut, '30자 절단 시 English 가 사라져야 재현이 성립한다'

    assert len(full & full_h) >= briefing_dedup.ENTITY_OVERLAP_THRESHOLD
    assert len(full & cut) < briefing_dedup.ENTITY_OVERLAP_THRESHOLD


def test_same_story_as_yesterday_is_blocked(no_history):
    """어제 발행한 사건과 같은 사건은 오늘 후보에서 막힌다."""
    dup, reason = briefing_dedup.is_duplicate_article_strict(TODAY_A, [YESTERDAY])
    assert dup is True, '어제와 같은 사건인데 통과했다'
    assert reason == 'entity(2)', reason


def test_different_story_is_not_blocked(no_history):
    """같은 날짜·같은 도메인이라도 다른 사건은 막지 않는다 (오탐 대조군)."""
    for candidate in (TODAY_A, TODAY_B):
        dup, reason = briefing_dedup.is_duplicate_article_strict(candidate, [YESTERDAY_OTHER])
        assert dup is False, f'{candidate["id"]} 오탐: {reason}'


# ---------------------------------------------------------------- ② 배치 내부
def test_batch_duplicates_collapse_only_when_enabled(no_history):
    """dedupe_within_batch=True 일 때만 같은 사건 2건이 1건으로 줄어든다."""
    arts = [dict(TODAY_A), dict(TODAY_B)]

    kept_off, _ = briefing_dedup.filter_duplicates(
        [dict(a) for a in arts], _empty_d1, dedupe_within_batch=False)
    kept_on, removed_on = briefing_dedup.filter_duplicates(
        [dict(a) for a in arts], _empty_d1, dedupe_within_batch=True)

    assert len(kept_off) == 2, '기본값(False)은 selector 동작 보존 — 배치 내부를 보지 않는다'
    assert len(kept_on) == 1, 'True 인데 같은 사건 2건이 그대로 남았다'
    assert removed_on[0][1] == 'batch_semantic', removed_on[0][1]


def test_batch_chain_through_removed_article(no_history, monkeypatch):
    """A 가 과거 이력과 중복이라 탈락하고 B 가 A 와 중복이면 B 도 탈락해야 한다.

    채택분만 비교하면 이 연쇄가 끊겨, 오늘 사고(1건은 이력으로, 1건은 배치로)가
    다시 재현된다.
    """
    monkeypatch.setattr(briefing_dedup, 'load_local_history', lambda: [dict(YESTERDAY)])
    arts = [dict(TODAY_A), dict(TODAY_B)]

    kept, removed = briefing_dedup.filter_duplicates(arts, _empty_d1, dedupe_within_batch=True)

    assert kept == [], '같은 사건이 하나라도 남으면 브리핑이 어제와 겹친다'
    reasons = [r for _, r in removed]
    assert reasons == ['local_entity(2)', 'batch_semantic'], reasons


# ---------------------------------------------------------------- ③ 기본값 보존
def test_default_keeps_selector_behaviour_for_generic_entities(no_history):
    """PIPE-08 이 되돌린 '범용 엔티티만 겹치는 후보'를 배치 층이 다시 막지 않는다.

    56076 류(공통 엔티티 {AI, API} 뿐, 다른 주제)가 배치 비교로 탈락하면
    브리핑이 0건이 되던 사고가 재발한다 → 기본값은 배치 비교를 하지 않는다.
    """
    generic_a = {
        'id': '56076', 'source': 'GeekNews',
        'title': 'AI API 요금 비교 정리', 'original_title': '',
        'description': '여러 AI API 제공사의 요금을 비교한 글입니다.',
        'link': 'https://example.com/a',
    }
    generic_b = {
        'id': '56389', 'source': 'GeekNews',
        'title': 'API 키 발급 절차 안내', 'original_title': '',
        'description': 'API 키를 발급받는 절차를 정리했습니다.',
        'link': 'https://example.com/b',
    }
    kept, removed = briefing_dedup.filter_duplicates([generic_a, generic_b], _empty_d1)
    assert len(kept) == 2, f'범용 엔티티 오탐으로 탈락: {[r for _, r in removed]}'
