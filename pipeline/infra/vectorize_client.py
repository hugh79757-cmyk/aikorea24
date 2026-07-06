"""
Vectorize REST API 클라이언트
- Cloudflare Vectorize v2 REST API 사용
- OpenAI text-embedding-3-small으로 임베딩 생성
- 실패 시 None 반환 (파이프라인 차단 안 함)
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
SIMILARITY_THRESHOLD = 0.85
BATCH_SIZE = 10
MAX_RETRIES = 2
TTL_HOURS = 24


def _get_cf_credentials():
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    return account_id, api_token


def _get_openai_key():
    return os.environ.get("OPENAI_API_KEY", "")


def _cf_base_url():
    account_id, _ = _get_cf_credentials()
    return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/vectorize/v2/indexes/{INDEX_NAME}"


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


def get_embedding(text: str) -> Optional[list[float]]:
    api_key = _get_openai_key()
    if not api_key:
        return None
    try:
        r = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "input": text[:8000],
                "model": EMBEDDING_MODEL,
                "dimensions": EMBEDDING_DIMS,
            },
            timeout=30,
        )
        data = r.json()
        return data["data"][0]["embedding"]
    except Exception:
        return None


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
