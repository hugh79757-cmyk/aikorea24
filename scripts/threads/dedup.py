"""
dedup.py — 언어 통합 중복 탐지 엔진

한글/영문 모든 기사에 대해 동일 주제 여부를 판단.
Phase 1 (db_reader: is_already_posted), Phase 2 (narrative_pitcher: is_duplicate_pitch),
Phase 3 (save_pitch_to_history)에서 공통 사용.
"""
import re

_EN_STOPWORDS = {
    'the', 'a', 'an', 'is', 'was', 'are', 'were', 'been', 'be', 'to', 'of',
    'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'and', 'or', 'but',
    'not', 'no', 'its', 'it', 'this', 'that', 'all', 'each', 'has', 'had',
    'have', 'do', 'did', 'does', 'will', 'would', 'can', 'may', 'said',
}

_KO_STOPWORDS = {
    '있는', '위한', '통해', '대한', '이런', '저런', '그런',
    '이번', '지난', '다음', '모든', '이후', '이상', '관련',
    '기자', '앵커', '특파원', '제공', '사진', '최근', '시작',
    '너무', '정말', '매우', '가장', '다시', '약간', '모두',
    '없는', '하는', '된다', '했다', '라는', '에서', '으로',
    '에게', '까지', '라고', '대한', '통한', '위해', '때문',
    '아직', '여전', '우선', '바로', '오히려', '과연', '마치',
    '하지만', '그러나', '그리고', '따라서', '그런데', '결국',
    '먼저', '다만', '단지', '단순', '가장', '대표', '주요',
}


def extract_keywords(title='', original_title='', description=''):
    """한글/영문 통합 키워드 추출"""
    keywords = set()
    combined = ' '.join(t for t in [title, original_title, description] if t)

    # 1. English words (2+ chars, non-stopword)
    for w in re.findall(r'[a-zA-Z][a-zA-Z0-9\']{1,}', combined):
        wl = w.lower()
        if wl not in _EN_STOPWORDS and len(wl) >= 2:
            keywords.add(wl)

    # 2. Korean sequences (2+ chars)
    for w in re.findall(r'[가-힣][가-힣]+', combined):
        if w not in _KO_STOPWORDS:
            keywords.add(w)

    return keywords


def extract_entities(title='', original_title='', description=''):
    """고유명사 추출 — 영문 capitalized entity만 사용

    한글은 entity 추출에서 제외 (형태소 분석 없이 정확한 고유명사 식별 불가).
    대신 한글은 keyword Jaccard로 유사도 측정.
    영문이 한글 문장에 포함된 경우 (e.g. "AI", "GPT-5") → entity로 취급 (capitalized).
    """
    entities = set()
    combined = ' '.join(t for t in [title, original_title, description] if t)

    for w in re.findall(r'\b[A-Z][a-zA-Z0-9.&+#\-]{1,}\b', combined):
        if len(w) >= 2:
            entities.add(w)

    return entities


def compute_similarity(title1, original_title1, desc1,
                       title2, original_title2, desc2):
    """두 기사/피치 간 유사도 계산

    Returns dict:
      jaccard_en: English original_title Jaccard (0 if either is empty)
      jaccard_ko: Korean title keyword Jaccard
      jaccard_all: combined (EN+KO+desc) keyword Jaccard
      entity_overlap: shared entity count
      has_original_title: (bool1, bool2)
      score: weighted composite score (0.0~1.0)
    """
    kw1 = extract_keywords(title1, original_title1, desc1)
    kw2 = extract_keywords(title2, original_title2, desc2)

    en1 = _tokenize_en(original_title1) if original_title1 else set()
    en2 = _tokenize_en(original_title2) if original_title2 else set()

    ent1 = extract_entities(title1, original_title1, desc1)
    ent2 = extract_entities(title2, original_title2, desc2)

    result = {
        'has_en1': bool(original_title1),
        'has_en2': bool(original_title2),
    }

    # EN-EN Jaccard on original_title
    if en1 and en2:
        result['jaccard_en'] = _set_jaccard(en1, en2)
    else:
        result['jaccard_en'] = 0.0

    # KO-KO Jaccard on combined title keywords
    ko1 = _extract_ko_keywords(title1)
    ko2 = _extract_ko_keywords(title2)
    if ko1 and ko2:
        result['jaccard_ko'] = _set_jaccard(ko1, ko2)
    else:
        result['jaccard_ko'] = 0.0

    # Combined keyword Jaccard
    if kw1 and kw2:
        result['jaccard_all'] = _set_jaccard(kw1, kw2)
    else:
        result['jaccard_all'] = 0.0

    # Entity overlap
    if ent1 and ent2:
        result['entity_overlap'] = len(ent1 & ent2)
    else:
        result['entity_overlap'] = 0
    result['entities1'] = ent1
    result['entities2'] = ent2

    # Weighted composite score
    w1 = 0.35 if en1 and en2 else 0.0
    w2 = 0.25 if ko1 and ko2 else 0.0
    w3 = 0.25 if kw1 and kw2 else 0.0
    has_ent = bool(ent1 and ent2)
    w4 = 0.15 if has_ent else 0.0
    total_w = w1 + w2 + w3 + w4
    if total_w > 0:
        ent_factor = min(1.0, result['entity_overlap'] / max(len(ent1), len(ent2)) * 3) if has_ent else 0.0
        score = (
            w1 * result['jaccard_en'] +
            w2 * result['jaccard_ko'] +
            w3 * result['jaccard_all'] +
            w4 * ent_factor
        ) / total_w
        result['score'] = round(score, 3)
    else:
        result['score'] = 0.0

    return result


def is_same_topic(title1, original_title1, desc1,
                  title2, original_title2, desc2):
    """동일 주제 여부 판정 — 언어 통합

    3가지 언어 모드:
      - EN-EN: 모두 original_title 보유
          → Jaccard ≥ 0.30 OR entity_overlap ≥ 2
      - KO-KO: 모두 original_title 미보유, 한글 제목
          → jaccard_ko ≥ 0.25
          → entity_overlap ≥ 2 (영문 capitalized entity가 한글 제목에 있는 경우만)
      - Mixed: 한쪽만 original_title 보유
          → jaccard_all ≥ 0.15 (description 포함 키워드)
          → entity_overlap ≥ 1 AND jaccard_all ≥ 0.10
    + Fallback: jaccard_all ≥ 0.30
    """
    sim = compute_similarity(
        title1, original_title1, desc1,
        title2, original_title2, desc2,
    )

    he1, he2 = sim['has_en1'], sim['has_en2']
    hk1 = _has_korean(title1)
    hk2 = _has_korean(title2)
    has_ko = hk1 and hk2

    if he1 and he2:
        if sim['jaccard_en'] >= 0.30:
            return True
        if sim['entity_overlap'] >= 2:
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


def _tokenize_en(text):
    words = re.findall(r'[a-zA-Z][a-zA-Z0-9\']{1,}', text.lower())
    return set(w for w in words if w not in _EN_STOPWORDS)


def _extract_ko_keywords(text):
    words = re.findall(r'[가-힣][가-힣]+', text)
    return set(w for w in words if w not in _KO_STOPWORDS)


def _set_jaccard(s1, s2):
    if not s1 or not s2:
        return 0.0
    return len(s1 & s2) / len(s1 | s2)


def _has_korean(text):
    return bool(re.search(r'[가-힣]', text))


def article_keywords(article):
    """D1 article dict → keyword set"""
    return extract_keywords(
        article.get('title', ''),
        article.get('original_title', ''),
        article.get('description', ''),
    )


def article_entities(article):
    """D1 article dict → entity set"""
    return extract_entities(
        article.get('title', ''),
        article.get('original_title', ''),
        article.get('description', ''),
    )
