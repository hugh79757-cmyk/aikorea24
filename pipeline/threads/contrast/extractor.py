"""pipeline/threads/contrast/extractor.py — A-F JSON extractor (LLM 1회, guard B>=1 C>=1 E==3)."""
import json
import sys

from pipeline.infra.config import project_root
from pipeline.infra.logger import get_scrubbed_logger

# Ensure scripts/threads on path for model_router import (same as writer.py:155 pattern)
_root = str(project_root())
if _root not in sys.path:
    sys.path.insert(0, _root)
_threads_path = str(project_root() / "scripts" / "threads")
if _threads_path not in sys.path:
    sys.path.insert(0, _threads_path)

from pipeline.threads.contrast.prompts import SYSTEM_EXTRACTOR

logger = get_scrubbed_logger(__name__)


def _validate_af(data: dict, require_c: bool = True) -> bool:
    """Guard: B>=1, C>=1 (require_c=True), E==3, D non-empty >5. Supports dict schemas."""
    try:
        b = data.get("B", [])
        c = data.get("C", [])
        e = data.get("E", [])
        d = data.get("D", "")
        if not isinstance(b, list) or len(b) < 1:
            return False
        # B: allow string or dict with value_text + metric (condition/evidence_sentence may be null/empty)
        for item in b:
            if isinstance(item, dict):
                if not item.get("value_text") or not str(item.get("value_text")).strip():
                    return False
                # metric must be non-empty; condition/evidence_sentence allowed null/empty
                if not item.get("metric") or not str(item.get("metric")).strip():
                    return False
            elif isinstance(item, str):
                if not item.strip():
                    return False
            else:
                return False
        # require_c=False(kicker7 등)는 인용 부족도 컬렉션으로 구출 — C 가드 생략
        if require_c:
            if not isinstance(c, list) or len(c) < 1:
                return False
            for item in c:
                if isinstance(item, dict):
                    if not item.get("text") or not str(item.get("text")).strip():
                        return False
                    if not item.get("text_translated") or not str(item.get("text_translated")).strip():
                        return False
                    if not item.get("speaker") or not str(item.get("speaker")).strip():
                        return False
                    # Wave3: speakers/speaker_type/source_topic_tag optional for legacy, validate if present
                    if "speakers" in item:
                        speakers=item.get("speakers")
                        if not isinstance(speakers, list) or len(speakers)<1 or any(not isinstance(s,str) or not s.strip() for s in speakers):
                            return False
                    if "speaker_type" in item and item.get("speaker_type") not in ("solo","joint_statement","spokesperson_for_org"):
                        return False
                    if "source_topic_tag" in item and not str(item.get("source_topic_tag")).strip():
                        return False
                elif isinstance(item, str):
                    if not item.strip():
                        return False
                else:
                    return False
        if not isinstance(e, list) or len(e) != 3:
            return False
        if not isinstance(d, str) or len(d.strip()) <= 5:
            return False
        if any(not isinstance(k, str) or not k.strip() for k in e):
            return False
        return True
    except Exception:
        return False


def _validate_details(data: dict) -> dict:
    """Check 5 categories + B condition hard fail (과반수 condition 필수)."""
    import re

    blob = json.dumps(data, ensure_ascii=False)
    name_pat = r"[A-Z][a-z]+ [A-Z][a-z]+|[가-힣]{2,4}"
    title_pat = r"대표|교수|위원|부장|이사|회장|사장|박사|연구원|감독|장관|의원|총장|소장"
    number_pat = r"\d+만|\d+위|\d+주|\d+%|\d+억|\d+명"
    date_pat = r"\d+월|\d+일|202\d|8월"
    quote_pat = r'"|「|\"'

    counts = {
        "name": len(re.findall(name_pat, blob)),
        "title": len(re.findall(title_pat, blob)),
        "number": len(re.findall(number_pat, blob)),
        "date": len(re.findall(date_pat, blob)),
        "quote": len(re.findall(quote_pat, blob)),
    }
    missing = [k for k, v in counts.items() if v < 1]
    if missing:
        logger.info(f"extractor: detail warn missing categories {missing} counts={counts}")
    else:
        logger.info(f"extractor: detail counts {counts}")

    # B condition hard check: 과반수 B items에 condition 채워야 함
    b = data.get("B", [])
    if isinstance(b, list) and b:
        dict_items = [x for x in b if isinstance(x, dict)]
        if dict_items:
            with_cond = sum(1 for x in dict_items if str(x.get("condition","")).strip() and str(x.get("condition")).strip() != "기사에 명시되지 않음")
            if with_cond < (len(dict_items) + 1)//2:
                # allow if evidence_sentence present for all? still require at least half with condition or explicit no-condition
                # if model honestly says "기사에 명시되지 않음" for condition, count as filled but warn
                filled = sum(1 for x in dict_items if str(x.get("condition","")).strip())
                if filled < (len(dict_items) + 1)//2:
                    logger.info("extractor: B condition hard fail %d/%d", with_cond, len(dict_items))
                    # mark via counts
                    counts["_b_condition_fail"] = 1
                else:
                    counts["_b_condition_warn"] = 1
    return counts


def extract_af(article_body: str, title: str, pub_date: str | None = None,
               require_c: bool = True) -> dict | None:
    """Extract A-F JSON from article. Returns dict or None on guard/parse fail."""
    if not article_body or not article_body.strip():
        logger.info("extractor: empty body -> drop")
        return None

    # Lazy import to allow mocking in tests
    try:
        from scripts.threads.v3.model_router import chat_completion
    except ImportError:
        try:
            from v3.model_router import chat_completion  # fallback
        except ImportError as e:
            logger.warning("extractor: model_router import fail: %s", e)
            return None

    snippet = article_body[:12000]
    pub_line = f"발행일(pub_date): {pub_date}" if pub_date else "발행일(pub_date): 명시되지 않음"
    user_prompt = (
        f"제목: {title}\n{pub_line}\n본문: {snippet}\n\n"
        'A-F JSON으로 출력: {"A":{"사건명":...,"시점":...,"장소":...,"행위자":...,"계기":...},'
        '"B":[{"value_text":...,"metric":...,"condition":...,"evidence_sentence":...}],'
        '"C":[{"text":...,"text_translated":...,"speaker":...,"speaker_title":...,"paragraph_hint":...}],'
        '"D":"...","E":["kw1","kw2","kw3"],"F":[...]}'
        '\n발행일은 위 pub_date를 기준으로 상대 날짜를 환산하고, 추정 금지 규칙을 준수하라.'
    )

    text = None
    try:
        text = chat_completion(
            system_prompt=SYSTEM_EXTRACTOR,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.2,
            max_tokens=3000,
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}},
        )
    except Exception as e:
        logger.warning("extractor chat_completion error: %s", e)
        return None

    if not text:
        logger.info("extractor: empty LLM response -> drop")
        return None

    # Strip code fence if present
    t = text.strip()
    if t.startswith("```"):
        # remove ```json ... ```
        import re
        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.DOTALL)
        if m:
            t = m.group(1)

    try:
        data = json.loads(t)
    except (json.JSONDecodeError, ValueError) as e:
        logger.info("extractor: JSON parse fail: %s", e)
        return None

    if not isinstance(data, dict):
        logger.info("extractor: not dict -> drop")
        return None

    # Pre-cap E to 3 before guard (LLM may produce 5) — keep first 3
    e = data.get("E")
    if isinstance(e, list) and len(e) > 3:
        logger.info("extractor: E cap 3 cut from %d", len(e))
        data["E"] = e[:3]

    if not _validate_af(data, require_c=require_c):
        logger.info("extractor: guard fail B>=1 C>=1 E==3 D>5 -> drop")
        return None

    # Post-filter: cap B to 6 and C to 4 by original appearance order
    b = data.get("B", [])
    if isinstance(b, list) and len(b) > 6:
        logger.info("extractor: B cap 6 cut from %d", len(b))
        data["B"] = b[:6]
    c = data.get("C", [])
    if isinstance(c, list) and len(c) > 4:
        logger.info("extractor: C cap 4 cut from %d", len(c))
        data["C"] = c[:4]

    detail_counts = _validate_details(data)
    if detail_counts.get("_b_condition_fail"):
        logger.info("extractor: B condition fail -> drop")
        return None

    return data
