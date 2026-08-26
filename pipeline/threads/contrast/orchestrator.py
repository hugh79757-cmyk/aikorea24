"""pipeline/threads/contrast/orchestrator.py — glue: extractor→background→writer→validator→save."""
import re
from pipeline.infra.logger import get_scrubbed_logger

logger = get_scrubbed_logger(__name__)


def run_contrast_thread(seed_article: dict, all_articles: list | None = None) -> dict | None:
    """End-to-end contrast pipeline for one seed article.

    Returns {"cards":[...5], "link":url} or None on any drop.
    Never calls publisher.publish — dry-run only.
    """
    try:
        if not seed_article or not isinstance(seed_article, dict):
            logger.info("contrast orchestrator: empty seed -> drop")
            return None

        seed_id = str(seed_article.get("id", "")).strip()
        title = seed_article.get("title", "") or ""
        link = seed_article.get("link", "") or seed_article.get("url", "") or ""

        # 1. body extraction: crawled_body > fetch_article_body(link) > description
        body = (seed_article.get("crawled_body") or seed_article.get("body") or "").strip() if isinstance(seed_article.get("crawled_body") or seed_article.get("body"), str) else ""
        # fallback handling above misses description; redo cleanly
        body = ""
        for key in ("crawled_body", "body"):
            v = seed_article.get(key)
            if isinstance(v, str) and v.strip():
                body = v.strip()
                break
        if not body:
            # try fetch_article_body for seed only
            if link:
                try:
                    from pipeline.threads.crawler import fetch_article_body
                    fetched = fetch_article_body(link, source=seed_article.get("source", ""), title=title)
                    if fetched and fetched.strip():
                        body = fetched.strip()
                except Exception as e:
                    logger.info("contrast orchestrator: fetch_article_body fail: %s", e)
            if not body:
                desc = seed_article.get("description") or ""
                if isinstance(desc, str) and desc.strip():
                    body = desc.strip()

        if not body or not body.strip():
            logger.info("contrast orchestrator: no body -> drop seed_id=%s", seed_id)
            return None

        # 2. extractor
        try:
            from pipeline.threads.contrast.extractor import extract_af
        except Exception as e:
            logger.warning("contrast orchestrator: extractor import fail: %s", e)
            return None

        af = extract_af(body, title)
        if not af:
            logger.info("contrast orchestrator: extractor_fail seed_id=%s -> drop", seed_id)
            return None

        # 3. background + cross — 5-step: cross up to 3 with crawl, D+E background
        e_keywords = af.get("E", []) if isinstance(af.get("E"), list) else []
        e_keywords = [str(k).strip() for k in e_keywords if str(k).strip()]
        d_topic = str(af.get("D", "")).strip() if isinstance(af.get("D"), str) else ""
        # D is a sentence like "물리적 AI 시장..." -> extract 2-3 keywords for LIKE
        bg_keywords = []
        if d_topic:
            # split D into meaningful 2-4 char nouns, filter stopwords
            for w in re.findall(r'[가-힣A-Za-z0-9]{2,10}', d_topic):
                if w not in ("그리고","하지만","대한","위한","통한","있는","없는","같은") and len(w)>=2:
                    if w not in bg_keywords and w not in e_keywords:
                        bg_keywords.append(w)
                    if len(bg_keywords)>=3:
                        break
            bg_keywords = bg_keywords + e_keywords
            # keep D sentence as first keyword for exact match attempt, then token keywords
            bg_keywords = [d_topic] + bg_keywords
        else:
            bg_keywords = e_keywords

        background = None
        cross_articles: list[dict] = []
        try:
            from pipeline.threads.contrast.background_search import find_background, find_cross_articles
            if e_keywords:
                try:
                    cross_articles = find_cross_articles(seed_id, e_keywords, 3) or []
                except Exception as e:
                    logger.info("contrast orchestrator: find_cross error: %s", e)
                    cross_articles = []
                # crawl cross bodies
                if cross_articles:
                    try:
                        from pipeline.threads.crawler import fetch_article_body as _fetch
                        crawled = 0
                        for art in cross_articles:
                            link_c = art.get("link") or art.get("url") or ""
                            if not link_c:
                                continue
                            try:
                                b = _fetch(link_c, source=art.get("source", ""), title=art.get("title", ""))
                                if b and b.strip():
                                    art["crawled_body"] = b.strip()
                                    crawled += 1
                            except Exception:
                                pass
                        logger.info("contrast cross crawled %d/%d", crawled, len(cross_articles))
                    except Exception as e:
                        logger.info("contrast orchestrator: cross crawl import fail: %s", e)
            # background: D+E first, exclude seed+cross ids
            if bg_keywords:
                cross_ids = [str(a.get("id", "")).strip() for a in cross_articles if str(a.get("id", "")).strip()]
                exclude_ids = ([seed_id] + cross_ids) if seed_id else cross_ids
                try:
                    background = find_background(bg_keywords, exclude_ids)
                except Exception as e:
                    logger.info("contrast orchestrator: find_background error: %s", e)
                    background = None
        except Exception as e:
            logger.info("contrast orchestrator: background_search import fail: %s", e)

        # search_count
        cross_n = len(cross_articles)
        bg_hit = 1 if background else 0
        bg_attempted = 1 if bg_keywords else 0
        # total = cross hits + bg hit (matches example cross3 bg1 total4); also log attempt variant
        total = cross_n + bg_hit if bg_hit else cross_n + bg_attempted if bg_attempted else cross_n
        # normalize: if bg attempted but miss, total = cross_n + 1 (attempt)
        # if no bg attempt, total = cross_n
        if bg_attempted and not bg_hit:
            total = cross_n + 1
        elif bg_hit:
            total = cross_n + 1
        logger.info("contrast search_count cross=%d bg=%s total=%d", cross_n, "hit" if background else "miss", total)

        # 4. build bundle
        bundle = {
            "seed_article": seed_article,
            "af": af,
            "background": background,
            "cross_articles": cross_articles,
            "search_meta": {"cross": cross_n, "bg": bool(background), "total": total, "bg_hit": bg_hit},
        }

        # 5. writer
        try:
            from pipeline.threads.contrast.contrast_writer import write_contrast_thread
        except Exception as e:
            logger.warning("contrast orchestrator: contrast_writer import fail: %s", e)
            return None

        # all_articles_with_background: include seed + background for validator context if needed
        pool = list(all_articles) if isinstance(all_articles, list) else []
        # ensure seed in pool
        if seed_article not in pool:
            pool = [seed_article] + pool

        result = write_contrast_thread(bundle, pool)
        if not result or not result.get("cards"):
            logger.info("contrast orchestrator: write_contrast_thread drop seed_id=%s", seed_id)
            return None

        cards = result["cards"]
        link_out = result.get("link", "") or link

        # 6. dedup: seed-only (avoid over-filter)
        try:
            from pipeline.threads.pitch import is_duplicate_pitch
            from pipeline.threads.pitch import load_pitch_history
            pitch_stub = {"hook": af.get("A", {}).get("사건명", "") if isinstance(af.get("A"), dict) else str(af.get("A", ""))[:80], "article_ids": [seed_id]}
            # keep hook fallback
            if not pitch_stub["hook"]:
                pitch_stub["hook"] = title[:80] or "대비 스토리텔링"
            history = []
            try:
                history = load_pitch_history()
            except Exception:
                history = []
            # optional check: log if duplicate but do not block (per spec: do not block)
            try:
                dup = is_duplicate_pitch(pitch_stub, history)
                if dup:
                    logger.info("contrast orchestrator: duplicate seed_id=%s detected (not blocking)", seed_id)
            except Exception:
                pass
        except Exception:
            pass

        # 7. save draft → contrast dry-run isolated folder (실발행 drafts와 분리)
        fpath = None
        try:
            from pipeline.threads.writer import save_draft, DRAFTS_DIR
            import os, shutil
            hook = af.get("A", {}).get("사건명", "") if isinstance(af.get("A"), dict) else str(af.get("A", ""))[:80]
            if not hook:
                hook = title[:80] or "대비 스토리텔링"
            pitch_stub_save = {"hook": hook, "article_ids": [seed_id]}
            fpath = save_draft(cards, pitch_stub_save)
            # move to drafts/contrast/ for isolation
            try:
                contrast_dir = os.path.join(DRAFTS_DIR, "contrast")
                os.makedirs(contrast_dir, exist_ok=True)
                if fpath and os.path.exists(fpath) and os.path.dirname(fpath) != contrast_dir:
                    dest = os.path.join(contrast_dir, os.path.basename(fpath))
                    # avoid overwrite
                    if os.path.exists(dest):
                        base, ext = os.path.splitext(dest)
                        dest = f"{base}_{seed_id}{ext}"
                    shutil.move(fpath, dest)
                    fpath = dest
            except Exception as me:
                logger.info("contrast draft move fail: %s", me)
            # header injection
            try:
                meta = bundle.get("search_meta") or {}
                cross_c = meta.get("cross", len(cross_articles))
                bg_b = 1 if meta.get("bg") else 0
                total_c = meta.get("total", cross_c + bg_b)
                header = f"# search: cross {cross_c} bg {bg_b} total {total_c}\n"
                if fpath:
                    import os
                    if os.path.exists(fpath):
                        with open(fpath, "r", encoding="utf-8") as fh:
                            body_txt = fh.read()
                        if not body_txt.startswith("# search:"):
                            with open(fpath, "w", encoding="utf-8") as fh:
                                fh.write(header + body_txt)
                        logger.info("contrast search_count cross=%d bg=%s total=%d (draft header injected)", cross_c, "hit" if bg_b else "miss", total_c)
                    else:
                        logger.info("contrast draft header skip: already has header")
                else:
                    logger.warning("contrast draft header inject: file not found %s", fpath)
            except Exception as e:
                logger.info("contrast draft header inject fail: %s", e)
        except Exception as e:
            logger.warning("contrast orchestrator: save_draft fail: %s", e)
            pass

        return {"cards": cards, "link": link_out, "search_meta": bundle.get("search_meta"), "draft_path": fpath}

    except Exception as e:
        logger.warning("contrast orchestrator: unexpected error: %s: %s", type(e).__name__, e)
        return None
