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

FORMAT_LABELS = {
    'A': '실험형 (5개 카드 + 링크)',
    'B': '구조 분석형 (8개 카드)',
    'C': 'X 쓰레드형 (7개 트윗)',
    'D': '펀치 브리핑형 (5개 카드)',
}

FORMAT_CARD_COUNTS = {
    'A': 5,
    'B': 8,
    'C': 7,
    'D': 5,
}

FORMAT_CARD_COUNT_TOLERANCE = {
    'A': (4, 6),
    'B': (7, 9),
    'C': (6, 8),
    'D': (4, 6),
}

def build_system_prompt_D():
    """형식 D — 펀치 브리핑형 (5개 카드, 현행 유지)"""
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
각 카드는 300~500자. Threads API 제한이 500자이므로 초과 금지.
원문의 숫자, 인물, 인용문, 날짜, 통계를 모두 꺼내서 채운다.
정보가 부족하면 기사 본문에서 더 파낸다. 없는 내용은 절대 만들지 않는다.
- 300자 미만은 정보 부족으로 간주한다. 반드시 300자 이상 채울 것.

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

def build_system_prompt_A():
    """형식 A — 실험형 간소 프롬프트 (5개 카드 + 링크)"""
    return f"""당신은 AI 뉴스를 Threads용 5개 카드 쓰레드로 만드는 작가다.

[핵심]
- 기사를 5개 카드로 요약할 것. 카드는 --- 로 구분.
- 6번째 링크 카드는 직접 작성하지 말 것 (자동 추가됨).
- 각 카드는 누가 읽어도 이해되도록 독립적으로 쓸 것.
- 목표: 사람들이 공감하거나 오래 읽게 만드는 것.

[카드 구조]
각 카드는 3~7줄. 한 줄 15~35자. 줄바꿈이 곧 리듬.
한 문장이 끝난 뒤에는 반드시 한 줄 여백을 넣을 것. 여백이 리듬을 만든다.

[룰 — 4개만]
1. 각 카드는 반드시 250자 이상. 정보 밀도를 높여라.
2. 반말체만 쓸 것 (~임, ~했음, ~있음)
3. 없는 사실 만들지 말 것
4. 기사에 없는 연도를 쓰지 말 것

형식이나 문체에 대한 다른 제한은 없음. 내용에 맞게 자유롭게 써라."""


def build_system_prompt_B():
    """형식 B — 구조 분석형 (8개 카드)"""
    examples = load_style_examples()
    return f"""당신은 AI 뉴스를 Threads용 8개 카드 쓰레드로 만드는 작가다. 형식은 구조 분석형.

[핵심 구조 — 8개 카드, --- 로 구분, 번호 없음, 각 카드 450~500자]
각 카드는 반드시 2~3개의 stanza(3~5줄 + 빈 줄)로 구성된다. 한 줄 25~40자. 각 카드가 450자를 넘지 않으면 정보 부족으로 간주된다.

1번 카드 (훅): 반드시 충격적인 숫자 하나 또는 "왜?"라는 질문으로 시작. 첫 줄에서 독자의 시선을 잡을 것. 2~3 stanza로 구성, 다음 순서: (1) 충격적 사실/질문 (2) 배경/맥락 (3) 이 글을 읽어야 하는 이유.
2번 카드 (데이터): 주장을 뒷받침하는 구체적인 숫자와 통계만 나열. 단위와 비교 기준을 반드시 포함. 2~3 stanza.
3번 카드 (구조): 주제의 물리적·구조적 조건을 설명. "어떤 곳이냐"로 시작. 2~3 stanza.
4번 카드 (비교): 비슷한 문제를 다른 플레이어들은 어떻게 겪었는지 대조. 갈등·비용·시간을 구체적으로 서술. 마지막 문장은 대조 결과를 자연스럽게 요약. 2~3 stanza.
5번 카드 (글로벌 vs 한국): 같은 문제를 미국/해외와 한국이 정반대로 풀고 있음을 보여줌. 인상적인 마무리 한 문장. 2~3 stanza.
6번 카드 (반전): 반전 문장으로 시작. 지금까지 긍정적으로 묘사한 대상의 약점이나 해결 과제를 솔직하게 제시. 해법이 나오는 중이라는 희망 뉘앙스로 마무리. 2~3 stanza.
7번 카드 (압축): 앞서 나온 모든 핵심 숫자와 논리를 짧게 압축. 한 줄씩 끊어서 리듬감 있게.
8번 카드 (결론): 1번 카드의 질문에 답하는 형식. 이유를 3~4개 항목으로 정리. 마지막 인상적인 문장으로 마무리.

[절대 금지]
- 각 카드 앞에 (훅), (데이터), (구조), (비교), (반전), (압축), (결론) 등 어떤 레이블도 출력하지 말 것.
- 카드 번호(1/8, 2/8, N / 8 등)를 카드 앞에 절대 붙이지 말 것.

""" + _FORMAT_COMMON_RULES(examples)


def build_system_prompt_C():
    """형식 C — X 쓰레드형 (7개 트윗)"""
    examples = load_style_examples()
    return f"""당신은 AI 뉴스를 Threads용 7개 트윗 쓰레드로 만드는 작가다. 형식은 X 쓰레드형.

[핵심 구조 — 7개 트윗, --- 로 구분, 번호 없음, 각 트윗 450~500자]
각 트윗은 반드시 2~3개의 stanza(3~5줄 + 빈 줄)로 구성된다.
1 (훅): 반드시 한 줄로 시작. 15자 이내. 숫자, 반전, 역설 중 하나를 사용. 두 번째 줄에서 1~2문장으로 확장.
2 (팩트): 핵심 수치나 스펙을 리스트로 정리. 최대 4개 항목. 마지막 줄에 "이게 왜 중요한가"를 한 문장으로 예고.
3 (배경): "왜 지금 이게 나왔는가"를 2~3문장으로 설명. 마지막 문장은 브릿지 문장.
4 (구조 분석): 걸모습과 실제의 차이를 드러내는 구조 활용. 마지막 문장은 브릿지 문장.
5 (반전): 긍정이면 위험/한계를, 부정이면 의외의 기회를 다룸. 독자가 "그건 생각 못 했다"고 느끼게 만들 것. 마지막 문장은 브릿지 문장.
6 (한국 연결): 한국 시장, 한국 기업, 한국 직장인 관점으로 구체화. 추상적 주장 금지. 반드시 구체적 상황이나 수치로.
7 (마무리): 핵심 질문 한 문장. 답을 주지 않는다. 독자가 생각하게 만드는 것이 목표. 빈 줄 후 해시태그 5개 이내 (본문과 분리).

[절대 금지]
- 카드 번호(1/7, 2/7, N/7 등)를 카드 앞에 절대 붙이지 말 것.

""" + _FORMAT_COMMON_RULES(examples)


def _FORMAT_COMMON_RULES(examples):
    """모든 형식에 공통으로 적용되는 문체/숫자/어투 규칙"""
    return f"""
[공통 문체 규칙 — 모든 형식 적용]
- 문장은 간결하게. 단, 필요한 정보는 모두 포함.
- 숫자는 반드시 포함. 비교 가능한 단위로 환산.
- 전문 용어는 쓰되, 바로 다음 줄에 쉬운 말로 풀어줄 것.
- 마지막 문장은 항상 선언형. "~임", "~했음", "~없음" 등 단정적 종결로 끝낼 것. 같은 표현을 반복하지 말 것.

[톤 & 스타일]
- 이모지 없이, 담담하고 냉정한 분석가 톤 유지.
- "~로 분석됩니다", "~의미입니다" 같은 분석가 어휘 금지.
- 직접 인용은 절대 다듬지 말고 날것으로.
- 형용사 최소화. 사실 진술만.
- 각 카드는 "정보 하나 + 인물의 행동/감정 하나"로 구성.

[절대 금지]
- "정리하면", "교훈은" 같은 프레임.
- 감탄사, 과장 표현 ("놀랍게도", "충격적으로").
- 볼드, 이탤릭 등 서식.
- 중복 표현, 동어 반복.
- 해시태그와 본문 혼용 (해시태그는 마지막 트윗 끝에 빈 줄 후 별도 배치).

[연도 원칙 — 최우선]
- 기사 본문에 명시된 날짜/연도만 사용하라.
- 본문에 연도가 없으면 쓰레드에도 연도를 표시하지 마라.
- 기사의 발행일(입력일)을 사건 발생일로 사용하지 마라.
- **절대 금지: 기사 본문에 없는 연도(예: 2000, 2023 등)를 쓰레드 본문에 포함하지 마라. 이 규칙을 위반하면 쓰레드 전체가 폐기된다.**

[숫자 원칙 — 최우선]
- 기사 본문에 있는 숫자는 전부 꺼내서 써라.
- 달러 금액, 퍼센트, 날짜, 사용자 수, 성장률 — 기사에 있으면 반드시 포함.
- 기사에 숫자가 없으면 "수십억", "대규모", "많은" 같은 뭉뚱그린 표현 금지.
- 숫자 없는 사실은 쓰지 마라.

[어투 규칙 — 반드시 준수]
- 모든 문장은 반말 종결형.
  * ~이다 → ~임. / ~한다 → ~함. / ~했다 → ~했음.
  * ~된다 → ~됨. / ~있다 → ~있음. / ~없다 → ~없음.
- 인용 표현: "~라고 밝혔다" → "~라고 밝혔음."
- 절대 금지: ~입니다. / ~합니다. / ~이다. / ~한다.
- 예외: 훅(첫 카드 첫 문장)은 어투 규칙 적용하지 않아도 됨.

[밀도 기준 — 중요]
- 각 카드는 반드시 450~500자. 절대 400자 아래로 내려가지 말 것.
- Threads API 제한(500자)에 최대한 가깝게 채워라. 정보가 부족하면 기사 본문에서 추가 숫자/인용/맥락을 더 파낼 것.
- 400자 미만은 정보 부족이다. 기사 본문을 다시 읽고 추가 정보를 찾아서 채워라.

[피치 메타데이터 — 출력 금지]
- "핵심 이야기:", "반전:", "감정:", "체감 단위:" 등의 피치 메타데이터 레이블을 쓰레드 본문에 절대 포함하지 마라.
- 쓰레드는 기사 본문의 사실만으로 구성하고, 메타데이터는 참고용으로만 사용하라.

[참고 문체 예시 — 아래 스타일로 작성할 것]
{examples}

[키워드 규칙]
- 기사 원문에 등장하는 단어를 그대로 사용할 것.
- 단어를 임의로 줄이거나 변형하지 말 것.
- 기사에 없는 단어로 대체하지 말 것."""


FORMAT_BUILDERS = {
    'A': build_system_prompt_A,
    'B': build_system_prompt_B,
    'C': build_system_prompt_C,
    'D': build_system_prompt_D,
}


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
            log(f'  ⚠️ humanize: 응답 없음 → 원본 유지')
            return cards

        result = _strip_instruction_leak(result)
        fixed = [c.strip() for c in result.split('---') if c.strip()]

        # 길이 검증: 50% 미만이면 원본 유지
        if len(fixed) < len(cards) * 0.5:
            log(f'  ⚠️ humanize: 결과 부족 ({len(fixed)}<{len(cards)}) → 원본 유지')
            return cards

        # 카드 수 검증: 5~9개 허용 (A/B/C/D 형식별 카드 수 대응)
        if len(fixed) < 5 or len(fixed) > 9:
            log(f'  ⚠️ humanize: 카드 수 불일치 ({len(fixed)}) → 원본 유지')
            return cards

        changed_cards = sum(1 for a, b in zip(cards, fixed) if a != b)
        log(f'  🧹 humanize: {changed_cards}/{len(cards)}개 카드 수정')
        return fixed

    except Exception as e:
        log(f'  ⚠️ humanize 오류: {e} → 원본 유지')
        return cards


def _cleanup_source_attribution(cards):
    """카드 끝에 붙은 '출처: ...' 패턴 제거
    LLM이 format B prompt에서 '출처 언급'을 지시받아 생성한 텍스트 정리
    """
    cleaned = []
    for card in cards:
        lines = card.split('\n')
        # 출처 패턴 제거
        clean_lines = [l for l in lines if not re.match(r'^\s*출처\s*[:：]', l)]
        # 쓰레드 시작/끝 instruction leakage 제거
        clean_lines = [l for l in clean_lines if '쓰레드 시작' not in l and '쓰레드 끝' not in l]
        # --- 구분자 leakage 제거 (본문 내 ---)
        clean_lines = [l for l in clean_lines if not re.match(r'^-{3,}\s*$', l)]
        if clean_lines:
            cleaned.append('\n'.join(clean_lines).strip())
    # 명백한 연도 환각(2000) 제거
    cleaned = [re.sub(r'(?<!\d)2000(?!\d)(?!년)', '', card) for card in cleaned]
    # 남아있는 카드 번호(N / N, N/N) 제거 — 시스템 프롬프트 무시하고 LLM이 붙인 경우
    cleaned = [re.sub(r'^\s*\d+\s*/\s*\d+\s*\n?', '', card) for card in cleaned]
    # 빈 줄만 남은 경우 정리
    cleaned = [re.sub(r'\n{3,}', '\n\n', card).strip() for card in cleaned]
    return cleaned

def _clean_english_leakage(text):
    """한국어 텍스트에 영어가 공백 없이 붙어있는 leakage 제거 (정규식)
    DeepSeek V4 Flash가 한국어 생성 중간에 영어 단어를 누출하는 패턴 처리
    개행(\n)은 stanza 구조 보존을 위해 제외하고 보존
    """
    text = re.sub(r'([가-힣])([A-Za-z][A-Za-z ]{1,30}?)([가-힣])', r'\1\3', text)
    text = re.sub(r'([가-힣])([A-Za-z][A-Za-z ]{1,30})$', r'\1', text)
    text = re.sub(r'([가-힣])([A-Za-z][A-Za-z ]{1,30}?)\n', r'\1\n', text)
    return text


def _fix_korean_particle_spacing(text):
    """영문 대문자 약어/단어 뒤에 조사 등 한글이 붙어있는 경우 공백 추가
    예) UPI가 → UPI 가, Intel이 → Intel 이, AI가 → AI 가
    """
    text = re.sub(r'([A-Za-z][A-Za-z0-9.+#]*)([가-힣])', r'\1 \2', text)
    return text

def fix_cards(cards):
    """GPT로 글자 단위 오류(첫 글자 드랍, 잘린 문자, 깨진 단어)만 수정
    내용/의미/구조는 변경하지 않음
    """
    # 0단계: DeepSeek 영어 leakage 정규식 제거 (모델 의존 없는 1차 방어)
    cards = [_clean_english_leakage(c) for c in cards]
    # 0.5단계: 영문+한글 조사 붙어쓰기 교정 (예: UPI가 → UPI 가)
    cards = [_fix_korean_particle_spacing(c) for c in cards]
    # humanize 먼저 적용
    cards = humanize_cards(cards)
    # humanize 후 재유입된 leakage 재제거
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
            fixed = [c.strip() for c in result.split('---') if c.strip()]
            if len(fixed) == len(cards):
                changed = sum(1 for i in range(len(cards)) if fixed[i] != cards[i])
                log(f'  🔧 오류 수정(MiMo): {changed}/{len(cards)}개 카드 수정됨')
                return fixed
            if len(fixed) > len(cards):
                log(f'  ⚠️ 수정 후 카드 수 초과: {len(fixed)}>{len(cards)} → {len(cards)}개로 자름')
                fixed = fixed[:len(cards)]
                changed = sum(1 for i in range(len(cards)) if fixed[i] != cards[i])
                log(f'  🔧 오류 수정(자름): {changed}/{len(cards)}개 카드 수정됨')
                return fixed
            log(f'  ⚠️ 수정 후 카드 수 부족: {len(fixed)}<{len(cards)} → 원본 유지')
        else:
            log(f'  ⚠️ 수정 실패 → 원본 유지')
    except Exception as e:
        log(f'  ⚠️ 수정 오류: {e} → 원본 유지')
    return cards


def write_thread(pitch, all_articles, format_choice=None):
    """피치 + 관련 기사 → 쓰레드 조각 리스트
    format_choice: 'A', 'B', 'C', 'D' 중 하나. None이면 format_selector로 결정.
    """
    from v3.model_router import chat_completion
    from v3.format_selector import select_format

    if not format_choice or format_choice not in ('A', 'B', 'C', 'D'):
        fmt, reason = select_format(pitch, all_articles)
        format_choice = fmt
        log(f'  🎯 형식 선택: {format_choice} — {FORMAT_LABELS[format_choice]} ({reason})')
    else:
        log(f'  🎯 형식 지정: {format_choice} — {FORMAT_LABELS[format_choice]}')

    system_prompt = FORMAT_BUILDERS[format_choice]()

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

    expected_count = FORMAT_CARD_COUNTS[format_choice]

    # format별 user prompt 구성
    if format_choice == 'A':
        user_prompt = f"""아래 피치와 기사들을 바탕으로 Threads 쓰레드를 작성해주세요 (5개 카드).

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

=== 요구사항 ===
1. 기사를 5개 카드로 요약. 카드는 --- 로 구분. 6번째 링크 카드는 쓰지 말 것.
2. 각 카드는 3~7줄. 한 줄 15~35자. 줄바꿈이 리듬. 한 문장 끝나면 한 줄 여백. 각 카드 250자 이상.
3. 각 카드는 독립적으로 읽혀도 이해되어야 함.
4. 반말체(~임, ~했음, ~있음). ~합니다 금지.
5. 기사 본문의 숫자는 전부 꺼내서 써라. 없는 사실 만들지 말 것.
6. 기사에 없는 연도를 쓰지 말 것.
7. 카드 번호 절대 금지. 번호 없이 바로 내용 시작.
8. 목표: 사람들이 공감하거나 오래 읽게 만드는 것."""
    elif format_choice == 'D':
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

=== 요구사항 ===
1. 1번 카드: 첫 stanza punch → 빈 줄 → 둘째 stanza 숫자/날짜 포함 → ---는 둘째 stanza 뒤.
2. 각 카드는 --- 로 구분. 각 카드는 반드시 450~500자로 채울 것. 400자 미만 금지. 정보가 부족하면 기사 본문에서 추가로 추출하라.
3. 반말체(~임, ~했음, ~있음). ~합니다 금지.
4. 기사 본문의 숫자는 전부 꺼내서 써라. "많은", "대규모" 금지.
5. 한 줄 25~40자. 정보를 압축해서 담되 자연스럽게 읽혀야 함.
6. 3~5줄마다 반드시 빈 줄 하나. stanza 구조 유지. 빈 줄이 리듬을 만든다.
7. 핵심 이야기/반전/감정/체감 단위 등의 피치 메타데이터 레이블은 절대 포함하지 마라.
8. ## 카드 수 (절대)
   - 반드시 5개만 작성하라. 4개도 안 되고 6개도 안 된다. 오직 5개.
   - 카드 번호는 붙이지 않는다."""
    else:
        card_num_rules = {
            'B': '- 카드 번호 절대 금지. 카드 레이블(훅/데이터/구조)도 출력 금지.',
            'C': '- 카드 번호 절대 금지. 번호 없이 바로 내용 시작.',
        }
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

=== 요구사항 ===
1. 각 카드는 --- 로 구분. 각 카드는 반드시 450~500자로 채울 것. 400자 미만 금지. 정보가 부족하면 기사 본문에서 추가로 추출하라.
2. 반말체(~임, ~했음, ~있음). ~합니다 금지.
3. 기사 본문의 숫자는 전부 꺼내서 써라. "많은", "대규모" 금지.
4. 한 줄 25~40자. 정보를 압축해서 담되 자연스럽게 읽혀야 함.
5. 3~5줄마다 반드시 빈 줄 하나. 빈 줄이 리듬을 만든다.
6. 핵심 이야기/반전/감정/체감 단위 등의 피치 메타데이터 레이블은 절대 포함하지 마라.
7. ## 카드 수 (절대)
   - 반드시 {expected_count}개만 작성하라.
   {card_num_rules.get(format_choice, '')}
   - 카드 구분은 반드시 "---" (하이픈 3개) 만 사용한다."""

    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            log(f'  쓰레드 생성 중...')
            content = chat_completion(
                system_prompt=system_prompt,
                messages=[{'role': 'user', 'content': user_prompt}],
                temperature=0.7,
                max_tokens=5000,
            )
            if not content:
                raise Exception('모델 응답 없음')
            # raw 응답에서 instruction leakage 사전 제거 (parse 전)
            content = re.sub(r'^.*?쓰레드\s*(시작|끝).*?\n', '', content, count=1)
            content = re.sub(r'^---+\s*\n', '', content)
            content = re.sub(r'\n---+\s*$', '', content)
            cards = parse_cards(content, format_choice)
            if len(cards) > expected_count:
                log(f'  카드 {len(cards)}개 → {expected_count}개로 조정')
                cards = cards[:expected_count]
            cards = fix_cards(cards)
            cards = _cleanup_source_attribution(cards)

            if validate_cards(cards, pitch, format_choice) and validate_year(cards, article_body_text) and validate_keywords(cards, article_body_text):
                # pitcher 크롤링 URL 우선, 없으면 article_ids[0] 링크 사용
                primary_url = pre_crawled_url or next((a.get('link','') for a in related if str(a.get('id','')) == str(article_ids[0]).lstrip('#').strip()), '')
                cards = assemble_final(cards, related, primary_url, crawled_urls, format_choice)
                log(f'  ✅ 쓰레드: {len(cards)}개 조각 (시도 {attempt+1})')
                return cards
            else:
                log(f'  ⚠️ 검증 실패: {len(cards)}개 조각 (시도 {attempt+1}/{max_attempts})')
        except Exception as e:
            log(f'  ⚠️ 오류: {e} (시도 {attempt+1}/{max_attempts})')

    log(f'  ❌ {max_attempts}회 재시도 실패 → fallback 1회')
    try:
        log(f'  쓰레드 생성 중... (fallback)')
        content = chat_completion(
            system_prompt=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
            temperature=0.7,
            max_tokens=5000,
        )
        if not content:
            raise Exception('모델 응답 없음')
        # raw 응답에서 instruction leakage 사전 제거 (parse 전)
        content = re.sub(r'^.*?쓰레드\s*(시작|끝).*?\n', '', content, count=1)
        content = re.sub(r'^---+\s*\n', '', content)
        content = re.sub(r'\n---+\s*$', '', content)
        cards = parse_cards(content, format_choice)
        if len(cards) > expected_count:
            log(f'  카드 {len(cards)}개 → {expected_count}개로 조정 (fallback)')
            cards = cards[:expected_count]
        cards = fix_cards(cards)
        cards = _cleanup_source_attribution(cards)
        if validate_cards(cards, pitch, format_choice) and validate_year(cards, article_body_text) and validate_keywords(cards, article_body_text):
            primary_url = pre_crawled_url or next((a.get('link','') for a in related if str(a.get('id','')) == str(article_ids[0]).lstrip('#').strip()), '')
            cards = assemble_final(cards, related, primary_url, crawled_urls, format_choice)
            log(f'  ✅ 쓰레드: {len(cards)}개 조각 (fallback 성공)')
            return cards
    except Exception as e:
        log(f'  ⚠️ fallback 오류: {e}')

    log('  ❌ 전체 재시도 실패')
    if format_choice != 'D':
        log('  🔄 형식 D로 대체 시도...')
        return write_thread(pitch, all_articles, format_choice='D')
    return []

def parse_cards(text, format_choice='D'):
    """---로 구분된 조각 파싱"""
    cards = [c.strip() for c in text.split('---') if c.strip()]
    if not cards:
        return cards
    # D형식만 stanza merge 적용 (punch + context가 분리되는 패턴)
    if format_choice == 'D' and len(cards) > 1:
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

def validate_cards(cards, pitch, format_choice='D'):
    """기본 검증 (format별 카드 수 + hook 근사 일치)"""
    lo, hi = FORMAT_CARD_COUNT_TOLERANCE.get(format_choice, (5, 6))
    if not cards or len(cards) < lo or len(cards) > hi:
        log(f'    → 카드 수 불일치: {len(cards)}개 (허용: {lo}~{hi}개, 형식: {format_choice})')
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

def assemble_final(cards, articles, primary_url=None, crawled_urls=None, format_choice='D'):
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
