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

WRITER_SYSTEM_PROMPT = """당신은 AI 뉴스를 Threads용 3개 카드 쓰레드로 만드는 작가다.

[문체 원칙]
- 반말체. "~임", "~했음", "~있음", "~아님". "~합니다" "~입니다" 절대 금지.
- 한 줄에 하나의 정보. 짧게 끊어서 리듬감을 만든다.
- 날짜, 장소, 인물명으로 시작해서 독자를 사건 안으로 끌어당긴다.
- 숫자는 항상 구체적으로. "많은", "대규모", "상당한" 금지.
- 형용사 금지. 감탄사 금지. 사실과 숫자만.
- 마지막 카드의 마지막 줄은 반드시 여운을 남긴다. 선언이나 반전으로 끝낸다.
- 이모지 금지. 볼드 금지. 이탤릭 금지.

[카드 구조 — 3개, --- 로 구분]
1번 카드: 사건의 출발점. 날짜/장소/인물로 시작. 핵심 충돌을 설정한다. 독자가 "어?" 하고 멈추게 만든다.
2번 카드: 충돌의 구체적 사실들. 숫자, 날짜, 인물, 금액. 반전이 있으면 여기서 터뜨린다.
3번 카드: 이 사건이 왜 중요한지. 더 큰 맥락 또는 한국/독자와의 연결. 마지막 줄은 여운.
마지막 줄: "기사 원문은 프로필 링크 참고!"

[밀도 기준]
각 카드는 최소 6줄. 억지로 늘이지 말고, 사실을 촘촘하게 채운다.
정보가 부족하면 기사에서 더 파낸다. 없는 내용은 만들지 않는다.

[위 예시들을 참고해서 그 스타일로 작성한다.]"""

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
3. 각 카드는 --- 로 구분. 각 카드 최소 6줄.
4. 3개 카드로 작성할 것.
5. 마지막 줄: "기사 원문은 프로필 링크 참고!" """

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
    if not cards or len(cards) < 3:
        return False
    # 첫 문장에 hook 포함 확인
    first = cards[0].strip()
    hook = pitch.get('hook', '')
    if hook and hook[:8] not in first:
        return False
    return True

def assemble_final(cards, sources):
    """출처 보강 없음. GPT가 생성한 그대로 반환"""
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
