"""pipeline/threads/contrast/orchestrator.py — glue: extractor→background→writer→validator→save."""
import re
from pipeline.infra.logger import get_scrubbed_logger

logger = get_scrubbed_logger(__name__)


# SPEC Wave5: contrast card-count targets — soft, not hard floors
# - B soft-target: 3+ uncapped B cards; post-filter cut at 6 (keep ≤6 B).
# - C soft-target: 2+ uncapped C cards; post-filter cut at 4 (keep ≤4 C).
# - Straight news (body 1500-2000 chars, distinct_fact_count 4-5 even with
#   max background) → emit 3-4 cards as normal; NOT forced up to 8.
# - Hard minimums (B≥5, C≥3) are NOT introduced. Revisit after rich material
#   yields stable 8-card output.
def run_contrast_thread(seed_article: dict, all_articles: list | None = None,
                        writer_fn=None, writer_kwargs=None) -> dict | None:
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

        pub_date = seed_article.get("pub_date") or seed_article.get("published_at") or ""
        # kicker7 경로는 컬렉션으로 씬소스 구출 → C 가드 완화
        require_c = (writer_fn is None)
        af = extract_af(body, title, pub_date=pub_date if pub_date else None, require_c=require_c)
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

        # Wave4-1: 2차 시도용 키워드 — D(상위 주제) + F(미해결 질문) 토큰
        _STOP = ("그리고", "하지만", "대한", "위한", "통한", "있는", "없는", "같은", "관련", "뉴스", "무엇", "어떻게")

        def _retry_keywords() -> list[str]:
            src = d_topic
            f_list = af.get("F", []) if isinstance(af.get("F"), list) else []
            src += " " + " ".join(str(x) for x in f_list)
            out: list[str] = []
            for w in re.findall(r'[가-힣A-Za-z0-9]{2,10}', src):
                if w in _STOP or w in out or w in e_keywords:
                    continue
                out.append(w)
                if len(out) >= 3:
                    break
            return out

        backgrounds: list[dict] = []
        background = None
        cross_articles: list[dict] = []
        try:
            from pipeline.threads.contrast.background_search import find_background, find_cross_articles

            def _collect_backgrounds(kws: list[str], exclude: list[str], want: int) -> None:
                """find_background는 1건 반환 → 누적 id 제외하며 want개까지 반복."""
                if not kws:
                    return
                for _ in range(want):
                    if len(backgrounds) >= want:
                        break
                    got_ids = [str(b.get("id", "")).strip() for b in backgrounds if str(b.get("id", "")).strip()]
                    try:
                        bg = find_background(kws, exclude + got_ids)
                    except Exception as be:
                        logger.info("contrast orchestrator: find_background error: %s", be)
                        break
                    if not bg:
                        break
                    bid = str(bg.get("id", "")).strip()
                    if bid and bid in got_ids:
                        break
                    backgrounds.append(bg)

            def _merge_cross(new_list: list[dict]) -> None:
                seen = {str(a.get("id", "")).strip() for a in cross_articles}
                for a in new_list:
                    aid = str(a.get("id", "")).strip()
                    if aid and aid in seen:
                        continue
                    seen.add(aid)
                    cross_articles.append(a)

            if e_keywords:
                try:
                    cross_articles = find_cross_articles(seed_id, e_keywords, 5) or []
                except Exception as e:
                    logger.info("contrast orchestrator: find_cross error: %s", e)
                    cross_articles = []
            # background: D+E first, exclude seed+cross ids (목표 2-3건)
            def _bg_exclude() -> list[str]:
                cross_ids = [str(a.get("id", "")).strip() for a in cross_articles if str(a.get("id", "")).strip()]
                return ([seed_id] + cross_ids) if seed_id else cross_ids

            if bg_keywords:
                _collect_backgrounds(bg_keywords, _bg_exclude(), 3)

            # Wave4-1: cross<4 또는 bg<2 → D+F 토큰으로 2차 시도 (재시도 1회만)
            if len(cross_articles) < 4 or len(backgrounds) < 2:
                rk = _retry_keywords()
                logger.info("contrast retry search cross=%d bg=%d keywords=%s", len(cross_articles), len(backgrounds), rk)
                if rk:
                    if len(cross_articles) < 4:
                        try:
                            _merge_cross(find_cross_articles(seed_id, rk, 5) or [])
                        except Exception as e:
                            logger.info("contrast orchestrator: retry find_cross error: %s", e)
                    if len(backgrounds) < 2:
                        _collect_backgrounds(rk, _bg_exclude(), 3)

            # crawl cross bodies (재시도 결과 포함)
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
        except Exception as e:
            logger.info("contrast orchestrator: background_search import fail: %s", e)

        # backward compat: writer는 background 단건 기대 → 첫 건 유지
        background = backgrounds[0] if backgrounds else None

        # search_count
        cross_n = len(cross_articles)
        bg_n = len(backgrounds)
        bg_hit = 1 if background else 0
        bg_attempted = 1 if bg_keywords else 0
        # distinct_fact_count = A(1) + B + C
        b_list = af.get("B", []) if isinstance(af.get("B"), list) else []
        c_list = af.get("C", []) if isinstance(af.get("C"), list) else []
        distinct_fact_count = 1 + len(b_list) + len(c_list)
        total = cross_n + bg_n
        if bg_attempted and not bg_n:
            total = cross_n + 1
        logger.info(
            "contrast search_count cross=%d bg=%d total=%d distinct_fact_count=%d",
            cross_n, bg_n, total, distinct_fact_count,
        )
        # Wave3: bridge_claim_ids 이진 판정 — 단순 시간 근접/상위 카테고리만 공유 시 반려, 공통 엔티티 또는 명시적 언급 시만 인정
        bridge_claim_ids=[]
        if background and isinstance(background, dict):
            try:
                import re as _re2
                def _tok(s): return set(m.group(0).lower() for m in _re2.finditer(r'[A-Za-z0-9]{2,}|[가-힣]{2,}', s or "")) - {"그리고","하지만","대한","위한","통한","있는","없는","같은","관련","뉴스"}
                seed_t=_tok(seed_article.get("title","")+" "+seed_article.get("description",""))
                bg_t=_tok(background.get("title","")+" "+background.get("description",""))
                # explicit mention: bg mentions seed title entity or vice versa
                overlap=len(seed_t & bg_t)
                explicit = False
                try:
                    bg_text=(background.get("title","")+ " "+background.get("description","")).lower()
                    seed_title_l=seed_article.get("title","").lower()
                    if seed_title_l[:12] and seed_title_l[:12] in bg_text: explicit=True
                except: pass
                if overlap>=2 or explicit:
                    bridge_claim_ids=[str(background.get("id",""))]
                    logger.info("contrast bridge_claim valid overlap=%d explicit=%s ids=%s", overlap, explicit, bridge_claim_ids)
                else:
                    logger.info("contrast bridge_claim rejected overlap=%d explicit=%s (date-only coincidence)", overlap, explicit)
            except Exception as e:
                logger.info("contrast bridge_claim check fail %s", e)
                bridge_claim_ids=[]

        # 4. build bundle
        bundle = {
            "seed_article": seed_article,
            "af": af,
            "background": background,
            "backgrounds": backgrounds,
            "cross_articles": cross_articles,
            "search_meta": {
                "cross": cross_n,
                "cross_n": cross_n,
                "bg": bool(background),
                "bg_n": bg_n,
                "bg_hit": bool(bg_hit),
                "total": total,
                "distinct_fact_count": distinct_fact_count,
                "bridge_claim_ids": bridge_claim_ids if "bridge_claim_ids" in locals() else [],
            },
        }

        # 5. writer
        try:
            from pipeline.threads.contrast.contrast_writer import write_contrast_thread
        except Exception as e:
            logger.warning("contrast orchestrator: contrast_writer import fail: %s", e)
            return None
        # writer_fn 주입 시 컬렉션(다각도+배경)은 그대로, 글쓰기만 교체 (kicker7 등)
        active_writer = writer_fn if writer_fn is not None else write_contrast_thread

        # all_articles_with_background: include seed + background for validator context if needed
        pool = list(all_articles) if isinstance(all_articles, list) else []
        # ensure seed in pool
        if seed_article not in pool:
            pool = [seed_article] + pool

        result = active_writer(bundle, pool, **(writer_kwargs or {}))
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
                bg_b = meta.get("bg_n", 1 if meta.get("bg") else 0)
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
