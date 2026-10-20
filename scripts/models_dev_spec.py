#!/usr/bin/env python3
"""AIK24-PIPE-05/06 — models.dev 카탈로그 스펙 조회.

무료 모델 글에 실어야 하는 사실(모델명·컨텍스트·최대 출력·입출력 비용·모달리티·
도구 호출·제공 경로·같은 이름의 유료 모델)을 **카탈로그 원본에서** 뽑는다.
LLM 이 지어내지 못하게 숫자를 프롬프트에 그대로 주입하는 용도.

카탈로그는 1회 호출로 전체를 받는다(api.json) — 143건 글 작성에서 매번 호출하지
않도록 로컬 캐시를 쓴다(TTL 12시간).

사용:
    from models_dev_spec import catalog, model_spec, free_routes, paid_siblings
    cat = catalog()
    spec = model_spec(cat, "opencode", "minimax-m3.1-flash-free")
"""
import json
import os
import time
import urllib.request
from pathlib import Path

API = "https://models.dev/api.json"
CACHE_PATH = Path(__file__).resolve().parent / "logs" / "models_dev_cache.json"
TTL_SEC = 12 * 3600
UA = {"User-Agent": "curl/8.0"}

# news.source → models.dev provider id
SOURCE_TO_PROVIDER = {
    "OpenCode Zen": "opencode",
    "Kilo Free Models": "kilo",
    "NVIDIA NIM Free": "nvidia",
    "OpenRouter Free Models": "openrouter",
}
# provider → OpenCode 설정 접두어
PROVIDER_PREFIX = {
    "opencode": "opencode",
    "kilo": "kilo",
    "nvidia": "nvidia",
    "openrouter": "openrouter",
}
FREE_SUFFIXES = (":free", "-free")


def _strip_free(model_id):
    for suf in FREE_SUFFIXES:
        if model_id.endswith(suf):
            return model_id[: -len(suf)]
    return model_id


def _core(model_id):
    """provider/org 접두사를 뗀 모델 핵심 이름 (같은 모델 판별용)."""
    m = _strip_free(model_id or "").lower()
    return m.split("/")[-1]


def fetch(force=False):
    """models.dev api.json 원본. 실패하면 None."""
    try:
        if not force and CACHE_PATH.exists():
            age = time.time() - CACHE_PATH.stat().st_mtime
            if age < TTL_SEC:
                return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    try:
        req = urllib.request.Request(API, headers=UA)
        with urllib.request.urlopen(req, timeout=45) as r:
            data = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        print("  ⚠️ models.dev 조회 실패: %s: %s" % (type(e).__name__, str(e)[:120]))
        return None
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return data


def catalog(force=False):
    """provider → models dict."""
    data = fetch(force=force)
    if not data:
        return {}
    return {pid: (p.get("models") or {}) for pid, p in data.items() if isinstance(p, dict)}


def model_spec(cat, provider, model_id):
    """provider 안의 model_id 스펙 dict. 없으면 None."""
    return (cat.get(provider) or {}).get(model_id)


def resolve_model(cat, provider, model_id):
    """news.original_title 로 카탈로그 스펙을 찾는다. 형태가 바뀌어도 같은 모델이면 매칭.

    Returns: (spec, matched_id) — 매칭 실패 시 (None, None)
      예: news 행의 "stepfun/step-5-preview-free" 와 카탈로그의
          "stepfun-ai/step-5-preview:free" 는 다른 표기지만 같은 모델이다.
    """
    models = (cat or {}).get(provider) or {}
    if model_id in models:
        return models[model_id], model_id
    core = _core(model_id)
    for mid, spec in (models or {}).items():
        if _core(mid) == core:
            return spec, mid
    # 다른 제공자까지 확장해서 찾는다 (제공 경로 표기만 바뀐 경우)
    for pid, pmodels in (cat or {}).items():
        for mid, spec in (pmodels or {}).items():
            if _core(mid) == core:
                return spec, mid
    return None, None


def free_routes(cat, provider, model_id):
    """같은 모델의 무료 제공 경로 목록.

    Returns: [{"provider","model_id","cli_id","context","output","input_cost","output_cost"}]
    """
    core = _core(model_id)
    out = []
    for pid, models in (cat or {}).items():
        for mid, spec in (models or {}).items():
            if _core(mid) != core:
                continue
            cost = spec.get("cost") or {}
            if cost.get("input") != 0 or cost.get("output") != 0:
                continue
            lim = spec.get("limit") or {}
            out.append({
                "provider": pid,
                "model_id": mid,
                "cli_id": "%s/%s" % (PROVIDER_PREFIX.get(pid, pid), mid),
                "context": lim.get("context") or 0,
                "output": lim.get("output") or 0,
                "input_cost": cost.get("input"),
                "output_cost": cost.get("output"),
            })
    out.sort(key=lambda r: r["provider"])
    return out


def paid_siblings(cat, provider, model_id, limit=4):
    """같은 이름의 유료 모델 (접미사만 다른 짝). 접미사를 떼면 유료로 넘어가는 위험.

    Returns: [{"model_id","cli_id","input_cost","output_cost"}]
    """
    models = (cat or {}).get(provider) or {}
    base = _strip_free(model_id or "")
    out = []
    for mid, spec in models.items():
        if mid == model_id:
            continue
        if _strip_free(mid) != base:
            continue
        cost = spec.get("cost") or {}
        if cost.get("input") == 0 and cost.get("output") == 0:
            continue
        out.append({
            "model_id": mid,
            "cli_id": "%s/%s" % (PROVIDER_PREFIX.get(provider, provider), mid),
            "input_cost": cost.get("input"),
            "output_cost": cost.get("output"),
        })
        if len(out) >= limit:
            break
    return out


def spec_facts(cat, provider, model_id):
    """글 프롬프트에 넣을 사실 dict. 확인 불가 항목은 None (지어내지 않게)."""
    spec, matched = resolve_model(cat, provider, model_id)
    if not spec:
        return None
    cost = spec.get("cost") or {}
    lim = spec.get("limit") or {}
    mod = spec.get("modalities") or {}
    return {
        "model_id": matched or model_id,
        "requested_id": model_id,
        "provider": provider,
        "name": spec.get("name") or (matched or model_id),
        "context": lim.get("context") or 0,
        "output": lim.get("output") or 0,
        "input_cost": cost.get("input"),
        "output_cost": cost.get("output"),
        "cache_read_cost": cost.get("cache_read"),
        "input_modalities": mod.get("input") or [],
        "output_modalities": mod.get("output") or [],
        "tool_call": spec.get("tool_call"),
        "reasoning": spec.get("reasoning"),
        "attachment": spec.get("attachment"),
        "last_updated": (spec.get("last_updated") or spec.get("release_date") or "")[:10],
        "cli_id": "%s/%s" % (PROVIDER_PREFIX.get(provider, provider), matched or model_id),
        "catalog_url": "https://models.dev/%s/%s" % (provider, matched or model_id),
    }
