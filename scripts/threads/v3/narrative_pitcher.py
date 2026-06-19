#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
narrative_pitcher.py — 100개 기사 → 가장 강력한 이야기 발견
- 모델: gpt-4o-mini (비용 절감)
- 50개씩 2개 청크 → 각 2개 피치 → 총 4개 → TOP 1 선정
"""
import os, sys, json, re
from datetime import datetime

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

[금지]
- 너무 많이 논의된 상식("AI가 일자리를 뺏는다", "AI가 미래다", "기술 발전이 중요하다")은 피할 것.
- 독자가 '어? 나는 몰랐는데?' 하는 상식과 실제의 충돌을 찾을 것.

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
{"hook": "이야기의 핵심 긴장을 한 줄로. 길이 제한 없음.", "narrative": "상식(A) vs 실제(B) — 한 줄", "twist": "A가 아니고 B인 진짜 이유", "emotion": "충격/불안/자부심/분노/놀라움", "article_ids": [2개이상 반드시], "sources": ["URL들"], "comparison_unit": "체감단위"}

중요: 
- 반드시 2개 이상의 다른 기사를 연결할 것.
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

def is_duplicate_pitch(pitch, history):
    """비슷한 피치가 이미 history에 있는지 확인 (내용 기반)"""
    hook = pitch.get('hook', '')[:8]
    narrative = pitch.get('narrative', '')[:30]
    for h in history:
        # hook 앞 8자 일치 → 중복
        if h.get('hook', '')[:8] == hook:
            return True
        # narrative 앞 30자 일치 → 중복
        if narrative and h.get('narrative', '')[:30] == narrative:
            return True
        # 같은 article_ids 조합
        old_ids = set(str(x) for x in h.get('article_ids', []))
        new_ids = set(str(x) for x in pitch.get('article_ids', []))
        if old_ids and new_ids and old_ids == new_ids:
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
            'article_ids': pitch.get('article_ids', []),
            'date': datetime.now().strftime('%Y-%m-%d')
        })
        # 최대 30개 유지
        if len(data['pitch_history']) > 30:
            data['pitch_history'] = data['pitch_history'][-30:]
        with open(path, 'w') as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def get_pitches(articles, max_articles=100):
    """100개 기사 → TOP 1 피치 (단일 호출)"""
    from v3.model_router import chat_completion
    pitch_history = load_pitch_history()
    if pitch_history:
        log(f'  피치 이력: {len(pitch_history)}개 존재')

    # 기사 텍스트 변환
    articles_text = []
    for a in articles[:max_articles]:
        aid = a.get('id', '')
        title = a.get('title', '')
        desc = (a.get('description', '') or '')[:500]
        source = a.get('source', '')
        link = a.get('link', '')
        articles_text.append(f"""기사 #{aid}:
제목: {title}
본문: {desc}
출처: {source}
링크: {link}""")

    if not articles_text:
        return []

    all_articles_joined = '\n---\n'.join(articles_text)
    log(f'  {len(articles_text)}개 기사 단일 호출...')

    try:
        resp = chat_completion(
            system_prompt=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': f"""아래 100개 기사 전체를 보고, 가장 강력한 이야기 3개를 찾아 PITCH JSON 형식으로 출력해주세요.

{all_articles_joined}"""}],
            temperature=0.9,
            max_tokens=3000,
        )
        pitches = parse_pitches_from_text(resp, articles_text)
        log(f'  → {len(pitches)}개 피치 발견 (DiffusionGemma)')

        # DiffusionGemma 실패 시 GPT-4o-mini fallback
        if not pitches:
            log('  ⚠️ DiffusionGemma JSON 파싱 실패 → GPT-4o-mini fallback')
            from v3.model_router import chat_completion as _cc
            resp2 = _cc(
                system_prompt=SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': f"""아래 100개 기사 전체를 보고, 가장 강력한 이야기 3개를 찾아 PITCH JSON 형식으로 출력해주세요.

{all_articles_joined}"""}],
                temperature=0.9,
                max_tokens=3000,
                model_override='openai',
            )
            pitches = parse_pitches_from_text(resp2, articles_text)
            log(f'  → {len(pitches)}개 피치 발견 (GPT-4o-mini)')
    except Exception as e:
        log(f'  ⚠️ 오류: {e}')
        return []

    if not pitches:
        log('  ❌ 피치 없음')
        return []

    # hook 길이 검증 (최소 5자, 상한 없음)
    valid = []
    for p in pitches:
        hook = p.get('hook', '')
        if len(hook) >= 5:
            valid.append(p)
        else:
            log(f'  ⚠️ hook {len(hook)}자 미달 제외: "{hook[:20]}"')

    if not valid:
        log('  ❌ 모든 피치 hook 길이 조건 불만족')
        return []

    # 중복 피치 제외
    unique = [p for p in valid if not is_duplicate_pitch(p, pitch_history)]
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

    save_pitch_to_history(top)
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
