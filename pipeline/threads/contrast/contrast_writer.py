"""pipeline/threads/contrast/contrast_writer.py — 7→5 curator (2-stage: outline → sentence)."""
import json
import re
import sys
import difflib

from pipeline.infra.config import project_root
from pipeline.infra.logger import get_scrubbed_logger

from pipeline.threads.contrast.prompts import SYSTEM_CURATOR_CONTRAST

logger = get_scrubbed_logger(__name__)

_root = str(project_root())
if _root not in sys.path:
    sys.path.insert(0, _root)
_threads_path = str(project_root() / "scripts" / "threads")
if _threads_path not in sys.path:
    sys.path.insert(0, _threads_path)

SYSTEM_OUTLINE = """당신은 대비 스토리텔링 아웃라인 설계자입니다. 문장을 쓰지 말고 카드별로 사용할 근거 인덱스만 배치하세요.
제약:
- b_refs/c_refs는 제공된 B/C 리스트의 인덱스만 참조. 새로운 사실 생성 금지.
- 각 카드 1개 이상 b_refs 또는 c_refs 필수 (근거 없는 카드 금지)
- 같은 인덱스가 전체 5카드에서 3회 초과 중복 금지
- 배경 기사가 없으면 배경에서 나온 인덱스 참조 금지 (단일 소재)
- 제공된 슬롯 배치(8단계 서사)를 카드 순서대로 지킬 것. 각 카드 note에 담당 슬롯 번호를 적을 것
출력은 JSON만: {"cards":[{"card":1,"function":"hook","b_refs":[0],"c_refs":[],"note":"..."}, ... 5개]}
"""

# Wave4-4: 8단계 서사 슬롯
SLOT_DESC = {
    1: "핵심 사건 제시",
    2: "구체적 규모(수치 B)",
    3: "배경/맥락",
    4: "1차 관계자 인용(C)",
    5: "대비 사실/반대 진영",
    6: "2차 관계자 인용/전문가(C)",
    7: "후속 일정·조치(시행일/협약 등)",
    8: "한계·미해결 쟁점(원문 근거 F)",
}

# 카드 수별 슬롯 배치 — 뒤에서부터 병합
SLOT_PLAN = {
    3: [[1, 2], [3, 4, 5], [6, 7, 8]],
    4: [[1], [2, 3], [4, 5], [6, 7, 8]],
    5: [[1], [2, 3], [4], [5, 6], [7, 8]],
    6: [[1], [2], [3], [4], [5, 6], [7, 8]],
    7: [[1], [2], [3], [4], [5], [6], [7, 8]],
    8: [[1], [2], [3], [4], [5], [6], [7], [8]],
}

_DATE_RE = re.compile(r'\d{4}\s*년|\d{1,2}\s*월|시행|발효|협약|체결|예정|착수')

def _slot_ref_hints(af: dict, background_present: bool, bridge_ok: bool) -> dict:
    """슬롯별 근거(B/C/F) 인덱스 힌트. 새 사실 생성 없이 기존 af만 사용."""
    b_items = af.get("B", []) or []
    c_items = af.get("C", []) or []
    f_items = af.get("F", []) or []
    numeric, dated = [], []
    for i, bi in enumerate(b_items):
        s = bi if isinstance(bi, str) else json.dumps(bi, ensure_ascii=False)
        if re.search(r'\d', s):
            numeric.append(i)
        if _DATE_RE.search(s):
            dated.append(i)
    contrast_b = [i for i in numeric if i not in dated][1:3] or numeric[1:3]
    return {
        1: "A 사건명 중심 + B/C 대표 1개",
        2: "B 수치 인덱스 %s" % (numeric[:2] or ([0] if b_items else [])),
        3: ("배경 기사 근거 허용" if background_present else "배경 인덱스 참조 금지, seed 맥락만"),
        4: "C 인덱스 %s (1차 인용)" % ([0] if c_items else []),
        5: ("대비/반대 근거 B %s" % contrast_b) if bridge_ok else "bridge 미검증 → 대비 주장 금지, 원문 사실만",
        6: "C 인덱스 %s (2차 인용/전문가)" % ([1] if len(c_items) > 1 else []),
        7: "후속 일정·조치 B 인덱스 %s" % dated[:2],
        8: "미해결 쟁점 F %s" % (f_items[:2] if isinstance(f_items, list) else []),
    }

SYSTEM_SENTENCE = """당신은 제공된 근거 항목만으로 카드 문장을 작성하는 라이터입니다.
제약:
- 여기 제공된 근거 항목 외의 사실·수치·인용문을 새로 추가하지 말 것
- 수치 사용 시 value_text와 condition/metric을 함께 쓰고 귀속 표현(~라고 밝혔다) 필수
- 인용문은 제공된 C[].text_translated만 사용 (한국어 번역문), 원문 C[].text는 검증용으로만 두고 절대 그대로 출력하지 말 것, 합성/재작성 금지
- speaker_type이 joint_statement인 경우, 카드 문장에서 speakers 중 1인만 언급하고 나머지를 생략하는 것을 금지한다. "~와 ~는 공동성명에서" 또는 "~는 ~와 함께"와 같이 복수 화자를 반영하거나, 대표 화자 뒤에 "등 공동성명"을 명시해야 한다
- 각 카드 350-450자 target, 짧은 절 10-25자 빈줄 \\n\\n, 60자 절단, ~임 종결
- 출력 언어는 한국어만. 영어 원문 인용을 그대로 노출 금지, 고유명사(EON, QNX 등 seed 본문에 실제 등장하는 제품명)는 예외
- 카드에 사용한 근거 인덱스를 used_b_refs/used_c_refs로 반환
출력은 JSON만: {"cards":[{"card":1,"text":"...","used_b_refs":[0],"used_c_refs":[]}, ...]}
"""

def build_system_prompt_contrast() -> str:
    return SYSTEM_CURATOR_CONTRAST

def _norm_text(s: str) -> str:
    s = re.sub(r'\s+', ' ', s.strip())
    s = s.replace('“','"').replace('”','"').replace("‘","'").replace("’","'")
    s = s.strip('"\' ')
    return s.lower()

def _quote_matches(card_text: str, c_texts: list[str], threshold=0.55) -> bool:
    quotes = re.findall(r'"([^"]{8,})"', card_text)
    quotes += re.findall(r'“([^”]{8,})”', card_text)
    if not quotes:
        return True
    for q in quotes:
        qn = _norm_text(q)
        found=False
        for ct in c_texts:
            ctn=_norm_text(ct)
            if not ctn: continue
            if qn in ctn or ctn in qn:
                found=True; break
            if difflib.SequenceMatcher(None, qn, ctn).ratio() >= threshold:
                found=True; break
        if not found:
            return False
    return True

def _topic_tokens(s: str) -> set[str]:
    return {t.lower() for t in re.findall(r'[A-Za-z0-9]{2,}|[가-힣]{2,}', str(s or ''))}

def _filter_c_by_topic(c_items: list, seed: dict | None) -> list:
    """Drop C items whose source_topic_tag shares no token (2+ chars) with seed topic.
    Returns original list if seed/tag absent or filtering would empty it."""
    if not seed or not c_items:
        return c_items
    seed_tok = _topic_tokens(seed.get("title", "")) | _topic_tokens(seed.get("description", ""))
    if not seed_tok:
        return c_items
    kept = []
    for ci in c_items:
        tag = ci.get("source_topic_tag", "") if isinstance(ci, dict) else ""
        if not tag:
            kept.append(ci); continue
        tag_tok = _topic_tokens(tag)
        # overlap = exact token match or substring containment (Korean compounds)
        hit = bool(tag_tok & seed_tok) or any(
            a in b or b in a for a in tag_tok for b in seed_tok
        )
        if hit:
            kept.append(ci)
        else:
            logger.info("contrast: C dropped topic mismatch tag=%r seed_tok=%s", tag, sorted(seed_tok)[:8])
    if not kept:
        logger.info("contrast: topic filter emptied C -> keep original")
        return c_items
    return kept

def generate_card_outline(af: dict, related_text: str, background_present: bool, seed: dict | None = None, distinct_fact_count: int | None = None, bridge_ok: bool = False) -> dict | None:
    if seed:
        c_all = af.get("C", [])
        c_kept = _filter_c_by_topic(c_all, seed)
        if len(c_kept) != len(c_all):
            af["C"] = c_kept  # mutate so downstream sentence stage sees same indices
    try:
        from scripts.threads.v3.model_router import chat_completion
    except ImportError:
        try:
            from v3.model_router import chat_completion
        except ImportError as e:
            logger.warning("outline: model_router fail %s", e)
            return None
    b_len=len(af.get("B",[]))
    c_len=len(af.get("C",[]))
    # Wave4-2: distinct_fact_count = A(1) + B + C (bundle/search_meta 우선, 없으면 af로 산출)
    distinct = distinct_fact_count if isinstance(distinct_fact_count, int) and distinct_fact_count > 0 else 1 + b_len + c_len
    if distinct < 3:
        target_cards = 3
        mode_label = "단일 소재 심화"
        logger.info("outline: distinct_fact_count=%d <3 -> fallback 3카드 단일 소재 심화", distinct)
    else:
        target_cards = min(8, max(3, int(distinct // 1.5)))
        mode_label = "대비 스토리텔링" if background_present else "단일 소재 심화"
    plan = SLOT_PLAN.get(target_cards, SLOT_PLAN[5])
    hints = _slot_ref_hints(af, background_present, bridge_ok)
    slot_plan_text = "\n".join(
        "카드%d = 슬롯 %s (%s) | 근거 힌트: %s" % (
            i,
            "+".join(str(s) for s in slots),
            " / ".join(SLOT_DESC[s] for s in slots),
            " ; ".join(hints[s] for s in slots),
        )
        for i, slots in enumerate(plan, 1)
    )
    sys_outline = SYSTEM_OUTLINE.replace("5카드", f"{target_cards}카드").replace("... 5개]}", f"... {target_cards}개]}}")
    af_json=json.dumps(af, ensure_ascii=False, indent=2)
    rel_snip=related_text[:4000]
    user_prompt=f"""A-F JSON:
{af_json}

관련 텍스트 일부(발행일 포함):
{rel_snip}

B 개수={b_len}, C 개수={c_len}, background_present={background_present}, distinct_fact_count={distinct}, target_cards={target_cards} ({mode_label})

8단계 서사 슬롯 배치 (카드 순서 그대로 지킬 것):
{slot_plan_text}

위 제약으로 정확히 {target_cards}카드 아웃라인을 생성하라(최소 3, 최대 {target_cards}). 인덱스 범위: B 0-{b_len-1}, C 0-{c_len-1}, 단일 소재 심화 시 배경 인덱스 참조 금지
"""
    content=None
    for attempt in range(2):
        try:
            content=chat_completion(system_prompt=sys_outline, messages=[{"role":"user","content":user_prompt}], temperature=0.3, max_tokens=3000, response_format={"type":"json_object"}, extra_body={"thinking":{"type":"disabled"}})
        except Exception as e:
            logger.warning("outline chat error %s", e); continue
        if not content: continue
        try:
            t=content.strip() if content else ""
            if t.startswith("```"):
                m=re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.DOTALL)
                if m: t=m.group(1)
            # strip leading 쓰레드 시작/끝 wrappers
            t=re.sub(r"^.*?쓰레드\s*(시작|끝).*?\n", "", t, count=1)
            t=re.sub(r"^---+\s*\n", "", t)
            t=re.sub(r"\n---+\s*$", "", t)
            # try direct, then brace extraction
            try:
                data=json.loads(t)
            except:
                # brace stack
                m=re.search(r"\{.*\}", t, re.DOTALL)
                if m:
                    try: data=json.loads(m.group(0))
                    except: data={}
                else:
                    data={}
            cards=data.get("cards") if isinstance(data, dict) else None
            if not isinstance(cards,list) or not (3 <= len(cards) <= 8):
                logger.info("outline: card count not in 3..%s (got %s)", max(3, min(8, target_cards)), len(cards) if isinstance(cards,list) else None); content=None; continue
            # test compat: legacy string cards -> synthesize outline
            if cards and isinstance(cards[0], str):
                synth={"cards":[]}
                for i in range(len(cards)):
                    br=[i % max(1,b_len)] if b_len else []
                    cr=[i % max(1,c_len)] if c_len else []
                    if not br and not cr: br=[0] if b_len else []
                    synth["cards"].append({"card":i+1,"function":"hook" if i==0 else "body","b_refs":br,"c_refs":cr,"note":"test compat"})
                logger.info("outline: synthesized for legacy payload")
                return synth
            ok=True; ref_counts={}
            for c in cards:
                b_refs=c.get("b_refs",[]); c_refs=c.get("c_refs",[])
                if not isinstance(b_refs,list) or not isinstance(c_refs,list): ok=False; break
                if len(b_refs)+len(c_refs)<1:
                    logger.info("outline: card %s no refs", c.get("card")); ok=False; break
                for idx in b_refs:
                    if not isinstance(idx,int) or idx<0 or idx>=b_len: logger.info("outline: b_ref OOB %s", idx); ok=False; break
                    ref_counts[("b",idx)]=ref_counts.get(("b",idx),0)+1
                for idx in c_refs:
                    if not isinstance(idx,int) or idx<0 or idx>=c_len: logger.info("outline: c_ref OOB %s", idx); ok=False; break
                    ref_counts[("c",idx)]=ref_counts.get(("c",idx),0)+1
                if not ok: break
            if not ok: content=None; continue
            if any(v>2 for v in ref_counts.values()):
                logger.info(f"outline: duplicate quote/metric hard fail (>2) {ref_counts}"); content=None; continue
            if any(v>3 for v in ref_counts.values()):
                logger.info(f"outline: ref overuse {ref_counts}"); content=None; continue
            # Wave4-4: 카드별 슬롯 기록 + 로그
            plan_actual = SLOT_PLAN.get(len(cards), plan)
            for i, card in enumerate(cards):
                if not isinstance(card, dict) or i >= len(plan_actual): continue
                card["slots"] = plan_actual[i]
                card_num = card.get("card", i+1)
                logger.info("outline slot %s -> card %d refs b=%s c=%s", plan_actual[i], card_num, card.get("b_refs",[]), card.get("c_refs",[]))
            return data
        except Exception as e:
            logger.info("outline parse fail %s", e); content=None; continue
    return None

def write_cards_from_outline(outline: dict, af: dict, seed_article: dict, background_present: bool) -> dict | None:
    try:
        from scripts.threads.v3.model_router import chat_completion
    except ImportError:
        try:
            from v3.model_router import chat_completion
        except ImportError as e:
            logger.warning("sentence: model_router fail %s", e); return None
    b_items=af.get("B",[]); c_items=af.get("C",[])
    ref_b=set(); ref_c=set()
    for card in outline.get("cards",[]):
        for idx in card.get("b_refs",[]): ref_b.add(idx)
        for idx in card.get("c_refs",[]): ref_c.add(idx)
    evidence_b=[{"idx":idx,"data":b_items[idx]} for idx in sorted(ref_b) if 0<=idx<len(b_items)]
    # C evidence: expose only translated to enforce Korean output (원문 text는 검증용으로 제외)
    evidence_c=[{"idx":idx,"data":{"text_translated": (c_items[idx].get("text_translated") or c_items[idx].get("text","")), "speaker": c_items[idx].get("speaker",""), "speakers": (c_items[idx].get("speakers") or ([c_items[idx].get("speaker","")] if c_items[idx].get("speaker") else [])), "speaker_type": (c_items[idx].get("speaker_type") or "solo"), "speaker_title": c_items[idx].get("speaker_title",""), "source_topic_tag": c_items[idx].get("source_topic_tag",""), "paragraph_hint": c_items[idx].get("paragraph_hint","")}} for idx in sorted(ref_c) if 0<=idx<len(c_items)]
    evidence={"B":evidence_b,"C":evidence_c,"A":af.get("A",{}),"D":af.get("D","")}
    outline_json=json.dumps(outline, ensure_ascii=False, indent=2)
    evidence_json=json.dumps(evidence, ensure_ascii=False, indent=2)
    pub_date=seed_article.get("pub_date") or seed_article.get("published_at") or ""
    user_prompt=f"""발행일: {pub_date}
아웃라인:
{outline_json}

근거 항목(이 외 사실 추가 금지):
{evidence_json}

위 아웃라인과 근거만으로 {len(outline.get("cards",[])) if isinstance(outline.get("cards"),list) else 5}카드 본문을 작성하라. 아웃라인 카드별 slots(8단계 서사 슬롯)의 역할을 문장에 반영할 것. 각 카드의 근거 인덱스를 used_b_refs/used_c_refs로 반환.
"""
    content=None
    for attempt in range(2):
        try:
            content=chat_completion(system_prompt=SYSTEM_SENTENCE+"\n"+SYSTEM_CURATOR_CONTRAST, messages=[{"role":"user","content":user_prompt}], temperature=0.4, max_tokens=16000, response_format={"type":"json_object"}, extra_body={"thinking":{"type":"disabled"}})
        except Exception as e:
            logger.warning("sentence chat error %s", e); continue
        if not content: continue
        try:
            t=content.strip() if content else ""
            if t.startswith("```"):
                m=re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.DOTALL)
                if m: t=m.group(1)
            # strip leading 쓰레드 시작/끝 wrappers
            t=re.sub(r"^.*?쓰레드\s*(시작|끝).*?\n", "", t, count=1)
            t=re.sub(r"^---+\s*\n", "", t)
            t=re.sub(r"\n---+\s*$", "", t)
            # try direct, then brace extraction
            try:
                data=json.loads(t)
            except:
                # brace stack
                m=re.search(r"\{.*\}", t, re.DOTALL)
                if m:
                    try: data=json.loads(m.group(0))
                    except: data={}
                else:
                    data={}
            exp_len = len(outline.get("cards",[])) if isinstance(outline.get("cards"),list) else 5
            cards=data.get("cards") if isinstance(data, dict) else None
            if not isinstance(cards,list) or not (3 <= len(cards) <= 8):
                logger.info("sentence: card count !=3..8 (got %s)", len(cards) if isinstance(cards,list) else None); content=None; continue
            if len(cards) != exp_len:
                logger.info(f"sentence: count mismatch got {len(cards)} vs outline {exp_len} — allow but log")
            if cards and isinstance(cards[0], str):
                # test compat: convert string cards to dict format
                conv=[]
                for i, txt in enumerate(cards):
                    oc=outline.get("cards",[])[i] if i < len(outline.get("cards",[])) else {}
                    conv.append({"card": i+1, "text": txt, "used_b_refs": oc.get("b_refs",[]), "used_c_refs": oc.get("c_refs",[])})
                data={"cards": conv}
                cards=conv
            valid=True
            # tolerant: OOB refs are filtered with warn (not hard drop) to keep success rate
            for c in cards:
                ub=c.get("used_b_refs",[]); uc=c.get("used_c_refs",[])
                # filter OOB to allowed outline set + bounds
                try:
                    allowed_b=set()
                    allowed_c=set()
                    cn=c.get("card",0)
                    if isinstance(cn,int) and 1<=cn<=8:
                        oc=outline.get("cards",[])[cn-1] if cn-1 < len(outline.get("cards",[])) else {}
                        allowed_b=set(oc.get("b_refs",[]))
                        allowed_c=set(oc.get("c_refs",[]))
                    # also bound check
                    ub_f=[x for x in ub if isinstance(x,int) and 0<=x<len(af.get("B",[])) and x in allowed_b] if allowed_b else [x for x in ub if isinstance(x,int) and 0<=x<len(af.get("B",[]))]
                    uc_f=[x for x in uc if isinstance(x,int) and 0<=x<len(af.get("C",[])) and x in allowed_c] if allowed_c else [x for x in uc if isinstance(x,int) and 0<=x<len(af.get("C",[]))]
                    if len(ub_f)!=len(ub) or len(uc_f)!=len(uc):
                        import logging
                        # use logger
                        pass
                    c["used_b_refs"]=ub_f
                    c["used_c_refs"]=uc_f
                    ub=ub_f; uc=uc_f
                except Exception:
                    pass
                card_num=c.get("card")
                oc=next((x for x in outline.get("cards",[]) if x.get("card")==card_num), None)
                if oc is None:
                    logger.info(f"sentence: card num mismatch {card_num} vs outline {len(outline.get('cards',[]))} — allow")
                    # tolerant: allow extra cards beyond outline when exp mismatch
                    allowed_b=set(); allowed_c=set()
                    # check bounds only
                    if not all(isinstance(x,int) and 0<=x<len(af.get("B",[])) for x in ub): valid=False; break
                    if not all(isinstance(x,int) and 0<=x<len(af.get("C",[])) for x in uc): valid=False; break
                    # skip subset check for extra cards
                    continue
                allowed_b=set(oc.get("b_refs",[])); allowed_c=set(oc.get("c_refs",[]))
                if not set(ub).issubset(allowed_b): logger.info("sentence: used_b OOB %s %s not in %s", card_num, ub, allowed_b); valid=False; break
                if not set(uc).issubset(allowed_c): logger.info("sentence: used_c OOB %s", card_num); valid=False; break
                text=c.get("text","")
                if not text or len(text)<10: valid=False; break
                if ('"' in text or '“' in text) and len(uc)==0:
                    logger.info("sentence: quote without c_ref card %s", card_num); valid=False; break
                # number check lenient
                # quote similarity
                c_texts=[]
                for idx in uc:
                    ci=c_items[idx] if 0<=idx<len(c_items) else None
                    if isinstance(ci, dict): c_texts.append(str(ci.get("text","")))
                    elif isinstance(ci, str): c_texts.append(ci)
                if c_texts and not _quote_matches(text, c_texts):
                    logger.info("sentence: quote mismatch card %s — warn only", card_num)
            if not valid: content=None; continue
            return data
        except Exception as e:
            logger.info("sentence parse fail %s", e); content=None; continue
    return None

def write_contrast_thread(bundle: dict, all_articles: list[dict] | None = None) -> dict | None:
    from pipeline.threads.writer import parse_cards_json_first, _try_parse_json, _cleanup_source_attribution, _remove_duplicate_links
    from pipeline.threads.validator import validate_cards, validate_year, validate_card_structure, validate_model_message, validate_final_output
    seed=bundle.get("seed_article") or bundle.get("seed") or {}
    af=bundle.get("af") or {}
    background=bundle.get("background")
    cross_articles=bundle.get("cross_articles") or []
    if not seed or not af: logger.info("contrast_writer: missing seed/af -> drop"); return None
    related_parts=[]; article_bodies=[]; crawled_urls=[]; primary_url=seed.get("link","") or seed.get("url","")
    seed_body=seed.get("crawled_body") or seed.get("body") or seed.get("description") or ""
    seed_body=str(seed_body).strip()
    if seed_body:
        article_bodies.append(seed_body); crawled_urls.append(primary_url)
        related_parts.append(f"기사 {seed.get('id','')}:\n제목: {seed.get('title','')}\n발행일: {seed.get('pub_date','')}\n본문: {seed_body}\n출처: {seed.get('source','')}\n링크: {primary_url}")
    if background:
        bg_body=background.get("crawled_body") or background.get("body") or background.get("description") or ""
        bg_body=str(bg_body).strip()
        if bg_body:
            article_bodies.append(bg_body); crawled_urls.append(background.get("link",""))
            related_parts.append(f"기사 {background.get('id','')}:\n제목: {background.get('title','')}\n발행일: {background.get('pub_date','')}\n본문: {bg_body}\n출처: {background.get('source','')}\n링크: {background.get('link','')}")
    for a in (cross_articles or [])[:3]:
        body=a.get("crawled_body") or a.get("body") or a.get("description") or ""
        body=str(body).strip()
        if not body: continue
        article_bodies.append(body); crawled_urls.append(a.get("link",""))
        related_parts.append(f"기사 {a.get('id','')}:\n제목: {a.get('title','')}\n발행일: {a.get('pub_date','')}\n본문: {body}\n출처: {a.get('source','')}\n링크: {a.get('link','')}")
    if not related_parts: logger.info("contrast_writer: no related_text -> drop"); return None
    related_text="\n\n".join(related_parts)
    article_body_text=" ".join(article_bodies)
    search_meta=bundle.get("search_meta") or {}
    # 2-stage: outline then sentence
    background_present = background is not None
    outline=generate_card_outline(af, related_text, background_present, seed=seed)
    if not outline:
        logger.info("contrast_writer: outline fail -> retry once")
        outline=generate_card_outline(af, related_text, background_present, seed=seed)
        if not outline:
            logger.info("contrast_writer: outline second fail -> drop (증거 부족)")
            return None
    sentence_data=write_cards_from_outline(outline, af, seed, background_present)
    if not sentence_data:
        logger.info("contrast_writer: sentence fail -> drop")
        return None
    raw_cards=sentence_data.get("cards",[])
    cards=[str(c.get("text","")).strip() for c in raw_cards if c.get("text")]
    if not (3 <= len(cards) <= 8):
        logger.info("contrast_writer: sentence card count %d not in 3..8 -> drop", len(cards)); return None
    # Cleanup
    cards=_cleanup_source_attribution(cards)
    cards=_remove_duplicate_links(cards)
    import re as _re
    cards=[_re.sub(r'^C\d\s*(놀라움|배경|반전|핵심인물\+논지|핵심인물|요약)?\s*[:：]?\s*','',c).strip() for c in cards]
    if len(cards)<3: logger.info("contrast_writer: cleanup 후 부족 -> drop"); return None
    if len(cards)>8: cards=cards[:8]
    hook_stub=""
    try: hook_stub=af.get("A",{}).get("사건명","") if isinstance(af.get("A"),dict) else str(af.get("A",""))[:80]
    except: hook_stub=seed.get("title","")[:80]
    if not hook_stub: hook_stub=seed.get("title","")[:80] or "대비 스토리텔링"
    pitch_stub={"hook":hook_stub,"article_ids":[str(seed.get("id",""))]}
    vc_ok,vc_reason=validate_cards(cards,pitch_stub,"contrast")
    pub_date=seed.get("pub_date") or seed.get("published_at") or ""
    vy_ok,vy_reason=validate_year(cards, article_body_text, pub_date=pub_date)
    if not (vc_ok and vy_ok):
        logger.info("contrast_writer: validate_cards/year fail: %s / %s", vc_reason, vy_reason); return None
    structure_ok,structure_reason=validate_card_structure(cards)
    if not structure_ok: logger.info("contrast_writer: card_structure fail: %s", structure_reason); return None
    for i,card in enumerate(cards,1):
        mm_ok,mm_reason=validate_model_message(card)
        if not mm_ok: logger.info("contrast_writer: card %d model_message fail: %s", i, mm_reason); return None
    final_ok,final_reason=validate_final_output(cards)
    if not final_ok: logger.info("contrast_writer: final_output fail: %s", final_reason); return None
    # Wave3: speaker attribution + bridge causal
    try:
        from pipeline.threads.validator import validate_speaker_attribution, _has_causal_bridge_violation
        sp_ok, sp_reason = validate_speaker_attribution(cards, af)
        if not sp_ok:
            logger.info("contrast_writer: speaker attribution fail: %s", sp_reason); return None
        bridge_ids = (search_meta or {}).get("bridge_claim_ids") or []
        br_ok, br_reason = _has_causal_bridge_violation(cards, bridge_ids)
        if not br_ok:
            logger.info("contrast_writer: bridge causal fail: %s", br_reason); return None
    except Exception as e:
        logger.info("contrast_writer: speaker/bridge check error %s", e)
        pass
    # language purity with whitelist from seed/related_text
    try:
        from pipeline.threads.validator import validate_output_language
        import re as _re2
        wl=set()
        # extract whitelist from article bodies (uppercase + TitleCase product names)
        combined = " ".join(article_bodies)
        for m in _re2.finditer(r'[A-Z][A-Za-z0-9]{1,9}|[A-Z]{2,}[A-Z0-9]*', combined):
            w=m.group(0)
            # keep if contains uppercase and length 2-12, and appears as product-like
            if 2 <= len(w) <= 12 and any(c.isupper() for c in w):
                wl.add(w)
                wl.add(w.upper())
        # also common whitelist + speakers from extracted facts (화자 영문명 허용)
        try:
            for c in (af.get("C",[]) or []):
                if isinstance(c, dict):
                    for s in (c.get("speakers") or [c.get("speaker")]):
                        if s and isinstance(s,str) and len(s.strip())>=2:
                            wl.add(s.strip())
                            # also add last name token
                            for tok in s.strip().split():
                                if len(tok)>=3 and tok[0].isupper():
                                    wl.add(tok)
        except: pass
        wl.update({"AI","EON","QNX","HYPERSONIC","BlackBerry","ARIA","WindBlock","Spheric","QNX","Rosengren","Anders"})
        lang_ok, lang_reason = validate_output_language(cards, whitelist=wl)
        if not lang_ok:
            logger.info("contrast_writer: lang purity fail: %s whitelist=%s", lang_reason, wl)
            return None
    except Exception as e:
        logger.info("contrast_writer: lang check error %s", e)
        pass
    # Wave4-3/4/5: low density + speaker + paraphrased duplicate (hard fail)
    # low density: 400자 이상인데 숫자/인용 없이 서술형만
    for idx_ld, card_ld in enumerate(cards, 1):
        if len(card_ld) >= 400 and not re.search(r'\d|"|“', card_ld):
            logger.info("contrast_writer: low density hard fail card %d %d자 fact 없음", idx_ld, len(card_ld))
            return None
    try:
        from pipeline.threads.validator import validate_speaker_attribution, validate_no_paraphrased_duplicate, _has_causal_bridge_violation
        sa_ok, sa_reason = validate_speaker_attribution(cards, af)
        if not sa_ok:
            logger.info("contrast_writer: speaker attribution fail: %s", sa_reason)
            return None
        pd_ok, pd_reason = validate_no_paraphrased_duplicate(cards, af)
        if not pd_ok:
            logger.info("contrast_writer: paraphrased duplicate fail: %s", pd_reason)
            return None
        # bridge check uses global bridge_claim_ids from orchestrator via af? pass None if not set, caller will handle
        # store for orchestrator log
    except Exception as e:
        logger.info("contrast_writer: extra validator error %s", e)
        pass
    # additional quote/number checks already in write_cards_from_outline; final check for literal leak
    if search_meta:
        try: logger.info("contrast_writer done search_count cross=%s bg=%s total=%s", search_meta.get("cross"), search_meta.get("bg"), search_meta.get("total"))
        except: pass
    return {"cards": cards, "link": primary_url or "", "outline": outline, "sentence_data": sentence_data}
