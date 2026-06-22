#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
aikorea24 Threads 글 작성기
- OpenAI GPT-4o
- prompts/ 5개 파일 → system prompt
- 하드코딩 추가 규칙 포함
- --dry-run 지원
"""
import os, sys, re
from datetime import datetime
from openai import OpenAI

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
PROMPTS_DIR = os.path.join(THREADS_DIR, 'prompts')
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
DRAFTS_DIR = os.path.join(LOGS_DIR, 'drafts')
os.makedirs(DRAFTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

def load_env(path):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    if line.startswith('export '):
                        line = line[7:]
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_env(os.path.join(PROJECT_DIR, '.env'))
load_env(os.path.join(PROJECT_DIR, 'api_test', '.env.sh'))

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

def load_prompts():
    files = ['prompt_00_selector.md', 'prompt_A_storytelling.md', 'prompt_B_analysis.md',
             'prompt_C_brief.md', 'prompt_rules.md']
    texts = []
    for fname in files:
        fpath = os.path.join(PROMPTS_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                texts.append(f.read().strip())
            log(f'  프롬프트: {fname}')
        else:
            log(f'  ⚠️ {fname} 없음')
    return '\n\n'.join(texts)

HARD_RULES = """
[절대 금지 사항]
1. 각 카드 앞에 (훅), (데이터), (구조), (비교), (반전), (압축), (결론) 등
   어떤 형태의 레이블도 붙이지 말 것. 카드 번호(1/8)만 표기.
2. 마크다운 문법(**, ##, -, * 등) 사용 금지
3. 이모지 사용 금지
4. 볼드/이탤릭 등 서식 금지

[카드 구분]
각 카드는 반드시 "---" 한 줄로만 구분할 것.
카드 번호는 카드 첫 줄에 "1 / 8" 형식으로만 표기.

[카드 밀도]
- 각 카드는 최소 6줄 이상
- 1번 카드는 최소 8줄
- 2줄짜리 카드는 실패한 카드

[1번 카드 필수 구성]
- 인물 또는 기업의 구체적 행동 한 줄
- 독자가 모르는 반전 질문 한 줄
- 글로벌 vs 한국 대비 한 줄
- 숫자 최소 2개
- 독자 일상과 연결되는 체감 단위 한 줄
- 마지막 줄은 선언형

[문체]
- 문장 하나당 최대 20자
- 줄바꿈이 리듬
- "근데"를 반전 신호로 적극 활용
- 인물 이름 대신 역할로 표현
- 마지막 문장은 선언형

[카드 중복 금지]
- 같은 단어나 개념이 3개 이상 카드에 반복되면 실패
- 각 카드는 이전 카드에서 다루지 않은 새로운 정보를 반드시 포함
- 카드 순서: 1번(사건) → 2번(규모/숫자) → 3번(구조/배경) → 4번(비교) → 5번(글로벌vs한국) → 6번(반전/약점) → 7번(압축+출처) → 8번(CTA만)

[숫자 보강]
- 숫자가 나올 때 반드시 비교 맥락을 옆에 붙일 것
- 예: 5370억 달러 — 삼성전자 시총의 약 2배
- 카드 하나에 최소 숫자 1개 이상

[8번 카드 형식]
8번 카드는 CTA 3줄만 작성. 본문 내용 없음.
형식:
8 / 8

매일 아침 AI 브리핑, 이메일로 받아보세요.
프로필 링크에서 무료 구독 가능합니다.
aikorea24.kr

[6번 카드 한국 연결 규칙]
반드시 한국 기업명 또는 기관명을 1개 이상 명시할 것.
추상적 표현 금지. 예: 카카오, 네이버, 삼성 중 비슷한 구조를 가진 곳은 어디인지 구체적으로 서술.

[출처 위치]
- 7번 카드 맨 끝에 출처를 붙일 것
- 형식: "출처: [기사 원문 URL]"
- 8번 카드에는 출처를 절대 포함하지 말 것

[8번 카드 예시]
8 / 8

매일 아침 AI 브리핑, 이메일로 받아보세요.
프로필 링크에서 무료 구독 가능합니다.
aikorea24.kr
"""

def write_thread(article):
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        log('  ❌ OPENAI_API_KEY 없음')
        return ''

    prompt_texts = load_prompts()
    score = article.get('score', 0)
    fmt = 'A' if score >= 70 else ('B' if score >= 40 else 'C')

    system_prompt = f"{prompt_texts}\n\n{HARD_RULES}\n\n이번 글의 형식: 형식 {fmt} (점수 {score}점)"

    user_prompt = f"""다음 기사로 Threads 스레드를 작성해주세요.

기사 제목: {article.get('title', '')}
기사 본문: {article.get('description', '')}
AI 코멘트: {article.get('comment', '')}
출처: {article.get('source', '')}
원문 링크: {article.get('link', '')}

형식 {fmt}에 맞게 작성하세요.
카드 번호는 반드시 "1 / 8" 형식으로만 표기하고, 레이블(훅/데이터 등)은 절대 붙이지 마세요."""

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0.7,
            max_tokens=2500,
        )
        content = resp.choices[0].message.content.strip()
        content = re.sub(r'^```[a-z]*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
        content = content.strip()
        log(f'  GPT-4o: {len(content)}자, 형식 {fmt}')
        return content
    except Exception as e:
        log(f'  ❌ GPT 오류: {e}')
        return ''

def save_draft(content, article):
    now = datetime.now()
    safe = re.sub(r'[^a-zA-Z0-9가-힣]', '_', article.get('title', 'untitled'))[:30]
    fname = f'{now.strftime("%Y-%m-%d-%H")}-{safe}.txt'
    fpath = os.path.join(DRAFTS_DIR, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    log(f'  초안 저장: {fpath}')
    return fpath


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    from db_reader import get_articles
    from scorer import score_articles, determine_format
    articles = get_articles()
    scored = score_articles(articles)
    if not scored:
        print('선택할 기사 없음'); sys.exit(0)
    top = scored[0]
    fmt = determine_format(top['score'])
    print(f'선택: [{top["score"]}점|{fmt}] {top["title"]}')
    content = write_thread(top)
    if content:
        print(f'\n{"="*70}\n{content}\n{"="*70}')
        save_draft(content, top)
        if args.dry_run:
            print('\n[DRY RUN] 발행 생략')
