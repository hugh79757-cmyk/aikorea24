#!/usr/bin/env python3
"""무료 모델 실무 투입 평가 (AIK24-EVAL-02)

OpenRouter 무료 모델을 12문항(4개 실무 축 × 3문항)으로 직접 실측하고
  1) 축별 원시 결과 ("12문항 중 8문항 정답 (기초 수준 문항 포함). 손발 작업에 적합.")
  2) 문항별 실제 답변 (오답도 그대로 보관 — 독자에게 가장 유용한 정보다)
  3) 컨트롤/손발 역할 판정
  4) 공개 지표 2개 이상 출처 (OpenRouter + Hugging Face)
를 반환한다. 브리핑 코멘트와 블로그 심층 분석이 그대로 인용한다.

AIK24-EVAL-02 로 바뀐 것: "Claude Sonnet 4.5급" 같은 티어 라벨을 삭제했다.
점수를 급수와 대응시키는 근거가 없었고, 급수를 모르는 독자에게 오도한다.
대신 실무 축별 관찰과 실패 사례를 그대로 보여준다.

인증: 원시 키를 로그·파일에 남기지 않는다. model_router.load_env()가 프로젝트
.env / ~/.env.common 에서 OPENROUTER_API_KEY 를 환경변수로 적재하고, 여기서는
os.environ 만 읽는다 (지시서가 참조한 ~/workspace/skills/llm-eval/ 경로는 이
머신에 존재하지 않아 프로젝트 기존 패턴으로 대체 — 완료보고 [위반 감지] 참고).
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts", "threads", "v3"))
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

OPENROUTER_CHAT = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"

QUESTION_TIMEOUT = 60
QUESTION_MAX_TOKENS = 1500  # EVAL-02: 실무 문항(12,000자 문서 참조·테스트 스위트) 답이 500에 잘림
JUDGE_TEMPERATURE = 0.1
JUDGE_MAX_TOKENS = 10

# OpenRouter 무료 티어는 분당 20회 제한이 있다. 8문항을 연속으로 쏘면 429가 터져
# "0점 처리"가 모델 능력 실패와 구분되지 않는다. 문항 간 간격을 두고, 429는
# Retry-After(또는 백오프)를 존중해 재시도한 뒤에도 실패하면 0점 처리한다.
RATE_GAP_SEC = 4
# EVAL-03 §4-2: "429 재시도 1회" 지시. 이미 _post_question() 안에
# Retry-After/지수 백오프 재시도가 HTTP_429_RETRIES 회 들어 있다(15→30→60초).
# 지시서의 1회보다 관대하고 무한 대기도 아니므로 값을 늘리지 않는다.
# EVAL-03 가 새로 더한 것은 문항별 실패 사유(structured) 기록 — 기존엔 errors 문자열뿐이었다.
HTTP_429_RETRIES = 3
REASONING_RETRY_TOKENS = 2000  # reasoning만으로 끝나 잘린 문항의 재시도 예산
ANSWER_STORE_CHARS = 1000  # 채점관과 블로그가 볼 상세 답변 보관 길이

# 평가 결과 캐시. 브리핑(09:00)과 블로그(09:30)가 같은 모델을 평가하면
# OpenRouter 무료 티어 20req/min에 두 번 걸리고 결과가 어긋난다.
# 파일 하나면 충분하다 — 캐시 DB는 과하다.
CACHE_PATH = os.path.join(PROJECT_DIR, "scripts", "logs", "model_eval_cache.json")
CACHE_TTL_HOURS = 20  # 하루 브리핑 안에서는 재평가 금지
CACHE_SCHEMA = 3  # EVAL-03: 문항별 실패 사유(failures) 신설. v2(EVAL-02, tier 없음)도 폐기

# BLOG-03: 문항 세트 버전. 문항·채점 기준이 바뀌면 이 값을 올린다.
# 리더보드는 qv가 같은 결과끼리만 순위를 매긴다(문항이 다르면 점수를 비교하는 것 자체가 거짓말).
EVAL_QUESTIONS_VERSION = 1

# BLOG-03: 모델 평가 리더보드. append-only — 실행할 때마다 1건씩 쌓인다.
LEADERBOARD_PATH = os.path.join(PROJECT_DIR, "scripts", "logs", "model_leaderboard.json")

# ============================================
# 평가 문항 (AIK24-EVAL-02 §4-3 / §4-7)
#
# 4개 실무 축 × 3문항 = 12문항. 축마다 서로 다른 유형을 최소 2개(여기선 3개) 넣는다.
#   지시이행 — 언어를 지키나, 형식을 지키나, 길이 제약을 지키나
#   코딩실무 — 논리 버그를 찾나, 테스트를 짜나, 중복을 줄이나 (toy 문제 금지)
#   맥락유지 — 멀티턴에서 초반 지시를 기억하나, 긴 문서 특정 지점을 참조하나,
#             여러 제약을 동시에 유지하나
#   역할판단 — 컨트롤(계획 수립)과 손발(단순 변환) 중 어디에 강한가
# ============================================

# 자료는 프롬프트 길이를 키우지 않기 위해 상수로 둔다.
_DOC_500 = (
    "검색 증강 생성(RAG)은 대규모 언어 모델의 답변 정확도를 높이기 위해 검색 단계를 앞단에 붙이는 방식이다. "
    "질문이 들어오면 먼저 이를 임베딩 벡터로 바꾸고, 벡터 데이터베이스에서 의미상 가까운 문서 조각만 찾아내 "
    "프롬프트에 함께 넣는다. 모델은 전체 학습 데이터 대신 검색된 문서만 근거로 삼아 답변하기 때문에 최신 정보 "
    "반영과 출처 추적이 훨씬 쉬워진다. 반면 청크를 잘못 자르거나 검색 정확도가 낮으면 오히려 근거 없는 내용을 "
    "그럴듯하게 만들어내므로, 청크 크기와 검색 개수를 튜닝하는 것이 핵심이다. 또한 같은 질문이 반복될 때마다 "
    "검색을 다시 하는 대신 캐시를 두어 지연과 비용을 줄이는 편이 좋다."
)

_DOC_1000 = (
    "대규모 언어 모델을 서비스에 붙일 때 가장 먼저 드는 질문은 비용이다. 입력 토큰과 출력 토큰에 단가가 붙고, "
    "요청이 늘어날수록 지수처럼 늘어난다. 비용을 낮추는 방법은 크게 네 가지다. 첫째, 자주 반복되는 질문에는 "
    "응답을 미리 저장해 두고 그대로 돌려주는 캐시를 쓴다. 단순 반복 질문이면 비용이 거의 사라진다. 둘째, 모델을 "
    "크기에 따라 나눠서 짧고 쉬운 요청은 작은 모델로, 복잡한 요청만 큰 모델로 보낸다. 셋째, 검색 단계에서 "
    "질문과 관련 없는 문서를 잘라내 입력 토큰 수를 줄인다. 넷째, 입력 전체를 다시 넣지 말고 직전 대화에서 "
    "필요한 부분만 잘라 붙인다. 다만 비용만 줄이다가 품질을 떨어뜨리는 경우가 많아, 같은 질문 묶음에 대해 "
    "비용과 정확도를 함께 기록하고 주기적으로 비교하는 습관이 필요하다. 마지막으로 속도가 중요한 화면이면 "
    "스트리밍으로 첫 글자가 나오기까지의 시간을 줄이는 편이 사용자 이탈률에 직접적인 영향을 준다."
)

# 멀티턴 제약 유지 테스트용 사전 대화 — 마지막 사용자 지시 3개를 기억해야 한다.
PRIOR_TURNS = [
    {"role": "user", "content": "앞으로 모든 답변은 반드시 존댓말(-습니다체)로만 써 주세요."},
    {"role": "assistant", "content": "알겠습니다. 앞으로 모든 답변을 존댓말로만 작성하겠습니다."},
    {"role": "user", "content": "그리고 숫자는 항상 원 단위로 표시해 주세요. 백만원이라고 하지 말고 1,000,000원이라고 써 주세요."},
    {"role": "assistant", "content": "네, 이후에는 금액을 반드시 원 단위 숫자로 표시하겠습니다."},
    {"role": "user", "content": "마지막으로, 답변에 마크다운 표를 쓰지 말아 주세요."},
    {"role": "assistant", "content": "확인했습니다. 표 없이 텍스트로만 답변드리겠습니다."},
]

# ============================================================================
# 긴 문서 참조 테스트 (EVAL-02 §4-7 "1,200자 지점의 함수명을 11,800자 지점에서
# 정확히 참조" 을 실제로 검증). 손으로 쓰면 글자 수가 틀어지므로 코드로 만든다.
# ============================================================================
_MARKER = "normalize_ledger_entries"
_MARKER_AT = 1200

_LONG_PARAS = [
    "이 문서는 벡터 데이터베이스 색인 튜닝에서 축적한 운영 노트다. 검색 품질이 나빠질 때마다 확인하는 순서를 정리했다.",
    "첫 단계는 청크 경계 재검토다. 청크가 문단 중간에서 끊기면 질의응답 쌍이 어긋나므로 문단 경계를 우선해 잘라야 한다.",
    "둘째 단계는 임베딩 차원 축소 여부 확인이다. 차원을 줄이면 저장비는 내려가지만 분리도가 무너지는 모델이 있다.",
    "셋째 단계는 유사도 임계값 조정이다. 임계값을 올리면 정밀도는 올라가지만 재현율이 떨어져 문서 자체를 놓친다.",
    "넷째 단계는 질의 확장이다. 사용자 문장이 짧을 때만 사전을 붙여 임베딩을 한 번 더 계산하는 방식이 비용 대비 낫다.",
    "다섯째 단계는 캐시 정책 점검이다. 같은 질문이 반복되는 비율이 높으면 응답 캐시만으로도 지연이 크게 줄어든다.",
    "여섯째 단계는 평가 세트 분리다. 튜닝에 쓴 문서를 평가에 재사용하면 지표가 과대평가되므로 반드시 갈라야 한다.",
    "일곱째 단계는 로그 보존 기간 결정이다. 질의응답 로그를 오래 남기면 개인정보 보관 정책 위반이 되므로 기간을 정해야 한다.",
]


def _build_long_doc(target=12400):
    """약 target 자의 문서를 만들고 _MARKER_AT 지점에 _MARKER 를 심는다.

    반환: (문서, 마커의 실제 오프셋)
    """
    parts, total, i = [], 0, 0
    while total < target:
        p = _LONG_PARAS[i % len(_LONG_PARAS)]
        parts.append(p)
        total += len(p) + 2
        i += 1
    doc = "\n\n".join(parts)
    ins = f"\n\n[참고] 이 구간의 내부 정합 함수 이름은 {_MARKER} 입니다.\n\n"
    return doc[:_MARKER_AT] + ins + doc[_MARKER_AT:], _MARKER_AT + ins.index(_MARKER)


_DOC_LONG, _MARKER_OFFSET = _build_long_doc()

# 비공개 문항 통과 시 결과 라벨 뒤에 붙는 난이도 고지용 축 목록.
_AXIS_DIFFICULTY = {
    "지시이행": "기초 수준",
    "코딩실무": "실무 수준",
    "맥락유지": "실무 수준",
    "역할판단": "중간 수준",
}

TEST_QUESTIONS = [
    # ── 축 1. 지시 이행 (언어 / 형식 / 길이) ───────────────────────────────
    {
        "axis": "지시이행",
        "q": "한국어로만 답해 주세요. 아래 코드가 하는 일을 설명하고, 답의 마지막 줄에 반드시 '---끝---' 를 출력하세요.\n```python\ndef add(a, b): return a + b\n```",
        "expected": "두 값을 받아 더한 값을 돌려주는 파이썬 함수에 대한 한국어 설명. 그리고 마지막 줄에 '---끝---' 가 나와야 함. 영어로 쓴 사고 과정이 섞이면 불합격",
    },
    {
        "axis": "지시이행",
        "q": "다음 정보를 JSON으로만 출력해 주세요. 마크다운 코드블록, 설명 문장, 앞뒤 문장은 일절 넣지 마세요.\n{\"이름\":\"김민수\",\"나이\":31,\"취미\":[\"등산\",\"독서\"]}",
        "expected": "이름 김민수, 나이 31, 취미 등산·독서를 담은 순수 JSON. 코드블록 표시나 설명 문장이 붙으면 불합격",
    },
    {
        "axis": "지시이행",
        "q": "아래 한국어 문장 3개를 각각 15자 이내로 줄여 주세요. 출력은 정확히 3줄이어야 하고 각 줄은 '-' 로 시작해야 합니다. 그 밖의 설명은 쓰지 마세요.\n1. henceforth the committee will review quarterly\n2. 검색 증강 생성은 답변 정확도를 높이는 방식\n3. 회의는 다음 주 수요일에 오후 세 시에 열립니다",
        "expected": "각 줄이 '-' 로 시작하는 정확히 3줄, 각 줄 15자 이내, 한국어 축약. 설명이 덧붙거나 3줄을 초과하면 불합격",
    },
    # ── 축 2. 코딩 실무 (버그 수정 / 테스트 작성 / 리팩토링) ───────────────
    {
        "axis": "코딩실무",
        "q": "아래 코드의 버그를 찾아 수정 코드를 제시하고, 왜 버그인지 한 줄로 설명해 주세요.\n```python\nfrom datetime import datetime, timedelta\n\ndef get_expired_tokens(tokens, now):\n    return [t for t in tokens\n            if datetime.fromisoformat(t['expires_at']) < now - timedelta(days=30)]\n```",
        "expected": "만료 조건이 뒤집혀 있다 — 지금 코드는 만료된 토큰이 아니라 앞으로 30일 안에 만료될 토큰을 제거한다. 만료된 토큰을 고르려면 `now` 가 아니라 `datetime.fromisoformat(t['expires_at']) < now` 여야 한다는 지적",
    },
    {
        "axis": "코딩실무",
        "q": "아래 함수를 pytest로 검증하는 테스트를 작성해 주세요. 정상 입력, 0으로 나누기, 음수 등 경계값을 모두 다루세요.\n```python\ndef safe_div(a, b):\n    if b == 0:\n        return None\n    return a / b\n```",
        "expected": "pytest 테스트 코드. b=0 이면 None 을 돌려주는지, 정상 나눗셈 결과가 맞는지, 0 나누기 예외가 나지 않는지, 음수 입력 등을 검증해야 하며 테스트 함수 이름과 assert 가 들어간 실행 가능한 코드",
    },
    {
        "axis": "코딩실무",
        "q": "아래 두 함수는 같은 로직을 반복합니다. 동작을 바꾸지 않으면서 중복을 제거해 리팩토링하세요.\n```python\ndef get_active_user(users):\n    out = []\n    for u in users:\n        if u['status'] == 'active':\n            out.append({'id': u['id'], 'name': u['name'], 'email': u['email']})\n    return out\n\ndef get_admin_user(users):\n    out = []\n    for u in users:\n        if u['role'] == 'admin':\n            out.append({'id': u['id'], 'name': u['name'], 'email': u['email']})\n    return out\n```",
        "expected": "필드 추출(사전 만들기) 공통 로직을 함수로 뽑아 두 함수가 재사용하게 하는 리팩토링. 필터 조건만 달라야 하고 출력 키(id, name, email)는 그대로여야 함",
    },
    # ── 축 3. 맥락 유지 (초반 지시 기억 / 긴 문서 특정 지점 / 제약 동시 유지) ─
    {
        "axis": "맥락유지",
        "q": "제1질문에 입력한 문서를 다시 한 번 붙여 드립니다. 이 문서의 약 1,200자 지점에 적힌 내부 정합 함수 이름은 정확히 무엇입니까? 함수 이름만 답하세요.",
        "expected": _MARKER,
        "seed": [{"role": "user", "content": _DOC_LONG}],
    },
    {
        "axis": "맥락유지",
        "q": "위 대화에서 내가 요청한 작업 3가지를 나열해 주세요.",
        "expected": "파이썬 설치 방법 확인, 변수 이름 짓는 규칙 3가지, 프로그램이 안 돌아갈 때 처음 할 일",
        "seed": [
            {"role": "user", "content": "파이썬을 처음 시작하려면 뭘부터 해야 해?"},
            {"role": "assistant", "content": "먼저 파이썬 공식 사이트에서 설치 프로그램을 받으신 뒤, 터미널에서 python --version으로 설치를 확인하세요."},
            {"role": "user", "content": "변수 이름 지을 때 규칙 3개만 알려줘."},
            {"role": "assistant", "content": "첫째, 의미를 분명히 나타내는 이름을 씁니다. 둘째, 밑줄이 아니라 카멜케이스를 씁니다. 셋째, 한 글자 이름은 피합니다."},
            {"role": "user", "content": "프로그램이 안 돌아갈 때 처음에 할 일은?"},
            {"role": "assistant", "content": "에러 메시지를 끝까지 읽고, 문제를 최소 재현 코드로 줄여 본 뒤, 변수 값을 하나씩 출력해 확인하세요."},
        ],
    },
    {
        "axis": "맥락유지",
        "q": "이번 서버의 월 비용은 1250000원이고 GPU 증설로 다음 분부터 3400000원입니다. 이 숫자만 먼저 답해 주세요.",
        "expected": "앞선 대화의 세 가지 제약(존댓말 -습니다체, 금액을 원 단위 숫자로 표기, 마크다운 표 금지)을 모두 지킨 답. 존댓말이고 1,250,000원 / 3,400,000원 형태의 원 단위 숫자이며 표가 없어야 함",
        "seed": PRIOR_TURNS,
    },
    # ── 축 4. 역할 판단 (컨트롤 / 손발) ─────────────────────────────────
    {
        "axis": "역할판단",
        "q": "소규모 팀 3명이 6개월 안에 온라인 주문 시스템을 처음부터 만들려고 합니다. 어떤 순서로 무엇을 먼저 만들지 단계별 계획을 세우세요. 각 단계마다 어떻게 검증할지도 함께 답하세요.",
        "expected": "오케스트레이션·계획 능력에 대한 답. 단계 구분(도메인 모델·결제·재고·주문 흐름·운영), 순서와 근거, 단계별 검증 방법을 포함하는 구조적 계획",
    },
    {
        "axis": "역할판단",
        "q": "아래 로그에서 timestamp 열만 뽑아서 CSV로 바꿔 주세요. 설명 없이 결과 데이터만 출력하세요.\n2026-01-02T03:04:05Z GET /a 200\n2026-01-02T03:04:06Z GET /b 404\n2026-01-02T03:05:00Z POST /c 500",
        "expected": "세 줄의 timestamp만 모은 CSV(헤더 유무는 무관, 구분자 쉼표) — 손발형 단순 변환 작업. 원문 그대로 복사하면 가변 변환이 아니고 시간만 추려야 함",
    },
    {
        "axis": "역할판단",
        "q": "지금 바로 처리해야 하는 것과 오늘은 미뤄도 되는 것을 나눠 주세요. 이유는 판단 근거까지 적어 주세요.\n- 운영 DB에서 느린 쿼리 하나가 관측됨(3초 소요)\n- 내부 도구의 버튼 색상 문구 수정 요청이 옴\n- 장애 후속 조치로 고객 메일 발송 대기 중",
        "expected": "우선순위 판단과 근거. 고객 메일 발송과 느린 쿼리는 즉시, 버튼 문구는 미룸으로 나누는 판단이 요구됨",
    },
]

AXES = ("지시이행", "코딩실무", "맥락유지", "역할판단")

# 축별 요약 라벨 — 브리핑·블로그가 그대로 인용한다.
AXIS_LABELS = {
    "지시이행": "지시 이행",
    "코딩실무": "코딩 실무",
    "맥락유지": "맥락 유지",
    "역할판단": "역할 판단(컨트롤 vs 손발)",
}

_models_cache = {}


def log(msg):
    print(f"[model_eval] {msg}")


def _api_key():
    """OPENROUTER_API_KEY 확보. 없으면 예외(원시 키는 절대 출력하지 않음)."""
    from model_router import load_env  # 프로젝트 공통 env 적재기

    load_env()
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY 없음 (프로젝트 .env 또는 ~/.env.common 확인)")
    return key


def _extract_answer(message):
    """추론 모델 대응: content가 null이면 reasoning에서 답을 뽑는다."""
    content = (message.get("content") or "").strip()
    if content:
        return content, "content"
    reasoning = (message.get("reasoning") or message.get("reasoning_content") or "").strip()
    if reasoning:
        return reasoning, "reasoning"
    return "", "empty"


def _post_question(headers, payload):
    """OpenRouter 문항 1회 호출. 429면 Retry-After/백오프를 존중해 재시도.

    반환: (response|None, 재시도 경고 리스트)
    """
    warnings = []
    delay = 15
    for attempt in range(HTTP_429_RETRIES + 1):
        try:
            resp = httpx.post(
                OPENROUTER_CHAT,
                headers=headers,
                json=payload,
                timeout=QUESTION_TIMEOUT,
            )
        except Exception as e:
            warnings.append(f"호출 예외 {type(e).__name__}")
            if attempt < HTTP_429_RETRIES:
                time.sleep(delay)
                delay *= 2
                continue
            return None, warnings
        if resp.status_code != 429:
            return resp, warnings
        retry_after = 0
        try:
            retry_after = int(resp.headers.get("Retry-After", 0))
        except (TypeError, ValueError):
            retry_after = 0
        wait = retry_after if retry_after > 0 else delay
        if attempt >= HTTP_429_RETRIES:
            warnings[-1] = f"HTTP 429 (재시도 {HTTP_429_RETRIES}회 소진)"
            return resp, warnings
        warnings.append(f"HTTP 429 (재시도 {attempt + 1}/{HTTP_429_RETRIES}, {wait}초 대기)")
        time.sleep(wait)
        delay *= 2
    return None, warnings


def cache_load():
    """평가 캐시 로드. 손상돼도 빈 dict로 시작한다(파이프라인을 죽이지 않음)."""
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def cache_get(model_id):
    """TTL 안의 캐시 결과. 없으면 None.

    EVAL-02 로 문항 체계가 바뀌어 예전 결과(티어 라벨 포함)는 형식이 다르다.
    스키마 버전이 다른 항목은 재평가 대상으로 돌려보낸다.
    """
    entry = cache_load().get(model_id)
    if not entry or not entry.get("details"):
        return None
    if entry.get("schema") != CACHE_SCHEMA:
        log(f"캐시 스키마 불일치(v{entry.get('schema')}) → 재평가")
        return None
    age_h = (time.time() - entry.get("ts", 0)) / 3600
    if age_h > CACHE_TTL_HOURS:
        return None
    return entry


def record_leaderboard(model_id, result):
    """BLOG-03 §1-4: 평가 1건을 리더보드에 append. 실패해도 조용히 넘긴다.

    전멸 판정(응답 실패가 절반 초과)은 올리지 않는다 — 점수 0이 순위를 오염시킨다.
    """
    max_score = result.get("max_score", 0)
    if result.get("failed", 0) * 2 > max_score:
        log(f"리더보드 기록 생략 (응답 실패 {result.get('failed')}/{max_score} — 전멸 판정)")
        return
    try:
        os.makedirs(os.path.dirname(LEADERBOARD_PATH), exist_ok=True)
        try:
            with open(LEADERBOARD_PATH, "r", encoding="utf-8") as f:
                rows = json.load(f)
        except Exception:
            rows = []
        if not isinstance(rows, list):
            rows = []
        rows.append({
            "model_id": model_id,
            "qv": result.get("qv", EVAL_QUESTIONS_VERSION),
            "score": result.get("score", 0),
            "max_score": max_score,
            "judge_failed_n": result.get("judge_failed", 0),
            "ts": time.time(),
        })
        tmp = LEADERBOARD_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        os.replace(tmp, LEADERBOARD_PATH)  # 원자적
        log(f"리더보드 기록: {model_id} {result.get('score')}/{max_score} (qv={result.get('qv')}, {len(rows)}건)")
    except Exception as e:
        log(f"리더보드 기록 실패(무시): {type(e).__name__}")


def cache_put(model_id, result):
    """평가 결과 저장. 실패해도 조용히 넘긴다(캐시가 본 작업을 막지 않음).

    응답 실패가 절반을 넘으면 캐시하지 않는다. 레이트리밋에 의한
    전멸 판정이 20시간 캐시에 박히면 내일 브리핑이 그걸 advertise한다.
    BLOG-03: 저장은 성공했지만 리더보드는 별도로 append한다(전멸 판정은 여기서도 배제).
    """
    if result.get("failed", 0) * 2 > result.get("max_score", 9):
        log(f"캐시 저장 생략 (응답 실패 {result['failed']}/{result['max_score']} — 전멸 판정)")
        return
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        data = cache_load()
        entry = dict(result)
        entry["ts"] = time.time()
        entry["schema"] = CACHE_SCHEMA
        entry["qv"] = EVAL_QUESTIONS_VERSION
        data[model_id] = entry
        tmp = CACHE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CACHE_PATH)  # 원자적
        record_leaderboard(model_id, entry)
    except Exception as e:
        log(f"캐시 저장 실패(무시): {type(e).__name__}")


def eval_model_cached(model_id, force=False):
    """캐시 우선 평가. 캐시가 오래됐으면 다시 평가하고 캐시를 갱신한다."""
    if not force:
        hit = cache_get(model_id)
        if hit:
            log(f"캐시 적중 ({model_id}): {hit.get('label')}")
            return hit
    r = eval_model(model_id)
    cache_put(model_id, r)
    return r


def _axis_ratio(by_axis, axis):
    b = by_axis.get(axis) or {}
    n = b.get("max_score") or 0
    return b.get("score", 0) / n if n else None


def judge_role(by_axis):
    """축별 원시 점수 → 한 줄 역할 판정(컨트롤 vs 손발).

    EVAL-02 §4-3: '단순 변환은 빠르나 아키텍처 판단은 피한다' 같은 구체적 판정을
    브리핑 한 줄에 실을 수 있게 압축한다. 티어 라벨(○○급)은 쓰지 않는다.
    """
    ctrl = _axis_ratio(by_axis, "역할판단")  # 계획·우선순위 = 컨트롤 능력
    hands = [
        r for r in (
            _axis_ratio(by_axis, "지시이행"),
            _axis_ratio(by_axis, "코딩실무"),
            _axis_ratio(by_axis, "맥락유지"),
        ) if r is not None
    ]
    hand_avg = sum(hands) / len(hands) if hands else 0.0
    if ctrl is None:
        return "판단 근거 부족 — 손발 작업으로 한정"
    if ctrl < 0.67:
        return "컨트롤(계획·오케스트레이션)에는 검증 부족, 손발 작업으로 보자"
    if ctrl > hand_avg + 0.2:
        return "컨트롤(계획·오케스트레이션)에 적합"
    return "손발 작업에 적합"


def _difficulty_note(by_axis):
    """실제로 채점된 축의 난이도 범위. 과대 평정을 막기 위해 범위로 알린다."""
    order = ("기초 수준", "중간 수준", "실무 수준")
    present = [lv for lv in order if any(
        (by_axis.get(a) or {}).get("max_score") and _AXIS_DIFFICULTY.get(a) == lv for a in by_axis
    )]
    if not present:
        return "난이도 미상"
    return present[0] if len(present) == 1 else f"{present[0]}~{present[-1]}"


def score_response(question, expected, actual):
    """무료 LLM 폴백 체인을 판관으로 사용해 1/0 채점.

    BLOG-03 §1-3: 판관이 0/1을 말하지 못하면 0점을 주지 않고 None(=judge_failed)을
    돌려준다. 0점은 '모델이 틀렸다'는 사실이고, None은 '우리가 못 쟀다'다. 둘을
    섞으면 측정 결함이 모델 실패로 기록돼 순위가 오염된다.
    """
    if not actual or not actual.strip():
        return 0
    from model_router import chat_completion

    verdict = chat_completion(
        messages=[
            {
                "role": "user",
                "content": (
                    f"문제: {question}\n정답: {expected}\n학생 답안: {actual}\n\n"
                    "위 답안이 정답과 의미적으로 일치하면 '1', 아니면 '0'으로만 답하세요.\n"
                    "반드시 '0'으로 판정: ① 질문이 특정 언어로 답을 요구했는데 다른 언어로 답한 경우 "
                    "② 답안에 포함된 코드에 버그가 있는 경우 ③ 질문에 직접 답하지 않고 둘러댄 경우."
                ),
            }
        ],
        system_prompt="당신은 엄격한 시험 채점관입니다.",
        temperature=JUDGE_TEMPERATURE,
        max_tokens=JUDGE_MAX_TOKENS,
        model_override=None,  # 무료 폴백 체인만
    )
    if not verdict:
        log(f"  채점 실패(응답 없음) → 측정 결함: {question[:40]}")
        return None
    m = re.search(r"[01]", verdict)
    if not m:
        log(f"  채점 파싱 실패({verdict[:30]!r}) → 측정 결함: {question[:40]}")
        return None
    return int(m.group(0))


def eval_model(model_id, with_judge=True):
    """표준 12문항(4개 실무 축 × 3문항) 평가. 반환 dict가 eval_model 결과의 전부.

    실패(429·타임아웃·빈 응답)는 해당 문항 0점으로 처리하고 계속 진행한다.
    예외를 던지지 않는다 — 브리핑을 깨뜨리지 않기 위함.
    """
    result = {
        "model_id": model_id,
        "qv": EVAL_QUESTIONS_VERSION,  # BLOG-03: 이 결과가 어느 문항 세트에서 나왔는지
        "score": 0,
        "max_score": len(TEST_QUESTIONS),
        "details": [],
        "errors": [],
        "failures": [],  # EVAL-03: 문항별 호출 실패 사유 — 블로그 '호출 안정성' 섹션 원자료
        "token_usage": {"prompt": 0, "completion": 0},  # BLOG-03 §1-2: 실측 비용 계산 원자료
        "judge_failed": 0,  # BLOG-03 §1-3: 판관이 0/1을 말하지 못한 문항 (모델 실패 아님)
        "by_axis": {a: {"score": 0, "max_score": 0, "failed": 0} for a in AXES},
    }
    try:
        key = _api_key()
    except Exception as e:
        result["errors"].append(f"인증 실패: {e}")
        log(f"인증 실패: {e}")
        return result

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body_tpl = {
        "model": model_id,
        "messages": None,
        "temperature": 0.2,
        "max_tokens": QUESTION_MAX_TOKENS,
    }

    def _reason(resp, warns):
        """문항 실패 사유 — 로그에 남은 문자열 그대로. 추측해서 만들지 않는다(§4-1)."""
        for w in reversed(warns):
            if "429" in w:
                return w
        for w in reversed(warns):
            if "호출 예외" in w:
                return w
        return f"HTTP {resp.status_code}" if resp is not None else "호출 실패"

    def _usage(data):
        """응답의 usage에서 prompt/completion 토큰 수만 뽑는다. 없는 값은 0."""
        u = data.get("usage") or {}
        try:
            return {"prompt_tokens": int(u.get("prompt_tokens") or 0),
                    "completion_tokens": int(u.get("completion_tokens") or 0)}
        except (TypeError, ValueError):
            return {"prompt_tokens": 0, "completion_tokens": 0}

    total = len(TEST_QUESTIONS)
    for idx, spec in enumerate(TEST_QUESTIONS, 1):
        axis, question, expected = spec["axis"], spec["q"], spec["expected"]
        if idx > 1:
            time.sleep(RATE_GAP_SEC)  # 무료 티어 분당 20회 보호
        # 멀티턴 문항은 사전 대화를 넣어야 "위 대화"가 의미를 갖는다
        seed = list(spec.get("seed") or [])
        messages = seed + [{"role": "user", "content": question}]
        # 채점관에게도 전체 대화를 보여준다. 안 그러면 "위 대화"를 검증할 수 없어
        # 멀티턴 문항이 틀린 답으로 판정된다(실측: 전부 맞았는데 0점).
        judge_q = question
        if seed:
            judge_q = (
                "=== 대화 기록 ===\n"
                + "\n".join(f"{m['role']}: {m['content']}" for m in messages)
                + "\n=== 질문 ==="
            )
        payload = dict(body_tpl, messages=messages)
        actual, source = "", "error"
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        resp, warns = _post_question(headers, payload)
        for w in warns:
            result["errors"].append(f"Q{idx} {w}")
        if resp is None:
            result["errors"].append(f"Q{idx} 호출 실패(예외)")
            log(f"  [{idx}/{total}] {axis} 호출 예외 → 0점")
            result["details"].append({"idx": idx, "axis": axis, "score": 0, "source": "exception", **usage})
            result["failures"].append({"idx": idx, "axis": axis, "reason": _reason(None, warns)})
            continue
        if resp.status_code != 200:
            result["errors"].append(f"Q{idx} HTTP {resp.status_code}")
            log(f"  [{idx}/{total}] {axis} HTTP {resp.status_code} → 0점")
            result["details"].append({"idx": idx, "axis": axis, "score": 0, "source": "http_error", **usage})
            result["failures"].append({"idx": idx, "axis": axis, "reason": _reason(resp, warns)})
            continue
        data = resp.json()
        usage = _usage(data)  # BLOG-03 §1-2: 잘림 재시도로 바꾸면 그 응답 usage로 덮어쓴다
        choices = data.get("choices") or []
        if not choices:
            result["errors"].append(f"Q{idx} choices 비어있음")
            result["details"].append({"idx": idx, "axis": axis, "score": 0, "source": "no_choices", **usage})
            result["failures"].append({"idx": idx, "axis": axis, "reason": "응답 없음(choices 비어있음)"})
            continue
        msg = choices[0].get("message") or {}
        actual, source = _extract_answer(msg)
        finish = choices[0].get("finish_reason")
        # 추론 모델은 답이 reasoning 끝에 나오므로 max_tokens=500이면 잘려 0점이 된다.
        # 잘림 + content 없음(답이 reasoning에만 있을 때)이면 한 번만 예산을 키워 재시도한다.
        if finish == "length" and source == "reasoning":
            bigger = dict(payload, max_tokens=REASONING_RETRY_TOKENS)
            time.sleep(RATE_GAP_SEC)
            rresp, rwarns = _post_question(headers, bigger)
            for w in rwarns:
                result["errors"].append(f"Q{idx} reasoning 재시도 {w}")
            if rresp is not None and rresp.status_code == 200:
                rdata = rresp.json()
                rmsg = ((rdata.get("choices") or [{}])[0].get("message")) or {}
                ractual, rsource = _extract_answer(rmsg)
                if ractual:
                    actual, source = ractual, rsource
                    usage = _usage(rdata)  # BLOG-03 §1-2: 재시도가 실제 과금이다
                    result["errors"].append(f"Q{idx} reasoning 잘림 → max_tokens={REASONING_RETRY_TOKENS} 재시도로 회수")
                    log(f"  [{idx}/{total}] {axis} reasoning 잘림 → {REASONING_RETRY_TOKENS}토큰 재시도로 회수 (via {source})")
        elif finish == "length" and actual:
            # EVAL-02: 새 문항은 12,000자 문서 참조·테스트 스위트 작성처럼 답이 길다.
            # 500토큰에 잘린 답을 0점으로 몰면 모델 능력 오판이 된다. 예산을 키워 한 번 더 받는다.
            bigger = dict(payload, max_tokens=REASONING_RETRY_TOKENS)
            time.sleep(RATE_GAP_SEC)
            rresp, rwarns = _post_question(headers, bigger)
            for w in rwarns:
                result["errors"].append(f"Q{idx} 길이 초과 재시도 {w}")
            if rresp is not None and rresp.status_code == 200:
                rdata = rresp.json()
                rmsg = ((rdata.get("choices") or [{}])[0].get("message")) or {}
                ractual, rsource = _extract_answer(rmsg)
                if ractual:
                    actual, source = ractual, rsource
                    usage = _usage(rdata)  # BLOG-03 §1-2: 재시도가 실제 과금이다
                    result["errors"].append(f"Q{idx} length 잘림 → {REASONING_RETRY_TOKENS}토큰 재시도로 회수")
                    log(f"  [{idx}/{total}] {axis} length 잘림 → {REASONING_RETRY_TOKENS}토큰 재시도로 회수 (via {source})")
        elif finish == "length":
            result["errors"].append(f"Q{idx} finish_reason=length(잘림 가능)")
            log(f"  [{idx}/{total}] {axis} finish_reason=length — max_tokens 부족 경고")

        if not actual:
            result["errors"].append(f"Q{idx} 빈 응답")
            result["details"].append({"idx": idx, "axis": axis, "score": 0, "source": "empty", **usage})
            result["failures"].append({"idx": idx, "axis": axis, "reason": "빈 응답"})
            log(f"  [{idx}/{total}] {axis} 빈 응답 → 0점")
            continue

        pts = score_response(judge_q, expected, actual) if with_judge else (1 if actual.strip() else 0)
        judge_failed = pts is None
        if judge_failed:
            pts = 0  # 점수 집계·축별 집계에서는 제외된다. failures[]에도 넣지 않는다(호출은 성공).
            result["judge_failed"] += 1
            log(f"  [{idx}/{total}] {axis} 측정 결함(판관 파싱 실패) — 점수에서 제외")
        else:
            result["score"] += pts
        result["token_usage"]["prompt"] += usage["prompt_tokens"]
        result["token_usage"]["completion"] += usage["completion_tokens"]
        # 상세 답변은 블로그 심층 분석에 그대로 인용된다. 잘라내지 말고 원문을 쓴다.
        result["details"].append({
            "idx": idx, "axis": axis, "score": pts, "source": source,
            "answer": actual[:ANSWER_STORE_CHARS],
            **usage, "judge_failed": judge_failed,
        })
        log(f"  [{idx}/{total}] {axis} {pts}점 (via {source}) ← {actual[:60]!r}")

    result["failed"] = sum(
        1 for d in result["details"] if d["source"] in ("http_error", "exception", "empty", "no_choices")
    )
    # 축별 집계 (EVAL-02 §4-3: 축마다 원시 결과를 그대로 보여준다)
    # BLOG-03 §1-3: 판관이 0/1을 못 한 문항은 분자·분모에서 모두 뺀다.
    for d in result["details"]:
        if d.get("judge_failed"):
            continue
        b = result["by_axis"].setdefault(d["axis"], {"score": 0, "max_score": 0, "failed": 0})
        b["max_score"] += 1
        b["score"] += d["score"]
        if d["source"] in ("http_error", "exception", "empty", "no_choices"):
            b["failed"] += 1
    result["role"] = judge_role(result["by_axis"] or {})
    # 429·타임아웃은 모델 능력 실패가 아니다. 분모에서 빼야 한다.
    # 단, 시도한 문항이 5개 미만이면 "모르겠다"가 정직한 답이다.
    jf = result["judge_failed"]
    scored = result["max_score"] - result["failed"] - jf
    if scored >= 5:
        result["label"] = (
            f"{scored}문항 중 {result['score']}문항 정답 "
            f"(문항 난이도: {_difficulty_note(result['by_axis'])} 기준)"
            + (f", {result['failed']}문항 응답 실패 제외" if result["failed"] else "")
            + (f", {jf}문항 측정 결함" if jf else "")
            + f". {result['role']}."
        )
    else:
        result["label"] = (
            f"{scored}문항 중 {result['score']}문항 정답 (응답 실패 과다 — 판단 보류)"
        )
    if result["failed"]:
        log(
            f"  ⚠️ 응답 실패 {result['failed']}/{result['max_score']}문항 — "
            f"분모에서 제외했다 (능력 실패 아님)"
        )
        log(f"  호출 안정성: {call_stability(result)['verdict']}")
    return result


# ── EVAL-CLI-01: OpenCode CLI 경유 평가 ──────────────────────────────────────
# 카탈로그 ID → `opencode run -m` 모델명. 분기문 대신 표로 관리한다(모델 추가 = 1줄).
# jev-1.13-free 는 OpenCode CLI 에 미등록이라 넣지 않는다.
CLI_MODEL_MAP = {
    "cat-jam-free": "opencode/cat-jam-free",
    "space-bunny-free": "opencode/space-bunny-free",
    # AIK24-EVAL-CLI-02: 2026-10-15 프리모델 페이지 추천 Top 3
    "mimo-v2.6-flash-free": "opencode/mimo-v2.6-flash-free",
    "muse-spark-1.3-contributor-free": "opencode/muse-spark-1.3-contributor-free",
}


def cli_prompt(spec):
    """CLI 는 한 번의 프롬프트만 받으므로 멀티턴 대화 기록을 본문에 못 박는다."""
    q = spec["q"]
    seed = spec.get("seed") or []
    if not seed:
        return q
    return (
        "다음은 대화 기록입니다:\n"
        + "\n".join(f"{m['role']}: {m['content']}" for m in seed)
        + "\n\n위 대화를 바탕으로 다음 질문에 답하세요:\n" + q
    )


def cli_call(cli_model, prompt, timeout=QUESTION_TIMEOUT):
    """`opencode run` 1회 호출. (텍스트, "") 또는 ("", 사유)."""
    try:
        p = subprocess.run(
            ["opencode", "run", "-m", cli_model, "--format", "json"],
            input=prompt, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "", f"CLI 타임아웃 {timeout}초"
    except FileNotFoundError:
        return "", "opencode CLI 없음"
    except Exception as e:
        return "", f"CLI 예외 {type(e).__name__}"
    texts, err = [], ""
    for line in p.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        kind = obj.get("type")
        if kind == "text":
            texts.append((obj.get("part") or {}).get("text") or "")
        elif kind == "error":
            err = (obj.get("error") or {}).get("message") or "CLI 오류"
    if err:
        return "", err
    out = "".join(texts).strip()
    return (out, "") if out else ("", "CLI 빈 응답")


def eval_model_cli(model_id, with_judge=True, cli_model=None):
    """OpenCode CLI 경유 12문항 평가. 반환 (result, blocked).

    blocked 가 문자열이면 모델에 아예 도달하지 못한 상태다. 이때 점수 0을 기록하면
    측정 실패가 모델 실패로 남으므로, 호출자가 zen_pending 사유 갱신에 쓴다.
    판관(score_response)은 API 경로와 같은 것으로 재사용한다.
    """
    cli_model = cli_model or CLI_MODEL_MAP.get(model_id)
    result = {
        "model_id": model_id,
        "source": "cli",            # API 경로와 구분 (EVAL-CLI-01 §작업5)
        "provider": "zen",
        "cli_model": cli_model,
        "qv": EVAL_QUESTIONS_VERSION,
        "score": 0,
        "max_score": len(TEST_QUESTIONS),
        "details": [],
        "errors": [],
        "failures": [],
        # CLI 는 토큰 수를 알려주지 않는다 — 미측정임을 명시하고 0으로 둔다.
        "token_usage": {"prompt": 0, "completion": 0},
        "notes": "CLI 경유 — 토큰 사용량 미측정",
        "judge_failed": 0,
        "by_axis": {a: {"score": 0, "max_score": 0, "failed": 0} for a in AXES},
    }
    if not cli_model:
        return result, f"CLI 미등록 모델 ({model_id})"

    total = len(TEST_QUESTIONS)
    for idx, spec in enumerate(TEST_QUESTIONS, 1):
        axis, question, expected = spec["axis"], spec["q"], spec["expected"]
        if idx > 1:
            time.sleep(RATE_GAP_SEC)
        judge_q = question
        if spec.get("seed"):
            judge_q = (
                "=== 대화 기록 ===\n"
                + "\n".join(f"{m['role']}: {m['content']}" for m in
                            list(spec.get("seed") or []) + [{"role": "user", "content": question}])
                + "\n=== 질문 ==="
            )
        actual, reason = cli_call(cli_model, cli_prompt(spec))
        if not actual:
            if idx == 1:
                # 첫 문항부터 CLI 레벨 실패 = 모델 도달 불가. 0점 기록 없이 중단.
                log(f"  CLI 호출 실패({reason}) — 모델 도달 불가, 중단")
                return result, reason
            result["errors"].append(f"Q{idx} {reason}")
            result["details"].append({"idx": idx, "axis": axis, "score": 0, "source": "exception",
                                      "judge_failed": False})
            result["failures"].append({"idx": idx, "axis": axis, "reason": reason})
            log(f"  [{idx}/{total}] {axis} {reason} → 0점")
            continue
        pts = score_response(judge_q, expected, actual) if with_judge else 1
        judge_failed = pts is None
        if judge_failed:
            pts = 0
            result["judge_failed"] += 1
            log(f"  [{idx}/{total}] {axis} 측정 결함(판관 파싱 실패) — 점수에서 제외")
        else:
            result["score"] += pts
        result["details"].append({
            "idx": idx, "axis": axis, "score": pts, "source": "cli",
            "answer": actual[:ANSWER_STORE_CHARS], "judge_failed": judge_failed,
        })
        log(f"  [{idx}/{total}] {axis} {pts}점 (via cli) ← {actual[:60]!r}")

    result["failed"] = sum(1 for d in result["details"] if d["source"] == "exception")
    for d in result["details"]:
        if d.get("judge_failed"):
            continue
        b = result["by_axis"].setdefault(d["axis"], {"score": 0, "max_score": 0, "failed": 0})
        b["max_score"] += 1
        b["score"] += d["score"]
        if d["source"] == "exception":
            b["failed"] += 1
    result["role"] = judge_role(result["by_axis"] or {})
    jf = result["judge_failed"]
    scored = result["max_score"] - result["failed"] - jf
    if scored >= 5:
        result["label"] = (
            f"{scored}문항 중 {result['score']}문항 정답 "
            f"(문항 난이도: {_difficulty_note(result['by_axis'])} 기준, CLI 경유)"
            + (f", {result['failed']}문항 응답 실패 제외" if result["failed"] else "")
            + (f", {jf}문항 측정 결함" if jf else "")
            + f". {result['role']}."
        )
    else:
        result["label"] = f"{scored}문항 중 {result['score']}문항 정답 (응답 실패 과다 — 판단 보류)"
    if result["failed"]:
        log(f"  ⚠️ 응답 실패 {result['failed']}/{result['max_score']}문항 — 분모에서 제외했다 (능력 실패 아님)")
    return result, None


def _fetch_openrouter_models():
    """OpenRouter 모델 목록 캐시 조회.

    반환: dict (조회 성공), None (조회 실패 — 존재 여부 판정 불가).
    빈 dict(성공했으나 목록 0건)와 None(실패)을 구분한다.
    """
    if "data" in _models_cache:
        return _models_cache["data"]
    data = None
    try:
        key = _api_key()
        r = httpx.get(
            OPENROUTER_MODELS,
            headers={"Authorization": f"Bearer {key}"},
            timeout=30,
        )
        if r.status_code == 200:
            data = {m["id"]: m for m in r.json().get("data", [])}
        else:
            log(f"OpenRouter 모델 목록 HTTP {r.status_code}")
    except Exception as e:
        log(f"OpenRouter 모델 목록 조회 실패: {type(e).__name__}")
    _models_cache["data"] = data
    return data


def _search_term(model_id):
    """`liquid/lfm-2.5-2.6b:free` → `liquid`"""
    base = model_id.split(":")[0]
    vendor = base.split("/")[0].strip()
    return vendor or base


def _model_entry(model_id):
    """OpenRouter 목록에서 모델 엔트리. ':free' 접미사를 벗겨 base도 본다."""
    models = _fetch_openrouter_models()
    if not models:
        return None
    for key in (model_id, model_id.split(":")[0]):
        if key in models:
            return models[key]
    return None


def pricing(model_id):
    """토큰당 단가 {"prompt": float, "completion": float}. 모르는 모델이면 None."""
    m = _model_entry(model_id)
    if not m:
        return None
    p = m.get("pricing") or {}
    try:
        return {"prompt": float(p.get("prompt") or 0.0), "completion": float(p.get("completion") or 0.0)}
    except (TypeError, ValueError):
        return None


def free_paths(model_id):
    """BLOG-03 §1-5: 실제로 확인된 접근 경로만 돌려준다.

    반환: [{"path": ..., "note": ...}]
    - '{base}:free' 가 OpenRouter 목록에 있으면 무료 경로가 있다고 보고 '무료'를 쓴다.
    - 유료만 있으면 실측 단가를 적는다. 목록 조회가 실패했으면 확인 불가라고 적는다.
      (확인 못 한 것을 '무료'라고 쓰지 않는 것이 이 함수의 존재 이유)
    """
    models = _fetch_openrouter_models()
    if models is None:
        return [{"path": "OpenRouter 접근 경로 확인 불가", "note": "OpenRouter 모델 목록 조회 실패 — 무료 여부를 확인하지 못했습니다"}]
    free_id = model_id.split(":")[0] + ":free"
    if free_id in models or model_id.endswith(":free"):
        return [{"path": "OpenRouter 무료", "note": "무료 변형 모델 ID — 일일 한도 확인 필요"}]
    if model_id in models or model_id.split(":")[0] in models:
        pr = pricing(model_id) or {}
        return [{"path": "OpenRouter 유료", "note": f"입력 ${pr.get('prompt', 0) * 1e6:.6f} / 출력 ${pr.get('completion', 0) * 1e6:.6f} (1M토큰당)"}]
    return [{"path": "OpenRouter 경로 미확인", "note": f"'{model_id}'가 OpenRouter 목록에 없습니다"}]


def get_access_guide(model_id):
    """OpenRouter 존재/무료 여부 확인 후 접근법 한 줄 생성."""
    models = _fetch_openrouter_models()
    known = (model_id in models) if models is not None else None
    if known is False:
        return f"OpenRouter에서 '{model_id}'를 직접 검색해보세요."
    free = model_id.endswith(":free")
    term = _search_term(model_id)
    prefix = "무료 티어" if free else "OpenRouter 모델"
    return (
        f"OpenCode에서 프로바이더를 OpenRouter로 하고 '{term}'를 검색해보세요. "
        f"({prefix}, 모델 ID: {model_id})"
    )


def extract_model_id(article):
    """브리핑 기사 dict → OpenRouter 모델 ID. 판별 불가하면 None.

    표기 변형 ((free), -free, :free 등)을 정규화한 뒤 OpenRouter 실제 목록에서
    존재 여부를 확인한다. 존재하지 않으면 None (평가 생략).
    """
    # 1. link 또는 제목에서 base ID 추출
    base_id = None
    link = article.get("link") or ""
    m = re.search(r"openrouter\.ai/([^?#\s]+)", link)
    if m:
        base_id = m.group(1).rstrip("/")
    if not base_id:
        # 제목 변형: [무료 LLM] id:free / [무료 모델] id (free) / id-free 등
        title = article.get("title") or ""
        m = re.search(r"\[무료 (?:LLM|모델)\]\s*([\w\-./]+)", title)
        if m:
            base_id = m.group(1)
    if not base_id:
        return None
    # 2. free 표기 변형 정규화 (:free, (free), -free, [free] 제거)
    base_id = re.sub(r"[:\-\s]*[\(\[]?free[\)\]]?\s*$", "", base_id, flags=re.IGNORECASE).strip()
    if not base_id:
        return None
    # 3. OpenRouter 실제 목록에서 존재 확인 (:free 우선, 없으면 base)
    models = _fetch_openrouter_models()
    if models is None:
        # 목록 조회 실패 시 기존 동작 유지 (호출 시 404로 자연스럽게 실패)
        return base_id + ":free"
    if base_id + ":free" in models:
        return base_id + ":free"
    if base_id in models:
        return base_id
    # 4. 둘 다 없으면 None (평가 생략)
    log(f"모델 미존재 → 평가 생략: {base_id}")
    return None


HF_API = "https://huggingface.co/api/models"


def external_signals(model_id):
    """'남들의 의견'용 공개 지표. EVAL-02 §4-4.

    출처 2곳(OpenRouter 모델 정보 + HuggingFace 모델 카드)을 조회한다.
    수치 지어내기 금지 — 실제로 못 얻은 값은 만들지 않고 '없음'으로 표시한다.
    반환: {"lines": [표시줄], "sources": 확보한 출처 수}
    """
    lines, sources = [], 0

    # 출처 1. OpenRouter — 제공 상태(무료/유료), 컨텍스트 길이
    models = _fetch_openrouter_models()
    if models:
        m = models.get(model_id)
        if m:
            sources += 1
            pricing = m.get("pricing") or {}
            try:
                cost = float(pricing.get("prompt") or 0) + float(pricing.get("completion") or 0)
            except (TypeError, ValueError):
                cost = None
            free_txt = "무료" if cost == 0 else (f"유료 (입력+출력 ${cost:.6f}/1M토큰 기준)" if cost is not None else "가격 정보 없음")
            ctx = m.get("context_length")
            lines.append(f"OpenRouter: {free_txt}, 컨텍스트 {ctx:,} 토큰" if ctx else f"OpenRouter: {free_txt}")

    # 출처 2. HuggingFace — 좋아요·다운로드·태스크
    try:
        r = httpx.get(f"{HF_API}/{model_id}", timeout=20, follow_redirects=True)
        if r.status_code == 200:
            d = r.json()
            likes, downloads = d.get("likes"), d.get("downloads")
            tag = d.get("pipeline_tag")
            bits = []
            if likes is not None:
                bits.append(f"좋아요 {likes:,}")
            if downloads is not None:
                bits.append(f"다운로드 {downloads:,}/월" if downloads >= 1000 else f"다운로드 {downloads}/월")
            if tag:
                bits.append(f"분류 {tag}")
            if bits:
                sources += 1
                lines.append("HuggingFace: " + ", ".join(bits))
    except Exception as e:
        log(f"HuggingFace 조회 실패: {type(e).__name__}")

    if not lines:
        return {"lines": ["공개된 외부 평가 없음"], "sources": 0}
    if sources < 2:
        lines.append("두 번째 출처에서 공개 지표를 확인할 수 없었습니다.")
    return {"lines": lines, "sources": sources}


def call_stability(result):
    """§4-1 호출 안정성 — 실패를 숨기지 않고 그대로 독자에게 보여줄 요약.

    반환: {total, ran, failed, rate, by_reason, by_axis, verdict}
    실패 원인은 로그에 기록된 문자열 그대로 쓴다(추측 금지).
    """
    total = result.get("max_score") or len(TEST_QUESTIONS)
    fails = result.get("failures") or []
    by_reason, by_axis = {}, {}
    for f in fails:
        by_reason[f["reason"]] = by_reason.get(f["reason"], 0) + 1
        by_axis[f["axis"]] = by_axis.get(f["axis"], 0) + 1
    rate = (len(fails) / total) if total else 0.0
    if not fails:
        verdict = f"{total}문항 전부 정상 응답 — 호출 안정성 문제 없음"
    elif rate >= 0.25:
        # 429는 성능 문제가 아니지만 무료 티어에서 못 쓰면 독자에게는 못 쓰는 모델이다.
        verdict = (
            f"{total}문항 중 {len(fails)}문항({rate:.0%})이 호출 실패. 성능과 무관하게 "
            f"현 시점 무료 티어로는 실무 투입이 어렵다"
        )
    else:
        verdict = (
            f"{total}문항 중 {len(fails)}문항({rate:.0%})이 호출 실패. "
            f"간헐적 제한이며 재시도로 대부분 회수될 여지가 있다"
        )
    return {
        "total": total, "ran": total - len(fails), "failed": len(fails), "rate": rate,
        "by_reason": by_reason, "by_axis": by_axis, "verdict": verdict,
    }


def eval_comment_block(model_id, deep_dive_url=None, result=None):
    """브리핑 코멘트용 3요소 티저 블록. 실패 시 빈 문자열(폴백 → 기존 코멘트 유지).

    지시서 1-5 갱신(2026-10-11): 기존 코멘트는 티저에서 제외한다(간결함 우선).
    deep_dive_url이 아직 없으면 해당 줄은 생략한다 — 블로그 글은 09:30 생성이라
    09:00 브리핑 시점에는 URL을 알 수 없다. 링크는
    src/pages/briefing/[date].astro의 deep-dive 카드가 같은 정보를 이미 보여준다.

    result를 넘기면 eval_model() 재호출 없이 재사용한다.
    """
    try:
        r = result if result is not None else eval_model(model_id)
        guide = get_access_guide(model_id)
    except Exception as e:
        log(f"평가 실패({type(e).__name__}: {str(e)[:80]}) → 평가 블록 생략")
        return ""
    if not r.get("details"):
        log("평가 결과 없음 → 블록 생략")
        return ""
    # 모델이 OpenRouter에 없으면(전 문항 http 실패) 블록 자체를 생략한다.
    # "티어 미확인" 표기는 오해를 유발하므로 출력하지 않는다. (2026-10-11)
    if r.get("failed", 0) >= r.get("max_score", 9):
        log(f"전 문항 응답 실패({r['failed']}/{r['max_score']}) → 블록 생략 (모델 미존재 가능)")
        return ""
    lines = [f"[{model_id}] — {r['label']}"]
    # EVAL-03 §4-3: 호출 실패가 있었다면 점수와 분리해 한 줄로 남긴다.
    st = call_stability(r)
    if st["failed"]:
        reasons = ", ".join(f"{k} {v}건" for k, v in st["by_reason"].items())
        lines.insert(1, f"호출 실패 {st['failed']}/{st['total']}문항 ({reasons}) — 점수에서 제외")
    if deep_dive_url:
        lines.append(f"👉 자세한 분석: {deep_dive_url}")
    lines.append(guide)  # EVAL-02 §4-1: 📍 이모티콘 제거, 문구는 텍스트로 유지
    return "\n".join(lines)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "liquid/lfm-2.5-2.6b:free"
    log(f"평가 시작: {target}")
    r = eval_model_cached(target, force="--force" in sys.argv)
    log(f"결과: {r['label']} (실패 {r.get('failed', 0)}/{r['max_score']}문항)")
    if r["errors"]:
        log(f"  경고 {len(r['errors'])}건: {r['errors'][:5]}")
    log(f"접근법: {get_access_guide(target)}")
    log(f"축별 결과: " + ", ".join(
        f"{a} {b['score']}/{b['max_score']}" for a, b in r.get("by_axis", {}).items()
    ))
    for d in r["details"]:
        log(f"  Q{d['idx']}[{d['axis']}] {d['score']}점 src={d['source']}")
    st = call_stability(r)
    log(f"호출 안정성: 실패 {st['failed']}/{st['total']} — {st['verdict']}")
    sig = external_signals(target)
    log(f"외부 지표 ({sig['sources']}개 출처): " + " | ".join(sig["lines"]))

# ── EVAL-CLI-01 작업 6: 실효 컨텍스트 길이 실측 ────────────────────────────
# 공칭 스펙이 아니라 "그만큼 넣어도 앞부분을 아직 기억하고 있나"를 잰다.
# 잊기 시작하는 지점이 실효 컨텍스트라 브리핑에 advertise할 값이다.
PROBE_SECRET = "7392"
PROBE_QUESTION = "위 문서의 첫 문장에 나왔던 비밀번호는 무엇입니까? 숫자만 답하세요."
PROBE_STEPS = (8192, 16384, 32768, 65536, 131072, 262144, 524288, 1048576)
PROBE_TIMEOUT_SEC = 240  # 큰 문서 수신용 — cli_call 기본 60초면 128K 부터 잘린다
PROBE_GAP_SEC = 4  # 무료 티어 보호 — 지시서 작업 6 주의


def _probe_doc(target_tokens):
    """대략 target_tokens 짜리 문서. 첫 문장에 비밀번호를 두고 나머지는 filler."""
    parts = [f"이 문서의 첫 문장에 비밀번호가 있습니다. 비밀번호는 {PROBE_SECRET}입니다.\n\n"]
    size, i = 0, 0
    while size < target_tokens:
        s = f"문장 {i}: 데이터 기록 번호 {i * 7 + 3} 은 검증 항목 {i % 13} 에 대응하며 요약값은 {i * 3 + 1} 입니다.\n"
        parts.append(s)
        size += len(s)
        i += 1
    return "".join(parts)


def _probe_hit(model_id, cli_model, target_tokens):
    """target_tokens 짜리 문서를 넣고 비밀번호를 되받았는지. (성답, 사유)"""
    prompt = _probe_doc(target_tokens) + "\n" + PROBE_QUESTION
    if cli_model:
        # 문서가 크다 — 문항당 60초 기본값이면 128K 부터 잘려 "컨텍스트 부족"으로 오판된다
        return cli_call(cli_model, prompt, timeout=PROBE_TIMEOUT_SEC)
    from model_router import chat_completion

    ans = chat_completion(
        messages=[{"role": "user", "content": prompt}],
        system_prompt="문서에 있는 사실만 답하세요.",
        temperature=0.2, max_tokens=32, model_override=model_id,
    )
    return (ans or ""), ("" if ans else "빈 응답")


def probe_context_length(model_id, cache=None):
    """실효 컨텍스트 길이(토큰) 탐색. 모델당 1회만 — 캐시에 있으면 돌리지 않는다.

    두 배씩 올려서 첫 실패 지점을 찾고, 앞 구간을 이분 탐색으로 좁힌다.
    """
    cache = cache if cache is not None else cache_load()
    if model_id in cache and cache[model_id].get("measured_context"):
        log(f"{model_id}: 실측 컨텍스트 이미 있음 ({cache[model_id]['measured_context']:,}) — 재측정 안 함")
        return cache[model_id]["measured_context"]
    cli_model = CLI_MODEL_MAP.get(model_id)
    ok_sizes = []
    for n in PROBE_STEPS:
        time.sleep(PROBE_GAP_SEC)
        ans, err = _probe_hit(model_id, cli_model, n)
        hit = PROBE_SECRET in (ans or "")
        log(f"{model_id}: {n:,} 토큰 → {'OK' if hit else '실패'}")
        if not hit:
            break
        ok_sizes.append(n)
    if not ok_sizes:
        log(f"{model_id}: {PROBE_STEPS[0]:,} 토큰도 못 받음 — 실측 실패")
        return None
    best = ok_sizes[-1]
    if best == PROBE_STEPS[-1]:
        log(f"{model_id}: {best:,} 토큰까지 통과 (상한 도달 — 실측 하한)")
        return best
    lo, hi = ok_sizes[-2] if len(ok_sizes) >= 2 else 0, best  # lo 는 실패 확정, hi 는 성공 확정
    while hi - lo > 1:
        mid = (lo + hi) // 2
        time.sleep(PROBE_GAP_SEC)
        ans, _ = _probe_hit(model_id, cli_model, mid)
        if PROBE_SECRET in (ans or ""):
            hi = mid
        else:
            lo = mid
    log(f"{model_id}: 실효 컨텍스트 ≈ {hi:,} 토큰")
    return hi
