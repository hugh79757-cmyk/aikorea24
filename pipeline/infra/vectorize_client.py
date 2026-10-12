"""
Vectorize REST API 클라이언트
- Cloudflare Vectorize v2 REST API 사용
- 임베딩은 순수 회전 체인(skill: llm-fallback-chain-management)으로 생성
- 모든 티어가 실패한 경우에만 None 반환 (파이프라인 차단 안 함)
"""
import json
import os
import time
from typing import Optional

import requests

from pipeline.infra.config import project_root

INDEX_NAME = "aikorea24-dedup"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536
SIMILARITY_THRESHOLD = 0.60
BATCH_SIZE = 10
MAX_RETRIES = 2
TTL_HOURS = 24


def _get_cf_credentials():
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    return account_id, api_token


def _cf_base_url():
    account_id, _ = _get_cf_credentials()
    return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/vectorize/v2/indexes/{INDEX_NAME}"


# =====================================================================
# 임베딩 순수 회전 큐 (llm-fallback-chain-management 계약)
#
# 왜 두 티어가 같은 모델인가: aikorea24-dedup 인덱스에 이미 OpenAI
# text-embedding-3-small 벡터 435개(1536차원, cosine)가 들어 있다.
# Cohere(embed-v4.0)·Gemini(gemini-embedding-001)도 1536차원을 내지만
# **벡터 공간이 다르므로** 같은 인덱스에 섞으면 유사도 검색이 무의미해진다.
# 그래서 OpenRouter를 경유 티어로 쓴다 — 동일 모델이라 공간이 완전히 같다.
#
# 금지(스킬): cooldown / sleep 기반 대기 / quota_until / blocked /
# 티어 영구 제외. 실패는 회전 신호일 뿐이다.
EMBEDDING_TIER_TIMEOUT_SEC = 30.0   # 티어 1회 호출 상한
EMBEDDING_CHAIN_BUDGET_SEC = 90.0   # 체인 1패스 전체 상한 (티어를 게이트하지 않음)
EMBEDDING_TIER_RETRY_5XX = 1        # 5xx/connection reset 만 1회 5초 재시도
EMBEDDING_TIER_RETRY_DELAY = 5

# (티어명, url, 모델, 키 환경변수)
EMBEDDING_TIERS = [
    ("openai", "https://api.openai.com/v1/embeddings",
     EMBEDDING_MODEL, "OPENAI_API_KEY"),
    ("openrouter", "https://openrouter.ai/api/v1/embeddings",
     "openai/text-embedding-3-small", "OPENROUTER_API_KEY"),
]
DEFAULT_EMBEDDING_TIER = EMBEDDING_TIERS[-1][0]

_ROTATION_STATE_PATH = os.path.join(
    project_root(), "pipeline", "infra", ".embedding_rotation.json")


def _rotation_state_path() -> str:
    return os.environ.get("EMBEDDING_ROTATION_STATE_PATH", _ROTATION_STATE_PATH)


def _load_tier_order() -> list[str]:
    """front(마지막 성공 티어)를 맨 앞에 두고 전체 티어를 순환 순서로 반환."""
    names = [t[0] for t in EMBEDDING_TIERS]
    front = DEFAULT_EMBEDDING_TIER
    try:
        with open(_rotation_state_path(), "r", encoding="utf-8") as f:
            saved = json.load(f).get("front")
        if saved in names:
            front = saved
    except Exception:
        pass
    return [front] + [n for n in names if n != front]


def _persist_tier_success(name: str) -> None:
    """os.replace 원자적 기록 — launchd가 매회 새 프로세스를 띄우므로 필수."""
    try:
        path = _rotation_state_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"front": name}, f)
        os.replace(tmp, path)
    except Exception:
        pass


def _embed_once(url: str, model: str, key: str, text: str) -> list[float]:
    """단일 티어 1회 호출. 실패는 예외로 알린다(회전 판단은 호출부)."""
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"input": text[:8000], "model": model, "dimensions": EMBEDDING_DIMS},
        timeout=EMBEDDING_TIER_TIMEOUT_SEC,
    )
    # 200 + 과금/에러 본문도 실패로 본다(JSON 게이트). data 키가 없으면 KeyError.
    data = r.json()
    vec = data["data"][0]["embedding"]
    if not isinstance(vec, list) or len(vec) != EMBEDDING_DIMS:
        raise ValueError(f"차원 불일치: {len(vec) if isinstance(vec, list) else '?'}")
    return vec


def get_embedding(text: str) -> Optional[list[float]]:
    """순수 회전 체인. 성공 → front 기록, 실패(429 포함) → 즉시 다음 티어.
    모든 티어가 실패한 경우에만 None. 어떤 티어도 제외·대기시키지 않는다."""
    by_name = {t[0]: t for t in EMBEDDING_TIERS}
    started = time.monotonic()
    for name in _load_tier_order():
        if time.monotonic() - started > EMBEDDING_CHAIN_BUDGET_SEC:
            print("  [embedding] 체인 예산 소진 — 남은 티어 미시도")
            return None
        _, url, model, key_env = by_name[name]
        key = os.environ.get(key_env, "")
        if not key:
            continue  # 키 자체가 없는 티어 = config에 없는 것과 동일
        for attempt in range(EMBEDDING_TIER_RETRY_5XX + 1):
            try:
                vec = _embed_once(url, model, key, text)
                _persist_tier_success(name)
                return vec
            except requests.exceptions.ConnectionError:
                err, retryable = "connection", True
            except requests.exceptions.Timeout:
                err, retryable = "timeout", False
            except requests.exceptions.RequestException as e:
                code = getattr(getattr(e, "response", None), "status_code", None)
                err, retryable = f"http {code}", code in (500, 502, 503, 504)
            except Exception as e:
                err, retryable = type(e).__name__, False
            # 429/401/403/404/410/과금본문/빈 응답 → 재시도 0회, 즉시 회전
            if attempt < EMBEDDING_TIER_RETRY_5XX and retryable:
                time.sleep(EMBEDDING_TIER_RETRY_DELAY)
                continue
            print(f"  [embedding] {name} 실패 ({err}) → 다음 티어")
            break
    return None


def _cf_headers():
    _, api_token = _get_cf_credentials()
    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }


def _request_with_retry(method, url, **kwargs):
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            if method == "POST":
                r = requests.post(url, **kwargs)
            elif method == "DELETE":
                r = requests.delete(url, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
            data = r.json()
            if data.get("success"):
                return data
            last_error = f"API error: {data.get('errors')}"
        except Exception as e:
            last_error = str(e)
        if attempt < MAX_RETRIES - 1:
            time.sleep(1.0 * (2.0 ** attempt))
    return None


def upsert_vectors(vectors: list[dict]) -> bool:
    account_id, api_token = _get_cf_credentials()
    if not account_id or not api_token:
        return False
    url = f"{_cf_base_url()}/upsert"
    for i in range(0, len(vectors), BATCH_SIZE):
        batch = vectors[i:i + BATCH_SIZE]
        result = _request_with_retry(
            "POST", url,
            headers=_cf_headers(),
            json={"vectors": batch},
            timeout=30,
        )
        if result is None:
            return False
    return True


def query_vectors(
    vector: list[float],
    top_k: int = 5,
    filter_dict: Optional[dict] = None,
) -> Optional[list[dict]]:
    account_id, api_token = _get_cf_credentials()
    if not account_id or not api_token:
        return None
    url = f"{_cf_base_url()}/query"
    body = {"vector": vector, "topK": top_k}
    if filter_dict:
        body["filter"] = filter_dict
    result = _request_with_retry(
        "POST", url,
        headers=_cf_headers(),
        json=body,
        timeout=10,
    )
    if result is None:
        return None
    return result.get("result", {}).get("matches", [])


def delete_vectors(ids: list[str]) -> bool:
    account_id, api_token = _get_cf_credentials()
    if not account_id or not api_token:
        return False
    url = f"{_cf_base_url()}/delete"
    result = _request_with_retry(
        "POST", url,
        headers=_cf_headers(),
        json={"ids": ids},
        timeout=10,
    )
    return result is not None


def embed_article(article: dict) -> Optional[dict]:
    parts = []
    if article.get("original_title"):
        parts.append(article["original_title"])
    if article.get("title"):
        parts.append(article["title"])
    if article.get("description"):
        parts.append(article["description"])
    text = " ".join(parts)
    if not text.strip():
        return None
    embedding = get_embedding(text)
    if embedding is None:
        return None
    return {
        "id": str(article.get("id", "")),
        "values": embedding,
        "metadata": {
            "title": (article.get("title") or "")[:200],
            "original_title": (article.get("original_title") or "")[:200],
        },
    }


def is_duplicate_with_vectorize(article: dict) -> bool:
    embedding = get_embedding(
        f"{article.get('original_title', '')} {article.get('title', '')} {article.get('description', '')}"
    )
    if embedding is None:
        return False
    matches = query_vectors(embedding, top_k=5)
    if not matches:
        return False
    for match in matches:
        score = match.get("score", 0)
        match_id = match.get("id", "")
        if score >= SIMILARITY_THRESHOLD and match_id != str(article.get("id", "")):
            return True
    return False
