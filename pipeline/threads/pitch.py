"""pipeline/threads/pitch.py — 피치 로직: 파싱, 중복 제거, 히스토리, 오케스트레이션"""
import os, sys, json, re, random
from datetime import datetime

from pipeline.infra import project_root
from pipeline.infra.logger import get_scrubbed_logger

PROJECT_DIR = project_root()
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
if THREADS_DIR not in sys.path:
    sys.path.insert(0, THREADS_DIR)

from db_reader import normalize_url
from dedup import is_same_topic, article_keywords, article_entities

logger = get_scrubbed_logger(__name__)
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)


def _log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [v3] {msg}\n')


LEAKED_PROMPT_PATTERNS = [
    r'상식\s*[\(（]\s*A\s*[\)）]\s*[:：]\s*',
    r'실제\s*[\(（]\s*B\s*[\)）]\s*[:：]\s*',
    r'\n+\s*(vs|VS|versus)\s*\n+',
]

_SYSTEM_PROMPT_FRAGMENTS = [
    '스토리 파인더',
    '핵심 원칙',
    '인과관계를 정확히 파악',
    '찾는 방법',
    '소스 신뢰도',
    'article_ids 작성 규칙',
    '[출력 형식]',
    '[1차] 태그',
]


def detect_prompt_leak(text: str) -> tuple[bool, str]:
    """프롬프트 노출 검사 — 2중 검증 (시스템 프래그먼트 + 라벨 패턴)"""
    # 1. 시스템 프래그먼트 검사 (처음 300자)
    short = text[:300].lower()
    for frag in _SYSTEM_PROMPT_FRAGMENTS:
        if frag.lower() in short:
            return True, f"프롬프트 프래그먼트 탐지: {frag}"
    
    # 2. 프롬프트 라벨 검사 (전체 텍스트)
    for pattern in LEAKED_PROMPT_PATTERNS:
        if re.search(pattern, text):
            return True, f"프롬프트 라벨 탐지: {pattern}"
    
    return False, "OK"


def clean_leaked_prompt(text):
    for pattern in LEAKED_PROMPT_PATTERNS:
        text = re.sub(pattern, '', text)
    return text.strip()


_KOREAN_PATTERN = re.compile(r'[가-힣]')
_LATIN_SENTENCE_PATTERN = re.compile(r'^[A-Z][a-z\s\']+(ed|s|es|ing|ment|tion|al|ive)\b')
_MIN_KOREAN_RATIO = 0.15


def validate_korean_output(hook: str, narrative: str) -> tuple[bool, str]:
    if not hook:
        return False, "hook이 비어있음"
    leaked, reason = detect_prompt_leak(hook + ' ' + narrative)
    if leaked:
        return False, reason
    combined = hook + ' ' + narrative
    cleaned = combined.replace("'", "").replace('"', '').replace('\u2019', '')
    from pipeline.threads.validator import CHINESE_PATTERN  # lazy import to avoid circular dependency
    chinese_chars = len(CHINESE_PATTERN.findall(cleaned))
    if chinese_chars > 0:
        return False, f"한자(중국어) 감지: {chinese_chars}개"
    korean_chars = len(_KOREAN_PATTERN.findall(cleaned))
    total_chars = len(cleaned.strip())
    no_korean = korean_chars == 0
    low_ratio = total_chars > 10 and korean_chars < total_chars * _MIN_KOREAN_RATIO
    latin_pattern = _LATIN_SENTENCE_PATTERN.search(hook)
    if no_korean and total_chars >= 5:
        return False, "한글이 전혀 없음 (완전 영문 문장)"
    if low_ratio and (no_korean or latin_pattern):
        return False, f"한글 비율 부족: {korean_chars}/{total_chars}, 영문 패턴 감지"
    if no_korean and latin_pattern:
        return False, "영문 문장 패턴 감지됨"
    return True, "OK"


def normalize_output(hook: str, narrative: str) -> dict:
    cleaned_hook = clean_leaked_prompt(hook)[:100]
    cleaned_narrative = clean_leaked_prompt(narrative)[:200]
    valid, reason = validate_korean_output(cleaned_hook, cleaned_narrative)
    return {
        "hook": cleaned_hook,
        "narrative": cleaned_narrative,
        "lang_valid": valid,
        "lang_reason": reason,
    }


_LANG_SECTION = """
[언어 규칙 - 최우선]
- 모든 문장은 반드시 한국어로 작성한다.
- 고유명사가 문장 맨 앞에 와도 해당 문장은 한국어로 시작해야 한다.
- 예시:
  ✓ "Boeing의 Wisk Aero가 FAA 테스트 축소 의혹으로 내부고발 소송에 직면했다."
  ✗ "Boeing's Wisk Aero faces whistleblower lawsuit..."
"""

_NOTE_ON_LABELS = """
- 출력에 '상식(A):', '실제(B):', 'vs' 같은 라벨·태그·구분자를 절대 포함하지 말 것. 자연스러운 문장만 출력.
"""

SYSTEM_PROMPT = f"""당신은 AI 뉴스 기사에서 통념-현실 간의 모순·역설·미해결 질문을 찾아내는 컨트라딕션 파인더입니다.
{_LANG_SECTION}
[핵심 원칙]
1. 기사의 인과관계를 정확히 파악하라
2. "A가 B를 하면 C가 된다"는 내용을 반드시 그대로 서술
3. 절대로 인과관계를 뒤집거나 반대로 해석하지 말 것
4. 상식과 실제의 충돌을 찾되, 기사에 근거한 내용만 사용
5. 기사에 없는 내용을 추가하거나 추측하지 말 것
6. **원문에 명시적 모순이 없더라도, 기사 속 사실들을 다른 맥락과 연결해 간극을 구성할 수 있다면 포함하라**

[찾는 대상]
기사가 던지는 **"하지만..."** 을 찾아라:
- 통념("당연히 A일 거야")과 현실("그런데 실제로는 B") 사이의 간극
- 예상 밖의 인과관계, 시스템의 역설, 미해결 질문
- AI 기술 자체가 아니라 AI가 만드는 **사회·제도·자본·지정학적 긴장**

[핵심 — 단일 기사 + 단일 질문]
- 반드시 **하나의 기사**만 사용하라. 두 개 이상의 기사를 절대 연결하지 말 것.
- **그 기사에서 단 1개의 핵심 질문/모순만 발췌하라.**
- 서로 다른 기사의 내용을 섞어 새로운 이야기를 만들지 말 것.

[금지]
- 너무 많이 논의된 상식("AI가 일자리를 뺏는다", "AI가 미래다", "기술 발전이 중요하다")은 피할 것.
- **단순 정보 전달·제품 발표·데모·펀딩 라운드 단순 보도는 제외.** 단, 그 정보가 사회·제도·자본 긴장을 시사한다면 포함.
- 인과관계를 반대로 서술하는 것은 오보이므로 절대 금지
- 출력에 '상식(A):' 또는 '실제(B):' 같은 라벨을 절대 포함하지 말 것.
{_NOTE_ON_LABELS}

[출력 형식]
응답은 반드시 유효한 JSON 배열만 출력합니다. 설명이나 라벨을 절대 포함하지 마세요.
```json
[
  {{
    "hook": "독자의 호기심을 자극하는 한 줄. 통념과 현실의 간극을 담을 것 (고유명사만 영어)",
    "narrative": "2-3문장. 기사의 핵심 긴장과 인과관계를 서술 (고유명사만 영어)",
    "twist": "예상 밖의 결과 또는 역설",
    "emotion": "불안/놀람/분노/희망 중 하나",
    "but_line": "\"X인데, 사실은 Y\" 형식. 기사가 던지는 '하지만...'을 한 줄로 (고유명사만 영어)",
    "question": "이 기사가 독자에게 남기는 단 하나의 질문 (고유명사만 영어)",
    "gap_source": "\"explicit\" 또는 \"reconstructed\". 원문에 명시적 간극이 있으면 explicit, 원문 사실을 재연결해 간극을 구성했으면 reconstructed",
    "article_ids": [1]
  }}
]
```

각 피치는 반드시 단일 기사(article_ids 1개)만 사용. 2개 이상 절대 금지.

주의사항:
- 인과관계를 반대로 서술하는 것은 오보이므로 절대 금지
- 기사에 없는 내용 추가 금지
- hook에서 주어와 객체를 명확히 구분하여 혼동 방지
{_NOTE_ON_LABELS}
## article_ids 작성 규칙
- 반드시 실제로 읽은 기사의 ID만 article_ids에 포함할 것
- 해당 기사의 내용이 hook/narrative/twist에 직접 인용된 경우만 포함
- 반드시 1개만 포함. 절대 2개 이상 금지."""


def fill_article_ids(pitch, articles_text):
    """피치의 hook/narrative로 관련 기사 ID 자동 매칭 (fallback: 기사 1개만 연결)"""
    if pitch.get('article_ids'):
        return pitch

    hook = pitch.get('hook', '')
    narrative = pitch.get('narrative', '')
    search_text = (hook + ' ' + narrative).lower()
    words = [w for w in search_text.split() if len(w) >= 2]
    if not words:
        return pitch

    scored = []
    for entry in articles_text:
        aid = ''
        text = ''
        for line in entry.split('\n'):
            if line.startswith('기사 #'):
                aid = line.replace('기사 #', '').split(':')[0].strip()
            else:
                text += line + ' '
        text_lower = text.lower()
        score = sum(1 for w in words if w in text_lower)
        if score > 0:
            scored.append((score, aid))

    scored.sort(key=lambda x: -x[0])
    pitch['article_ids'] = [aid for _, aid in scored[:1]]
    if pitch['article_ids']:
        print(f'  [매칭] {len(pitch["article_ids"])}개 기사 연결 (fallback)')
    return pitch


def parse_pitches_from_text(text, articles_text=None):
    """GPT 출력에서 PITCH JSON 블록 추출. JSON 모드 → 직접 json.loads, fallback → regex"""
    if not text or not text.strip():
        return []
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            pitches = data
        elif isinstance(data, dict):
            pitches = data.get('pitches', [data])
        else:
            pitches = []
        result = []
        for p in pitches:
            if 'hook' in p and 'narrative' in p:
                norm = normalize_output(p.get('hook', ''), p.get('narrative', ''))
                p['hook'] = norm['hook']
                p['narrative'] = norm['narrative']
                p['_lang_valid'] = norm['lang_valid']
                p['_lang_reason'] = norm['lang_reason']
                result.append(p)
        if result:
            return result
    except (json.JSONDecodeError, Exception):
        pass
    return _parse_pitches_fallback(text, articles_text)


def _parse_pitches_fallback(text, articles_text=None):
    """regex 기반 fallback 파서 (JSON 모드 실패 시)"""
    pitches = []
    for m in re.finditer(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', text, re.DOTALL):
        try:
            p = json.loads(m.group(0))

            if 'hook' in p and 'narrative' in p and 'article_ids' in p:
                norm = normalize_output(p.get('hook', ''), p.get('narrative', ''))
                p['hook'] = norm['hook']
                p['narrative'] = norm['narrative']
                p['_lang_valid'] = norm['lang_valid']
                p['_lang_reason'] = norm['lang_reason']
                pitches.append(p)
                continue

            if 'title' in p and 'summary' in p:
                norm = normalize_output(p.get('title', '') or '', p.get('summary', '') or '')
                pitches.append({
                    'hook': norm['hook'],
                    'narrative': norm['narrative'],
                    'twist': '',
                    'emotion': '놀라움',
                    'article_ids': [],
                    'sources': [],
                    'comparison_unit': '',
                    '_lang_valid': norm['lang_valid'],
                    '_lang_reason': norm['lang_reason'],
                })
                continue

            if 'pitch_id' in p and 'title' in p:
                norm = normalize_output(p.get('title', '') or '', p.get('summary', '') or '')
                pitches.append({
                    'hook': norm['hook'],
                    'narrative': norm['narrative'],
                    'twist': '',
                    'emotion': '놀라움',
                    'article_ids': [],
                    'sources': [],
                    'comparison_unit': '',
                    '_lang_valid': norm['lang_valid'],
                    '_lang_reason': norm['lang_reason'],
                })
                continue
        except Exception:
            continue
    return pitches


def parse_top_pitch(text, fallback_pitches):
    """TOP 1 피치 파싱 (fallback: 첫 번째 피치)"""
    pitches = parse_pitches_from_text(text)
    if pitches:
        return pitches[0]
    seen = set()
    for p in fallback_pitches:
        key = p.get('hook', '')[:20]
        if key not in seen:
            seen.add(key)
            return p
    return fallback_pitches[0] if fallback_pitches else None


def load_pitch_history():
    """posted.json에서 피치 이력 로드"""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'posted.json')
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            return data.get('pitch_history', [])
        except Exception:
            return []
    return []


def _but_line_similarity(bl1: str, bl2: str) -> float:
    """but_line 간 단어 Jaccard 유사도"""
    if not bl1 or not bl2:
        return 0.0
    w1 = set(w.lower() for w in bl1.split() if len(w) >= 2)
    w2 = set(w.lower() for w in bl2.split() if len(w) >= 2)
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


def is_duplicate_pitch(pitch, history, posted=None):
    """비슷한 피치가 이미 history에 있는지 확인"""
    # Defensive: article_ids can be int or list from LLM
    raw_ids = pitch.get('article_ids', [])
    if isinstance(raw_ids, int):
        raw_ids = [raw_ids]
    hook = pitch.get('hook', '')[:80]
    narrative = pitch.get('narrative', '')[:120]
    new_but_line = pitch.get('but_line', '')
    new_question = pitch.get('question', '')
    new_ids = set(str(x).lstrip('#').strip() for x in raw_ids if str(x).strip())
    new_urls = set(pitch.get('article_urls', []))
    new_titles = list(pitch.get('article_titles', []))
    new_original_titles = list(pitch.get('article_original_titles', []))

    if posted:
        for i in range(len(raw_ids)):
            aid = str(raw_ids[i]).lstrip('#').strip()
            link = list(new_urls)[i] if i < len(new_urls) else ''
            title = new_titles[i] if i < len(new_titles) else ''
            orig_title = new_original_titles[i] if i < len(new_original_titles) else ''

            posted_links_norm = set(normalize_url(l) for l in posted.get('posted_links', []))
            posted_titles_set = set(t[:80] for t in posted.get('posted_titles', []))
            posted_orig_titles_set = set(ot[:80] for ot in posted.get('posted_original_titles', []))

            if (aid and aid in posted.get('posted_ids', []) or
                link and normalize_url(link) in posted_links_norm or
                title and title[:30] in posted_titles_set or
                orig_title and orig_title[:30] in posted_orig_titles_set):
                return True

    for h in history:
        if h.get('hook', '')[:80] == hook:
            return True
        if narrative and h.get('narrative', '')[:120] == narrative:
            return True
        if new_ids:
            old_ids = set(str(x).lstrip('#').strip() for x in h.get('article_ids', []) if str(x).strip())
            if old_ids:
                overlap = len(old_ids & new_ids)
                if overlap / len(new_ids) >= 0.5:
                    return True
        if new_urls:
            old_urls = set(h.get('article_urls', []))
            if old_urls:
                overlap = len(old_urls & new_urls)
                if overlap / len(new_urls) >= 0.5:
                    return True

        pt = h.get('article_titles', [])
        po = h.get('article_original_titles', [])
        pd = h.get('article_descriptions', [])
        for i in range(max(len(pt), len(po), len(pd))):
            t1 = pt[i] if i < len(pt) else ''
            o1 = po[i] if i < len(po) else ''
            d1 = pd[i] if i < len(pd) else ''
            for j in range(len(new_titles)):
                t2 = new_titles[j]
                o2 = new_original_titles[j]
                d2 = ''
                if is_same_topic(t1, o1, d1, t2, o2, d2):
                    return True

        # but_line/question 보조 중복 체크: 동일 article_ids + 유사 but_line → 탈락
        if new_ids and new_but_line:
            old_ids = set(str(x).lstrip('#').strip() for x in h.get('article_ids', []) if str(x).strip())
            if old_ids:
                overlap = len(old_ids & new_ids)
                if overlap / len(new_ids) >= 0.5:
                    h_but_line = h.get('but_line', '')
                    if h_but_line and _but_line_similarity(new_but_line, h_but_line) >= 0.5:
                        return True

    return False


def save_pitch_to_history(pitch):
    """선택된 피치를 posted.json 피치 이력 + posted_article_meta에 저장"""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'posted.json')

    hook_raw = pitch.get('hook', '')
    narrative_raw = pitch.get('narrative', '')
    norm = normalize_output(hook_raw, narrative_raw)

    if not norm['lang_valid']:
        _log(f'  ⚠️ [발행 게이트] 한국어 검증 실패: {norm["lang_reason"]}')
        _log(f'     hook: "{norm["hook"][:60]}"')
        _log(f'     → 그래도 저장 진행 (추후 검토용)')

    try:
        data = {}
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
        if 'pitch_history' not in data:
            data['pitch_history'] = []
        if 'posted_article_meta' not in data:
            data['posted_article_meta'] = {}

        entities = set()
        for t in pitch.get('article_original_titles', []):
            for w in re.findall(r'\b[A-Z][a-zA-Z0-9.&+#\-]{1,}\b', t):
                entities.add(w)

        data['pitch_history'].append({
            'hook': norm['hook'],
            'narrative': norm['narrative'],
            'but_line': pitch.get('but_line', ''),
            'question': pitch.get('question', ''),
            'gap_source': pitch.get('gap_source', ''),
            'article_ids': pitch.get('article_ids', []),
            'article_urls': pitch.get('article_urls', []),
            'article_titles': pitch.get('article_titles', []),
            'article_original_titles': pitch.get('article_original_titles', []),
            'article_descriptions': pitch.get('article_descriptions', []),
            'entities': list(entities),
            'date': datetime.now().strftime('%Y-%m-%d'),
            '_lang_valid': norm['lang_valid'],
            '_lang_reason': norm['lang_reason'],
        })

        aids = pitch.get('article_ids', [])
        titles = pitch.get('article_titles', [])
        origs = pitch.get('article_original_titles', [])
        descs = pitch.get('article_descriptions', [])
        for i, aid in enumerate(aids):
            aid_str = str(aid).lstrip('#').strip()
            if aid_str:
                data['posted_article_meta'][aid_str] = {
                    'title': titles[i] if i < len(titles) else '',
                    'original_title': origs[i] if i < len(origs) else '',
                    'description': descs[i] if i < len(descs) else '',
                }

        with open(path, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _pre_filter_candidates(articles, limit=10):
    """D1 후보 기사를 시의성 + AI 관련도 기준으로 선별하여 상위 limit개만 반환"""
    def score_article(a):
        score = 0
        pub_date = a.get('pub_date', '')
        if pub_date:
            try:
                days_old = (datetime.now() - datetime.strptime(pub_date, '%Y-%m-%d')).days
                if days_old <= 1:
                    score += 10
                elif days_old <= 3:
                    score += 5
                elif days_old <= 7:
                    score += 2
            except Exception:
                pass
        
        title_desc = (a.get('title', '') + ' ' + a.get('description', '')).lower()
        ai_keywords = ['ai', '인공지능', '머신러닝', 'llm', '챗gpt', '클로드', '제미나이', 'gemini', 'anthropic']
        for kw in ai_keywords:
            if kw in title_desc:
                score += 3
        return score
    
    scored = [(score_article(a), a) for a in articles]
    scored.sort(key=lambda x: -x[0])
    return [a for _, a in scored[:limit]]


def get_pitches(articles, max_articles=600, batch_size=200, exclude_ids=None):
    """배치 처리: description 스캔 → 후보 선별 → 단일 기사 크롤링 → 크롤링 본문 기반 피치 생성"""
    from v3.model_router import chat_completion
    from db_reader import load_posted
    from pipeline.threads.pitch_evaluator import filter_pitches
    from pipeline.threads.crawler import fetch_article_body
    pitch_history = load_pitch_history()
    posted = load_posted()
    if pitch_history:
        _log(f'  피치 이력: {len(pitch_history)}개 존재')

    selected = articles[:max_articles]
    
    # Phase 24-02: 사전 필터링 - 시의성 + AI 관련도 기준 상위 10개만 선별
    shuffled = _pre_filter_candidates(selected)
    if not shuffled:
        _log('  ❌ 사전 필터링 후 후보 없음')
        return ([], set())

    exclude_ids = exclude_ids or set()
    if exclude_ids:
        before = len(shuffled)
        shuffled = [a for a in shuffled if str(a.get('id', '')) not in exclude_ids]
        excluded_count = before - len(shuffled)
        if excluded_count:
            _log(f'  🚫 제외: {excluded_count}개 기사 (크롤링 실패 이력)')

    if not shuffled:
        _log('  ❌ 모든 기사가 제외됨 (크롤링 실패 이력)')
        return ([], set())

    # Phase 24-01: batch_size 축소 - LLM context overflow 방지
    effective_batch_size = min(batch_size, 5)
    batches = [shuffled[i:i+effective_batch_size] for i in range(0, len(shuffled), effective_batch_size)]
    _log(f'[배치 처리] 총 {len(shuffled)}개 → {effective_batch_size}개 × {len(batches)}배치')

    id_to_link = {}
    id_to_title = {}
    id_to_original_title = {}
    id_to_description = {}
    for a in shuffled:
        aid = str(a.get('id', ''))
        if aid:
            id_to_link[aid] = a.get('link', '')
            id_to_title[aid] = a.get('title', '')
            id_to_original_title[aid] = a.get('original_title', '')
            id_to_description[aid] = a.get('description', '')

    all_pitches = []
    for idx, batch in enumerate(batches):
        _log(f'[배치 {idx+1}/{len(batches)}] {len(batch)}개 기사 처리 중...')

        articles_text = []
        for a in batch:
            aid = a.get('id', '')
            title = a.get('title', '')
            source = a.get('source', '')
            link = a.get('link', '')
            desc = (a.get('description', '') or '')
            articles_text.append(f"""기사 #{aid}:
제목: {title}
본문: {desc}
출처: {source}
링크: {link}""")

        all_articles_joined = '\n---\n'.join(articles_text)

        try:
            resp = chat_completion(
                system_prompt=SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': f"""아래 {len(batch)}개 기사 전체를 보고, 가장 강한 모순·역설·미해결 질문을 담은 기사 3개를 PITCH JSON 형식으로 찾아주세요. 단순 정보 전달·제품 발표·데모는 제외.

{all_articles_joined}"""}],
                temperature=0.9,
                max_tokens=8000,
                model_override=None,
            )
            pitches = parse_pitches_from_text(resp, articles_text)
            _log(f'[배치 {idx+1}/{len(batches)}] → {len(pitches)}개 피치 발견')

            if pitches:
                korean_ok = sum(1 for p in pitches if p.get('_lang_valid', True))
                _log(f'  한국어 검증: {korean_ok}/{len(pitches)} 통과')
                if korean_ok == 0:
                    _log(f'  ⚠️ 모든 피치가 한국어 검증 실패 → 일반 텍스트 fallback')
                    pitches = []

            if not pitches:
                _log(f'  ⚠️ JSON 파싱 실패 또는 한국어 불량 → fallback')
                from v3.model_router import chat_completion as _cc
                resp2 = _cc(
                    system_prompt=SYSTEM_PROMPT,
                    messages=[{'role': 'user', 'content': f"""아래 {len(batch)}개 기사 전체를 보고, 가장 강한 모순·역설·미해결 질문을 담은 기사 3개를 찾아 PITCH JSON 형식으로 출력해주세요. 단순 정보 전달·제품 발표·데모는 제외.

{all_articles_joined}"""}],
                    temperature=0.9,
                    max_tokens=8000,
                    model_override=None,
                )
                pitches = parse_pitches_from_text(resp2, articles_text)
                _log(f'[배치 {idx+1}/{len(batches)}] → {len(pitches)}개 피치 발견')
        except Exception as e:
            _log(f'  ⚠️ 배치 {idx+1} 오류: {e}')
            continue

        all_pitches.extend(pitches)

    if not all_pitches:
        _log('  ❌ 피치 없음')
        return ([], set())

    _log(f'[전체] {len(all_pitches)}개 후보 발견')

    valid = []
    for p in all_pitches:
        hook = p.get('hook', '')
        if len(hook) >= 5:
            valid.append(p)
        else:
            _log(f'  ⚠️ hook {len(hook)}자 미달 제외: "{hook[:20]}"')

    if not valid:
        _log('  ❌ 모든 피치 hook 길이 조건 불만족')
        return ([], set())

    unique = []
    for p in valid:
        p_urls = []
        p_titles = []
        p_original_titles = []
        p_descriptions = []
        # Defensive: article_ids can be int or list from LLM
        article_ids = p.get('article_ids', [])
        if isinstance(article_ids, int):
            article_ids = [article_ids]
        for aid in article_ids:
            aid_str = str(aid).lstrip('#').strip()
            if aid_str:
                p_urls.append(id_to_link.get(aid_str, ''))
                p_titles.append(id_to_title.get(aid_str, ''))
                p_original_titles.append(id_to_original_title.get(aid_str, ''))
                p_descriptions.append(id_to_description.get(aid_str, ''))
        p['article_urls'] = p_urls
        p['article_titles'] = p_titles
        p['article_original_titles'] = p_original_titles
        p['article_descriptions'] = p_descriptions

        if is_duplicate_pitch(p, pitch_history, posted):
            _log(f'  ⚠️ 중복 피치 제외: "{p.get("hook", "")[:30]}" (기사: {len(p.get("article_ids", []))}개)')
        else:
            unique.append(p)

    _log(f'[전체] {len(valid)}개 후보 → 중복 제외 후 {len(unique)}개')

    if not unique:
        _log('  ❌ 모든 피치가 이력과 중복')
        return ([], set())

    top = filter_pitches(unique)

    if not top:
        _log('  ❌ 모든 피치 품질 평가 불통')
        return ([], set())

    _log(f'  ✅ TOP 1: "{top.get("hook", "")}" ({top.get("emotion", "")})')
    _log(f'     기사: {top.get("article_ids", [])}')

    lang_valid = top.get('_lang_valid', True)
    lang_reason = top.get('_lang_reason', '')
    if not lang_valid:
        _log(f'  ⚠️ [발행 게이트] 한국어 검증 실패: {lang_reason}')
        _log(f'     -> 발행 차단되지 않음 (검증 로그만 기록)')

    article_id = top.get('article_ids', [''])[0] if top.get('article_ids') else ''
    article_id_str = str(article_id).lstrip('#').strip()
    article_url = id_to_link.get(article_id_str, '')
    article_title = id_to_title.get(article_id_str, '')
    article_desc = id_to_description.get(article_id_str, '')

    if not article_url:
        _log(f'  ⚠️ 기사 {article_id_str}의 URL을 찾을 수 없음 → 피치 폐기')
        return ([], {article_id_str} if article_id_str else set())

    _log(f'  📰 피치 기사 원문 크롤링: {article_url[:60]}...')
    crawled_body = fetch_article_body(article_url, source='', title=article_title)

    if not crawled_body:
        _log(f'  ⚠️ 크롤링 실패 → D1 description 기반 원 피치로 발행')
        return ([top], set())

    _log(f'  📰 크롤링 완료: {len(crawled_body)}자')

    regenerated = _regenerate_pitch_from_crawl(
        crawled_body, article_id_str, article_url, article_title, top
    )

    if regenerated:
        regenerated['crawled_body'] = crawled_body
        _log(f'  ✅ 크롤링 기반 피치 재생성 완료: "{regenerated.get("hook", "")[:50]}"')
        return ([regenerated], set())
    else:
        _log(f'  ⚠️ 피치 재생성 실패 → D1 description 기반 원 피치 사용')
        return ([top], set())


def _regenerate_pitch_from_crawl(body, article_id, article_url, article_title, original_pitch):
    """크롤링된 원문 본문으로 피치를 재생성한다."""
    from v3.model_router import chat_completion

    system = f"""당신은 AI 뉴스 기사에서 통념-현실 간의 모순·역설·미해결 질문을 찾아내는 컨트라딕션 파인더입니다.
아래 제공된 기사 원문(크롤링된 전체 본문)을 근거로 피치를 작성합니다.
{_LANG_SECTION}
[핵심 원칙]
1. 반드시 아래 기사 원문에 나오는 내용만 사용할 것
2. 기사에 없는 인물, 제품명, 사건을 절대 만들어내지 말 것
3. 인과관계를 뒤집거나 반대로 해석하지 말 것
4. **원문에 명시적 모순이 없더라도, 기사 속 사실들을 연결해 통념-현실 간극을 구성할 수 있다면 포함하라**

[찾는 대상]
기사가 던지는 **"하지만..."** 을 찾아라:
- 통념과 현실 사이의 간극
- 예상 밖의 인과관계, 시스템의 역설, 미해결 질문
- AI가 만드는 사회·제도·자본·지정학적 긴장

[출력 형식]
응답은 반드시 유효한 JSON 객체만 출력합니다. 설명이나 라벨을 절대 포함하지 마세요.
{{"hook": "한국어로 작성된 호기심을 자극하는 한 줄 (고유명사만 영어)", "narrative": "한국어로 작성된 2-3문장 내러티브 (고유명사만 영어)", "twist": "예상 밖의 결과", "emotion": "불안/놀람/분노/희망 중 하나", "but_line": ""X인데, 사실은 Y" 형식. 기사가 던지는 '하지만...'을 한 줄로", "question": "이 기사가 독자에게 남기는 단 하나의 질문", "gap_source": ""explicit" 또는 "reconstructed". 원문에 명시적 간극 -> explicit, 재구성 -> reconstructed", "article_ids": [{article_id}]}}

[gap_source 규칙]
- 원문에 명시적 모순/간극이 있으면 → gap_source: "explicit"
- 원문에 명시적 간극이 없더라도, 원문의 핵심 사실을 다른 맥락(AI 노동 대체, 자본 긴장, 시스템 재귀, 지정학적 갈등 등)과 연결해 통념-현실 간극을 새로 구성할 수 있다면 → gap_source: "reconstructed", **반드시 재구성한 근거를 기사 원문에서 찾아낼 것**

주의사항:
- 반드시 1개 기사만 사용. 2개 이상 절대 금지.
- 기사 원문에 없는 내용 추가 금지
- hook에서 주어와 객체를 명확히 구분
{_NOTE_ON_LABELS}"""

    ref_hook = original_pitch.get('hook', '')
    ref_narrative = original_pitch.get('narrative', '')
    ref_but_line = original_pitch.get('but_line', '')
    ref_question = original_pitch.get('question', '')

    user_msg = f"""아래 기사 원문을 읽고 피치를 작성해주세요.

=== 기사 원문 (크롤링된 전체 본문) ===
제목: {article_title}
URL: {article_url}
본문:
{body[:15000]}

=== 참고: description 기반 1차 선별 결과 ===
hook: {ref_hook}
narrative: {ref_narrative}
but_line: {ref_but_line}
question: {ref_question}
→ 위 선별 결과는 참고용이며, 기사 원문과 다를 경우 원문을 우선할 것. but_line/question 각도는 보존할 것."""

    try:
        resp = chat_completion(
            system_prompt=system,
            messages=[{'role': 'user', 'content': user_msg}],
            temperature=0.7,
            max_tokens=8000,
            model_override=None,
        )
        if not resp:
            return None
        pitches = parse_pitches_from_text(resp)
        if pitches:
            p = pitches[0]
            p['article_ids'] = [article_id]
            p['crawled_url'] = article_url
            return p
    except Exception as e:
        _log(f'  ⚠️ 피치 재생성 오류: {e}')
    return None
