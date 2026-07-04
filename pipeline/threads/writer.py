"""pipeline/threads/writer.py — Thread writing logic: format building, post-processing, assembly, orchestration."""
import os, sys, json, re, time
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
    'D': '펀치 브리핑형 (5개 발행글 + 1개 출처링크)',
}


def build_system_prompt_D():
    examples = load_style_examples()
    return f"""당신은 AI 뉴스를 Threads용 5개 카드 쓰레드로 만드는 작가다.

[최우선 — 리듬 + 밀도 규칙, 반드시 지킬 것]
- 각 카드 내부는 3~5개의 줄이 하나의 stanza(연)를 이룬다.
- stanza와 stanza 사이는 반드시 한 줄 비운다. (빈 줄이 리듬을 만든다)
- 한 줄은 25~40자 내외. 정보를 압축해서 담되 자연스럽게 읽혀야 함.
- 줄바꿈 위치: 의미 단위(조사, 연결어미, 쉼표)가 끝나는 곳.
- 각 카드는 반드시 450~500자로 채운다. 정보 밀도가 곧 품질이다. 절대 400자 아래로 내려가지 말 것.

stanza 예시 (반드시 이 구조를 따라라):
  머스크의 우주 회사 스페이스X가 AI 회사들한테       ← 1개 줄 (34자)
  컴퓨터를 빌려주고 한 달에 3조 넘게 받기로 했음.     ← 1개 줄 (33자)
  이 돈을 1년치로 환산하면 작년 스페이스X 전체        ← 1개 줄 (33자)
  매출을 넘는 규모임.                                 ← 1개 줄 (20자)
                                                        ← 빈 줄 (stanza 구분)
  스페이스X가 상장한 지 4일 만에 맺은 계약.           ← 새 stanza 시작
  상대는 로켓 회사가 아니라 MIT 출신 4명이 만든       ← stanza 내부
  AI 코딩 스타트업 Cursor였음.                        ← stanza 끝

[문체 원칙]
- 반말체. "~임", "~했음", "~있음", "~아님". "~합니다" "~입니다" 절대 금지.
- 인과관계를 설명하라. "A → B"가 아니라 "A로 인해 B가 발생한 이유는..." 식으로 풀어써라.
- 날짜, 장소, 인물명으로 시작해서 독자를 사건 안으로 끌어당긴다.
- 형용사 금지. 감탄사 금지. 사실과 숫자만.
"덜", "더", "가장" 같은 비교 표현 절대 금지. "~한"으로 끝나는 형용사 사용 금지.
- 마지막 카드의 마지막 줄 바로 앞은 반드시 여운을 남긴다. 선언이나 반전으로 끝낸다.
- 이모지 금지. 볼드 금지. 이탤릭 금지.
- 고유명사(기업명, 인물명, 제품명)는 영어 원문을 그대로 사용하라. 예: 화웨이(X) → Huawei(O), 앤트로픽(X) → Anthropic(O), 오픈AI(X) → OpenAI(O)
- 중국어(한자) 사용 절대 금지. 한자 1글자라도 출력 시 발행이 차단된다. 반드시 한국어로 번역하라. 예: 新加坡금융관리국(X) → 싱가포르금융관리국(O)
- 일본어(히라가나·가타카나) 사용 절대 금지. 모든 외국어는 한국어로만 작성하라.
- 고유명사는 영어 원문 유지. 중국어·일본어·한자·특수 유니코드 문자 절대 금지.

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

[카드 구조 — 6개, --- 로 구분]
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
3번 카드 (500자 이내): 반전. 예상 못 한 제3의 사실. 방향 전환. 숫자와 사례로 가득 채운다.
4번 카드 (500자 이내): 확장. 더 큰 맥락 또는 연결점.
5번 카드 (500자 이내): 여운. 지금까지 나온 숫자/사실을 한 번 더 반전시킨다. 마지막 줄은 선언형으로.
6번 카드: 출처 링크만. 내용 없음. 예: 🔗 https://example.com/news

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
- "이 모든 사실이 말하는 것은."
- "결국 이 질문으로 돌아옴."
- "핵심은 하나임."
- "결론은 명확함."
- "결국 핵심은 이거였음."
- "이 이야기의 끝은."
- "되돌아보면 결국."
- "이 모든 상황의 본질은."

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
1~5번 카드: 각각 450~500자. Threads API 제한이 500자이므로 초과 금지.
6번 카드: 출처 링크만. 내용 불필요. 예: 🔗 https://example.com/news
원문의 숫자, 인물, 인용문, 날짜, 통계를 모두 꺼내서 채운다.
정보가 부족하면 기사 본문에서 더 파낸다. 없는 내용은 절대 만들지 않는다.

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


def humanize_cards(cards):
    from v3.model_router import chat_completion

    if not cards:
        return cards

    text = '\n---\n'.join(cards)
    original_len = len(text)

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
        )
        if not result:
            _log(f'  ⚠️ humanize: 응답 없음 → 원본 유지')
            return cards

        result = _strip_instruction_leak(result)
        result = _strip_model_explanatory(result)
        fixed = [c.strip() for c in result.split('---') if c.strip()]

        if len(fixed) != len(cards):
            _log(f'  ⚠️ humanize: 카드 수 불일치 (입력 {len(cards)}개 → 출력 {len(fixed)}개) → 원본 유지')
            return cards

        changed_cards = sum(1 for a, b in zip(cards, fixed) if a != b)
        _log(f'  🧹 humanize: {changed_cards}/{len(cards)}개 카드 수정')
        return fixed

    except Exception as e:
        _log(f'  ⚠️ humanize 오류: {e} → 원본 유지')
        return cards


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
    cleaned = [re.sub(r'\n{3,}', '\n\n', card).strip() for card in cleaned]
    return cleaned


def _clean_english_leakage(text):
    text = re.sub(r'([가-힣])([A-Za-z][A-Za-z ]{1,30}?)([가-힣])', r'\1\3', text)
    text = re.sub(r'([가-힣])([A-Za-z][A-Za-z ]{1,30})$', r'\1', text)
    text = re.sub(r'([가-힣])([A-Za-z][A-Za-z ]{1,30}?)\n', r'\1\n', text)
    return text


def _fix_korean_particle_spacing(text):
    text = re.sub(r'([A-Za-z][A-Za-z0-9.+#]*)([가-힣])', r'\1 \2', text)
    return text


def fix_cards(cards):
    cards = [_clean_english_leakage(c) for c in cards]
    cards = [_fix_korean_particle_spacing(c) for c in cards]
    cards = humanize_cards(cards)
    cards = [_clean_english_leakage(c) for c in cards]
    cards = [_fix_korean_particle_spacing(c) for c in cards]

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
        )
        if result:
            result = _strip_model_explanatory(result)
            fixed = [c.strip() for c in result.split('---') if c.strip()]
            if len(fixed) == len(cards):
                changed = sum(1 for i in range(len(cards)) if fixed[i] != cards[i])
                _log(f'  🔧 오류 수정(MiMo): {changed}/{len(cards)}개 카드 수정됨')
                return fixed
            if len(fixed) > len(cards):
                _log(f'  ⚠️ 수정 후 카드 수 초과: {len(fixed)}>{len(cards)} → {len(cards)}개로 자름')
                fixed = fixed[:len(cards)]
                changed = sum(1 for i in range(len(cards)) if fixed[i] != cards[i])
                _log(f'  🔧 오류 수정(자름): {changed}/{len(cards)}개 카드 수정됨')
                return fixed
            _log(f'  ⚠️ 수정 후 카드 수 부족: {len(fixed)}<{len(cards)} → 원본 유지')
        else:
            _log(f'  ⚠️ 수정 실패 → 원본 유지')
    except Exception as e:
        _log(f'  ⚠️ 수정 오류: {e} → 원본 유지')
    return cards


def parse_cards(text, format_choice='D'):
    cards = [c.strip() for c in text.split('---') if c.strip()]
    if not cards:
        return cards
    lo, _ = FORMAT_CARD_COUNT_TOLERANCE.get(format_choice, (5, 5))
    if len(cards) < lo:
        alt = [c.strip() for c in text.split('\n\n') if c.strip()]
        alt = [c for c in alt if len(c) > 20]
        if len(alt) >= lo:
            _log(f'  parse_cards: --- 없음, \\n\\n으로 {len(alt)}개 분할')
            cards = alt
    if format_choice == 'D' and len(cards) > 1:
        c1_lines = [l for l in cards[0].split('\n') if l.strip()]
        if len(c1_lines) <= 3:
            c2_lines = [l for l in cards[1].split('\n') if l.strip()]
            if c2_lines:
                merge = c2_lines[:min(3, len(c2_lines))]
                cards[0] = cards[0] + '\n\n' + '\n'.join(merge)
                cards[1] = '\n'.join(c2_lines[min(3, len(c2_lines)):])
                cards = [c.strip() for c in cards if c.strip()]
    return cards


def write_thread(pitch, all_articles, format_choice=None):
    from v3.model_router import chat_completion

    if not format_choice:
        format_choice = 'D'
    _log(f'  🎯 형식: {format_choice} — {FORMAT_LABELS[format_choice]}')

    system_prompt = FORMAT_BUILDERS[format_choice]()

    pre_crawled_body = pitch.get('crawled_body', '')
    pre_crawled_url = pitch.get('crawled_url', '')

    article_ids = pitch.get('article_ids', [])
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
            if not validate_link(url, timeout=5):
                _log(f'  ⚠️ URL 차단/실패 → 기사 제외: {url[:60]}...')
                log_failed_crawl(url, a.get('source', ''), a.get('title', ''), 'validate_link_fail')
                continue
            body = fetch_article_body(url, source=a.get('source', ''), title=a.get('title', ''))
            if not body:
                _log(f'  ⚠️ 크롤링 실패 → 기사 제외 (URL: {url[:60]}...)')
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

    user_prompt = f"""아래 피치와 기사들을 바탕으로 Threads 쓰레드를 작성해주세요.

=== 피치 ===
첫 문장 (변경 금지): {pitch['hook']}
핵심 이야기: {pitch.get('narrative','')}
반전: {pitch.get('twist','')}
감정: {pitch.get('emotion','')}
체감 단위: {pitch.get('comparison_unit','')}

=== 형식 ===
{FORMAT_LABELS[format_choice]}

=== 관련 기사 ===
{related_text}

=== 작성 방법 ===
Threads는 발행글 하나당 500자 제한이 있음.
따라서 하나의 이야기를 여러 발행글로 나누어 연쇄 발행해야 함.
각 발행글은 --- 로 구분하며, 마지막 발행글은 출처 링크만 넣음.

아래 형식을 정확히 따라라:

발행글 내용 450~500자
---
발행글 내용 450~500자
---
발행글 내용 450~500자
---
발행글 내용 450~500자
---
발행글 내용 450~500자
---
🔗 https://...

=== 요구사항 ===
1. 각 발행글 450~500자. 400자 미만 금지. 정보 부족 시 기사 본문에서 추가 추출.
2. 반말체(~임, ~했음, ~있음). ~합니다 금지.
3. 기사 본문 숫자는 전부 사용. "많은", "대규모" 금지.
4. 한 줄 25~40자. 정보를 압축.
5. 3~5줄마다 빈 줄 하나. stanza 구조 유지.
6. 핵심 이야기/반전/감정/체감 단위 등의 피치 메타데이터 레이블 절대 포함 금지.
7. 발행글 번호는 붙이지 않음."""

    TEMPS = [0.4]
    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            temp = TEMPS[attempt] if attempt < len(TEMPS) else 0.1
            _log(f'  쓰레드 생성 중... (temperature={temp})')
            content = chat_completion(
                system_prompt=system_prompt,
                messages=[{'role': 'user', 'content': user_prompt}],
                temperature=temp,
                max_tokens=5000,
            )
            if not content:
                raise Exception('모델 응답 없음')
            content = re.sub(r'^.*?쓰레드\s*(시작|끝).*?\n', '', content, count=1)
            content = re.sub(r'^---+\s*\n', '', content)
            content = re.sub(r'\n---+\s*$', '', content)
            cards = parse_cards(content, format_choice)
            if len(cards) > expected_count:
                _log(f'  카드 {len(cards)}개 → {expected_count}개로 조정')
                cards = cards[:expected_count]
            lo, _ = FORMAT_CARD_COUNT_TOLERANCE.get(format_choice, (5, 5))
            if len(cards) < lo:
                _log(f'  ⚠️ 카드 수 부족: {len(cards)}개 (최소 {lo}개 필요) → 재시도')
                continue
            cards = fix_cards(cards)
            cards = _cleanup_source_attribution(cards)

            if validate_cards(cards, pitch, format_choice) and validate_year(cards, article_body_text) and validate_keywords(cards, article_body_text):
                # New structural validation
                structure_ok, structure_reason = validate_card_structure(cards)
                if not structure_ok:
                    _log(f'⚠️ 카드 구조 검증 실패: {structure_reason} → 재시도')
                    continue

                # Model message validation
                for i, card in enumerate(cards, 1):
                    if not validate_model_message(card):
                        _log(f'⚠️ Card {i}: 모델 메시지 탐지 → 재시도')
                        break
                else:
                    # No model message found — proceed to final validation
                    final_ok, final_reason = validate_final_output(cards)
                    if not final_ok:
                        _log(f'⚠️ 최종 검증 실패: {final_reason} → 재시도')
                        continue
                    primary_url = pre_crawled_url or next((a.get('link','') for a in related if str(a.get('id','')) == str(article_ids[0]).lstrip('#').strip()), '')
                    cards = assemble_final(cards, related, primary_url, crawled_urls, format_choice)
                    _log(f'✅ 쓰레드: {len(cards)}개 조각 (시도 {attempt+1})')
                    return cards
            else:
                _log(f'⚠️ 검증 실패: {len(cards)}개 조각 (시도 {attempt+1}/{max_attempts})')
        except Exception as e:
            _log(f'  ⚠️ 오류: {e} (시도 {attempt+1}/{max_attempts})')

    _log(f'  ❌ {max_attempts}회 재시도 실패 → fallback 1회')
    try:
        _log(f'  쓰레드 생성 중... (fallback, temperature=0.0)')
        content = chat_completion(
            system_prompt=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
            temperature=0.0,
            max_tokens=5000,
        )
        if not content:
            raise Exception('모델 응답 없음')
        content = re.sub(r'^.*?쓰레드\s*(시작|끝).*?\n', '', content, count=1)
        content = re.sub(r'^---+\s*\n', '', content)
        content = re.sub(r'\n---+\s*$', '', content)
        cards = parse_cards(content, format_choice)
        if len(cards) > expected_count:
            _log(f'  카드 {len(cards)}개 → {expected_count}개로 조정 (fallback)')
            cards = cards[:expected_count]
        lo, _ = FORMAT_CARD_COUNT_TOLERANCE.get(format_choice, (5, 5))
        if len(cards) < lo:
            _log(f'  ⚠️ 카드 수 부족: {len(cards)}개 (최소 {lo}개 필요) → fallback 실패')
            raise Exception(f'fallback 카드 수 부족: {len(cards)}개')
        cards = fix_cards(cards)
        cards = _cleanup_source_attribution(cards)
        if validate_cards(cards, pitch, format_choice) and validate_year(cards, article_body_text) and validate_keywords(cards, article_body_text):
            # New structural validation
            structure_ok, structure_reason = validate_card_structure(cards)
            if not structure_ok:
                _log(f'⚠️ 카드 구조 검증 실패 (fallback): {structure_reason}')
                raise Exception(f'카드 구조 검증 실패: {structure_reason}')

            # Model message validation
            for i, card in enumerate(cards, 1):
                if not validate_model_message(card):
                    _log(f'⚠️ Card {i}: 모델 메시지 탐지 (fallback)')
                    raise Exception(f'Card {i}: 모델 메시지 탐지')

            final_ok, final_reason = validate_final_output(cards)
            if not final_ok:
                _log(f'⚠️ 최종 검증 실패 (fallback): {final_reason}')
                raise Exception(f'최종 검증 실패: {final_reason}')
            primary_url = pre_crawled_url or next((a.get('link','') for a in related if str(a.get('id','')) == str(article_ids[0]).lstrip('#').strip()), '')
            cards = assemble_final(cards, related, primary_url, crawled_urls, format_choice)
            _log(f'  ✅ 쓰레드: {len(cards)}개 조각 (fallback 성공)')
            return cards
    except Exception as e:
        _log(f'  ⚠️ fallback 오류: {e}')

    _log('  ❌ 전체 재시도 실패')
    if format_choice != 'D':
        _log('  🔄 형식 D로 대체 시도...')
        return write_thread(pitch, all_articles, format_choice='D')
    return []


def assemble_final(cards, articles, primary_url=None, crawled_urls=None, format_choice='D'):
    from db_reader import validate_link

    url_to_use = None

    if crawled_urls:
        if primary_url and primary_url in crawled_urls:
            url_to_use = primary_url
        else:
            url_to_use = crawled_urls[0]
    elif primary_url:
        if validate_link(primary_url, timeout=5):
            url_to_use = primary_url
        else:
            _log(f'  ⚠️ primary URL 유효성 실패: {primary_url[:50]}...')
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
            _log(f'  ⚠️ URL 유효성 실패 — 다음 URL 시도: {url[:50]}...')

    if url_to_use:
        link_card = f'🔗 {url_to_use}'
        if len(cards) == 6:
            cards[-1] = link_card
        else:
            cards.append(link_card)
    else:
        _log(f'  ❌ 유효한 URL 없음 — 링크 생략')
        if len(cards) == 6:
            cards.pop()

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
