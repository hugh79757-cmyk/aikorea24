"""v2 큐레이션 판정 모듈 (AIK24-NEWS-01).

"한국인 초보자가 오늘 무료로 쓸 수 있는 것인가?" 기준.

원칙: `scripts/briefing_scorer.py` 의 `_score_free_usability()` +
`_penalty_excluded_topic()` 로직을 가져온 공용 모듈. **원본은 수정하지 않는다**
(브리핑 파이프라인 회귀 방지 — 지시서 Step 2).
"""

from __future__ import annotations

import json
import os

_WEIGHTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "impact_weights.json",
)

_TAG_LABELS = {"free-llm": "무료 LLM", "opensource": "오픈소스", "tool": "실전 도구"}

# 소스 기반 태그 힌트 (지시서 Step 2-2)
_FREE_SOURCES = {"openrouter free models", "openrouter"}
_OSS_SOURCES = {"huggingface trending", "huggingface blog"}


def _weights() -> dict:
    with open(_WEIGHTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _free_score(text: str, cfg: dict) -> tuple[int, list[str]]:
    """briefing_scorer._score_free_usability 와 동일 로직."""
    kw = cfg.get("keywords", {})
    t = (text or "").lower()
    matched = [k for k in kw if k in t]
    return min(cfg.get("cap", 25), sum(kw[k] for k in matched)), matched


def _excluded(text: str, cfg: dict, free_hits: list[str]) -> tuple[int, list[str]]:
    """briefing_scorer._penalty_excluded_topic 와 동일 로직."""
    t = (text or "").lower()
    hard = [k for k in cfg.get("hard_exclude", []) if k in t]
    if hard:
        return cfg.get("penalty", -100), hard
    soft = [k for k in cfg.get("launch_soft", []) if k in t]
    if soft and not free_hits:
        return cfg.get("penalty", -100), soft
    return 0, []


def classify(title: str, description: str = "", source: str = "") -> tuple[bool, str | None]:
    """뉴스 1건의 v2 통과 여부와 태그를 반환.

    Returns:
        (False, None)          — 제외 대상(펀딩·기업 전략·무료 신호 없는 출시성)
        (True,  "free-llm")    — 무료 LLM
        (True,  "opensource")  — 오픈소스
        (True,  "tool")        — 그 외 통과분
    """
    w = _weights()
    text = f"{title or ''}\n{description or ''}"

    free_score, hits = _free_score(text, w.get("free_usability", {}))
    penalty, _ = _excluded(text, w.get("excluded_topic", {}), hits)
    if penalty < 0:
        return False, None

    s = (source or "").strip().lower()
    is_oss_src = s in _OSS_SOURCES
    is_free_src = s in _FREE_SOURCES

    # 통과 조건: 무료 사용 신호가 있거나 오픈소스 소스다.
    # (지시서 Step 2 — "무료 benefits 노출 / 기업·펀딩류 미노출". 점수 0 은 통과 아님.)
    if free_score <= 0 and not is_oss_src:
        return False, None

    if is_free_src or any("무료" in k or "free" in k for k in hits):
        return True, "free-llm"
    if is_oss_src or any(k in hits for k in ("open source", "open-source", "opensource", "open weights")):
        return True, "opensource"
    return True, "tool"


def tag_label(tag: str | None) -> str:
    """DB v2_tag → 페이지 표시명."""
    return _TAG_LABELS.get(tag or "", "")


if __name__ == "__main__":  # 자체 점검 (인메모리, 시크릿 무관)
    cases = [
        ("앤트로픽 스타트업, 초보자 무료 티어 확대", "무료 티어 확대", "The Decoder", True, "free-llm"),
        ("OpenAI releases free GPT-5 mini for all users", "open weights available", "OpenRouter Free Models", True, "free-llm"),
        ("디오 임플란트 AI 생태계 확산", "기업 전략 논의", "The Decoder", False, None),
        ("Acme raises $50M Series B to expand AI platform", "funding round", "TechCrunch", False, None),
        ("HuggingFace releases new open-source embedding model", "open source weights", "HuggingFace Trending", True, "opensource"),
        ("GitHub Copilot 튜토리얼 10가지", "tutorial cookbook", "GitHub", True, "tool"),
    ]
    bad = 0
    for t, d, s, exp_pass, exp_tag in cases:
        got = classify(t, d, s)
        ok = got[0] == exp_pass and got[1] == exp_tag
        bad += not ok
        print(("ok  " if ok else "FAIL"), got, "| expected", (exp_pass, exp_tag), "|", t[:44])
    raise SystemExit(1 if bad else 0)