"""v2 큐레이션 판정 모듈 (AIK24-NEWS-01).

"한국인 초보자가 오늘 무료로 쓸 수 있는 것인가?" 기준.

원칙: `scripts/briefing_scorer.py` 의 `_score_free_usability()` +
`_penalty_excluded_topic()` 로직을 가져온 공용 모듈. **원본은 수정하지 않는다**
(브리핑 파이프라인 회귀 방지 — 지시서 Step 2).
"""

from __future__ import annotations

import json
import os

# AIK24-PIPE-13: 파라미터 규모 추출·실행 가능성 판정은 briefing_scorer 와 동일 로직.
# (구현을 한 곳에 두고 v2_filter 는 그대로 가져온다 — 중복 방지)
from briefing_scorer import (  # noqa: E402
    _OPEN_WEIGHT_KEYWORDS,
    extract_param_scale_b,
    is_open_weight,
    is_runnable_scale,
)

_WEIGHTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "impact_weights.json",
)

_TAG_LABELS = {"free-llm": "무료 LLM", "opensource": "오픈소스", "tool": "실전 도구"}

# 소스 기반 태그 힌트 (지시서 Step 2-2)
_FREE_SOURCES = {"openrouter free models", "openrouter",
                 "opencode zen", "kilo free models", "nvidia nim free"}
_OSS_SOURCES = {"huggingface trending", "huggingface blog"}

# 2026-11-06 대표님 지시: "무료 LLM으로 개발하는 개발자를 위한 사이트" — 큐레이션 통과율이
# 1~3%(하루 1~5건)로 너무 낮아 브리핑이 일반 뉴스로 메워지고 있었다. 개발자 신호가
# 2개 이상이면 통과시키고, 무료 신호 최소 점수도 4점으로 낮춘다(기존: 0점 초과).
_DEV_STRONG = (
    "github", "오픈소스", "open source", "open-source", "opensource", "오픈 웨이트",
    "open weight", "가중치 공개", "weights released", "ollama", "llama.cpp", "gguf",
    "양자화", "quantization", "파인튜닝", "fine-tuning", "huggingface", "hugging face",
    "vllm", "lm studio", "self-host", "self host", "로컬 실행", "sdk", "cli", "쿡북", "cookbook",
)
_DEV_WEAK = ("api", "가이드", "guide", "개발자", "developer", "튜토리얼", "tutorial",
             "library", "라이브러리", "예제", "로컬", "local", "코드")
MIN_FREE_SCORE = 4        # 무료 신호 최소 점수 (완화: 기존 >0)
MIN_WEAK_SIGNALS = 2      # 약한 개발 신호 2개면 통과


def _weights() -> dict:
    with open(_WEIGHTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _free_score(text: str, cfg: dict) -> tuple[int, list[str]]:
    """briefing_scorer._score_free_usability 와 동일 로직 (AIK24-PIPE-13 조건부)."""
    kw = cfg.get("keywords", {})
    t = (text or "").lower()
    matched = [k for k in kw if k in t]
    runnable_max_b = cfg.get("runnable_max_b", 32)
    scale_b = extract_param_scale_b(text)
    runnable = is_runnable_scale(scale_b, runnable_max_b)
    open_weight = is_open_weight(text)
    if open_weight and not runnable:
        matched = [k for k in matched if k not in _OPEN_WEIGHT_KEYWORDS]
    return min(cfg.get("cap", 25), sum(kw[k] for k in matched)), matched


def _excluded(text: str, cfg: dict, free_hits: list[str]) -> tuple[int, list[str]]:
    """briefing_scorer._penalty_excluded_topic 와 동일 로직 (AIK24-PIPE-13 조건부)."""
    t = (text or "").lower()
    hard = [k for k in cfg.get("hard_exclude", []) if k in t]
    if hard:
        return cfg.get("penalty", -100), hard
    soft = [k for k in cfg.get("launch_soft", []) if k in t]
    # AIK24-PIPE-13: 실행 불가 오픈 웨이트는 free_hits가 있어도 launch_soft 면제하지 않는다.
    runnable_max_b = 32
    # weights 에서 runnable_max_b 를 가져오려면 cfg 가 excluded_topic cfg 이므로 weights 전체가 필요.
    # v2_filter.classify 는 weights 전체를 w 로 들고 있으므로 _excluded 호출 시 전달받지 않는다.
    # 여기서는 config 를 직접 읽어 일관성을 유지한다.
    try:
        import json, os
        wpath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "impact_weights.json")
        w = json.load(open(wpath, encoding="utf-8"))
        runnable_max_b = w.get("free_usability", {}).get("runnable_max_b", 32)
    except Exception:
        runnable_max_b = 32
    scale_b = extract_param_scale_b(text)
    runnable = is_runnable_scale(scale_b, runnable_max_b)
    nonrunnable_openweight = is_open_weight(text) and not runnable
    if soft and (not free_hits or nonrunnable_openweight):
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
    low = text.lower()
    strong = [k for k in _DEV_STRONG if k in low]
    weak = [k for k in _DEV_WEAK if k in low]
    dev_ok = bool(strong) or len(weak) >= MIN_WEAK_SIGNALS
    # 2026-11-06 완화: 출시성 기사(launch_soft)라도 개발자 신호가 있으면 통과 후보로 남긴다.
    # (기존엔 '공개했습니다'·'발표했습니다' 한 마디로 전부 -100 → 통과율 1~3%.)
    penalty, _ = _excluded(text, w.get("excluded_topic", {}), hits + strong + weak)
    if penalty < 0:
        return False, None

    s = (source or "").strip().lower()
    is_oss_src = s in _OSS_SOURCES
    is_free_src = s in _FREE_SOURCES

    # 통과 조건 (2026-11-06 완화):
    #  ① 무료 신호 점수 ≥ MIN_FREE_SCORE, 또는 ② 무료 모델 소스, 또는
    #  ③ 개발자 신호(강 1개 / 약 2개 이상) — 개발자용 사이트 목적에 맞는 기사.
    # 기존에는 free_score > 0 만 봐서 통과율이 1~3%였다.
    if (free_score < MIN_FREE_SCORE and not is_free_src and not is_oss_src and not dev_ok):
        return False, None

    if is_free_src or any("무료" in k or "free" in k for k in hits):
        return True, "free-llm"
    if (is_oss_src
            or any(k in hits for k in ("open source", "open-source", "opensource", "open weights"))
            or any(k in strong for k in ("오픈소스", "open source", "open-source", "opensource",
                                         "오픈 웨이트", "open weight", "huggingface", "hugging face",
                                         "가중치 공개", "ollama", "llama.cpp"))):
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