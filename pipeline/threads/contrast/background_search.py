"""pipeline/threads/contrast/background_search.py — D1 LIKE + Vectorize fallback."""
from pipeline.infra.d1_client import d1_query
from pipeline.infra.logger import get_scrubbed_logger

logger = get_scrubbed_logger(__name__)


def _esc(s: str) -> str:
    return s.replace("'", "''")


def find_background(keywords: list[str], exclude_id: str | list[str] | tuple[str, ...] | set[str] | None) -> dict | None:
    """Search D1 LIKE for background article (30 days), fallback to Vectorize."""
    if not keywords:
        return None
    # normalize exclude_id: accept str or list/tuple/set (backward compat)
    kws = [(k or "").strip() for k in keywords]
    kws = [k for k in kws if k]
    if not kws:
        return None
    if isinstance(exclude_id, (list, tuple, set)):
        exclude_ids = {str(x).strip() for x in exclude_id if str(x).strip()}
    elif exclude_id is None:
        exclude_ids = set()
    else:
        eid_single = str(exclude_id).strip()
        exclude_ids = {eid_single} if eid_single else set()
    if len(exclude_ids) == 1:
        eid = _esc(next(iter(exclude_ids)))
        exclude_clause = f"AND id != '{eid}' "
    elif len(exclude_ids) > 1:
        ids_sql = ",".join(f"'{_esc(x)}'" for x in exclude_ids)
        exclude_clause = f"AND id NOT IN ({ids_sql}) "
    else:
        exclude_clause = ""
    like_parts = []
    for k in kws:
        ek = _esc(k)
        like_parts.append(f"(title LIKE '%{ek}%' OR description LIKE '%{ek}%')")
    like_clause = " OR ".join(like_parts)
    sql = (
        "SELECT id,title,description,link,pub_date,source FROM news "
        f"WHERE ({like_clause}) "
        f"{exclude_clause}"
        "AND pub_date >= date('now','-7 days') "
        "ORDER BY pub_date DESC LIMIT 1"
    )
    try:
        rows = d1_query(sql)
    except Exception as e:
        logger.warning("find_background d1_query error kws=%s: %s", kws, e)
        rows = None
    if rows:
        logger.info("find_background hit kws=%s id=%s", kws, rows[0].get("id"))
        return rows[0]

    # Vectorize fallback — lazy import, graceful
    try:
        # try `query` first (research name), then `query_vectors`
        try:
            from pipeline.infra.vectorize_client import query as vquery  # type: ignore
        except ImportError:
            from pipeline.infra.vectorize_client import query_vectors as vquery  # type: ignore

        # vectorize expects embedding workflow; attempt direct query with keyword
        # If vquery needs vector, this will fail gracefully and return None
        try:
            res = vquery(keywords[0], top_k=1)  # type: ignore
        except TypeError:
            # query_vectors(vector, top_k) signature — can't call with string
            # try get_embedding + query_vectors path
            from pipeline.infra.vectorize_client import get_embedding, query_vectors
            emb = get_embedding(keywords[0])
            if emb is None:
                return None
            res = query_vectors(emb, top_k=1)

        if res:
            first = res[0] if isinstance(res, list) else res
            # adapt vectorize match to news dict shape if needed
            if isinstance(first, dict) and "id" in first:
                return first
            # vectorize match has id/score/metadata
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
    """Find up to limit cross articles via D1 LIKE (description reuse, no crawl).

    Collect up to limit distinct ids/sources across keywords (same-event).
    """
    seed_id = str(seed_id).strip()
    if not keywords or limit <= 0:
        return []
    seen_ids: set[str] = {seed_id} if seed_id else set()
    seen_sources: set[str] = set()
    out: list[dict] = []
    kws = [(k or "").strip() for k in keywords]
    kws = [k for k in kws if k]
    if not kws:
        return []
    like_parts = []
    for k in kws:
        ek = _esc(k)
        like_parts.append(f"(title LIKE '%{ek}%' OR description LIKE '%{ek}%')")
    eid = _esc(seed_id)
    sql = (
        "SELECT id,title,description,link,pub_date,source FROM news "
        f"WHERE ({' OR '.join(like_parts)}) "
        f"AND id != '{eid}' "
        "AND pub_date >= date('now','-7 days') "
        "ORDER BY pub_date DESC LIMIT 5"
    )
    try:
        rows = d1_query(sql)
    except Exception as e:
        logger.warning("find_cross d1_query error: %s", e)
        return []
    if rows:
        for r in rows:
            if len(out) >= limit:
                break
            rid = str(r.get("id") or "").strip()
            if not rid or rid in seen_ids:
                continue
            src = str(r.get("source") or "").strip()
            # distinct source filter (allow empty source once)
            if src and src in seen_sources:
                continue
            seen_ids.add(rid)
            if src:
                seen_sources.add(src)
            out.append(r)
        logger.info("find_cross hit %d/%d kws=%s", len(out), limit, kws)
    return out[:limit]
