#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
writer_v3.py — 피치 → 쓰레드 작성
- 모델: gpt-4o (1회, 3회 재시도)
- 입력: pitcher의 내러티브 + 관련 기사
- 출력: ["조각1", "조각2", ...]
"""
import os, sys, json, re
from datetime import datetime

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
DRAFTS_DIR = os.path.join(LOGS_DIR, 'drafts')
os.makedirs(DRAFTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [v3] {msg}\n')

CTA_FOOTER = """aikorea24.kr"""

WRITER_SYSTEM_PROMPT = """당신은 뉴스를 Threads 쓰레드로 만드는 사람입니다.

[목표 — 뉴스 기사들을 엮어서 7개 카드 쓰레드 작성. 각 카드는 정보로 빽빽해야 함.]

[카드 구성]
1/7: (hook 한 줄. 선언형. 숫자 포함.) → (이어서 A vs B 충돌 전개, 3줄) → "근데 진짜 이유는..."
2/7: (A측 구체적 사실들. 숫자, 인물, 날짜. 5줄 이상)
3/7: (B측 구체적 사실들. A와 대비되는 내용. 5줄 이상)
4/7: (추가 반전 또는 확장. 예상 못 한 제3의 사실. 5줄 이상)
5/7: (한국 연결점. 한국 기업/정부/독자와의 접점. 5줄 이상)
6/7: 🔗 URL1\n🔗 URL2
7/7: aikorea24.kr

[필수 규칙]
1. 반말체: "~임", "~했음", "~있음", "~아님". "~합니다" 절대 금지.
2. 첫 줄 = hook 정확히 한 줄. 질문형 금지.
3. 한 줄 하나의 정보. 최대 25자. 짧게 끊어서 리듬감.
4. 각 카드 최소 5줄 (카드 번호 줄 제외).
5. **1번 카드 마지막 줄은 반드시 "근데 진짜 이유는..."으로 끝날 것.** 이걸로 독자의 궁금증 유발.
6. **5번 카드(한국 연결)는 반드시 한국 기업명 1개 + 숫자 1개 이상 포함.** "한국 기업들", "정부", "필요함" 같은 추상적 표현 금지.
   좋은 예: "삼성전자, AI 반도체에 15조 투자" / "과기정통부, 전기료 20% 인하 추진"
   나쁜 예: "한국 기업들 AI 도입 가속화" / "정부 정책 지원 필요함"
7. 숫자는 체감 단위로 환산: "잠실 수영장 40개 분량", "한강 유량의 3분의 1"
8. 형용사 금지. 감탄사 금지. 사실과 숫자만.
9. 이모지, 볼드, 이탤릭 금지.
10. 마지막 카드: "aikorea24.kr" 한 줄만."""

def write_thread(pitch, all_articles):
    """피치 + 관련 기사 → 쓰레드 조각 리스트 (GPT-4o 직접 호출)"""
    from openai import OpenAI
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        log('  ❌ OPENAI_API_KEY 없음')
        return []
    gpt_client = OpenAI(api_key=api_key)

    # 관련 기사만 필터링
    article_ids = pitch.get('article_ids', [])
    related = [a for a in all_articles if a.get('id') in article_ids]

    # 그래도 없으면 첫 2개 사용
    if not related:
        related = all_articles[:2]

    related_text = '\n\n'.join([
        f"""기사 {a['id']}:
제목: {a.get('title','')}
본문: {(a.get('description','') or '')[:500]}
출처: {a.get('source','')}
링크: {a.get('link','')}"""
        for a in related
    ])

    user_prompt = f"""아래 피치와 기사들을 바탕으로 Threads 쓰레드를 작성해주세요.

=== 피치 ===
첫 문장 (변경 금지): {pitch['hook']}
핵심 이야기: {pitch.get('narrative','')}
반전: {pitch.get('twist','')}
감정: {pitch.get('emotion','')}
체감 단위: {pitch.get('comparison_unit','')}

=== 관련 기사 ===
{related_text}

=== 요구사항 ===
1. 첫 문장은 반드시 "{pitch['hook']}" 그대로 사용할 것
2. 반말체(~임, ~했음, ~있음). ~합니다 금지.
3. 한 줄 하나의 정보. 최대 25자. 짧게 끊을 것.
4. 각 카드는 --- 로 구분. 각 카드 최소 4줄.
5. 마지막-1 카드: 🔗 URL
6. 마지막 카드: aikorea24.kr"""

    for attempt in range(3):
        try:
            log(f'  [GPT-4o] 쓰레드 생성 중...')
            resp = gpt_client.chat.completions.create(
                model='gpt-4o',
                messages=[
                    {'role': 'system', 'content': WRITER_SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=0.7,
                max_tokens=3000,
            )
            content = resp.choices[0].message.content
            cards = parse_cards(content)

            if validate_cards(cards, pitch):
                cards = assemble_final(cards, pitch.get('sources', []))
                log(f'  ✅ 쓰레드: {len(cards)}개 조각 (시도 {attempt+1})')
                return cards
            else:
                log(f'  ⚠️ 검증 실패: {len(cards)}개 조각 (시도 {attempt+1}/3)')
        except Exception as e:
            log(f'  ⚠️ 오류: {e} (시도 {attempt+1}/3)')

    log('  ❌ 3회 재시도 실패')
    return []

def parse_cards(text):
    """---로 구분된 조각 파싱"""
    cards = [c.strip() for c in text.split('---') if c.strip()]
    return cards

def validate_cards(cards, pitch):
    """기본 검증"""
    if not cards or len(cards) < 4:
        return False
    # 첫 문장에 hook 포함 확인
    first = cards[0].strip()
    hook = pitch.get('hook', '')
    if hook and hook[:8] not in first:
        return False
    # 출처 확인
    all_text = '\n'.join(cards)
    if 'http' not in all_text:
        return False
    # 마지막 카드 확인
    if 'aikorea24' not in cards[-1]:
        return False
    # 출처 확인
    if len(cards) >= 2:
        if '출처:' not in cards[-2] and 'http' not in cards[-2]:
            return False
    return True

def assemble_final(cards, sources):
    """출처 보강만 (CTA는 GPT가 생성한 것 유지)"""
    if len(cards) >= 2 and sources:
        prev = cards[-2]
        has_url = any(s in prev for s in sources[:1])
        if not has_url:
            urls = '\n'.join(f'🔗 {s}' for s in sources)
            cards[-2] = prev + f'\n\n{urls}'
    return cards

    return cards

def save_draft(cards, pitch):
    """초안 저장"""
    now = datetime.now()
    safe = re.sub(r'[^a-zA-Z0-9가-힣]', '', pitch.get('hook', ''))[:20]
    fname = f'v3_{now.strftime("%Y-%m-%d-%H")}_{safe}.txt'
    fpath = os.path.join(DRAFTS_DIR, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write('\n---\n'.join(cards))
    log(f'  💾 초안 저장: {fpath}')
    return fpath


if __name__ == '__main__':
    from db_reader import get_articles
    from v3.narrative_pitcher import get_pitches
    articles = get_articles()
    pitches = get_pitches(articles)
    if pitches:
        cards = write_thread(pitches[0], articles)
        if cards:
            print(f'\n{"="*60}')
            print('\n---\n'.join(cards))
            print(f'\n{"="*60}')
            save_draft(cards, pitches[0])
    else:
        print('피치 없음 → 스킵')
