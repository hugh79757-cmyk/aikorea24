#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
narrative_pitcher.py — 100개 기사 → 가장 강력한 이야기 발견
- 모델: gpt-4o-mini (비용 절감)
- 50개씩 2개 청크 → 각 2개 피치 → 총 4개 → TOP 1 선정
"""
import os, sys, json, re, random
from datetime import datetime

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
sys.path.insert(0, THREADS_DIR)
from db_reader import normalize_url, jaccard_similarity, extract_title_entities
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [v3] {msg}\n')

def load_env():
    # 공통 환경변수 먼저 로드 (~/.env.common)
    common = os.path.expanduser('~/.env.common')
    if os.path.exists(common):
        with open(common) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') \
                   and '=' in line and not line.startswith('source'):
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(),
                                         v.strip().strip('"').strip("'"))

    env_path = os.path.join(PROJECT_DIR, '.env')
    env_sh = os.path.join(PROJECT_DIR, 'api_test', '.env.sh')
    for p in [env_path, env_sh]:
        if os.path.exists(p):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        if line.startswith('export '):
                            line = line[7:]
                        k, v = line.split('=', 1)
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_env()

SYSTEM_PROMPT = """당신은 AI 뉴스 기사에서 독자가 몰랐던 사실을 찾아내는 스토리 파인더입니다.

[핵심 원칙]
1. 기사의 인과관계를 정확히 파악하라
2. "A가 B를 하면 C가 된다"는 내용을 반드시 그대로 서술
3. 절대로 인과관계를 뒤집거나 반대로 해석하지 말 것
4. 상식과 실제의 충돌을 찾되, 기사에 근거한 내용만 사용
5. 기사에 없는 내용을 추가하거나 추측하지 말 것
6. hook은 독자의 호기심을 자극하되 사실에 충실할 것

[찾는 방법]
"상식적으로 A였어야 하는데 실제로는 B인 상황"을 찾아라.

[핵심 — 반드시 단일 기사만 사용]
- 하나의 기사에서 가장 강력한 이야기를 발견하라.
- 절대 두 개 이상의 기사를 연결하지 말 것.
- 서로 다른 기사의 내용을 섞어 새로운 이야기를 만들지 말 것.
- 한 기사의 내용만으로 hook/narrative/twist를 구성하라.

[hook]
hook: 이야기의 핵심 긴장을 한 줄로. 날짜/인물/숫자로 시작해도 됨. 길이 제한 없음.
- 고유명사(기업명, 인물명, 제품명)는 영어 원문을 사용하라. 예: 엔비디아(X) → Nvidia(O), 오픈AI(X) → OpenAI(O)

[금지]
- 너무 많이 논의된 상식("AI가 일자리를 뺏는다", "AI가 미래다", "기술 발전이 중요하다")은 피할 것.
- 독자가 '어? 나는 몰랐는데?' 하는 상식과 실제의 충돌을 찾을 것.
- 인과관계를 반대로 서술하는 것은 오보이므로 절대 금지

[소스 신뢰도]
- [1차] 태그 기사: 원문. 숫자/주어/방향을 그대로 사용할 것.
- [요약] 태그 기사: 2차 요약본. 주어-동사 방향이 뒤집혔을 수 있음.
  [요약] 기사만으로 twist 방향을 결정하지 말 것.

[출력 형식 — JSON만]
{"hook": "독자가 몰랐던 사실을 담은 한 문장 (기사에 근거)", "narrative": "왜 이것이 중요한지 2-3문장 설명 (인과관계 정확히)", "twist": "상식과 다른 실제 결과 (기사 내용에만 근거)", "emotion": "불안/놀람/분노/희망 중 하나", "article_ids": [관련 기사 ID — 반드시 1개만]}

주의사항:
- 인과관계를 반대로 서술하는 것은 오보이므로 절대 금지
- 기사에 없는 내용 추가 금지
- hook에서 주어와 객체를 명확히 구분하여 혼동 방지
- 반드시 1개 기사만 사용할 것. 2개 이상 절대 금지.

## article_ids 작성 규칙
- 반드시 실제로 읽은 기사의 ID만 article_ids에 포함할 것
- 해당 기사의 내용이 hook/narrative/twist에 직접 인용된 경우만 포함
- 반드시 1개만 포함. 절대 2개 이상 금지."""

def fill_article_ids(pitch, articles_text):
    """피치의 hook/narrative로 관련 기사 ID 자동 매칭 (fallback: 기사 1개만 연결)"""
    # 모델이 이미 article_ids를 포함하고 있으면 그대로 사용
    if pitch.get('article_ids'):
        return pitch
    
    hook = pitch.get('hook', '')
    narrative = pitch.get('narrative', '')
    search_text = (hook + ' ' + narrative).lower()
    # 의미 있는 단어만 추출
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
    # fallback 시 최대 1개 기사만 연결 (관련 없는 기사 연결 방지)
    pitch['article_ids'] = [aid for _, aid in scored[:1]]
    if pitch['article_ids']:
        print(f'  [매칭] {len(pitch["article_ids"])}개 기사 연결 (fallback)')
    return pitch

def parse_pitches_from_text(text, articles_text=None):
    """GPT 출력에서 PITCH JSON 블록 추출 (멀티 스키마 지원)"""
    pitches = []
    for m in re.finditer(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', text, re.DOTALL):
        try:
            p = json.loads(m.group(0))

            # 스키마 1: 우리 형식 (hook/narrative/article_ids)
            if 'hook' in p and 'narrative' in p and 'article_ids' in p:
                pitches.append(p)
                continue

            # 스키마 2: DiffusionGemma 형식 (title/summary/tags)
            if 'title' in p and 'summary' in p:
                pitches.append({
                    'hook': (p.get('title', '') or '')[:18],
                    'narrative': p.get('summary', '')[:100],
                    'twist': '',
                    'emotion': '놀라움',
                    'article_ids': [],
                    'sources': [],
                    'comparison_unit': '',
                })
                continue

            # 스키마 3: pitch_id 기반
            if 'pitch_id' in p and 'title' in p:
                pitches.append({
                    'hook': (p.get('title', '') or '')[:18],
                    'narrative': p.get('summary', '')[:100] if 'summary' in p else '',
                    'twist': '',
                    'emotion': '놀라움',
                    'article_ids': [],
                    'sources': [],
                    'comparison_unit': '',
                })
                continue
        except:
            continue
    return pitches

def parse_top_pitch(text, fallback_pitches):
    """TOP 1 피치 파싱 (fallback: 첫 번째 피치)"""
    pitches = parse_pitches_from_text(text)
    if pitches:
        return pitches[0]
    # fallback
    seen = set()
    for p in fallback_pitches:
        key = p.get('hook', '')[:20]
        if key not in seen:
            seen.add(key)
            return p
    return fallback_pitches[0] if fallback_pitches else None

def load_pitch_history():
    """posted.json에서 피치 이력 로드"""
    import json as _json
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'posted.json')
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = _json.load(f)
            return data.get('pitch_history', [])
        except:
            return []
    return []

def is_duplicate_pitch(pitch, history, posted=None):
    """비슷한 피치가 이미 history에 있는지 확인 (4조건: link, title, original_title, id)"""
    hook = pitch.get('hook', '')[:15]
    narrative = pitch.get('narrative', '')[:30]
    new_ids = set(str(x).lstrip('#').strip() for x in pitch.get('article_ids', []) if str(x).strip())
    new_urls = set(pitch.get('article_urls', []))
    new_titles = set(pitch.get('article_titles', []))
    new_original_titles = set(pitch.get('article_original_titles', []))

    if posted:
        # 새 pitch의 기사들 중 하나라도 posted와 매칭되면 중복
        for i in range(len(pitch.get('article_ids', []))):
            aid = str(pitch['article_ids'][i]).lstrip('#').strip()
            link = list(new_urls)[i] if i < len(new_urls) else ''
            title = list(new_titles)[i] if i < len(new_titles) else ''
            orig_title = list(new_original_titles)[i] if i < len(new_original_titles) else ''

            posted_links_norm = set(normalize_url(l) for l in posted.get('posted_links', []))
            posted_titles_set = set(t[:30] for t in posted.get('posted_titles', []))
            posted_orig_titles_set = set(ot[:30] for ot in posted.get('posted_original_titles', []))

            if (aid and aid in posted.get('posted_ids', []) or
                link and normalize_url(link) in posted_links_norm or
                title and title[:30] in posted_titles_set or
                orig_title and orig_title[:30] in posted_orig_titles_set):
                return True

    # 새 pitch entity set (루프 밖에서 한 번만 계산)
    new_entities = set()
    for t in pitch.get('article_original_titles', []):
        new_entities.update(extract_title_entities(t))

    for h in history:
        # hook 앞 15자 일치 → 중복
        if h.get('hook', '')[:15] == hook:
            return True
        # narrative 앞 30자 일치 → 중복
        if narrative and h.get('narrative', '')[:30] == narrative:
            return True
        # article_ids 교집합이 새 pitch의 50% 이상이면 중복
        if new_ids:
            old_ids = set(str(x).lstrip('#').strip() for x in h.get('article_ids', []) if str(x).strip())
            if old_ids:
                overlap = len(old_ids & new_ids)
                if overlap / len(new_ids) >= 0.5:
                    return True
        # article_urls 교집합이 새 pitch의 50% 이상이면 중복
        if new_urls:
            old_urls = set(h.get('article_urls', []))
            if old_urls:
                overlap = len(old_urls & new_urls)
                if overlap / len(new_urls) >= 0.5:
                    return True
        # entity overlap (다른 매체 같은 주제 탐지)
        old_entities = set()
        for t in h.get('article_original_titles', []):
            old_entities.update(extract_title_entities(t))
        if new_entities and old_entities and len(new_entities & old_entities) >= 2:
            return True
    return False

def save_pitch_to_history(pitch):
    """선택된 피치를 posted.json 피치 이력에 저장"""
    import json as _json
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'posted.json')
    try:
        data = {}
        if os.path.exists(path):
            with open(path) as f:
                data = _json.load(f)
        if 'pitch_history' not in data:
            data['pitch_history'] = []
        entities = set()
        for t in pitch.get('article_original_titles', []):
            entities.update(extract_title_entities(t))
        data['pitch_history'].append({
            'hook': pitch.get('hook', '')[:30],
            'narrative': pitch.get('narrative', '')[:50],
            'article_ids': pitch.get('article_ids', []),
            'article_urls': pitch.get('article_urls', []),
            'article_titles': pitch.get('article_titles', []),
            'article_original_titles': pitch.get('article_original_titles', []),
            'entities': list(entities),
            'date': datetime.now().strftime('%Y-%m-%d')
        })
        with open(path, 'w') as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def get_pitches(articles, max_articles=600, batch_size=200):
    """배치 처리: articles를 batch_size개씩 배치로 나눠 각 배치에서 피치 생성 → TOP 1 반환"""
    from v3.model_router import chat_completion
    from db_reader import load_posted
    pitch_history = load_pitch_history()
    posted = load_posted()
    if pitch_history:
        log(f'  피치 이력: {len(pitch_history)}개 존재')

    # 기사 셔플 후 배치 분할
    selected = articles[:max_articles]
    shuffled = selected.copy()
    random.shuffle(shuffled)
    batches = [shuffled[i:i+batch_size] for i in range(0, len(shuffled), batch_size)]
    log(f'[배치 처리] 총 {len(shuffled)}개 → {batch_size}개 × {len(batches)}배치')

    # 배치별 id→필드 매핑 (전체 기사 기준)
    id_to_link = {}
    id_to_title = {}
    id_to_original_title = {}
    for a in shuffled:
        aid = str(a.get('id', ''))
        if aid:
            id_to_link[aid] = a.get('link', '')
            id_to_title[aid] = a.get('title', '')
            id_to_original_title[aid] = a.get('original_title', '')

    all_pitches = []
    for idx, batch in enumerate(batches):
        log(f'[배치 {idx+1}/{len(batches)}] {len(batch)}개 기사 처리 중...')

        # 배치별 기사 텍스트 변환
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

        # DeepSeek V4 Pro 호출
        try:
            resp = chat_completion(
                system_prompt=SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': f"""아래 {len(batch)}개 기사 전체를 보고, 가장 강력한 이야기 3개를 찾아 PITCH JSON 형식으로 출력해주세요.

{all_articles_joined}"""}],
                temperature=0.9,
                max_tokens=3000,
            )
            pitches = parse_pitches_from_text(resp, articles_text)
            log(f'[배치 {idx+1}/{len(batches)}] → {len(pitches)}개 피치 발견 (Qwen3 Next 80B)')

            # Qwen3 Next 80B 실패 시 GPT-4o-mini fallback
            if not pitches:
                log(f'  ⚠️ DiffusionGemma JSON 파싱 실패 → GPT-4o-mini fallback')
                from v3.model_router import chat_completion as _cc
                resp2 = _cc(
                    system_prompt=SYSTEM_PROMPT,
                    messages=[{'role': 'user', 'content': f"""아래 {len(batch)}개 기사 전체를 보고, 가장 강력한 이야기 3개를 찾아 PITCH JSON 형식으로 출력해주세요.

{all_articles_joined}"""}],
                    temperature=0.9,
                    max_tokens=3000,
                    model_override='openai',
                )
                pitches = parse_pitches_from_text(resp2, articles_text)
                log(f'[배치 {idx+1}/{len(batches)}] → {len(pitches)}개 피치 발견 (GPT-4o-mini)')
        except Exception as e:
            log(f'  ⚠️ 배치 {idx+1} 오류: {e}')
            continue

        all_pitches.extend(pitches)

    if not all_pitches:
        log('  ❌ 피치 없음')
        return []

    log(f'[전체] {len(all_pitches)}개 후보 발견')

    # hook 길이 검증 (최소 5자)
    valid = []
    for p in all_pitches:
        hook = p.get('hook', '')
        if len(hook) >= 5:
            valid.append(p)
        else:
            log(f'  ⚠️ hook {len(hook)}자 미달 제외: "{hook[:20]}"')

    if not valid:
        log('  ❌ 모든 피치 hook 길이 조건 불만족')
        return []

    # 중복 피치 제외
    unique = []
    for p in valid:
        # article_ids에서 각 필드 매핑
        p_urls = []
        p_titles = []
        p_original_titles = []
        for aid in p.get('article_ids', []):
            aid_str = str(aid).lstrip('#').strip()
            if aid_str:
                p_urls.append(id_to_link.get(aid_str, ''))
                p_titles.append(id_to_title.get(aid_str, ''))
                p_original_titles.append(id_to_original_title.get(aid_str, ''))
        p['article_urls'] = p_urls
        p['article_titles'] = p_titles
        p['article_original_titles'] = p_original_titles

        if is_duplicate_pitch(p, pitch_history, posted):
            log(f'  ⚠️ 중복 피치 제외: "{p.get("hook", "")[:30]}" (기사: {len(p.get("article_ids", []))}개)')
        else:
            unique.append(p)

    log(f'[전체] {len(valid)}개 후보 → 중복 제외 후 {len(unique)}개')

    if not unique:
        log('  ❌ 모든 피치가 이력과 중복')
        return []

    # 품질 평가 게이트
    from v3.pitch_evaluator import filter_pitches
    top = filter_pitches(unique)

    if not top:
        log('  ❌ 모든 피치 품질 평가 불통')
        return []

    log(f'  ✅ TOP 1: "{top.get("hook", "")}" ({top.get("emotion", "")})')
    log(f'     기사: {top.get("article_ids", [])}')

    return [top] if top else []


if __name__ == '__main__':
    from db_reader import get_articles
    articles = get_articles()
    pitches = get_pitches(articles)
    if pitches:
        p = pitches[0]
        print(f'\n=== TOP PITCH ===')
        print(f'  Hook: {p.get("hook")}')
        print(f'  Narrative: {p.get("narrative")}')
        print(f'  Twist: {p.get("twist")}')
        print(f'  Emotion: {p.get("emotion")}')
        print(f'  Articles: {p.get("article_ids")}')
        print(f'  Sources: {p.get("sources")}')
        print(f'  Comparison: {p.get("comparison_unit")}')
    else:
        print('\n❌ 피치 없음')
