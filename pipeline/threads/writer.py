"""pipeline/threads/writer.py — Thread writing logic: format building, post-processing, assembly, orchestration."""
import os, sys, json, re, time, concurrent.futures
from datetime import datetime
from pathlib import Path
from collections import Counter

from pipeline.infra import project_root
from pipeline.infra.logger import get_scrubbed_logger

from pipeline.threads.validator import validate_cards, validate_year, validate_keywords, validate_final_output, validate_model_message, validate_card_structure
from pipeline.threads.validator import FORMAT_CARD_COUNTS, FORMAT_CARD_COUNT_TOLERANCE, MODEL_MESSAGE_PATTERNS
from pipeline.threads.crawler import fetch_article_body, log_failed_crawl

logger = get_scrubbed_logger(__name__)

PROJECT_DIR = project_root()
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
DRAFTS_DIR = os.path.join(LOGS_DIR, 'drafts')
FAILED_CRAWLS_FILE = os.path.join(LOGS_DIR, 'failed_crawls.json')
os.makedirs(DRAFTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)


def _log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(LOGS_DIR, datetime.now().strftime('%Y-%m-%d') + '.log'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] [v3] {msg}\n')


STYLE_EXAMPLES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts', 'threads', 'v3', 'style_examples.md')


def load_style_examples():
    try:
        with open(STYLE_EXAMPLES_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''


FORMAT_LABELS = {
    'D': '펀치 브리핑형 (5개 콘텐츠 카드 + 루트 답글 링크)',
}


def build_system_prompt_D():
    examples = load_style_examples()
    return f"""You are a journalist writing 5-card Korean threads on Threads, based on AI news articles.

FORMAT:
- 5 content cards only (card 1→5), no link card in the main chain
- Cards separated by ---
- Each card: max 500 characters (Threads API hard limit) — 각 카드는 이 공간을 충분히 활용해 구체적인 숫자·인용·비교 등 정보를 전달할 것

RHYTHM (핵심 스타일 — 반드시 따라라):
- 한 문장을 한 덩어리로 길게 쓰지 말고, **짧은 절 단위로 줄바꿈**해 리듬감을 만들어라
- 각 절은 10~25자 정도로 짧게. 문장 종결 어미(~임, ~했음)는 절 끝에 둘 것
- **절과 절 사이에는 반드시 빈 줄(\n\n)을 넣어라.** 빈 줄이 리듬의 쉼표다.
- 문장 하나가 60자를 넘지 않게 절단하라 (필수)
- 출력 예: "AI가 내 돈을\n\n대신 관리해준다고?\n\n핀테크 앱이\n은행 계좌에 직접 접근해\n자동 투자까지 가능함"

CONSTRAINTS:
- 종결어미 ~임/~했음/~있음 중심 (대화하듯 자연스럽게). ~다/~했다 신문 기사체는 Threads에 부자연스러우니 지양.
- 한자·일본어·히라가나·가타카나 절대 금지 — 발행이 차단됨
- DO NOT include pitch metadata labels like "핵심 이야기:", "반전:", "감정:" in the thread
- DO NOT include explanatory text, reasoning, or anything outside the JSON output

CARD 5 RULE (필수):
- 반드시 열린 질문, 불완전한 결론, 또는 반론을 유발하는 형태로 끝낼 것
- 물음표(?) 또는 열린 어미("~일까", "~일수록", "~인데" 등)로 종결
- 완결된 주장("~했다", "~이다")으로 끝내는 것 금지
- 독자가 답글을 쓰고 싶게 만드는 한 줄만 허용

OUTPUT FORMAT — JSON only, no explanation:
{{"cards": ["card1", "card2", "card3", "card4", "card5"]}}

STYLE — follow these examples exactly:
{examples}"""



FORMAT_BUILDERS = {
    'D': build_system_prompt_D,
}

INSTRUCTION_PATTERNS = [
    '다음 Threads 쓰레드의 AI 말투를',
    '[원본]',
    '[출력 규칙]',
    '수정된 쓰레드만 출력',
    '--- 구분자 정확히 유지',
    '내용(사실, 수치, 고유명사)은 절대 변경',
    '반말체(~임, ~했음, ~있음) 그대로 유지',
    '구분자 정확히 유지',
]





def _strip_model_explanatory(result: str) -> str:
    """Remove model explanatory messages from response."""
    lines = result.split('\n')
    filtered = []
    for line in lines:
        is_message = False
        for pattern in MODEL_MESSAGE_PATTERNS:
            if re.match(pattern, line.strip()):
                is_message = True
                break
        if not is_message:
            filtered.append(line)
    return '\n'.join(filtered)


def _strip_instruction_leak(text):
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if any(stripped.startswith(p) for p in INSTRUCTION_PATTERNS):
            continue
        if stripped.startswith('- 내용(') or stripped.startswith('- 반말체('):
            continue
        if stripped == '- --- 구분자 정확히 유지':
            continue
        if stripped == '- 수정된 쓰레드만 출력':
            continue
        if stripped == '-':
            continue
        cleaned.append(line)
    return '\n'.join(cleaned).strip()


# 실제 한국어 AI 출력에서 자주 관찰되는 패턴 (의미 불변 교체 대상)
# writer_v3.py 테스트 주석과 달리 humanize는 AI-어휘 방어용으로 보존됨
AI_KOREAN_PATTERNS = [
    ("획기적인", "새로운"),
    ("혁명적인", "큰"),
    ("궁극적으로", "결국"),
    ("가속화되", "빨라지"),
    ("융합하여", "합쳐"),
    ("핵심은", "중요한 건"),
    ("중요한 것은", "중요한 건"),
    ("~게 됩니다", "~게 돼"),
    ("~할 수 있습니다", "~할 수 있어"),
    ("~입니다.", "~임."),
    ("~합니다.", "~함."),
]


def humanize_cards(cards):
    from v3.model_router import chat_completion

    if not cards:
        return cards

    system_prompt = """당신은 한국어 Threads 쓰레드 에디터입니다. AI가 생성한 글에서 'AI 티'가 나는 패턴을 자연스러운 한국어로 교체합니다.
## 핵심 원칙
1. **의미 불변**: 사실·수치·고유명사·링크는 절대 변경 금지
2. **국소 수정**: 문장 전체를 재작성하지 말고 AI 티 구간만 교체
3. **과윤문 금지**: 전체의 30% 이상 변경 금지
4. **톤 유지**: 반말체(~임, ~했음, ~있음) 그대로 유지

## 교체 대상 패턴

**아래 패턴이 발견되면 반드시 즉시 교체하라. 미교체 시 실패로 간주된다.**

### 번역투 (가장 결정적 AI 시그니처)
- '~에 대해(서)' → '~를'
- '~를 통해/통하여' → '~로', '~해서'
- '~에 있어(서)' → '~에서'
- '~와 관련하여' → '~에', '~의'
- '~에 기반하여/바탕으로' → '~로', '~을 보고'
- '가지고 있다' → 동사·형용사로 환원
- '~되어진다' → '~된다' 또는 능동
- '~에 의해' → 행위자 주어로 ('AI에 의해 생성' → 'AI가 만든')
- '~할 수 있다' 남발 → 단언으로
- '~을 위해' → '~려고', '~하도록'

### AI 특유 관용구
- '결론적으로/따라서/이를 통해/그러므로/요약하면' → 3회 초과 시 일부 삭제
- '시사하는 바가 크다/주목할 만하다' → 삭제 또는 구체 결론
- '본질적으로/핵심적으로/궁극적으로' → 삭제
- 의인화 추상 주어 ('기술이 묻는다') → 사람·기관 주어
- '매우/정말/대단히/상당히' → 90% 삭제
- 동의어 이중 수식 ('중요하고 핵심적인') → 하나만

### 과장/과장/형용사 표현 (반드시 교체)
- '덜 아름다운' → '보기 좋은' 또는 사실 기반 표현
- '가장 중요한' → '핵심' 또는 삭제
- '놀랍게도' → 삭제
- '충격적으로' → 삭제
- '더 빠른/높은/큰' → '기존보다' 또는 삭제
- '이러한' → '이' 또는 삭제
- '그러한' → '이' 또는 삭제
- 과장 괄호 ('~등', '~외 다수') → 구체적 수치나 삭제
- '~것이다/~할 것이다' 미래 확정 → 현재형·확정형
- '~로 보인다/~인 듯하다' 추정 → 단언 가능하면 단언

### 리듬
- 단문만 반복 (복문·중문 부재) → 문장 길이 다양화
- 연결어미 뒤 쉼표 (-고, -며, -지만 뒤) → 쉼표 제거

### 영어 혼용 패턴 (한국어 텍스트 내 영어 누출 — 반드시 교체)
- 한글 문장 중간에 영어 단어가 공백 없이 붙어나오는 경우 → 해당 영어 제거 또는 자연스러운 한글로 교체
  예: "위험에Expose toExposed to" → "위험에 노출"
  예: "위험에Expose toExposed to비율임" → "위험에 노출된 비율임"
- 고유명사·제품명·브랜드명(OpenAI, CEO, Threads 등)은 제외 — 공백으로 분리되어 있으면 유지
- 영어 단어가 공백 없이 한글 앞뒤에 붙어 있으면 무조건 교체 대상

### 비표준 한국어 합성어
- '~시키다' 남용 → 자연스러운 능동형/피동형으로 교체
- '부차시하다', '우선시하다' 등 한자어+하다/시다 비표준 동사 → 자연스러운 표현으로 교체
  예: "부차시하고 있음" → "부차적으로 여기고 있음" 또는 "뒷전으로 미루고 있음"
- 영어-한국어 혼성어(하이브리드 합성어) 제거

## 절대 변경 금지
- 수치·날짜·통계
- 고유명사·제품명·브랜드명
- 직접 인용문
- 반말체 어미 (~임, ~했음, ~있음)

## 출력 규칙
- 수정된 쓰레드만 출력 (--- 구분자 포함)
- 설명·요약·메타 텍스트 절대 금지
- 원본과 동일한 카드 수 유지
- 카드 사이 --- 구분자 정확히 유지"""

    def _humanize_one(i, card):
        if len(card) < 10:
            return i, card
        prompt = f"""다음 카드의 AI 말투를 자연스러운 한국어로 다듬어라.

[카드 내용]
{card}

[출력 규칙]
- 내용(사실, 수치, 고유명사)은 절대 변경하지 말 것
- 반말체(~임, ~했음, ~있음) 그대로 유지
- 수정된 카드 내용만 출력 (부가 설명 금지)
- 수정할 게 없으면 원본을 그대로 반환"""
        try:
            result = chat_completion(
                system_prompt=system_prompt,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.3,
                max_tokens=2000,
                model_override=None,  # 무료 체인 사용 (GPT-4o-mini 제거 2026-08-12)
            )
            if result:
                result = _strip_instruction_leak(result)
                result = _strip_model_explanatory(result)
                result = result.strip()
                if result:
                    return i, result
            return i, card
        except Exception as e:
            _log(f'  ⚠️ humanize 카드 {i} 오류: {e} → 원본 유지')
            return i, card

    fixed = [None] * len(cards)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(cards)) as ex:
        fut_map = {ex.submit(_humanize_one, i, cards[i]): i for i in range(len(cards))}
        for fut in concurrent.futures.as_completed(fut_map):
            i, text = fut.result()
            fixed[i] = text
    changed = sum(1 for i in range(len(cards)) if fixed[i] != cards[i])
    _log(f'  🧹 humanize: {changed}/{len(cards)}개 카드 수정')
    return fixed


def _cleanup_source_attribution(cards):
    cleaned = []
    for card in cards:
        lines = card.split('\n')
        clean_lines = [l for l in lines if not re.match(r'^\s*출처\s*[:：]', l)]
        clean_lines = [l for l in clean_lines if '쓰레드 시작' not in l and '쓰레드 끝' not in l]
        clean_lines = [l for l in clean_lines if not re.match(r'^-{3,}\s*$', l)]
        if clean_lines:
            cleaned.append('\n'.join(clean_lines).strip())
    cleaned = [re.sub(r'(?<!\d)2000(?!\d)(?!년)', '', card) for card in cleaned]
    cleaned = [re.sub(r'^\s*\d+\s*/\s*\d+\s*\n?', '', card) for card in cleaned]
    cleaned = [re.sub(r'\*\*', '', card) for card in cleaned]  # 방어적: LLM이 남긴 볼드 마크다운 제거
    cleaned = [re.sub(r'\n{3,}', '\n\n', card).strip() for card in cleaned]
    return cleaned


def fix_cards(cards):
    return cards


def parse_cards_json_first(text: str, format_choice: str = 'D'):
    """Parse LLM output as JSON array: {"cards": ["...", "..."]}.
    Falls back to JSON extraction from surrounding text."""
    # 1단계: 직접 JSON 파싱
    cards = _try_parse_json(text, format_choice)
    if cards:
        return cards

    # 2단계: JSON 코드 블록 추출
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        cards = _try_parse_json(m.group(1), format_choice)
        if cards:
            return cards

    # 3단계: 중괄호로 둘러싸인 JSON 객체 추출
    brace_stack = []
    for i, ch in enumerate(text):
        if ch == '{':
            brace_stack.append(i)
        elif ch == '}' and brace_stack:
            start = brace_stack.pop()
            if not brace_stack:
                candidate = text[start:i+1]
                cards = _try_parse_json(candidate, format_choice)
                if cards:
                    _log(f'  ⚠️ 본문에서 JSON 추출 성공')
                    return cards

    # 4단계: delimiter 기반 fallback (---카드 1--- 또는 "카드 1:" 형식)
    delimiters = [
        (r'^[-=]{3,}\s*(?:카드|card)\s*\d+', r'^[-=]{3,}\s*$'),
        (r'^(?:카드|card)\s*\d+\s*[:.]', None),
    ]
    for start_pat, end_pat in delimiters:
        result = _parse_by_delimiter(text, start_pat, end_pat, format_choice)
        if result:
            return result

    _log(f'  ⚠️ JSON/델리미터 파싱 실패 — 카드 생성 불가')
    return []


def _parse_by_delimiter(text, start_pat, end_pat, format_choice):
    lines = text.split('\n')
    chunks = []
    current = []
    inside = False
    for line in lines:
        if re.match(start_pat, line, re.IGNORECASE):
            if current:
                chunks.append('\n'.join(current).strip())
                current = []
            inside = True
            continue
        if end_pat and re.match(end_pat, line) and inside:
            if current:
                chunks.append('\n'.join(current).strip())
                current = []
            inside = False
            continue
        if inside:
            current.append(line)
    if current:
        chunks.append('\n'.join(current).strip())
    if chunks:
        lo, hi = FORMAT_CARD_COUNT_TOLERANCE.get(format_choice, (5, 5))
        if lo <= len(chunks) <= hi:
            _log(f'  ⚠️ delimiter fallback: {len(chunks)}개 카드')
            return chunks
    return []


def _try_parse_json(text: str, format_choice: str) -> list:
    try:
        data = json.loads(text)
        cards = data.get('cards', [])
        if not isinstance(cards, list):
            return []
        lo, hi = FORMAT_CARD_COUNT_TOLERANCE.get(format_choice, (5, 5))
        if not (lo <= len(cards) <= hi):
            return []
        return [c.strip() for c in cards if c and isinstance(c, str)]
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError, KeyError):
        return []


def _remove_duplicate_links(cards):
    if len(cards) < 2:
        return cards
    seen_urls = set()
    deduped = []
    for c in cards:
        if c.startswith('🔗') or c.startswith('http'):
            url = c.split('\n')[0].strip()
            if '🔗' in url:
                url = url.replace('🔗', '').strip()
            if url in seen_urls:
                continue
            seen_urls.add(url)
        deduped.append(c)
    return deduped


def write_thread(pitch, all_articles, format_choice=None):
    from v3.model_router import chat_completion

    if not format_choice:
        format_choice = 'D'
    _log(f'  🎯 형식: {format_choice} — {FORMAT_LABELS[format_choice]}')

    system_prompt = FORMAT_BUILDERS[format_choice]()
    json_schema = {"type": "json_object"}

    pre_crawled_body = pitch.get('crawled_body', '')
    pre_crawled_url = pitch.get('crawled_url', '')

    article_ids = pitch.get('article_ids', [])
    # Defensive: article_ids can be int or list from LLM
    if isinstance(article_ids, int):
        article_ids = [article_ids]
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
        try:
            if str(int(db_id)) in article_id_set or str(db_id) in article_id_set:
                related.append(a)
        except (ValueError, TypeError):
            if str(db_id) in article_id_set:
                related.append(a)

    if not related:
        _log(f'  ⚠️ 피치 article_ids({article_ids})를 DB 풀에서 찾을 수 없음 → 스킵')
        return []

    related_parts = []
    article_bodies = []
    all_fallback = True
    crawled_urls = []

    if pre_crawled_body and related:
        a = related[0]
        url = pre_crawled_url or a.get('link', '')
        article_bodies.append(pre_crawled_body)
        crawled_urls.append(url)
        all_fallback = False
        pub_date_str = str(a.get('pub_date', ''))
        related_parts.append(f"""기사 {a['id']}:
제목: {a.get('title','')}
발행일: {pub_date_str}
본문: {pre_crawled_body}
출처: {a.get('source','')}
링크: {url}""")
        _log(f'  📰 pitcher 크롤링 본문 사용: {len(pre_crawled_body)}자 (재크롤링 없음)')
    else:
        for a in related:
            url = a.get('link', '')
            from db_reader import validate_link
            fetch_ok = validate_link(url, timeout=5)
            if not fetch_ok:
                _log(f'  ⚠️ URL 검증 실패 → D1 description 폴백 시도: {url[:60]}...')
            body = fetch_article_body(url, source=a.get('source', ''), title=a.get('title', ''))
            if not body:
                # Fall back to D1 description (1차 pitch 선별에 이미 사용된 텍스트)
                body = a.get('description', '') or ''
                if body:
                    _log(f'  ⚠️ 크롤링/검증 실패 → D1 description 사용 ({len(body)}자)')
                else:
                    _log(f'  ⚠️ 본문 확보 불가 → 기사 제외 (URL: {url[:60]}...)')
                    continue
            all_fallback = False
            crawled_urls.append(url)
            article_bodies.append(body)
            pub_date_str = str(a.get('pub_date', ''))
            related_parts.append(f"""기사 {a['id']}:
제목: {a.get('title','')}
발행일: {pub_date_str}
본문: {body}
출처: {a.get('source','')}
링크: {url}""")

    if all_fallback or not related_parts:
        _log(f'  ⚠️ 모든 기사 크롤링 불가 → 스킵 (실패 목록: logs/failed_crawls.json)')
        return []

    related_text = '\n\n'.join(related_parts)
    article_body_text = ' '.join(article_bodies)
    expected_count = FORMAT_CARD_COUNTS[format_choice]

    user_prompt = f"""Write a Threads thread based on the pitch and articles below.

=== PITCH ===
Hook: {pitch['hook']}
Narrative: {pitch.get('narrative','')}
Twist: {pitch.get('twist','')}
Emotion: {pitch.get('emotion','')}
But_line: {pitch.get('but_line','')}
Question: {pitch.get('question','')}
Gap source: {pitch.get('gap_source','')}

=== FORMAT ===
{FORMAT_LABELS[format_choice]}

=== ARTICLES ===
{related_text}

=== REQUIREMENTS ===
1. Follow the system prompt format exactly.
2. Use ALL numbers from the article body — no vague expressions like "많은" or "대규모".
3. Never include pitch metadata labels (핵심 이야기:, 반전:, 감정:) in the output.
4. Output: JSON only — {{"cards": ["card1", ..., "card5"]}} (5 content cards only, no link card)"""

    _log(f'  쓰레드 생성 중... (temperature=0.4)')

    def _try_model(model_name):
        extra = None
        if model_name in (None, 'deepseek'):
            extra = {"thinking": {"type": "disabled"}}
        return chat_completion(
            system_prompt=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
            temperature=0.4,
            max_tokens=16000,
            model_override=model_name,
            response_format=json_schema,
            extra_body=extra,
        )

    content = _try_model(None)
    if not content:
        _log('  ⚠️ 1차 실패 → 1회 재시도')
        content = _try_model(None)

    if not content:
        _log('  ❌ DeepSeek 응답 실패')
        return []

    content = re.sub(r'^.*?쓰레드\s*(시작|끝).*?\n', '', content, count=1)
    content = re.sub(r'^---+\s*\n', '', content)
    content = re.sub(r'\n---+\s*$', '', content)
    content = re.sub(r'^\[/\s*카드\s*내용\s*\]$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\[카드\s*내용\s*\]$', '', content, flags=re.MULTILINE)
    cards = parse_cards_json_first(content, format_choice)
    cards = [re.sub(r'^\[/?\s*카드\s*내용\s*\]\s*', '', c).strip() for c in cards]
    cards = [c for c in cards if c]
    if len(cards) > expected_count:
        _log(f'  카드 {len(cards)}개 → {expected_count}개로 조정')
        cards = cards[:expected_count]
    lo, _ = FORMAT_CARD_COUNT_TOLERANCE.get(format_choice, (5, 5))
    if len(cards) < lo:
        _log(f'  ⚠️ 카드 수 부족: {len(cards)}개 (최소 {lo}개 필요)')
        return []
    cards = fix_cards(cards)
    cards = _cleanup_source_attribution(cards)

    vc_ok, vc_reason = validate_cards(cards, pitch, format_choice)
    vy_ok, vy_reason = validate_year(cards, article_body_text)
    if not (vc_ok and vy_ok):
        _log(f'⚠️ 검증 실패:')
        _log(f'   - cards: {vc_reason}')
        _log(f'   - year: {vy_reason}')
        return []

    structure_ok, structure_reason = validate_card_structure(cards)
    if not structure_ok:
        _log(f'⚠️ 카드 구조 검증 실패: {structure_reason}')
        _log(f'  [RAW CARDS DUMP] {json.dumps(cards, ensure_ascii=False)}')
        return []

    # Model message validation
    for i, card in enumerate(cards, 1):
        mm_ok, mm_reason = validate_model_message(card)
        if not mm_ok:
            _log(f'⚠️ Card {i} 모델 메시지 검증 실패: {mm_reason}')
            return []

    final_ok, final_reason = validate_final_output(cards)
    if not final_ok:
        _log(f'⚠️ 최종 검증 실패: {final_reason}')
        for i, card in enumerate(cards, 1):
            _log(f'   원본 Card {i}: {card[:60]}')
        return []

    primary_url = pre_crawled_url or next((a.get('link','') for a in related if str(a.get('id','')) == str(article_ids[0]).lstrip('#').strip()), '')
    cards = assemble_final(cards, related, primary_url, crawled_urls, format_choice)
    _log(f'✅ 쓰레드: {len(cards)}개 콘텐츠 카드')
    return {"cards": cards, "link": primary_url or ""}


def assemble_final(cards, articles, primary_url=None, crawled_urls=None, format_choice='D'):
    """Post-process cards: cleanup only. Link card is no longer added here (moved to publisher).

    Returns list of content cards only (no link card).
    """
    # Final safety dedup (링크 카드 없으므로 🔗 시작 카드 걸러지지 않음)
    cards = _remove_duplicate_links(cards)
    return cards


def save_draft(cards, pitch):
    now = datetime.now()
    safe = re.sub(r'[^a-zA-Z0-9가-힣]', '', pitch.get('hook', ''))[:20]
    fname = f'v3_{now.strftime("%Y-%m-%d-%H")}_{safe}.txt'
    fpath = os.path.join(DRAFTS_DIR, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write('\n---\n'.join(cards))
    _log(f'  💾 초안 저장: {fpath}')
    return fpath
