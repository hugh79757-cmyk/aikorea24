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


def _validate_af(data: dict) -> bool:
    """Guard: B>=1, C>=1, E==3, D non-empty >5."""
    try:
        b = data.get("B", [])
        c = data.get("C", [])
        e = data.get("E", [])
        d = data.get("D", "")
        if not isinstance(b, list) or len(b) < 1:
            return False
        if not isinstance(c, list) or len(c) < 1:
            return False
        if not isinstance(e, list) or len(e) != 3:
            return False
        if not isinstance(d, str) or len(d.strip()) <= 5:
            return False
        # E keywords must be non-empty strings
        if any(not isinstance(k, str) or not k.strip() for k in e):
            return False
        return True
    except Exception:
        return False


# ponytail: global warn-only, no per-category hard fail; upgrade to hard guard if detail quality matters
def _validate_details(data: dict) -> dict:
    """Check 5 categories via regex: name/title/number/date/quote. Warn only, never hard fail."""
    import re

    blob = json.dumps(data, ensure_ascii=False)
    # 1) name: Western "John Smith" or Korean 2-4 char (heuristic)
    name_pat = r"[A-Z][a-z]+ [A-Z][a-z]+|[가-힣]{2,4}"
    # 2) title: 대표|교수|위원|부장 etc
    title_pat = r"대표|교수|위원|부장|이사|회장|사장|박사|연구원|감독|장관|의원|총장|소장"
    # 3) number: \d+만|\d+위|\d+주|\d+%
    number_pat = r"\d+만|\d+위|\d+주|\d+%|\d+억|\d+명"
    # 4) date: \d+월|\d+일|202\d|8월
    date_pat = r"\d+월|\d+일|202\d|8월"
    # 5) quote: " or 「
    quote_pat = r'"|「|\"'

    counts = {
        "name": len(re.findall(name_pat, blob)),
        "title": len(re.findall(title_pat, blob)),
        "number": len(re.findall(number_pat, blob)),
        "date": len(re.findall(date_pat, blob)),
        "quote": len(re.findall(quote_pat, blob)),
    }
    # warn only — any category <1 logs but does not fail
    missing = [k for k, v in counts.items() if v < 1]
    if missing:
        logger.info("extractor: detail warn missing categories %s counts=%s", missing, counts)
    else:
        logger.info("extractor: detail counts %s", counts)
    return counts


def extract_af(article_body: str, title: str) -> dict | None:
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
    user_prompt = (
        f"제목: {title}\n본문: {snippet}\n\n"
        'A-F JSON으로 출력: {"A":{"사건명":...,"시점":...,"장소":...,"행위자":...,"계기":...},'
        '"B":[...],"C":[...],"D":"...","E":["kw1","kw2","kw3"],"F":[...]}'
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

    if not _validate_af(data):
        logger.info("extractor: guard fail B>=1 C>=1 E==3 D>5 -> drop")
        return None

    _validate_details(data)

    return data
