#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""
writer_v3.py — 피치 → 쓰레드 작성
- 모델: gpt-4o (1회, 3회 재시도)
- 입력: pitcher의 내러티브 + 관련 기사
- 출력: ["조각1", "조각2", ...]
"""
import os, sys, json, re, time
import urllib.request, urllib.parse
from datetime import datetime
import requests
from bs4 import BeautifulSoup

PROJECT_DIR = '/Users/twinssn/Projects/aikorea24'
THREADS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'threads')
LOGS_DIR = os.path.join(THREADS_DIR, 'logs')
DRAFTS_DIR = os.path.join(LOGS_DIR, 'drafts')
FAILED_CRAWLS_FILE = os.path.join(LOGS_DIR, 'failed_crawls.json')
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
    return f"""당신은 AI 뉴스를 Threads용 5개 카드 쓰레드로 만드는 작가다.

[최우선 — 리듬 규칙, 반드시 지킬 것]
- 각 카드 내부는 2~3개의 짧은 줄이 하나의 stanza(연)를 이룬다.
- stanza와 stanza 사이는 반드시 한 줄 비운다. (빈 줄이 리듬을 만든다)
- 한 줄은 15~25자 내외. 절대 30자 넘기지 말 것.
- 줄바꿈 위치: 의미 단위(조사, 연결어미, 쉼표)가 끝나는 곳.

stanza 예시 (반드시 이 구조를 따라라):
  머스크의 우주 회사 스페이스X가           ← 1개 줄 (21자)
  AI 회사들한테 컴퓨터를 빌려주고           ← 1개 줄 (22자)
  한 달에 3조 넘게 받기로 했음.             ← 1개 줄 (22자)
                                              ← 빈 줄 (stanza 구분)
  이 돈을 1년치로 환산하면                  ← 새 stanza 시작
  작년 스페이스X 전체 매출을 넘음.          ← stanza 끝

[문체 원칙]
- 반말체. "~임", "~했음", "~있음", "~아님". "~합니다" "~입니다" 절대 금지.
- 인과관계를 설명하라. "A → B"가 아니라 "A로 인해 B가 발생한 이유는..." 식으로 풀어써라.
- 날짜, 장소, 인물명으로 시작해서 독자를 사건 안으로 끌어당긴다.
- 형용사 금지. 감탄사 금지. 사실과 숫자만.
"덜", "더", "가장" 같은 비교 표현 절대 금지. "~한"으로 끝나는 형용사 사용 금지.
- 마지막 카드의 마지막 줄 바로 앞은 반드시 여운을 남긴다. 선언이나 반전으로 끝낸다.
- 이모지 금지. 볼드 금지. 이탤릭 금지.
- 고유명사(기업명, 인물명, 제품명)는 영어 원문을 그대로 사용하라. 예: 화웨이(X) → Huawei(O), 앤트로픽(X) → Anthropic(O), 오픈AI(X) → OpenAI(O)

[대비 구조 — 문장 리듬]
- 두 개의 사실을 대비시켜라. 대비는 줄바꿈으로 분리.
- 패턴 예시:
  * A였음. 그런데 B. / A가 아니라 B. / A는 X. B는 Y.
  * 돈은 주되 결정권은 쥐겠다는 것. (X이지만 Y)
  * 이기려고 지은 컴퓨터를. 자기는 못 쓰고. 경쟁자가 잘 쓰는 중. (A였는데 B가 됨)
- 한 줄이 하나의 대비 항목. A와 B 사이는 반드시 개행.

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

[숫자-설명 쌍 — 정보 전달 리듬]
- 숫자를 무더기로 나열하지 마라. 숫자 하나 → 설명 하나가 한 쌍.
- 패턴: 숫자를 먼저 던지고, 그 의미를 다음 줄에서 풀어써라.
- 예:
  약 9,600조 원.
  여기서 매년 5%만 떼서 국민한테 나눠주는 구조.
  → (한 쌍 끝, 빈 줄)
  한 명당 약 138만 원.
  남녀노소 전부, 매년.
- 숫자-설명 쌍과 쌍 사이는 빈 줄로 구분.

[카드 구조 — 5개, --- 로 구분]
반드시 아래 예시의 카드-줄-빈줄 구조를 그대로 따라라.
1번 카드 예시 (정확히 이 구조):
  Notion이 이메일 앱을 죽였음.
  AI가 이미 대신 일하고 있어서.
  사용자가 직접 열 필요가 없었음.

  9월 22일. 18개월 만에 접는 결정.
  2024년 2월 Skiff 인수 → 2025년 4월 출시.
  1년 만에 종료. 기사 본문의 실제 숫자만.
---
2번 카드 (500자 이내): 충돌의 A면. 구체적 사실, 숫자, 인용, 연구 결과를 빽빽하게 채운다.
2번 카드 (500자 이내): 충돌의 A면. 구체적 사실, 숫자, 인용, 연구 결과를 빽빽하게 채운다.
3번 카드 (500자 이내): 반전. 예상 못 한 제3의 사실. 방향 전환. 숫자와 사례로 가득 채운다.
4번 카드 (500자 이내): 확장. 더 큰 맥락 또는 연결점.
5번 카드 (500자 이내): 여운. 지금까지 나온 숫자/사실을 한 번 더 반전시킨다. 마지막 줄은 선언형으로.

[전환 시그널 — 카드 시작 표현, 매번 다양하게 선택, 같은 표현 2회 연속 금지]
3번 카드(반전) 시작 덩어리 예시 — 아래 목록에서 매번 다른 것을 골라라. "여기서 반전이 있음"은 가장 마지막 수단으로만 사용하고, 먼저 아래 윗줄의 표현들부터 사용하라:
- "근데 여기서부터가 진짜임."
- "그런데 사실은 이렇지 않음."
- "이걸 다른 시각으로 보면 이럼."
- "표면과 다른 진실이 있음."
- "진짜 이야기는 여기서 시작됨."
- "하지만 뒤집어 보면."
- "이 주장의 반대편에는."
- "이 구조의 함정은 여기에 있음."
- "이걸 다른 말로 표현하면."
- "여기서 반전이 있음."

4번 카드(확장) 시작 덩어리 예시:
- "이 현상을 더 큰 그림으로 보면."
- "이걸 다른 맥락에 놓고 보면."
- "왜 하필 지금이냐."
- "여기서 질문을 던져볼 수 있음."
- "이 흐름의 더 깊은 층위가 있음."
- "이게 왜 중요한가."
- "이 사건이 말하는 진짜 의미는."
- "이걸 역사적 맥락에서 보면."

5번 카드(마무리) 시작 덩어리 예시:
- "정리하면 이럼."
- "결론적으로 이렇게 볼 수 있음."
- "한 문장으로 요약하면."
- "이 모든 사실이 말하는 것은."
- "결국 이 질문으로 돌아옴."
- "핵심은 하나임."
- "이 이야기가 주는 교훈은."
- "결론은 명확함."

[어투 규칙 — 반드시 준수]
- 모든 문장은 반말 종결형으로 작성한다.
- 종결 어미 규칙:
  * ~이다 → ~임.
  * ~한다 → ~함.
  * ~했다 / ~하였다 → ~했음.
  * ~된다 → ~됨.
  * ~있다 → ~있음.
  * ~없다 → ~없음.
  * ~이다/다 로 끝나는 모든 서술문 → ~임. 으로 변경
- 인용 표현: "~라고 밝혔다" → "~라고 밝혔음."
- 예외: 훅(첫 카드 첫 문장)은 어투 규칙 적용하지 않아도 됨
- 절대 금지: ~이다. / ~한다. / ~됩니다. / ~합니다. 로 끝나는 문장

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
{examples}

[키워드 규칙]
- 기사 원문에 등장하는 단어를 그대로 사용할 것
- 단어를 임의로 줄이거나 변형하지 말 것
  예: "표준으로" → "표준으로" 그대로 (절대 "표준"으로 자르지 말 것)
  예: "예산을" → "예산을" 그대로 (절대 "예산"으로 자르지 말 것)
- 기사에 없는 단어로 대체하지 말 것"""

def log_failed_crawl(url, source, title, status):
    """크롤링 실패한 URL을 failed_crawls.json에 기록"""
    data = {"failed": [], "updated_at": ""}
    if os.path.exists(FAILED_CRAWLS_FILE):
        try:
            with open(FAILED_CRAWLS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            pass
    now = datetime.now().isoformat()
    entry = {"url": url, "source": source, "title": title, "status": status, "failed_at": now}
    # 중복 제거 (같은 url이 있으면 갱신)
    data['failed'] = [e for e in data['failed'] if e.get('url') != url]
    data['failed'].append(entry)
    data['updated_at'] = now
    with open(FAILED_CRAWLS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_article_body(url, source='', title=''):
    """원문 기사 본문을 크롤링해서 텍스트 반환. 실패 시 빈 문자열.
    2회 재시도. 실패 시 failed_crawls.json에 기록.
    URL은 D1 DB에서 이미 제공되므로, 본문 텍스트만 반환 (URL 변경 금지).
    """
    if not url:
        return ''

    max_attempts = 2
    for attempt in range(max_attempts):
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
            err_msg = f'{type(e).__name__}'
            log(f'  ⚠️ 크롤링 실패 ({attempt+1}/{max_attempts}): {url[:50]}... ({err_msg})')
            if attempt < max_attempts - 1:
                time.sleep(3)
            else:
                log_failed_crawl(url, source, title, err_msg)
                return ''

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

def _strip_instruction_leak(text):
    """LLM이 출력에 포함시킨 프롬프트 명령어를 제거"""
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
        # 하이픈만 있는 라인 제거 (지시문이 split된 잔재)
        if stripped == '-':
            continue
        cleaned.append(line)
    return '\n'.join(cleaned).strip()

def humanize_cards(cards):
    """LLM 기반 AI 티 교체 (im-not-ai 택소노미 기반)
    - 번역투, AI 관용구, 과장, 형용사 등 10대 카테고리 패턴 교체
    - 의미 불변: 사실·수치·고유명사 보존
    - 국소 수정: AI 티 구간만 교체, 전체 재작성 금지
    - 실패 시 원본 반환
    """
    from v3.model_router import chat_completion

    if not cards:
        return cards

    text = '\n---\n'.join(cards)
    original_len = len(text)

    # 빈 텍스트 방지
    if original_len < 10:
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

    user_prompt = f"""다음 Threads 쓰레드의 AI 말투를 자연스러운 한국어로 다듬어라.
[원본]
{text}

[출력 규칙]
- 내용(사실, 수치, 고유명사)은 절대 변경하지 말 것
- 반말체(~임, ~했음, ~있음) 그대로 유지
- --- 구분자 정확히 유지
- 수정된 쓰레드만 출력"""

    try:
        result = chat_completion(
            system_prompt=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
            temperature=0.3,
            max_tokens=5000,
            model_override='mimo',
        )
        if not result:
            log(f'  ⚠️ humanize: 응답 없음 → 원본 유지')
            return cards

        result = _strip_instruction_leak(result)
        fixed = [c.strip() for c in result.split('---') if c.strip()]

        # 길이 검증: 50% 미만이면 원본 유지
        if len(fixed) < len(cards) * 0.5:
            log(f'  ⚠️ humanize: 결과 부족 ({len(fixed)}<{len(cards)}) → 원본 유지')
            return cards

        # 카드 수 검증: 5~6개 허용
        if len(fixed) < 5 or len(fixed) > 6:
            log(f'  ⚠️ humanize: 카드 수 불일치 ({len(fixed)}) → 원본 유지')
            return cards

        changed_cards = sum(1 for a, b in zip(cards, fixed) if a != b)
        log(f'  🧹 humanize: {changed_cards}/{len(cards)}개 카드 수정')
        return fixed

    except Exception as e:
        log(f'  ⚠️ humanize 오류: {e} → 원본 유지')
        return cards


def fix_cards(cards):
    """MiMo로 글자 단위 오류(첫 글자 드랍, 잘린 문자, 깨진 단어)만 수정
    내용/의미/구조는 변경하지 않음
    DiffusionGemma 대신 별도 모델 사용 — 자기 오류를 스스로 수정하는 구조적 문제 해결
    """
    # humanize 먼저 적용
    cards = humanize_cards(cards)

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
            model_override='mimo',
        )
        if result:
            fixed = [c.strip() for c in result.split('---') if c.strip()]
            if len(fixed) == len(cards):
                changed = sum(1 for i in range(len(cards)) if fixed[i] != cards[i])
                log(f'  🔧 오류 수정(MiMo): {changed}/{len(cards)}개 카드 수정됨')
                return fixed
            log(f'  ⚠️ 수정 후 카드 수 불일치: {len(fixed)}≠{len(cards)} → 원본 유지')
        else:
            log(f'  ⚠️ 수정 실패 → 원본 유지')
    except Exception as e:
        log(f'  ⚠️ 수정 오류: {e} → 원본 유지')
    return cards


def write_thread(pitch, all_articles):
    """피치 + 관련 기사 → 쓰레드 조각 리스트 (DeepSeek → MiMo fallback)"""
    from v3.model_router import chat_completion

    # pitcher가 이미 크롤링한 본문이 있는 경우 — 재크롤링 없이 사용
    pre_crawled_body = pitch.get('crawled_body', '')
    pre_crawled_url = pitch.get('crawled_url', '')

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
    crawled_urls = []  # 크롤링 성공한 URL 기록

    # pitcher가 이미 크롤링한 본문이 있으면 해당 기사만 사용 (재크롤링 없이)
    if pre_crawled_body and related:
        a = related[0]  # 단일 기사
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
        log(f'  📰 pitcher 크롤링 본문 사용: {len(pre_crawled_body)}자 (재크롤링 없음)')
    else:
        # 기존 로직: 기사 URL 크롤링
        for a in related:
            url = a.get('link', '')
            # URL 검증 선행 — 403/404 차단 매체는 리소스 낭비 없이 스킵
            from db_reader import validate_link
            if not validate_link(url, timeout=5):
                log(f'  ⚠️ URL 차단/실패 → 기사 제외: {url[:60]}...')
                log_failed_crawl(url, a.get('source', ''), a.get('title', ''), 'validate_link_fail')
                continue
            body = fetch_article_body(url, source=a.get('source', ''), title=a.get('title', ''))
            if not body:
                log(f'  ⚠️ 크롤링 실패 → 기사 제외 (URL: {url[:60]}...)')
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

    # 모든 기사 URL이 차단/실패 → 스킵 (할루시네이션 방지)
    if all_fallback or not related_parts:
        log(f'  ⚠️ 모든 기사 크롤링 불가 → 스킵 (실패 목록: logs/failed_crawls.json)')
        return []

    related_text = '\n\n'.join(related_parts)

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
1. 1번 카드: 반드시 예시 구조 그대로. 첫 stanza punch → 빈 줄 → 둘째 stanza 숫자/날짜 포함 → ---는 둘째 stanza 뒤. 절대 첫 stanza 뒤에 ---를 넣지 말 것.
2. 반말체(~임, ~했음, ~있음). ~합니다 금지.
3. 각 카드는 --- 로 구분. 각 카드는 반드시 500자 이내로 작성할 것. 500자 초과 시 API가 거부함.
4. ## 카드 수 규칙 (절대 준수)
   - 카드는 반드시 5개만 작성한다.
   - 4개도 안 되고 6개도 안 된다. 오직 5개.
   - 카드 구분은 반드시 "---" (하이픈 3개) 만 사용한다.
   - "---" 는 카드와 카드 사이에만 사용한다. 카드 내부에는 사용하지 않는다.
5. 기사 본문의 숫자(금액, 퍼센트, 날짜, 사용자 수)를 반드시 추출해서 써라. "많은", "대규모" 금지.
6. [필수] 한 줄 15~25자. 30자 넘는 줄 금지.
7. [필수] 2~3줄마다 반드시 빈 줄 하나. stanza 구조 절대 유지.
8. [필수] 반말체(~임/~했음/~있음/~됨). ~이다/~한다/~됩니다 전면 금지.
9. "핵심 이야기:", "반전:", "감정:", "체감 단위:" 등의 피치 메타데이터 레이블을
   쓰레드에 절대 포함하지 마라."""

    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            log(f'  쓰레드 생성 중...')
            from v3.model_router import WRITER_DEEPSEEK_MODEL
            content = chat_completion(
                system_prompt=build_system_prompt(),
                messages=[{'role': 'user', 'content': user_prompt}],
                temperature=0.7,
                max_tokens=5000,
                deepseek_model=WRITER_DEEPSEEK_MODEL,
            )
            if not content:
                raise Exception('모델 응답 없음')
            cards = parse_cards(content)
            if len(cards) > 5:
                log(f'  카드 {len(cards)}개 → 5개로 조정')
                cards = cards[:5]
            cards = fix_cards(cards)

            if validate_cards(cards, pitch) and validate_year(cards, article_body_text) and validate_keywords(cards, article_body_text):
                # pitcher 크롤링 URL 우선, 없으면 article_ids[0] 링크 사용
                primary_url = pre_crawled_url or next((a.get('link','') for a in related if str(a.get('id','')) == str(article_ids[0]).lstrip('#').strip()), '')
                cards = assemble_final(cards, related, primary_url, crawled_urls)
                log(f'  ✅ 쓰레드: {len(cards)}개 조각 (시도 {attempt+1})')
                return cards
            else:
                log(f'  ⚠️ 검증 실패: {len(cards)}개 조각 (시도 {attempt+1}/{max_attempts})')
        except Exception as e:
            log(f'  ⚠️ 오류: {e} (시도 {attempt+1}/{max_attempts})')

    log(f'  ❌ {max_attempts}회 재시도 실패 → MiMo fallback 1회')
    try:
        log(f'  쓰레드 생성 중... (MiMo fallback)')
        content = chat_completion(
            system_prompt=build_system_prompt(),
            messages=[{'role': 'user', 'content': user_prompt}],
            temperature=0.7,
            max_tokens=5000,
                    model_override='mimo',
        )
        if not content:
            raise Exception('모델 응답 없음')
        cards = parse_cards(content)
        cards = fix_cards(cards)
        if validate_cards(cards, pitch) and validate_year(cards, article_body_text) and validate_keywords(cards, article_body_text):
            primary_url = pre_crawled_url or next((a.get('link','') for a in related if str(a.get('id','')) == str(article_ids[0]).lstrip('#').strip()), '')
            cards = assemble_final(cards, related, primary_url, crawled_urls)
            log(f'  ✅ 쓰레드: {len(cards)}개 조각 (MiMo fallback 성공)')
            return cards
    except Exception as e:
        log(f'  ⚠️ MiMo fallback 오류: {e}')

    log('  ❌ 전체 재시도 실패')
    return []

def parse_cards(text):
    """---로 구분된 조각 파싱"""
    cards = [c.strip() for c in text.split('---') if c.strip()]
    if not cards:
        return cards
    # 1번 카드가 3줄 이하(punch stanza만)면 2번 카드의 첫 stanza를 1번으로 병합
    if len(cards) > 1:
        c1_lines = [l for l in cards[0].split('\n') if l.strip()]
        if len(c1_lines) <= 3:
            c2_lines = [l for l in cards[1].split('\n') if l.strip()]
            if c2_lines:
                # punch stanza + 빈 줄 + context stanza (2~3줄만 가져옴)
                merge = c2_lines[:min(3, len(c2_lines))]
                cards[0] = cards[0] + '\n\n' + '\n'.join(merge)
                cards[1] = '\n'.join(c2_lines[min(3, len(c2_lines)):])
                cards = [c.strip() for c in cards if c.strip()]
    return cards

def validate_cards(cards, pitch):
    """기본 검증 (카드 수 5~6개 허용 + hook 근사 일치)"""
    if not cards or len(cards) < 5 or len(cards) > 6:
        log(f'    → 카드 수 불일치: {len(cards)}개 (허용: 5~6개)')
        return False
    # 첫 줄이 비어있지 않은지 확인
    first_line = cards[0].strip().split('\n')[0].strip()
    if len(first_line) < 3:
        log(f'    → 첫 줄 너무 짧음: "{first_line}"')
        return False
    return True

def validate_year(cards, article_body_text):
    """연도 검증: 쓰레드 본문(1번 카드 첫 줄 제외)의 연도가 기사 본문에 있는 연도인지 확인
    - pitcer가 생성한 hook(1번 카드 첫 줄)은 검증에서 제외 (변경 불가이므로)
    - 기사 본문에 없는 연도를 쓰레드 본문이 표시하면 할루시네이션
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

    # 뉴스 사이트 boilerplate stoplist — 키워드 검증에서 제외
    _STOPLIST = {
        '무단전재', '수정하거나', '관련기사', '보도했다', '보도했음',
        '기사제공', '저작권자', '기사보기', '바로가기', '메일로',
        '카카오톡', '페이스북', '트위터', '구독하기', '네이버',
        '데일리', '머니투데이', '조선일보', '동아일보', '한국경제',
        '매일경제', '서울경제', '헤럴드경제', '아시아경제',
        '입력', '수정', '기자', '사진', '제공', '문의', '저작권',
        '구독', '뉴스', '대표', '대표번호', '이메일', '전화번호',
        '블로그', '인스타그램', '유튜브', '채널', '팔로우',
        'All', 'Rights', 'Reserved', 'Copyright',
    }
    keywords = keywords - _STOPLIST

    # 전체 키워드 수가 너무 적으면 검증 불가 → 통과
    if len(keywords) <= 5:
        log(f'    → 키워드 검증 통과: 핵심 단어 {len(keywords)}개 (boilerplate 제외 후 소수 → 검증 불필요)')
        return True

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
                # 쓰레드 단어가 너무 짧으면 조사 탈락으로 간주 (잘림 아님)
                if len(tw) < 3:
                    continue
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
        # 치명적 누락(접두사/접미사 잘림)이 3개 이상이면 실패
        critical = [m for m in missing if '잘림' in m[2]]
        if len(critical) >= 3:
            log(f'    → 키워드 검증 실패: 접두사/접미사 잘림 {len(critical)}개')
            return False
        return True  # 잘림 2개 이하면 통과

    log(f'    → 키워드 검증 통과: 핵심 단어 {len(keywords)}개 매칭')
    return True

def assemble_final(cards, articles, primary_url=None, crawled_urls=None):
    """대표 URL 1개를 마지막 카드 끝에 추가 (카드 수 변경 없음)
    crawled_urls: 크롤링 성공한 URL 목록
    articles: D1 DB 기사 객체 리스트 (related) — fallback용
    primary_url: article_ids[0]에 해당하는 기사의 링크 (가장 우선시)
    """
    from db_reader import validate_link

    url_to_use = None

    # 크롤링 성공 URL이 있으면 해당 목록에서만 선택
    if crawled_urls:
        if primary_url and primary_url in crawled_urls:
            url_to_use = primary_url
        else:
            url_to_use = crawled_urls[0]
    elif primary_url:
        if validate_link(primary_url, timeout=5):
            url_to_use = primary_url
        else:
            log(f'  ⚠️ primary URL 유효성 실패: {primary_url[:50]}...')
    if not url_to_use and articles:
        for a in articles:
            url = a.get('link', '').strip()
            if url == primary_url:
                continue
            if not url or not url.startswith('http'):
                continue
            if validate_link(url, timeout=5):
                url_to_use = url
                break
            log(f'  ⚠️ URL 유효성 실패 — 다음 URL 시도: {url[:50]}...')

    if url_to_use:
        cards.append(f'🔗 {url_to_use}')
    else:
        log(f'  ❌ 유효한 URL 없음 — 링크 생략')

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
