#!/usr/bin/env python3
"""무료 모델 능력 자동 평가 (AIK24-MODELEVAL-01)

OpenRouter에 있는 무료 모델(:free)을 8문항 표준 테스트로 평가하고
  1) 실용/정확도 점수 (0~8)
  2) 능력 티어 라벨 ("AI 추정: Claude Sonnet 4.5급 (6/8점)")
  3) 접근법 ("OpenCode에서 프로바이더를 OpenRouter로 하고 'liquid'를 검색해보세요.")
를 반환한다. 브리핑 코멘트에 그대로 붙일 수 있는 형태.

인증: 원시 키를 로그·파일에 남기지 않는다. model_router.load_env()가 프로젝트
.env / ~/.env.common 에서 OPENROUTER_API_KEY 를 환경변수로 적재하고, 여기서는
os.environ 만 읽는다 (지시서가 참조한 ~/workspace/skills/llm-eval/ 경로는 이
머신에 존재하지 않아 프로젝트 기존 패턴으로 대체 — 완료보고 [위반 감지] 참고).
"""
import json
import os
import re
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
QUESTION_MAX_TOKENS = 500
JUDGE_TEMPERATURE = 0.1
JUDGE_MAX_TOKENS = 10

# OpenRouter 무료 티어는 분당 20회 제한이 있다. 8문항을 연속으로 쏘면 429가 터져
# "0점 처리"가 모델 능력 실패와 구분되지 않는다. 문항 간 간격을 두고, 429는
# Retry-After(또는 백오프)를 존중해 재시도한 뒤에도 실패하면 0점 처리한다.
RATE_GAP_SEC = 4
HTTP_429_RETRIES = 3
REASONING_RETRY_TOKENS = 2000  # reasoning만으로 끝나 잘린 문항의 재시도 예산
ANSWER_STORE_CHARS = 1000  # 채점관과 블로그가 볼 상세 답변 보관 길이

# 평가 결과 캐시. 브리핑(09:00)과 블로그(09:30)가 같은 모델을 평가하면
# OpenRouter 무료 티어 20req/min에 두 번 걸리고 결과가 어긋난다.
# 파일 하나면 충분하다 — 캐시 DB는 과하다.
CACHE_PATH = os.path.join(PROJECT_DIR, "scripts", "logs", "model_eval_cache.json")
CACHE_TTL_HOURS = 20  # 하루 브리핑 안에서는 재평가 금지

# (2026-10-11 대표님 실제 평가 기준)
# ponytail: 아래 평가 재료(기술 문서 2건)는 세션 상수로 둔다. 파일/DB로 뺄 이유가 없음.
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

# 멀티턴 맥락 유지 테스트용 사전 대화 (Q4가 "위 대화"를 참조하므로 실제로 넣어줘야 한다)
PRIOR_TURNS = [
    {"role": "user", "content": "파이썬을 처음 시작하려면 뭘부터 해야 해?"},
    {"role": "assistant", "content": "먼저 파이썬 공식 사이트에서 설치 프로그램을 받으신 뒤, 터미널에서 python --version으로 설치를 확인하세요."},
    {"role": "user", "content": "변수 이름 지을 때 규칙 3개만 알려줘."},
    {"role": "assistant", "content": "첫째, 의미를 분명히 나타내는 이름을 씁니다. 둘째, 밑줄이 아니라 카멜케이스를 씁니다. 셋째, 한 글자 이름은 피합니다."},
    {"role": "user", "content": "프로그램이 안 돌아갈 때 처음에 할 일은?"},
    {"role": "assistant", "content": "에러 메시지를 끝까지 읽고, 문제를 최소 재현 코드로 줄여 본 뒤, 변수 값을 하나씩 출력해 확인하세요."},
]

# ponytail: 평가 재료는 프롬프트 길이를 키우지 않기 위해 상수로 둔다.
TEST_QUESTIONS = [
    {
        "cat": "코딩",
        "q": "Write a Python function that reads a CSV file and returns the average of a column named 'price'. Only the code.",
        "expected": "CSV를 읽고 'price' 컬럼의 평균값을 반환하는 파이썬 함수. csv 모듈 또는 pandas를 사용",
    },
    {
        "cat": "코딩",
        "q": "이 코드의 버그를 찾아 고쳐줘: `def add(a, b) return a + b` — 고친 코드만 출력.",
        "expected": "return 앞에 콜론이 빠진 것이 버그. def add(a, b): return a + b 로 고친 코드",
    },
    {
        "cat": "맥락정리",
        "q": f"다음 내용을 3줄로 요약해줘:\n{_DOC_500}",
        "expected": "RAG는 검색 단계를 앞단에 붙여 답변 정확도를 높이는 방식이며, 질문 벡터로 관련 문서를 찾아 프롬프트에 넣고, 청크 자르기나 검색 정확도가 낮으면 그럴듯한 오답을 만들므로 청크 크기와 검색 개수 튜닝이 핵심이라는 요약",
    },
    {
        "cat": "맥락정리",
        "q": "위 대화에서 내가 요청한 3가지 작업을 나열해줘.",
        "expected": "파이썬 설치 방법, 변수 이름 짓는 규칙 3가지, 프로그램이 안 돌아갈 때 처음 할 일",
        "seed": PRIOR_TURNS,
    },
    {
        "cat": "압축",
        "q": f"이 글을 200자로 줄여줘. 핵심 정보는 유지해야 해.\n{_DOC_1000}",
        "expected": "LLM 서비스 비용 줄이는 방법(캐시, 모델 크기 분할, 검색 문자 축소, 대화 슬라이스) 중 하나 이상을 축약하되 핵심은 유지한 요약",
    },
    {
        "cat": "한국어",
        "q": "이 Python 코드를 한국어로 설명해줘: `def add(a, b): return a + b`",
        "expected": "두 값을 받아 더한 값을 돌려주는 파이썬 함수에 대한 한국어 설명",
    },
    {
        "cat": "한국어",
        "q": "다음을 정중한 비즈니스 이메일로 바꿔줘: '회의 시간 바꿔줘'",
        "expected": "'회의 시간을 변경해 주시면 감사하겠습니다' 처럼 존댓말과 정중한 비즈니스 어조로 바꾼 이메일 문장",
    },
    {
        "cat": "한국어",
        "q": "'인공지능'을 영어로 번역하세요.",
        "expected": "Artificial Intelligence (또는 AI)",
    },
    {
        "cat": "추론",
        "q": "If all Bloops are Razzies and all Razzies are Lazzies, are all Bloops Lazzies? Answer yes or no only.",
        "expected": "yes",
    },
]

TIERS = [
    (9, "Claude Opus급"),
    (7, "Claude Sonnet 4.5급"),
    (5, "GPT-4o mini급"),
    (3, "입문용 (기본 작업 가능)"),
    (0, "티어 미확인 (응답 불안정)"),
]

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
    """TTL 안의 캐시 결과. 없으면 None."""
    entry = cache_load().get(model_id)
    if not entry or not entry.get("details"):
        return None
    age_h = (time.time() - entry.get("ts", 0)) / 3600
    if age_h > CACHE_TTL_HOURS:
        return None
    return entry


def cache_put(model_id, result):
    """평가 결과 저장. 실패해도 조용히 넘긴다(캐시가 본 작업을 막지 않음).

    응답 실패가 절반을 넘으면 캐시하지 않는다. 레이트리밋에 의한
    전멸 판정이 20시간 캐시에 박히면 내일 브리핑이 그걸 advertise한다.
    """
    if result.get("failed", 0) * 2 > result.get("max_score", 9):
        log(f"캐시 저장 생략 (응답 실패 {result['failed']}/{result['max_score']} — 전멸 판정)")
        return
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        data = cache_load()
        entry = dict(result)
        entry["ts"] = time.time()
        data[model_id] = entry
        tmp = CACHE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CACHE_PATH)  # 원자적
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


def score_to_tier(score):
    """0~N점 → 능력 티어 라벨 (N = 문항 수, 지시서 2026-10-11 규칙)"""
    score = max(0, min(len(TEST_QUESTIONS), int(score)))
    for threshold, label in TIERS:
        if score >= threshold:
            return label
    return TIERS[-1][1]


def score_response(question, expected, actual):
    """무료 LLM 폴백 체인을 판관으로 사용해 1/0 채점. 판독 불가 시 0점."""
    if not actual or not actual.strip():
        return 0
    from model_router import chat_completion

    verdict = chat_completion(
        messages=[
            {
                "role": "user",
                "content": (
                    f"문제: {question}\n정답: {expected}\n학생 답안: {actual}\n\n"
                    "위 답안이 정답과 의미적으로 일치하면 '1', 아니면 '0'으로만 답하세요."
                ),
            }
        ],
        system_prompt="당신은 엄격한 시험 채점관입니다.",
        temperature=JUDGE_TEMPERATURE,
        max_tokens=JUDGE_MAX_TOKENS,
        model_override=None,  # 무료 폴백 체인만
    )
    if not verdict:
        log(f"  채점 실패(응답 없음) → 0점: {question[:40]}")
        return 0
    m = re.search(r"[01]", verdict)
    if not m:
        log(f"  채점 파싱 실패({verdict[:30]!r}) → 0점: {question[:40]}")
        return 0
    return int(m.group(0))


def eval_model(model_id, with_judge=True):
    """표준 9문항 평가. 반환 dict가 eval_model 결과의 전부.

    실패(429·타임아웃·빈 응답)는 해당 문항 0점으로 처리하고 계속 진행한다.
    예외를 던지지 않는다 — 브리핑을 깨뜨리지 않기 위함.
    """
    result = {
        "model_id": model_id,
        "score": 0,
        "max_score": len(TEST_QUESTIONS),
        "tier": score_to_tier(0),
        "details": [],
        "errors": [],
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

    total = len(TEST_QUESTIONS)
    for idx, spec in enumerate(TEST_QUESTIONS, 1):
        cat, question, expected = spec["cat"], spec["q"], spec["expected"]
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
        resp, warns = _post_question(headers, payload)
        for w in warns:
            result["errors"].append(f"Q{idx} {w}")
        if resp is None:
            result["errors"].append(f"Q{idx} 호출 실패(예외)")
            log(f"  [{idx}/{total}] {cat} 호출 예외 → 0점")
            result["details"].append({"idx": idx, "cat": cat, "score": 0, "source": "exception"})
            continue
        if resp.status_code != 200:
            result["errors"].append(f"Q{idx} HTTP {resp.status_code}")
            log(f"  [{idx}/{total}] {cat} HTTP {resp.status_code} → 0점")
            result["details"].append({"idx": idx, "cat": cat, "score": 0, "source": "http_error"})
            continue
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            result["errors"].append(f"Q{idx} choices 비어있음")
            result["details"].append({"idx": idx, "cat": cat, "score": 0, "source": "no_choices"})
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
                rmsg = ((rresp.json().get("choices") or [{}])[0].get("message")) or {}
                ractual, rsource = _extract_answer(rmsg)
                if ractual:
                    actual, source = ractual, rsource
                    result["errors"].append(f"Q{idx} reasoning 잘림 → max_tokens={REASONING_RETRY_TOKENS} 재시도로 회수")
                    log(f"  [{idx}/{total}] {cat} reasoning 잘림 → {REASONING_RETRY_TOKENS}토큰 재시도로 회수 (via {source})")
        elif finish == "length":
            result["errors"].append(f"Q{idx} finish_reason=length(잘림 가능)")
            log(f"  [{idx}/{total}] {cat} finish_reason=length — max_tokens 부족 경고")

        if not actual:
            result["errors"].append(f"Q{idx} 빈 응답")
            result["details"].append({"idx": idx, "cat": cat, "score": 0, "source": "empty"})
            log(f"  [{idx}/{total}] {cat} 빈 응답 → 0점")
            continue

        pts = score_response(judge_q, expected, actual) if with_judge else (1 if actual.strip() else 0)
        result["score"] += pts
        # 상세 답변은 블로그 심층 분석에 그대로 인용된다. 잘라내지 말고 원문을 쓴다.
        result["details"].append({"idx": idx, "cat": cat, "score": pts, "source": source, "answer": actual[:ANSWER_STORE_CHARS]})
        log(f"  [{idx}/{total}] {cat} {pts}점 (via {source}) ← {actual[:60]!r}")

    result["tier"] = score_to_tier(result["score"])
    result["failed"] = sum(
        1 for d in result["details"] if d["source"] in ("http_error", "exception", "empty", "no_choices")
    )
    # 429·타임아웃은 모델 능력 실패가 아니다. 분모에서 빼야 한다.
    # 단, 시도한 문항이 5개 미만이면 "모르겠다"가 정직한 답이다.
    scored = result["max_score"] - result["failed"]
    if scored >= 5:
        result["label"] = (
            f"AI 추정: {result['tier']} ({result['score']}/{scored}점"
            + (f", {result['failed']}문항 응답 실패 제외" if result["failed"] else "")
            + ")"
        )
    else:
        result["tier"] = "티어 미확인 (응답 실패 과다)"
        result["label"] = f"AI 추정: {result['tier']} ({result['score']}/{scored}점)"
    if result["failed"]:
        log(
            f"  ⚠️ 응답 실패 {result['failed']}/{result['max_score']}문항 — "
            f"분모에서 제외했다 (능력 실패 아님)"
        )
    return result


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

    news_collector_v2가 link를 `https://openrouter.ai/{id}`(':free' 접미사 제거)로
    넣으므로 link를 우선 사용하고, 없으면 제목의 `[무료 LLM] {id}:free` 패턴으로 폴백.
    """
    link = article.get("link") or ""
    m = re.search(r"openrouter\.ai/([^?#\s]+)", link)
    if m:
        mid = m.group(1).rstrip("/")
        return mid if ":" in mid else mid + ":free"
    m = re.search(r"\[무료 (?:LLM|모델)\]\s*([\w\-./]+:free)", article.get("title") or "")
    return m.group(1) if m else None


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
    lines = [f"[{model_id}] — {r['label']}"]
    if deep_dive_url:
        lines.append(f"👉 자세한 분석: {deep_dive_url}")
    lines.append(f"📍 {guide}")
    return "\n".join(lines)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "liquid/lfm-2.5-2.6b:free"
    log(f"평가 시작: {target}")
    r = eval_model_cached(target, force="--force" in sys.argv)
    log(f"결과: {r['label']} (실패 {r.get('failed', 0)}/{r['max_score']}문항)")
    for d in r["details"]:
        log(f"  Q{d['idx']}[{d['cat']}] {d['score']}점 src={d['source']}")
    if r["errors"]:
        log(f"  경고 {len(r['errors'])}건: {r['errors'][:5]}")
    log(f"접근법: {get_access_guide(target)}")
    print()
    print("--- 브리핑 코멘트 블록 ---")
    print(eval_comment_block(target, result=r))