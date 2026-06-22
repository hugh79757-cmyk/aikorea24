#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
writer_v3.py — 피치 → 쓰레드 작성
- 모델: gpt-4o (1회, 3회 재시도)
- 입력: pitcher의 내러티브 + 관련 기사
- 출력: ["조각1", "조각2", ...]
"""
import os, sys, json, re
import urllib.request, urllib.parse
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
- 각 문장은 구체적인 사실(숫자, 인물, 날짜)을 포함해 최소 2~3줄로 서술하라. 한 줄짜리 축약 문장 금지.
- 인과관계를 설명하라. "A → B"가 아니라 "A로 인해 B가 발생한 이유는..." 식으로 풀어써라.
- 날짜, 장소, 인물명으로 시작해서 독자를 사건 안으로 끌어당긴다.
- 형용사 금지. 감탄사 금지. 사실과 숫자만.
- 마지막 카드의 마지막 줄 바로 앞은 반드시 여운을 남긴다. 선언이나 반전으로 끝낸다.
- 이모지 금지. 볼드 금지. 이탤릭 금지.
- 카드 안에서도 주제가 바뀌거나 시점/장소/인물이 바뀌면 빈 줄로 나눠라. 같은 주제의 문장은 붙이고, 화제 전환 시에만 띄운다.
- 고유명사(기업명, 인물명, 제품명)는 영어 원문을 그대로 사용하라. 예: 화웨이(X) → Huawei(O), 앤트로픽(X) → Anthropic(O), 오픈AI(X) → OpenAI(O)

[연도 원칙 — 중요]
- 기사 본문에 명시된 날짜/연도만 사용하라.
- 본문에 연도가 없으면 쓰레드에도 연도를 표시하지 마라.
- 예: 본문에 "2026년 5월 30일" → "2026년 5월 30일" 사용
- 예: 본문에 "5월 30일" (연도 없음) → "5월 30일"만 사용, 연도 추가 금지
- 예: 본문에 날짜 언급 자체가 없음 → 날짜/연도 아예 표시 금지
- 기사의 발행일(입력일)을 사건 발생일로 사용하지 마라.

[숫자 원칙]
- 기사 본문에 있는 숫자는 전부 꺼내서 써라.
- 달러 금액, 퍼센트, 날짜, 사용자 수, 성장률 — 기사에 있으면 반드시 포함.
- 기사에 숫자가 없으면 "수십억", "대규모", "많은" 같은 뭉뚱그린 표현 금지.
- 숫자 없는 사실은 쓰지 마라.

[카드 구조 — 5개, --- 로 구분]
1번 카드 (500자 이내): 첫 줄은 hook 그대로. 그 뒤에 구체적 사실(날짜/장소/숫자)을 이어붙여라. hook만 단독으로 쓰지 말고 내용을 채워라.
2번 카드 (500자 이내): 충돌의 A면. 구체적 사실, 숫자, 인용, 연구 결과를 빽빽하게 채운다.
3번 카드 (500자 이내): 반전. 예상 못 한 제3의 사실. 방향 전환. 숫자와 사례로 가득 채운다.
4번 카드 (500자 이내): 확장. 더 큰 맥락 또는 연결점.
5번 카드 (500자 이내): 여운. 지금까지 나온 숫자/사실을 한 번 더 반전시킨다. 마지막 줄은 선언형으로.

[밀도 기준]
1번 카드: 500자 이내.
2~5번 카드: 500자 이내. 원문의 숫자, 인물, 인용문, 날짜를 모두 꺼내서 채운다.
정보가 부족하면 기사 본문에서 더 파낸다. 없는 내용은 절대 만들지 않는다.
- 각 카드는 반드시 500자를 초과하지 않도록 작성하라. Threads API 제한.

[피치 메타데이터 — 출력 금지]
- "핵심 이야기:", "반전:", "감정:", "체감 단위:" 등의 피치 메타데이터 레이블을
  쓰레드 본문에 절대 포함하지 마라.
- 쓰레드는 기사 본문의 사실만으로 구성하고, 메타데이터는 참고용으로만 사용하라.

[참고 문체 예시 — 아래 스타일로 작성할 것]
{examples}"""

def fetch_article_body(url):
    """원문 기사 본문을 크롤링해서 텍스트 반환. 실패 시 빈 문자열.
    URL은 D1 DB에서 이미 제공되므로, 본문 텍스트만 반환 (URL 변경 금지).
    """
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
        log(f'  📰 크롤링: {url[:50]}... ({len(text)}자)')
        return text
    except Exception as e:
        log(f'  ⚠️ 크롤링 실패: {url[:50]}... ({type(e).__name__})')
        return ''

def fix_cards(cards):
    """GPT-4o-mini로 글자 단위 오류(첫 글자 드랍, 잘린 문자, 깨진 단어)만 수정
    내용/의미/구조는 변경하지 않음
    DiffusionGemma 대신 GPT-4o-mini 사용 — 자기 오류를 스스로 수정하는 구조적 문제 해결
    """
    from v3.model_router import chat_completion
    text = '\n---\n'.join(cards)
    prompt = f"""다음 Threads 쓰레드에서 글자 단위 오류만 수정하라.

[수정 대상 — 반드시 아래 패턴을 찾아 복구할 것]
- 첫 글자/숫자 생략: "국 청소년"→"미국 청소년",  "년 만에"→"1년 만에",  "비디아"→"엔비디아",  "트로픽"→"앤트로픽"
- 한국어 음절 생략: "데팅"→"데이팅",  "앱스"→"앱스토어",  "인공지"→"인공지능",  "챗지"→"챗GPT"
- 한글 자모 누락: "테크놀로지"→"테크놀로지",  "알고리즘"→"알고리즘",  "플랫폼"→"플랫폼"
- 단어 중간 음절 생략: "운동하기 위한"→"운영하기 위한" (영→운),  "수학올림픽"→"수학올림피아드" (픽→피아드)
- 중복 글자/단어: "모델 간 간"→"모델 간",  "있는 있는"→"있는"
- 따옴표/특수문자 오류: "'신발"→"신발",  "제조'"→"제조"

[금지 — 의미 변경 절대 금지]
- 문장의 내용/의미/구조를 절대 변경하지 말 것
- 틀린 글자는 올바른 글자로 교체하되, 원래 의도된 단어를 유지할 것
- 문장을 추가하거나 삭제하지 말 것
- 문체를 변경하지 말 것
- 수정할 게 없으면 원본을 그대로 반환할 것

[출력]
수정된 쓰레드 전체를 --- 구분자와 함께 그대로 출력하라. 원본과 동일한 카드 수를 유지할 것.

--- 쓰레드 시작 ---
{text}
--- 쓰레드 끝 ---"""
    try:
        result = chat_completion(
            system_prompt="당신은 한국어 텍스트 교정 전문가입니다. 글자 단위 오류만 정확히 수정합니다.",
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.1,
            max_tokens=8000,
            model_override='openai',
        )
        if result:
            fixed = [c.strip() for c in result.split('---') if c.strip()]
            if len(fixed) == len(cards):
                changed = sum(1 for i in range(len(cards)) if fixed[i] != cards[i])
                log(f'  🔧 오류 수정(GPT-4o-mini): {changed}/{len(cards)}개 카드 수정됨')
                return fixed
            log(f'  ⚠️ 수정 후 카드 수 불일치: {len(fixed)}≠{len(cards)} → 원본 유지')
        else:
            log(f'  ⚠️ 수정 실패 → 원본 유지')
    except Exception as e:
        log(f'  ⚠️ 수정 오류: {e} → 원본 유지')
    return cards


def write_thread(pitch, all_articles):
    """피치 + 관련 기사 → 쓰레드 조각 리스트 (DiffusionGemma → GPT-4o-mini fallback)"""
    from v3.model_router import chat_completion

    # 관련 기사만 필터링
    article_ids = pitch.get('article_ids', [])
    # 타입 안전: str/int/#접두사 혼용 대비
    article_id_set = set()
    for aid in article_ids:
        raw = str(aid).lstrip('#').strip()
        try:
            article_id_set.add(int(raw))
        except (ValueError, TypeError):
            article_id_set.add(str(aid).strip())
    related = []
    for a in all_articles:
        db_id = a.get('id')
        if db_id in article_id_set:
            related.append(a)
            continue
        # str로 한 번 더 시도 (DB 타입 불확실 대응)
        try:
            if str(int(db_id)) in article_id_set or str(db_id) in article_id_set:
                related.append(a)
        except (ValueError, TypeError):
            if str(db_id) in article_id_set:
                related.append(a)

    # 매칭 실패 → 스킵 (다음 주제로)
    if not related:
        log(f'  ⚠️ 피치 article_ids({article_ids})를 DB 풀에서 찾을 수 없음 → 스킵')
        return []

    related_parts = []
    article_bodies = []
    all_fallback = True
    for a in related:
        body = fetch_article_body(a.get('link', ''))
        if not body:
            body = (a.get('description', '') or '')[:500]
        else:
            all_fallback = False
        article_bodies.append(body)
        pub_date_str = str(a.get('pub_date', ''))
        related_parts.append(f"""기사 {a['id']}:
제목: {a.get('title','')}
발행일: {pub_date_str}
본문: {body}
출처: {a.get('source','')}
링크: {a.get('link','')}""")
    related_text = '\n\n'.join(related_parts)

    # 모든 기사 크롤링 실패 → 무조건 스킵 (RSS description만으로 품질 보장 불가)
    if all_fallback:
        log(f'  ⚠️ 모든 기사 원문 크롤링 실패 → 스킵 (hallucination 방지)')
        return []

    # 연도 검증용: 기사 본문 텍스트 (메타데이터 제외)
    article_body_text = ' '.join(article_bodies)

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
1. 첫 문장(hook)은 반드시 "{pitch['hook']}" 그대로 사용할 것. 단, hook이 1번 카드의 유일한 문장이 되어서는 안 됨. hook 뒤에 날짜/장소/숫자로 내용을 이어붙여 1번 카드를 5~6줄로 채워라.
2. 반말체(~임, ~했음, ~있음). ~합니다 금지.
3. 각 카드는 --- 로 구분. 각 카드는 반드시 500자 이내로 작성할 것. 500자 초과 시 API가 거부함.
4. 5개 카드로 작성할 것.
5. 기사 본문의 숫자(금액, 퍼센트, 날짜, 사용자 수)를 반드시 추출해서 써라. "많은", "대규모" 금지.
6. 같은 주제 문장은 붙이고, 시점/장소/인물 전환 시 빈 줄로 나눠라.
7. "핵심 이야기:", "반전:", "감정:", "체감 단위:" 등의 피치 메타데이터 레이블을 쓰레드에 절대 포함하지 마라. """

    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            log(f'  쓰레드 생성 중...')
            from v3.model_router import WRITER_NVIDIA_MODEL
            content = chat_completion(
                system_prompt=build_system_prompt(),
                messages=[{'role': 'user', 'content': user_prompt}],
                temperature=0.7,
                max_tokens=5000,
                nvidia_model=WRITER_NVIDIA_MODEL,
            )
            if not content:
                raise Exception('모델 응답 없음')
            cards = parse_cards(content)
            cards = fix_cards(cards)

            if validate_cards(cards, pitch) and validate_year(cards, article_body_text) and validate_keywords(cards, article_body_text):
                # article_ids[0] 링크를 1순위로 사용
                primary_url = next((a.get('link','') for a in related if str(a.get('id','')) == str(article_ids[0]).lstrip('#').strip()), '')
                cards = assemble_final(cards, related, primary_url)
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
        cards = fix_cards(cards)
        if validate_cards(cards, pitch) and validate_year(cards, article_body_text) and validate_keywords(cards, article_body_text):
            primary_url = next((a.get('link','') for a in related if str(a.get('id','')) == str(article_ids[0]).lstrip('#').strip()), '')
            cards = assemble_final(cards, related, primary_url)
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
    """기본 검증 (hook 정합성 + 카드 수)"""
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

def validate_year(cards, article_body_text):
    """연도 검증: 쓰레드 본문(1번 카드 첫 줄 제외)의 연도가 기사 본문에 있는 연도인지 확인
    - pitcer가 생성한 hook(1번 카드 첫 줄)은 검증에서 제외 (변경 불가이므로)
    - 기사 본문에 없는 연도를 쓰레드 본문이 표시하면 할루시네이션 → 실패
    - 단, 현재 연도(current_year)는 본문에 없어도 허용 (문맥상 자연스러운 사용)
    """
    body_text = article_body_text or ''
    current_year = datetime.now().year

    # hook(1번 카드 첫 줄)은 pitcer 생성 → 검증 제외
    first_card = cards[0] if cards else ''
    hook_line = first_card.split('\n')[0] if first_card else ''
    rest_text = ' '.join(cards)
    # rest_text에서 hook_line 제거
    rest_text = rest_text.replace(hook_line, '', 1)

    rest_years = set()
    for m in re.finditer(r'(?<!\d)20\d{2}(?!\d)', rest_text):
        rest_years.add(int(m.group()))

    body_years = set()
    for m in re.finditer(r'(?<!\d)20\d{2}(?!\d)', body_text):
        body_years.add(int(m.group()))

    # 본문(hook 제외)에 연도가 없음 → 통과
    if not rest_years:
        log(f'    → 연도 검증 통과: 본문(hook 제외)에 연도 미표기')
        return True

    # 현재 연도는 본문에 없어도 허용 (문맥상 자연스러움)
    allowed = body_years | {current_year}

    # 본문(hook 제외)의 연도가 허용된 연도 안에 있는지 확인
    invented = rest_years - allowed
    if invented:
        log(f'    → 연도 검증 실패: 본문에 없는 연도 {invented}를 쓰레드가 표시함 (허용={allowed})')
        return False

    log(f'    → 연도 검증 통과: 쓰레드 연도 {rest_years} ⊆ 허용 {allowed}')
    return True

def validate_keywords(cards, article_body_text):
    """키워드 검증: 기사 본문에 있는 핵심 한글 단어가 쓰레드에서 누락/변형됐는지 확인
    DiffusionGemma의 음절 잘림으로 인한 변형 탐지
    """
    body_text = article_body_text or ''
    thread_text = ' '.join(cards)
    if not body_text or not thread_text:
        return True  # 검증 불가 → 통과

    # 기사 본문에서 2~8자 한글 단어 추출 (2회 이상 등장하는 것만)
    from collections import Counter
    body_words = re.findall(r'[가-힣]{2,8}', body_text)
    body_counter = Counter(body_words)
    # 2회 이상 등장한 단어만 핵심 키워드로 간주
    keywords = {w for w, cnt in body_counter.items() if cnt >= 2 and len(w) >= 3}

    # 쓰레드에 등장하는 한글 단어 추출
    thread_words = set(re.findall(r'[가-힣]{2,}', thread_text))

    # 기사 핵심 키워드 중 쓰레드에 없는 것 탐지
    missing = []
    for kw in keywords:
        if kw not in thread_words:
            # 음절 잘림 패턴 탐지: 키워드 앞/뒤가 잘렸는지 확인
            # 예: "데이팅" → "데팅" (이 누락), "인공지능" → "인공지" (능 누락)
            truncated = False
            for tw in thread_words:
                # 키워드가 쓰레드 단어의 접두사 (앞이 잘린 경우)
                if len(tw) >= 2 and kw.startswith(tw) and len(tw) < len(kw):
                    truncated = True
                    missing.append((kw, tw, '접두사 잘림'))
                    break
                # 키워드가 쓰레드 단어의 접미사 (뒤가 잘린 경우)
                if len(tw) >= 2 and kw.endswith(tw) and len(tw) < len(kw):
                    truncated = True
                    missing.append((kw, tw, '접미사 잘림'))
                    break
            if not truncated and len(kw) >= 4:
                # 4자 이상 키워드가 쓰레드에 전혀 없으면 누락 의심
                missing.append((kw, '', '누락'))

    if missing:
        issues = [f'{kw}→{tw}({reason})' if tw else f'{kw}({reason})' for kw, tw, reason in missing]
        log(f'    → 키워드 검증 경고: {len(issues)}개 의심 키워드: {", ".join(issues[:5])}')
        # 치명적 누락(접두사 잘림)이 아니면 경고만 하고 통과
        critical = [m for m in missing if '잘림' in m[2]]
        if critical:
            log(f'    → 키워드 검증 실패: 접두사/접미사 잘림 {len(critical)}개')
            return False
        return True  # 누락 의심만 있고 잘림 없으면 통과

    log(f'    → 키워드 검증 통과: 핵심 단어 {len(keywords)}개 매칭')
    return True

def assemble_final(cards, articles, primary_url=None):
    """대표 URL 1개를 마지막 카드로 추가 (DB 저장된 실제 링크 사용)
    articles: D1 DB 기사 객체 리스트 (related)
    primary_url: article_ids[0]에 해당하는 기사의 링크 (가장 우선시)
    """
    from db_reader import validate_link

    # 1순위: primary_url (pitcher가 가장 중요하게 판단한 기사)
    if primary_url:
        if validate_link(primary_url, timeout=5):
            cards.append(f'🔗 {primary_url}')
            return cards
        log(f'  ⚠️ primary URL 유효성 실패: {primary_url[:50]}...')

    # 2순위: 나머지 related 기사 링크
    if articles:
        for a in articles:
            url = a.get('link', '').strip()
            if url == primary_url:
                continue  # 이미 시도함
            if not url or not url.startswith('http'):
                continue
            if validate_link(url, timeout=5):
                cards.append(f'🔗 {url}')
                return cards
            log(f'  ⚠️ URL 유효성 실패 — 다음 URL 시도: {url[:50]}...')
        log(f'  ❌ 모든 {len(articles)}개 URL 유효성 실패 — 링크 생략')
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
