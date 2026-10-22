#!/usr/bin/env python3
"""AIK24-PIPE-10: 자동 생성 글의 주제 귀속(모델 ID) 검사.

## 0단계 — 생성 코드 경로 특정 (2026-10-22 실측)

사고: 2026-10-22 07:32 `kr.aikorea24.blog-draft` 가 발행한 글 중 1건
(원본 revision `01M5GGA6KWGXBX7VQA6Z4F96JG`, 2026-10-22 00:31:26 UTC).

- 생성 경로: `scripts/blog_draft_generator.py::generate_draft()`
  · `is_deep = (len(articles) == 1)` → True
  · 라우팅 조건 `articles[0].get("v2_tag") == "free-llm"` → **False**
    (사고 항목 news 56082 의 실제 `v2_tag` 는 `free-opportunity`)
    → `model_eval.extract_model_id()` 는 **호출조차 되지 않았다**
    → **뉴스 블로그 경로**(일반 GPT 프롬프트)로 직행.
      (로그에 "OpenRouter 모델 ID 미확인" 줄조차 남지 않는다 — v2_tag 조건 밖이기 때문)
- 프롬프트에 실리는 것: `keyword`(제목) · `articles_str`(제목·출처·description 300자) · `links_str`.
  **원본 항목의 모델 ID 는 실리지 않는다.**
- 사고 항목(56082)의 실체: title/original_title = "OpenRouter 무료 모델 (:free 태그)",
  link = `https://openrouter.ai/models?max_price=0&order=newest`(= **목록 페이지**, ID 아님),
  description = ":free 태그가 붙은 모델을 무료로 호출 …". → **추출 가능한 특정 모델 ID 가 없다.**
- 그래서 GPT 는 "OpenRouter 무료 모델" 일반론으로 글을 썼고, 실측 섹션에
  "5. ai.kr.24 실측 결과 — 신뢰도 검증 / 2026년 10월 16일 기준, ai.kr.24 팀은 OpenRouter 무료 모델
  `google/gemini-2.0-flash-exp:free` 에 대해 100회 연속 호출 테스트를 수행했습니다" 라고 적었다.
  **그 모델은 프로젝트 전체에 존재하지 않는다**(model_eval 캐시·리더보드·실행 로그 전부 검색 0건)
  → 실측 기록이 없는 수치를 만들어낸 것이 규칙 2 의 정확한 위반이다.

## 규칙

1. **모델 ID 강제 포함** — 원본 항목이 특정 모델이면 그 ID 를 생성 입력에 명시적으로 전달하고,
   발행 게이트에서 제목·본문 어디에도 없으면 hold.
2. **실측 섹션은 실행 기록이 있을 때만** — 정량 실측 수치는 model_eval 캐시·리더보드·실행 로그에
   근거가 있을 때만 허용. 없으면 실측 섹션 자체를 만들지 않는다.
   다른 모델의 평가 결과를 해당 모델 글에 쓰는 것도 금지(model_id 기준 캐시 조회).
3. **발행 전 모델명 일치** — 생성 시 사용한 모델 ID 와 원본 항목의 모델 ID 를 정규화 비교.
   불일치면 hold.

규칙 1·3 의 게이트는 규칙 2 와 **같은 지점**(발행 품질 게이트)에 통합한다 — 게이트를 두 개로 늘리지 않는다.

## 정규화

PIPE-05 `blog_link_resolver.normalize_model_key` 를 그대로 재사용한다
(프로바이더 접두사 + `:free`/`-free` 접미사 제거). 이 모듈은 네트워크·D1 을 쓰지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:  # PIPE-05 정규화 재사용
    from blog_link_resolver import normalize_model_key as _normalize_key
except Exception:  # pragma: no cover — 폴백 (같은 규칙)
    def _normalize_key(model_id: str) -> str:
        s = str(model_id or "").strip()
        s = re.sub(r"[:\-\s]*[\(\[]?free[\)\]]?\s*$", "", s, flags=re.IGNORECASE).strip()
        if "/" in s:
            head, _, tail = s.partition("/")
            if "." not in head and head not in ("kilo", "opencode", "nvidia", "openrouter", "zen"):
                s = tail
        return s.lower()

LOGS_DIR = Path(__file__).resolve().parent / "logs"
CACHE_PATH = LOGS_DIR / "model_eval_cache.json"
LEADERBOARD_PATH = LOGS_DIR / "model_leaderboard.json"
RUNS_PATH = LOGS_DIR / "model_eval_runs.jsonl"

# 링크에서 모델 ID 로 오인하기 쉬운 경로 세그먼트(목록·문서 페이지)
_NON_MODEL_SEGMENTS = {
    "models", "models-dev", "docs", "api", "chat", "completions", "rankings",
    "providers", "pricing", "search", "settings", "account", "settings",
}

# 백틱 안의 모델 ID 모양: provider/model 또는 model-name(:free|-free)
_BACKTICK_MODEL_RE = re.compile(
    r"`([a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)+(?::free|-free)?)`",
    re.IGNORECASE,
)
_BACKTICK_BARE_RE = re.compile(
    r"`([a-z0-9][a-z0-9._-]*(?::free|-free))`", re.IGNORECASE
)

# 정량 실측 주장 패턴 — "숫자 + 측정 동사"
_QUANT_CLAIM_RES = [
    re.compile(r"\d+\s*회\s*(?:연속\s*)?(?:호출|테스트|요청|실행|시도|반복)"),
    re.compile(r"(?:성공률|정확도|통과율|응답률)\s*[:=]?\s*\d+(?:\.\d+)?\s*%"),
    re.compile(r"평균\s*\d+(?:\.\d+)?\s*(?:ms|밀리초|초)"),
    re.compile(r"\d+\s*/\s*12\s*문항"),
    re.compile(r"12문항\s*(?:중|만)\s*\d+"),
    re.compile(r"\d+\s*문항\s*(?:정답|맞힘|통과)"),
]
# 측정 맥락어 — 수치가 "실측"인지 단순 숫자인지 가른다
_MEASURE_CONTEXT_RE = re.compile(
    r"실측|측정|테스트|호출|요청|평가|벤치마크|실행|검증|성능|벤치|크롤|응답\s*시간",
    re.IGNORECASE,
)


def normalize_model_key(model_id: str) -> str:
    """PIPE-05 정규화 키 (프로바이더 접두사·무료 접미사 제거)."""
    return _normalize_key(model_id or "")


_PROVIDER_PREFIXES = ("opencode/", "kilo/", "nvidia/", "openrouter/", "zen/")
_FREE_SUFFIXES = (":free", "-free")


def model_match_keys(model_id: str) -> set:
    """모델 ID 비교용 키 집합.

    단일 정규화 키는 **비대칭**이라 그대로 쓰면 오탐이 난다(2026-10-22 실측):
        normalize_model_key("opencode/flint-40b-free") → "flint-40b"
        normalize_model_key("flint-40b-free")          → "flint-40b-free"
    → 같은 모델인데 키가 달라 규칙 1 이 오탐으로 hold 낸다.

    그래서 비교는 **키 집합의 교집합**으로 한다:
        원본 / 프로바이더 접두사 제거 / 무료 접미사 제거 의 조합을 모두 넣고,
        두 모델의 키 집합이 겹치면 같은 모델로 본다.
    """
    raw = str(model_id or "").strip().lower()
    if not raw:
        return set()
    out = {raw}
    forms = {raw}
    for pref in _PROVIDER_PREFIXES:
        if raw.startswith(pref):
            forms.add(raw[len(pref):].lstrip("/"))
    for f in list(forms):
        for suf in _FREE_SUFFIXES:
            if f.endswith(suf):
                out.add(f[: -len(suf)])
                forms.add(f[: -len(suf)])
    for f in list(forms):
        if "/" in f:
            out.add(f.split("/", 1)[1])
    return {x for x in out if x}


def same_model(a: str, b: str) -> bool:
    """두 모델 ID 가 같은 모델인지(정규화 비교)."""
    ka, kb = model_match_keys(a), model_match_keys(b)
    return bool(ka & kb)


# ---------------------------------------------------------------- 원본 모델 ID
def _from_title(text: str) -> str | None:
    if not text:
        return None
    # [무료 LLM] flint-40b-free — OpenCode Zen 무료 티어
    m = re.search(r"\[\s*무료\s*(?:LLM|모델)\s*\]\s*([\w][\w\-./:]*)", text)
    if m:
        return m.group(1).strip().rstrip(".,;:")
    # provider/model 형태
    m = re.search(r"(?<![\w./-])([a-z0-9][\w.-]*/[a-z0-9][\w.-]*(?:/[a-z0-9][\w.-]*)?)(:free|-free)?(?![\w./-])", text)
    if m:
        return (m.group(1) + (m.group(2) or "")).strip()
    return None


def _from_link(link: str) -> str | None:
    if not link:
        return None
    m = re.search(r"openrouter\.ai/([^?#\s]+)", link)
    if m:
        seg = m.group(1).strip("/")
        if seg and seg.lower() not in _NON_MODEL_SEGMENTS:
            return seg
    return None


def source_model_id(article: dict | None) -> str | None:
    """원본 항목(브리핑 news 행)에서 특정 모델 ID 를 추출한다.

    0단계 결과 반영: `original_title` 우선 → `title` → `description` → `link`.
    사고 항목(56082)처럼 **모델 ID 가 없는 항목은 None** 을 돌려준다
    (그 경우 규칙 1·3 은 발동하지 않고, 규칙 2 가 허위 실측을 잡는다).
    """
    if not article:
        return None
    for key in ("original_title", "title"):
        got = _from_title(article.get(key) or "")
        if got:
            return got
    got = _from_title(article.get("description") or "")
    if got:
        return got
    return _from_link(article.get("link") or "")


# ---------------------------------------------------------------- 본문에서 모델 ID
def mentioned_model_ids(text: str) -> list:
    """본문(마크다운)에 등장한 모델 ID. 백틱 표기만 신뢰한다.

    백틱을 쓰는 이유: 이 프로젝트의 글은 모델 ID 를 항상 `코드` 로 표기한다
    (PT JSON 변환 전 마크다운 기준 `"marks": ["code"]`).
    링크·경로(techcrunch.com/2026, application/json 등)를 오인하지 않으려면 백틱이 필수다.
    """
    if not text:
        return []
    out = []
    for m in _BACKTICK_MODEL_RE.finditer(text):
        out.append(m.group(1))
    for m in _BACKTICK_BARE_RE.finditer(text):
        out.append(m.group(1))
    # 중복 제거(정규화 키 기준 아님 — 원문 표기를 유지)
    seen = set()
    uniq = []
    for x in out:
        if x.lower() in seen:
            continue
        seen.add(x.lower())
        uniq.append(x)
    return uniq


# ---------------------------------------------------------------- 실행 기록
def evaluated_model_ids() -> set:
    """실측 실행 기록이 있는 모델(정규화 키). 캐시·리더보드·실행 로그 3곳을 모두 본다.

    TTL 은 보지 않는다 — 규칙 2 는 "발행된 수치의 근거가 있는가"를 따지며, 최신성은 별도 문제다.
    """
    keys = set()
    try:
        with CACHE_PATH.open(encoding="utf-8") as f:
            for mid in json.load(f).keys():
                keys |= model_match_keys(mid)
    except (OSError, ValueError):
        pass
    try:
        with LEADERBOARD_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        rows = data if isinstance(data, list) else data.get("ranked", [])
        for row in rows:
            mid = row.get("model_id") if isinstance(row, dict) else None
            if mid:
                keys |= model_match_keys(mid)
    except (OSError, ValueError):
        pass
    try:
        with RUNS_PATH.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                mid = row.get("model_id")
                if mid:
                    keys |= model_match_keys(mid)
    except OSError:
        pass
    return keys


# ---------------------------------------------------------------- 실측 주장
def quant_claims(text: str) -> list:
    """본문의 정량 실측 주장 목록. (근거 스니펫) 리스트."""
    if not text:
        return []
    out = []
    for rx in _QUANT_CLAIM_RES:
        for m in rx.finditer(text):
            start = max(0, m.start() - 120)
            ctx = text[start:m.end() + 120]
            if not _MEASURE_CONTEXT_RE.search(ctx):
                continue
            snippet = re.sub(r"\s+", " ", ctx).strip()
            out.append(snippet)
            break
    return out


# ---------------------------------------------------------------- 본 게이트
def check_attribution(title: str, body: str, article: dict | None = None,
                      used_model_id: str | None = None) -> list:
    """규칙 1·2·3 검사. 문제가 있으면 사유 문자열 리스트(게이트 issues 와 같은 형식)."""
    issues: list[str] = []
    text = f"{title or ''}\n{body or ''}"

    src_id = source_model_id(article)
    used = used_model_id or src_id

    # 규칙 1 — 원본 항목이 특정 모델이면 제목·본문에 그 ID 가 있어야 한다
    if src_id:
        mentioned = mentioned_model_ids(text)
        if not any(same_model(src_id, m) for m in mentioned):
            issues.append(
                f"모델 귀속 누락: 원본 항목의 모델 `{src_id}` 가 제목·본문에 없음 → "
                f"생성 입력에 모델 ID 를 명시하고 본문에도 반드시 `{src_id}` 를 쓸 것"
            )

    # 규칙 3 — 생성 시 사용한 모델 ID 와 원본 항목의 모델 ID 가 같아야 한다
    if used and src_id and not same_model(used, src_id):
        issues.append(
            f"모델명 불일치: 생성에 사용한 모델 `{used}` ≠ 원본 항목의 모델 `{src_id}` → "
            f"다른 모델 글이 될 위험"
        )

    # 규칙 2 — 정량 실측은 실행 기록이 있을 때만
    claims = quant_claims(text)
    if claims:
        mentioned = mentioned_model_ids(text)
        if mentioned:
            recorded = evaluated_model_ids()
            unrecorded = [m for m in mentioned
                          if not (model_match_keys(m) & recorded)]
            if len(unrecorded) == len(mentioned):
                issues.append(
                    "미실측 수치: 본문에 정량 실측 수치가 있지만 그 모델의 실행 기록이 없다 "
                    f"({', '.join(mentioned[:3])}) → 실측 섹션을 만들지 말 것 "
                    "(근거: model_eval 캐시·리더보드·실행 로그)"
                )
    return issues


if __name__ == "__main__":  # 자체 점검
    art = {"title": "[무료 LLM] flint-40b-free — OpenCode Zen 무료 티어",
           "original_title": "[무료 LLM] flint-40b-free — OpenCode Zen 무료 티어",
           "link": "https://openrouter.ai/flint-40b-free"}
    print("source_model_id:", source_model_id(art))
    print("evaluated:", sorted(evaluated_model_ids())[:5])
    print("mentioned:", mentioned_model_ids("`flint-40b-free` 와 `google/gemini-2.0-flash-exp:free`"))
