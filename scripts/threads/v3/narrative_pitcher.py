#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
narrative_pitcher.py — 100개 기사 → 가장 강력한 이야기 발견
- 모델: gpt-4o-mini (비용 절감)
- 50개씩 2개 청크 → 각 2개 피치 → 총 4개 → TOP 1 선정
"""
import os, sys, json, re, random
from datetime import datetime
from db_reader import normalize_url

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
sys.path.insert(0, THREADS_DIR)
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

SYSTEM_PROMPT = """당신은 100개 기사에서 '상식과 실제의 충돌'을 찾아내는 스토리 파인더입니다.

[찾는 방법]
"상식적으로 A였어야 하는데 실제로는 B인 상황"을 찾아라.
그리고 왜 A가 아니고 B인지를 설명하는 기사들을 연결해라.

[hook]
hook: 이야기의 핵심 긴장을 한 줄로. 날짜/인물/숫자로 시작해도 됨. 길이 제한 없음.
- 고유명사(기업명, 인물명, 제품명)는 영어 원문을 사용하라. 예: 엔비디아(X) → Nvidia(O), 오픈AI(X) → OpenAI(O)

[금지]
- 너무 많이 논의된 상식("AI가 일자리를 뺏는다", "AI가 미래다", "기술 발전이 중요하다")은 피할 것.
- 독자가 '어? 나는 몰랐는데?' 하는 상식과 실제의 충돌을 찾을 것.

[소스 신뢰도]
- [1차] 태그 기사: 원문. 숫자/주어/방향을 그대로 사용할 것.
- [요약] 태그 기사: 2차 요약본. 주어-동사 방향이 뒤집혔을 수 있음.
  [요약] 기사만으로 twist 방향을 결정하지 말 것.

[예시]
- 상식: 미국이 AI 데이터센터 짓기에 가장 적합한 환경이다
- 실제: 가뭄으로 809개 중 3분의 2가 막혀있다
→ 연결된 기사들: "美 데이터센터 809개 가뭄" + "새만금 규제 83% 해제" + "삼성 평택 물갈등"

- 상식: 로스쿨일수록 AI를 적극 도입해야 한다
- 실제: UC버클리가 AI 사용을 전면 금지했다
→ 연결된 기사들: "UC버클리 AI 금지" + "AI 법률도구 6건 중 1건 오류"

- 상식: 스코틀랜드는 전력이 부족해서 데이터센터를 유치하기 어렵다
- 실제: 전력이 남아서 풍력발전기를 꺼달라고 돈을 주고 있다
→ 연결된 기사들: "스코틀랜드 600MW 데이터센터" + "풍력 발전중단 보상금 6,140억"

- 상식: 구글은 '해를 끼치지 않는다'는 AI 원칙을 가지고 있다
- 실제: 펜타곤과 '어떤 합법적 목적에도 사용 가능' 계약을 체결했다
→ 연결된 기사들: "구글 펜타곤 계약" + "구글 AI 원칙 삭제" + "9년차 엔지니어 사임"

[출력 형식 — JSON만]
{"hook": "이야기의 핵심 긴장을 한 줄로. 길이 제한 없음.", "narrative": "상식(A) vs 실제(B) — 한 줄", "twist": "A가 아니고 B인 진짜 이유", "emotion": "충격/불안/자부심/분노/놀라움", "article_ids": [1개 이상], "sources": ["URL들"], "comparison_unit": "체감단위"}

중요: 
- 2개 이상의 기사를 연결하면 더 강력함. 단, 관련 없는 기사를 억지로 연결하지 말 것.
- 기사 하나로도 쓰레드 작성이 가능함. 강제로 여러 기사를 연결할 필요 없음.
- '상식'은 기사에 없어도 됨. 네가 '이게 상식적으로는 A인데...' 하고 발견하면 됨."""

def fill_article_ids(pitch, articles_text):
    """피치의 hook/narrative로 관련 기사 ID 자동 매칭"""
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
    pitch['article_ids'] = [aid for _, aid in scored[:3]]
    if pitch['article_ids']:
        print(f'  [매칭] {len(pitch["article_ids"])}개 기사 연결')
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
        data['pitch_history'].append({
            'hook': pitch.get('hook', '')[:30],
            'narrative': pitch.get('narrative', '')[:50],
            'article_ids': pitch.get('article_ids', []),
            'article_urls': pitch.get('article_urls', []),
            'article_titles': pitch.get('article_titles', []),
            'article_original_titles': pitch.get('article_original_titles', []),
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

        # DiffusionGemma 호출
        try:
            resp = chat_completion(
                system_prompt=SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': f"""아래 {len(batch)}개 기사 전체를 보고, 가장 강력한 이야기 3개를 찾아 PITCH JSON 형식으로 출력해주세요.

{all_articles_joined}"""}],
                temperature=0.9,
                max_tokens=3000,
            )
            pitches = parse_pitches_from_text(resp, articles_text)
            log(f'[배치 {idx+1}/{len(batches)}] → {len(pitches)}개 피치 발견 (DiffusionGemma)')

            # DiffusionGemma 실패 시 GPT-4o-mini fallback
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
