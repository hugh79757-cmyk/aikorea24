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
    'D': '펀치 브리핑형 (5개 발행글 + 1개 출처링크)',
}


def build_system_prompt_D():
    examples = load_style_examples()
    return f"""당신은 AI 뉴스를 Threads용 5개 카드 쓰레드로 만드는 작가다.

[최우선 — 리듬 + 밀도 규칙, 반드시 지킬 것]
- 각 카드 내부는 3~5개의 줄이 하나의 stanza(연)를 이룬다.
- stanza와 stanza 사이는 반드시 한 줄 비운다. (빈 줄이 리듬을 만든다)
- 줄 길이는 문체 원칙을 따를 것.
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
- 반말체. "~임", "~했음", "~있음", "~아님, ~함". "~합니다" "~입니다" 절대 금지.
- 인과관계를 설명하라. "A → B"가 아니라 "A로 인해 B가 발생한 이유는..." 식으로 풀어써라.
- 날짜, 장소, 인물명으로 시작해서 독자를 사건 안으로 끌어당긴다.
- 형용사 금지. 감탄사 금지. 사실과 숫자만.
- "덜", "더", "가장" 같은 비교 표현 절대 금지. "~한"으로 끝나는 형용사 사용 금지.
- 한 줄에 문장을 길게 늘어놓지 않는다. 한 줄은 20~30자. 35자 초과 시 무조건 줄바꿈. 40자 이상 절대 금지.
- 줄바꿈 단위: 의미 단위(조사, 연결어미, 쉼표, 숫자 뒤) 끝에서.
- 구체적 숫자/인명/직접 인용이 들어가면 자연스럽게 짧은 줄이 만들어짐. 추상적 서술만으로 한 카드를 채우지 말 것.
- 문장과 문장 사이에도 한 줄씩 띄워서 카드 안에서 숨 쉴 공간을 만들어라. 문단처럼 뭉쳐 쓰지 마라.
- 5번 카드는 반드시 열린 질문으로 끝낸다. 답을 주지 말고, 선언 금지.
- 이모지 금지. 볼드 금지. 이탤릭 금지.
- 고유명사(기업명, 인물명, 제품명)는 영어 원문을 그대로 사용하라. 예: 화웨이(X) → Huawei(O), 앤트로픽(X) → Anthropic(O), 오픈AI(X) → OpenAI(O)
- 중국어(한자) 사용 절대 금지. 한자 1글자라도 출력 시 발행이 차단된다. 반드시 한국어로 번역하라.
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
반드시 아래 카드 역할 정의와 구조를 그대로 따라라.
각 카드의 역할을 반드시 지켜라. 역할을 바꾸거나 생략하지 말 것.

1번 — 3-stanza 강제 구조:
  stanza 1 (통념): 반드시 2줄로 분리. 한 줄로 이어쓰기 금지.
    줄1: "~라는 말, 지난 N년간 모두가 믿었음" / "다들 ~라고 생각했음" / "지금까지는 ~였음"
    줄2: 통념의 구체적 내용 1줄
  stanza 2 (전환+증거 시작): 2줄.
    줄1: 전환 ("근데..." / "하지만...")
    줄2: 첫 번째 구체적 증거 (인명/숫자 1개)
  stanza 3 (구체적 증거): 2-3줄. 각 줄에 하나의 사실만.
    예: "Kylie Jenner가 메타 AI 안경의 얼굴이 되었음."
        "28세 리얼리티 TV 스타."
        "카메라 내장 안경을 공동 디자인하고 홍보함."
  stanza 내 한 줄 20~30자. 35자 초과 금지.
  통념은 사람들이 긍정적으로 믿던 것이어야 함. 비판적 서술을 통념으로 쓰지 말 것.

---
2번 — but_line 전개 + 뒷받침 사실:
  첫 1-2줄: but_line을 직접 전개. "하지만..." 전환 시그널 사용.
  다음 2-3줄: but_line을 뒷받침하는 기사 구체적 사실 (숫자/인명/인용).
  but_line만 쓰지 말 것. 반드시 기사 사실로 보강.
  시작 표현 (매번 다양하게):
  - "근데 이게 깨지는 중임."
  - "하지만 여기서 방향이 꺾임."
  - "그런데 사실은 반대임."
  - "여기서 통념이 흔들림."
  - "근데 숫자가 거꾸로 돌기 시작함."
  - "표면과 다른 진실이 있음."
  - "그런데 실제로는 이렇지 않음."
  - "이 구조의 함정은 여기에 있음."

---
3번 — 증거 A:
  기사에서 but_line을 뒷받침하는 구체적 숫자/발언/사실.
  기사 본문을 직접 인용한다 (숫자, 날짜, 인용문).

---
4번 — 증거 B:
  기사에서 또 다른 구체적 사실, 또는 but_line을 더 큰 맥락에서 해석.
  3번과 다른 각도의 증거.

---
5번 — 열린 질문 = question:
  답을 주지 않는다. 질문만 던지고 끝낸다.
  "선언" 금지. "결론" 금지. "핵심은" 금지.
  question 필드의 질문을 그대로 사용한다.
  반드시 질문으로 끝날 것. 질문 이후 어떤 문장도 추가 금지.
  "되돌아보면", "결국", "수렴함" 등 메타 진술 금지.
  시작 패턴 (매번 다양하게):
  - "남는 질문은 하나임."
  - "진짜 질문은 이거임."
  - "그럼 이게 어디로 가는지 아무도 모름."
  - "둘 중 어느 쪽이 진짜가 될까."
  - "누가 먼저 선을 넘을까."
  - "되돌아보면 결국 하나의 질문으로 수렴함."

---
6번: 출처 링크만. 내용 없음. 예: 🔗 https://example.com/news

[5번 카드 — 절대 금지]
- "결론은 명확함", "이것이 핵심임", "우리는 ~해야 한다" 같은 닫힌 결론 금지
- "선언" 형태의 마무리 금지
- 질문 다음에 답·메타 진술·어떤 문장도 추가 금지
- "되돌아보면", "결국", "수렴함", "핵심은" 등 메타 진술 금지
- "핵심은 하나임", "결국 핵심은 이거였음" 금지
- 5번 카드는 반드시 열린 질문으로 끝나야 함. 질문이 마지막 줄이어야 함.

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
- 예외: 1번 카드(통념 세우기) 첫 문장은 어투 규칙 적용하지 않아도 됨
- 절대 금지: ~이다. / ~한다. / ~됩니다. / ~합니다. 로 끝나는 문장

[밀도 기준]
1~5번 카드: 각각 450~500자. Threads API 제한이 500자이므로 초과 금지.
6번 카드: 출처 링크만. 내용 불필요. 예: 🔗 https://example.com/news
3번·4번 카드(증거)에 기사 원문의 숫자, 인물, 인용문, 날짜, 통계를 집중적으로 채운다.
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
- 기사에 없는 단어로 대체하지 말 것

[OUTPUT FORMAT]
- 출력은 반드시 JSON 객체를 사용한다. 최상위 키는 "cards"이며, 값은 카드 문자열의 배열이다.
- 카드 개수는 6개. 카드 1~5번 (통념→전환→증거A→증거B→열린질문) + 6번 출처 링크.
- 각 카드는 위의 카드 역할 정의와 스타일을 반드시 준수해야 한다.
- 예:
{{
  "cards": [
    "1번: 통념 세우기 (450~500자)",
    "2번: 전환 = but_line (450~500자)",
    "3번: 증거 A (450~500자)",
    "4번: 증거 B (450~500자)",
    "5번: 열린 질문 (450~500자)",
    "🔗 https://example.com/news"
  ]
}}
"""



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
                model_override='openai',
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
    def _fix_one(i, card):
        prompt = f"""다음 Threads 카드에서 글자 단위 오류만 수정하라.

[수정 대상 — 반드시 아래 패턴을 찾아 복구할 것]
- 첫 글자/숫자 생략: "국 청소년"→"미국 청소년",  "년 만에"→"1년 만에",  "비디아"→"엔비디아",  "트로픽"→"앤트로픽"
- 한국어 음절 생략: "데팅"→"데이팅",  "앱스"→"앱스토어",  "인공지"→"인공지능",  "챗지"→"챗GPT"
- 한글 자모 누락: "테크놀로지"→"테크놀로지",  "알고리즘"→"알고리즘",  "플랫폼"→"플랫폼"
- 단어 중간 음절 생략: "운동하기 위한"→"운영하기 위한" (영→운),  "수학올림픽"→"수학올림피아드" (픽→피아드)
- 중복 글자/단어: "모델 간 간"→"모델 간",  "있는 있는"→"있는"
- 따옴표/특수문자 오류: "'신발"→"신발",  "제조'"→"제조"

[금지 — 의미 변경 절대 금지]
- 문장의 내용/의미/구조를 절대 변경하지 말 것
- 수정할 게 없으면 원본을 그대로 반환할 것

[출력]
수정된 카드 내용만 출력하라. 부가 설명 금지.

[카드 내용]
{card}
[/카드 내용]"""
        try:
            result = chat_completion(
                system_prompt="당신은 한국어 텍스트 교정 전문가입니다. 글자 단위 오류만 정확히 수정합니다.",
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.1,
                max_tokens=2000,
                model_override='openai',
            )
            if result:
                result = _strip_model_explanatory(result)
                result = _strip_instruction_leak(result)
                result = result.strip()
                if result:
                    return i, result, result != card
            return i, card, False
        except Exception as e:
            _log(f'  ⚠️ 수정 오류: {e} → 원본 유지')
            return i, card, False

    fixed_cards = [None] * len(cards)
    changed_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(cards)) as ex:
        fut_map = {ex.submit(_fix_one, i, cards[i]): i for i in range(len(cards))}
        for fut in concurrent.futures.as_completed(fut_map):
            i, text, changed = fut.result()
            fixed_cards[i] = text
            if changed:
                changed_count += 1

    _log(f'  🔧 오류 수정(MiMo): {changed_count}/{len(cards)}개 카드 수정됨')
    return fixed_cards


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
첫 문장 (통념으로 재구성): {pitch['hook']}
  hook이 but_line 성격이면(모순/역설/하지만 포함), 통념의 반대편으로 바꿀 것.
  예: "AI 교육이 진보를 약속하지만 역설" → "AI 교육이 시민을 강화한다는 말, 모두가 믿었음"
  hook이 이미 통념이면 그대로 사용.
핵심 이야기: {pitch.get('narrative','')}
반전: {pitch.get('twist','')}
감정: {pitch.get('emotion','')}
모순 한 줄 (but_line): {pitch.get('but_line','')}
열린 질문 (question): {pitch.get('question','')}
간극 유형 (gap_source): {pitch.get('gap_source','')}

=== 형식 ===
{FORMAT_LABELS[format_choice]}

=== 관련 기사 ===
{related_text}

=== 요구사항 ===
1. 각 발행글 450~500자. 400자 미만 금지. 정보 부족 시 기사 본문에서 추가 추출.
2. 각 발행글 내부는 3~5줄의 stanza 구조. stanza 사이는 빈 줄 한 줄(\n\n)로 구분.
3. 반말체(~임, ~했음, ~있음). ~합니다 금지.
4. 기사 본문 숫자는 전부 사용. "많은", "대규모" 금지.
5. 한 줄 20~30자. 35자 초과 시 무조건 줄바꿈. 40자 이상 절대 금지. 숫자/인명/인용이 줄바꿈을 만듦.
6. 핵심 이야기/반전/감정/체감 단위 등의 피치 메타데이터 레이블 절대 포함 금지.
7. 각 발행글은 반드시 완전한 문장으로 끝내라. 단, 5번 카드는 질문으로 끝나야 함.
8. 최종 출력은 JSON 객체로 하며, 각 발행글은 "cards" 배열의 문자열이다.

=== 카드별 필수 규칙 (반드시 준수) ===
- 1번: 3-stanza 강제. stanza1 통념2줄 → stanza2 전환1줄+증거1줄 → stanza3 증거 각1줄. 35자 초과 금지. 통념은 긍정적 믿음이어야 함.
- 2번: but_line 전개 1-2줄 → but_line 뒷받침 기사 사실 2-3줄. but_line만 쓰지 말 것.
- 3번: but_line을 뒷받침하는 또 다른 숫자/발언 인용. 증거 집중.
- 4번 카드: 기사에서 또 다른 증거, 또는 but_line을 더 큰 맥락에서 해석.
- 5번 카드: question을 그대로 사용. 질문 다음에 답·메타진술·어떤 문장도 추가 금지. 질문이 마지막 줄이어야 함.
- 6번 카드: 출처 링크만.

=== gap_source 분기 ===
- gap_source=explicit: but_line이 기사에 명시적 모순으로 존재. 3번 카드에서 기사 직접 인용.
- gap_source=reconstructed: but_line이 기사 사실을 재연결해 구성한 모순. 2번 카드에서 통념과 기사 사실을 연결해 but_line을 직접 구성. 3번 카드는 기사의 핵심 사실만 인용."""

    _log(f'  쓰레드 생성 중... (temperature=0.4)')

    def _try_model(model_name):
        return chat_completion(
            system_prompt=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
            temperature=0.4,
            max_tokens=5000,
            model_override=model_name,
        )

    content = _try_model('deepseek')
    if not content:
        _log('  ⚠️ DeepSeek 1차 실패 → 1회 재시도')
        content = _try_model('deepseek')

    if not content:
        _log('  ⚠️ DeepSeek 2차 실패 → GPT-4o-mini fallback')
        content = _try_model('openai')

    if not content:
        _log('  ❌ 모든 모델 응답 실패')
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

    # Card length validation: 각 카드는 100자 이상 (링크 제외)
    for i, c in enumerate(cards, 1):
        if c.startswith('🔗') or c.startswith('http'):
            continue
        if len(c) < 100:
            _log(f'  ⚠️ 카드 {i} 너무 짧음 ({len(c)}자) — 재시도 필요')
            return []

    if not (validate_cards(cards, pitch, format_choice) and validate_year(cards, article_body_text) and validate_keywords(cards, article_body_text)):
        _log(f'⚠️ 검증 실패: {len(cards)}개 조각')
        return []

    structure_ok, structure_reason = validate_card_structure(cards)
    if not structure_ok:
        _log(f'⚠️ 카드 구조 검증 실패: {structure_reason}')
        _log(f'  [RAW CARDS DUMP] {json.dumps(cards, ensure_ascii=False)}')
        return []

    # Model message validation
    for i, card in enumerate(cards, 1):
        if not validate_model_message(card):
            _log(f'⚠️ Card {i}: 모델 메시지 탐지')
            return []

    final_ok, final_reason = validate_final_output(cards)
    if not final_ok:
        _log(f'⚠️ 최종 검증 실패: {final_reason}')
        return []

    primary_url = pre_crawled_url or next((a.get('link','') for a in related if str(a.get('id','')) == str(article_ids[0]).lstrip('#').strip()), '')
    cards = assemble_final(cards, related, primary_url, crawled_urls, format_choice)
    _log(f'✅ 쓰레드: {len(cards)}개 조각')
    return cards


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

    # Final safety dedup
    cards = _remove_duplicate_links(cards)
    
    # Pad to 6 cards if needed (split longest card at sentence boundary)
    if len(cards) < 6:
        longest_idx = -1
        longest_len = -1
        for i, c in enumerate(cards):
            if c.startswith('🔗'):
                continue
            if len(c) > longest_len:
                longest_len = len(c)
                longest_idx = i
        
        if longest_idx >= 0:
            card = cards[longest_idx]
            # Split at a sentence boundary near the middle
            mid = len(card) // 2
            split_pos = -1
            for sep in ['. ', '.\n', '했음\n', '있음\n', '임\n']:
                pos = card.find(sep, max(mid - 30, 0), min(mid + 30, len(card)))
                if pos > 0:
                    split_pos = pos + len(sep) - 1
                    break
            
            if split_pos > 0:
                cards[longest_idx] = card[:split_pos]
                cards.insert(longest_idx + 1, card[split_pos:].strip())
    
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
