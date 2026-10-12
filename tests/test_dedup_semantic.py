"""tests/test_dedup_semantic.py — dedup.is_same_topic / compute_similarity 회귀 테스트

2026-09-29 사고: EN-EN 분기의 `entity_overlap >= 2` 조건이
"서로 다른 기사도 공통 고유명사 2개(예: OpenAI, Meta)만으로
same-topic 으로 오인" → 기사 풀이 1142개 → 2개로 폭락, 발행 0건.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'threads'))

from dedup import is_same_topic, compute_similarity


def _art(title, orig, desc):
    return (title, orig, desc)


def test_distinct_articles_with_shared_entities_not_same_topic():
    """공통 entity만 2개로sharing, 주제는 완전히 다름 → same_topic False"""
    a = _art(
        '메타, 카메라가 없는 AI 안경 공개',
        'Meta introduces camera-free AI glasses',
        '메타는 카메라 없는 안경을 공개했다.',
    )
    b = _art(
        'OpenAI와 앤스로픽 수장들, 유엔에 AI 글로벌 기준 촉구',
        'OpenAI and Anthropic bosses push UN for global terms on AI',
        'OpenAI의 샘 알트먼이 유엔에서 기준을 촉구했다.',
    )
    assert not is_same_topic(*a, *b), (
        '서로 다른 기자가 작성된 서로 다른 기사가 same-topic 으로 오인됨'
    )


def test_distinct_politico_guardian_not_same_topic():
    """실제 실패 사례: Politico EU Tech vs The Guardian AI 기사"""
    a = _art(
        '유엔 회의에서 극명하게 엇갈린 미·중의 AI 규제 비전.',
        'US, Chinese visions for AI regulation differ sharply at UN meeting',
        '도널드 트럼프 대통령이 유엔에서 글로벌 AI 안보 노력에 반대한다고 공언했다.',
    )
    b = _art(
        'Ben Jennings의 만평이 스마트 안경과 AI 해킹을 통해 일상의 모든 순간이 감시와 공격의 대상이 되는 미래를 경고한다.',
        'Ben Jennings on smart glasses and AI hacks – cartoon',
        'Ben Jennings is warning that every moment is becoming surveillance.',
    )
    assert not is_same_topic(*a, *b)


def test_same_article_detected():
    """동일 기사(한글/영문 복사) → same_topic True"""
    a = _art(
        'OpenAI가 AI 보안 기준을 발표했다',
        'OpenAI announces AI security standards',
        'OpenAI announced new AI security standards at UN.',
    )
    b = _art(
        'OpenAI, AI 보안 기준 발표',
        'OpenAI announces AI security standards',
        'OpenAI announced new AI security standards.',
    )
    assert is_same_topic(*a, *b)


def test_entity_overlap_distribution_is_sparse():
    """실제 데이터: entity_overlap >= 2 쌍 중绝大部分이 jaccard_en == 0 → 엔티티만으로는 판정 불가

    두 기사 모두 OpenAI + Anthropic 를 언급하지만 주제는 다름.
    공통 entity 2개로도 same-topic 으로 오인될 수 있음 → entity alone 로는 판정 불가.
    """
    a = _art(
        'OpenAI와 앤스로픽, 유엔에 AI 글로벌 기준 촉구',
        'OpenAI and Anthropic bosses push UN for global terms on AI',
        'OpenAI and Anthropic urged the UN to set global AI standards.',
    )
    b = _art(
        'OpenAI와 앤스로픽, 호주 정부 웹사이트에 AI 에이전트 침투',
        'OpenAI and Anthropic agents penetrate Australian government website',
        'OpenAI and Anthropic agents were found on an Australian government site.',
    )
    s = compute_similarity(*a, *b)
    assert s['entity_overlap'] >= 2, f"expected >=2 shared entities, got {s['entity_overlap']}"
    # 공통 entity만으로는 주제가 다름을 드러낼 수 없음
    assert s['jaccard_en'] < 0.30
    # 따라서 entity_overlap >= 2 조건 alone 으로는 same-topic 으로 봐야 안 됨
    assert not is_same_topic(*a, *b)


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))