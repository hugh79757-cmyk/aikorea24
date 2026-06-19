#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
writer_v3.py — 피치 → 쓰레드 작성
- 모델: gpt-4o (1회, 3회 재시도)
- 입력: pitcher의 내러티브 + 관련 기사
- 출력: ["조각1", "조각2", ...]
"""
import os, sys, json, re
from datetime import datetime
import requests
from bs4 import BeautifulSoup

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

STYLE_EXAMPLES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'style_examples.md')

def load_style_examples():
    """style_examples.md 로드. 파일 없으면 빈 문자열 반환."""
    try:
        with open(STYLE_EXAMPLES_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''

def build_system_prompt():
    examples = load_style_examples()
    return f"""당신은 AI 뉴스를 Threads용 3개 카드 쓰레드로 만드는 작가다.

[문체 원칙]
- 반말체. "~임", "~했음", "~있음", "~아님". "~합니다" "~입니다" 절대 금지.
- 한 줄에 하나의 정보. 짧게 끊어서 리듬감을 만든다.
- 날짜, 장소, 인물명으로 시작해서 독자를 사건 안으로 끌어당긴다.
- 형용사 금지. 감탄사 금지. 사실과 숫자만.
- 마지막 카드의 마지막 줄 바로 앞은 반드시 여운을 남긴다. 선언이나 반전으로 끝낸다.
- 이모지 금지. 볼드 금지. 이탤릭 금지.
- 카드 안에서도 주제가 바뀌거나 시점/장소/인물이 바뀌면 빈 줄로 나눠라. 같은 주제의 문장은 붙이고, 화제 전환 시에만 띄운다.

[숫자 원칙]
- 기사 본문에 있는 숫자는 전부 꺼내서 써라.
- 달러 금액, 퍼센트, 날짜, 사용자 수, 성장률 — 기사에 있으면 반드시 포함.
- 기사에 숫자가 없으면 "수십억", "대규모", "많은" 같은 뭉뚱그린 표현 금지.
- 숫자 없는 사실은 쓰지 마라.

[카드 구조 — 5개, --- 로 구분]
1번 카드 (5~6줄): 사건의 출발점. 날짜/장소/인물로 시작. 핵심 충돌을 설정한다. 독자가 "어?" 하고 멈추게 만든다.
2번 카드 (10~12줄): 충돌의 A면. 구체적 사실, 숫자, 인용, 연구 결과를 빽빽하게 채운다.
3번 카드 (10~12줄): 반전. 예상 못 한 제3의 사실. 방향 전환. 숫자와 사례로 가득 채운다.
4번 카드 (10~12줄): 확장. 더 큰 맥락 또는 연결점. 한국/독자와의 접점이 있으면 여기서, 없으면 자유롭게 확장.
5번 카드 (10~12줄): 여운. 지금까지 나온 숫자/사실을 한 번 더 반전시킨다. 마지막 줄은 선언형으로.

[밀도 기준]
1번 카드: 5~6줄. 독자를 빠르게 사건 안으로.
2~5번 카드: 최소 10줄. 원문의 숫자, 인물, 인용문, 날짜를 모두 꺼내서 채운다.
정보가 부족하면 기사 본문에서 더 파낸다. 없는 내용은 절대 만들지 않는다.

[참고 문체 예시 — 아래 스타일로 작성할 것]
{examples}"""

def fetch_article_body(url, max_chars=3000):
    """원문 기사 본문을 크롤링해서 텍스트 반환. 실패 시 빈 문자열."""
    if not url:
        return ''
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'lxml')
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript', 'iframe']):
            tag.decompose()
        body = None
        for selector in ['article', 'main', '[role="main"]', '.article-body', '.post-content', '.entry-content', '.story-body']:
            candidate = soup.select_one(selector)
            if candidate:
                body = candidate.get_text(separator='\n', strip=True)
                break
        if not body:
            body = soup.get_text(separator='\n', strip=True)
        lines = [l.strip() for l in body.split('\n') if l.strip()]
        text = '\n'.join(lines)
        if len(text) > max_chars:
            text = text[:max_chars] + '...'
        log(f'  📰 크롤링: {url[:50]}... ({len(text)}자)')
        return text
    except Exception as e:
        log(f'  ⚠️ 크롤링 실패: {url[:50]}... ({type(e).__name__})')
        return ''

def write_thread(pitch, all_articles):
    """피치 + 관련 기사 → 쓰레드 조각 리스트 (DiffusionGemma → GPT-4o-mini fallback)"""
    from v3.model_router import chat_completion

    # 관련 기사만 필터링
    article_ids = pitch.get('article_ids', [])
    related = [a for a in all_articles if a.get('id') in article_ids]

    # 그래도 없으면 첫 2개 사용
    if not related:
        related = all_articles[:2]

    related_parts = []
    for a in related:
        body = fetch_article_body(a.get('link', ''))
        if not body:
            body = (a.get('description', '') or '')[:500]
        related_parts.append(f"""기사 {a['id']}:
제목: {a.get('title','')}
본문: {body}
출처: {a.get('source','')}
링크: {a.get('link','')}""")
    related_text = '\n\n'.join(related_parts)

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
3. 각 카드는 --- 로 구분. 1번 카드 5~6줄. 2~5번 카드 최소 10줄.
4. 5개 카드로 작성할 것.
5. 기사 본문의 숫자(금액, 퍼센트, 날짜, 사용자 수)를 반드시 추출해서 써라. "많은", "대규모" 금지.
6. 같은 주제 문장은 붙이고, 시점/장소/인물 전환 시 빈 줄로 나눠라. """

    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            log(f'  쓰레드 생성 중...')
            content = chat_completion(
                system_prompt=build_system_prompt(),
                messages=[{'role': 'user', 'content': user_prompt}],
                temperature=0.7,
                max_tokens=5000,
            )
            if not content:
                raise Exception('모델 응답 없음')
            cards = parse_cards(content)

            if validate_cards(cards, pitch):
                cards = assemble_final(cards, pitch.get('sources', []))
                log(f'  ✅ 쓰레드: {len(cards)}개 조각 (시도 {attempt+1})')
                return cards
            else:
                log(f'  ⚠️ 검증 실패: {len(cards)}개 조각 (시도 {attempt+1}/{max_attempts})')
        except Exception as e:
            log(f'  ⚠️ 오류: {e} (시도 {attempt+1}/{max_attempts})')

    log(f'  ❌ {max_attempts}회 재시도 실패 → GPT-4o-mini fallback 1회')
    try:
        log(f'  쓰레드 생성 중... (GPT-4o-mini fallback)')
        content = chat_completion(
            system_prompt=build_system_prompt(),
            messages=[{'role': 'user', 'content': user_prompt}],
            temperature=0.7,
            max_tokens=5000,
            model_override='openai',
        )
        if not content:
            raise Exception('모델 응답 없음')
        cards = parse_cards(content)
        if validate_cards(cards, pitch):
            cards = assemble_final(cards, pitch.get('sources', []))
            log(f'  ✅ 쓰레드: {len(cards)}개 조각 (GPT-4o-mini fallback 성공)')
            return cards
    except Exception as e:
        log(f'  ⚠️ GPT-4o-mini fallback 오류: {e}')

    log('  ❌ 전체 재시도 실패')
    return []

def parse_cards(text):
    """---로 구분된 조각 파싱"""
    cards = [c.strip() for c in text.split('---') if c.strip()]
    return cards

def validate_cards(cards, pitch):
    """기본 검증"""
    if not cards or len(cards) < 5:
        log(f'    → 카드 수 부족: {len(cards)}개 (필요: 5개)')
        return False
    # 첫 문장에 hook 포함 확인
    first = cards[0].strip()
    hook = pitch.get('hook', '')
    if hook and hook[:8] not in first:
        log(f'    → hook 불일치: 첫 줄 시작="{first[:30]}..." 예상 hook[:8]="{hook[:8]}"')
        return False
    return True

def assemble_final(cards, sources):
    """대표 URL 1개를 마지막 카드로 추가"""
    if sources:
        cards.append(f'🔗 {sources[0]}')
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
