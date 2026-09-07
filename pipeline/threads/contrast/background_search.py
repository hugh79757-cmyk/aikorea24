"""pipeline/threads/contrast/background_search.py — 30일 풀 1회 로드 + Python 키워드 매칭 + Vectorize fallback.

기존: 키워드당 `LIKE '%kw%'` 풀스캔 (23k rows × ~28회/일 = 99.5만 rows/일).
변경: pub_date 인덱스로 30일 풀 1회 조회(~3k rows, TTL 5분) 후 메모리 매칭.
side effect: SQL에 키워드 문자열이 안 들어가므로 "LIKE pattern too complex [7500]" 에러 계열 소멸.
"""
import time

from pipeline.infra.d1_client import d1_query
from pipeline.infra.logger import get_scrubbed_logger

logger = get_scrubbed_logger(__name__)

# ponytail: 모듈 캐시 5분 — 대조 파이프라인 1회 실행 수십 초 내 종료라 신규 기사 지연 허용.
# 오염 우려 시 _reset_pool_cache() 후 재호출.
_POOL_TTL = 300.0
_pool_cache: list[dict] | None = None
_pool_ts: float = 0.0

_POOL_SQL = (
    "SELECT id,title,description,link,pub_date,source FROM news "
    "WHERE pub_date >= date('now','-30 days') "
    "ORDER BY pub_date DESC"
)


def _esc(s: str) -> str:
    """SQL escape — 하위호환 유지(기존 import 방지용). 새 코드 미사용."""
    return s.replace("'", "''")


def _reset_pool_cache() -> None:
    global _pool_cache, _pool_ts
    _pool_cache = None
    _pool_ts = 0.0


def _get_pool() -> list[dict]:
    """최근 30일 news 풀 (pub_date DESC). TTL 5분 캐시."""
    global _pool_cache, _pool_ts
    now = time.time()
    if _pool_cache is not None and now - _pool_ts < _POOL_TTL:
        return _pool_cache
    try:
        rows = d1_query(_POOL_SQL)
    except Exception as e:
        logger.warning("background pool fetch error: %s", e)
        rows = []
    _pool_cache = rows or []
    _pool_ts = now
    return _pool_cache


def _match(r: dict, kw_l: str) -> bool:
    return kw_l in str(r.get("title") or "").lower() or kw_l in str(r.get("description") or "").lower()


def find_background(keywords: list[str], exclude_id: str | list[str] | tuple[str, ...] | set[str] | None) -> dict | None:
    """최근 30일 풀에서 배경 기사 검색 (Python 매칭), fallback to Vectorize."""
    if not keywords:
        return None
    if isinstance(exclude_id, (list, tuple, set)):
        exclude_ids = {str(x).strip() for x in exclude_id if str(x).strip()}
    elif exclude_id is None:
        exclude_ids = set()
    else:
        eid_single = str(exclude_id).strip()
        exclude_ids = {eid_single} if eid_single else set()

    pool = _get_pool()
    for kw in keywords:
        kw = (kw or "").strip()
        if not kw:
            continue
        kw_l = kw.lower()
        for r in pool:  # pub_date DESC 정렬 → 첫 매치 = 최신
            if str(r.get("id") or "") in exclude_ids:
                continue
            if _match(r, kw_l):
                logger.info("find_background hit kw=%s id=%s", kw, r.get("id"))
                return r

    # Vectorize fallback — lazy import, graceful
    try:
        try:
            from pipeline.infra.vectorize_client import query as vquery  # type: ignore
        except ImportError:
            from pipeline.infra.vectorize_client import query_vectors as vquery  # type: ignore

        try:
            res = vquery(keywords[0], top_k=1)  # type: ignore
        except TypeError:
            from pipeline.infra.vectorize_client import get_embedding, query_vectors
            emb = get_embedding(keywords[0])
            if emb is None:
                return None
            res = query_vectors(emb, top_k=1)

        if res:
            first = res[0] if isinstance(res, list) else res
            if isinstance(first, dict) and "id" in first:
                return first
            if isinstance(first, dict) and "metadata" in first:
                meta = first.get("metadata", {})
                return {
                    "id": str(first.get("id", "")),
                    "title": meta.get("title", ""),
                    "description": meta.get("original_title", ""),
                    "link": "",
                    "pub_date": "",
                    "source": "",
                }
    except Exception as e:
        logger.info("find_background vectorize fallback fail: %s", e)

    logger.info("find_background no hit -> None (graceful)")
    return None


def find_cross_articles(seed_id: str, keywords: list[str], limit: int = 3) -> list[dict]:
    """최근 30일 풀에서 크로스 기사 최대 limit개 (동일 사건, 소스 중복 제거)."""
    seed_id = str(seed_id or "").strip()
    if not keywords or limit <= 0:
        return []
    pool = _get_pool()
    seen_ids: set[str] = {seed_id} if seed_id else set()
    seen_sources: set[str] = set()
    out: list[dict] = []
    for kw in keywords:
        if len(out) >= limit:
            break
        kw = (kw or "").strip()
        if not kw:
            continue
        kw_l = kw.lower()
        hits = 0
        for r in pool:
            if hits >= 5:  # 원래 키워드당 LIMIT 5와 동일 상한
                break
            rid = str(r.get("id") or "").strip()
            if not rid or rid in seen_ids:
                continue
            if _match(r, kw_l):
                hits += 1
                src = str(r.get("source") or "").strip()
                if src and src in seen_sources:
                    continue
                seen_ids.add(rid)
                if src:
                    seen_sources.add(src)
                out.append(r)
                if len(out) >= limit:
                    break
        logger.info("find_cross hit %d/3 kw=%s", len(out), kw)
    return out[:limit]
