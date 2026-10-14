#!/usr/bin/env python3
"""AIK24-EVAL-03 — 외부 평가 데이터 수집.

우리 CLI 평가만으로는 공신력에 한계가 있어 외부 검증 신호를 모은다.
대표님 확정 원칙: **검증 가능한 것만**, 검증 불가한 항목은 억지로 넣지 않는다,
그리고 **토큰 점유율처럼 "무료라서 많이 씀"과 "좋아서 많이 씀"이 섞인 지표는 제외**.

소스 3개 (전부 공개 HTTP, D1 미사용):
  1. OpenCode Data  — https://opencode.ai/data/index.json 의 `weeklyRetention` 만 쓴다.
     dailyTokens / dailyUniqueUsers / marketShare / countries 는 토큰 점유율이라 불채택.
  2. KiloBench      — https://kilo.ai/kilobench 표에서 `(free)` + `$0.00` 행만.
  3. OpenCode Zen   — 무료 모델 목록과 데이터 정책(프롬프트 학습 사용 여부).
     https://opencode.ai/docs/zen/ 는 302 로 /v2/docs/console/models/ 에 착지한다.

출력: scripts/logs/external_evals.json

작업3 — 결합 규칙 (AIK24-EVAL-03)
  `combine()` 이 네 신호를 모델별로 묶어 `combined.models[]` 로 저장한다.
  신호별 임계값(상수로 고정): eval 비율 ≥ 0.6 / retention ≥ 50% / kilobench ≥ 40%.
    - `eval`      — 우리 CLI 12문항 점수. scripts/logs/model_eval_cache.json 에서 읽는다.
    - `retention` — OpenCode Data 주간 재사용률(%). "다음 주에도 다시 쓴 비율"이라
                    토큰 점유율과 달리 "좋아서 씀"에 가깝다.
    - `kilobench` — KiloBench completion(%). 무료($0) 행만.
    - `zen`       — 무료 여부·데이터 정책. **품질 신호가 아니라 판정 투표에 넣지 않는다.**
  판정: 데이터가 있는 신호가 전부 임계값을 넘으면 `강한 추천`(2개 이상) 또는 `추천 (…단일 신호)`,
        전부 미달이면 `비추천`, 섞이면 `신호 불일치 (<낮은 신호> 낮음)`.
  지시서 ③: **데이터가 없는 항목은 표시하지 않는다.** 신호가 하나도 없는 모델은
        `combined.models[]` 에서 아예 빠지고, zen 단독 항목은 `verdict` 키 자체를 만들지 않는다
        (빈 칸·"미확인" 을 만들지 않는다).
  매칭: 소스마다 표기가 달라 `normalize_model()` 로 맞춘다. 안 붙는 표기(예: KiloBench `Hy3`)는
        외부 신호 단독으로 남긴다 — 억지로 붙이지 않는다.

데이터 구조:
  {"fetchedAt": str,
   "sources": {"opencode_data": {"url","updatedAt","temporalCoverage","excluded","retention":[…]},
               "kilobench":     {"url","free":[…]},
               "zen_policy":    {"url","freeModels":[…]}},
   "combined": {"thresholds": {...}, "models": [{"model","signals":{…}[,"verdict"]}]}}
"""
import html
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

LOG_DIR = Path(__file__).resolve().parent / "logs"
OUT_PATH = LOG_DIR / "external_evals.json"

OPENCODE_DATA_URL = "https://opencode.ai/data/index.json"
KILOBENCH_URL = "https://kilo.ai/kilobench"
ZEN_DOCS_URL = "https://opencode.ai/docs/zen/"
HTTP_TIMEOUT = 60
UA = "Mozilla/5.0"  # 없으면 opencode.ai 가 403 을 준다(2026-10-14 실측)


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def _get(url):
    return httpx.get(url, timeout=HTTP_TIMEOUT, follow_redirects=True,
                     headers={"User-Agent": UA})


def _text(h):
    """태그 제거한 평문. 표/문장 추출용."""
    h = re.sub(r"<script.*?</script>", " ", h, flags=re.S)
    h = re.sub(r"<style.*?</style>", " ", h, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def fetch_opencode_data():
    """주간 재사용률. 토큰 점유율 지표는 대표님 원칙에 따라 담지 않는다."""
    r = _get(OPENCODE_DATA_URL)
    r.raise_for_status()
    d = r.json()
    ret = []
    for e in d.get("weeklyRetention") or []:
        m = e.get("model")
        if not m or e.get("retentionPercent") is None:
            continue  # 검증 가능한 값이 없으면 항목을 넣지 않는다
        ret.append({
            "model": m,
            "name": e.get("name") or m,
            "page": e.get("page"),
            "retentionPercent": e.get("retentionPercent"),
            "eligibleUserWeeks": e.get("eligibleUserWeeks"),
            "retainedUserWeeks": e.get("retainedUserWeeks"),
        })
    return {
        "url": OPENCODE_DATA_URL,
        "updatedAt": d.get("updatedAt"),
        "temporalCoverage": "2026-08-20/2026-10-14",
        "retention": ret,
        "excluded": "dailyTokens·dailyUniqueUsers·marketShare·countries — 토큰 점유율은 "
                    "'무료라서 많이 씀'과 '좋아서 많이 씀'이 섞여 해석 불가(대표님 원칙)",
    }


def fetch_kilobench():
    """KiloBench 표에서 무료($0.00) 행만. 유료 모델 점수는 우리 관심사가 아니다."""
    r = _get(KILOBENCH_URL)
    r.raise_for_status()
    free = []
    for tr in re.findall(r"<tr.*?</tr>", r.text, flags=re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", " ", c)) for c in
                 re.findall(r"<t[dh].*?</t[dh]>", tr, flags=re.S)]
        cells = [re.sub(r"\s+", " ", c).strip() for c in cells]
        if len(cells) < 4:
            continue
        raw = cells[1]
        cost = cells[3]
        if "(free)" not in raw.lower() or "$0.00" not in cost:
            continue
        # 모델명 괄호 접미사 제거: (free) / (retires Oct 31) / (50% off) / ($$$$)
        model = re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip()
        pct = re.search(r"([\d.]+)\s*%", cells[2])
        free.append({
            "model": model,
            "rawName": raw,
            "completionPercent": float(pct.group(1)) if pct else None,
            "costUsdPerAttempt": 0.0,
        })
    return {"url": KILOBENCH_URL, "free": free}


# Zen 무료 모델의 데이터 정책 — /v2/docs/console/models/#privacy 의 예외 문단을 그대로 옮긴 것.
# 여기 없는 무료 모델은 "제로-retention, 학습 미사용"(기본 정책)이다.
ZEN_TRAIN_EXCEPTIONS = {
    "big-pickle": "무료 기간 중 수집 데이터를 모델 개선에 사용",
    "exo-free": "무료 기간 중 수집 데이터를 모델 개선에 사용",
    "mimo-v2.6-flash-free": "무료 기간 중 수집 데이터를 모델 개선에 사용",
    "mimo-v2.5-free": "무료 기간 중 수집 데이터를 모델 개선에 사용",
    "nemotron-3-ultra-free": "NVIDIA 무료 엔드포인트 — 시험용. 로그가 NVIDIA 제품 개선에 사용됨",
    "nemotron-3.5-lightning-free": "NVIDIA 무료 엔드포인트 — 시험용. 로그가 NVIDIA 제품 개선에 사용됨",
    "muse-spark-1.3-contributor-free": "프롬프트·완성을 Meta 미래 모델 학습에 사용하는 조건의 할인",
    "cat-jam-free": "학습 미사용. 안전 목적으로 30일 보관",
}


def fetch_zen_policy():
    """무료 모델 목록 + 데이터 정책. 이름이 `-free` 로 끝나지 않는 무료 모델도 잡는다."""
    r = _get(ZEN_DOCS_URL)
    r.raise_for_status()
    t = _text(r.text)
    # Endpoints 표는 "모델명  model-id  https://opencode.ai/inference/..." 3연속 형태다.
    pairs = re.findall(
        r"([A-Za-z0-9][A-Za-z0-9 .\-]{1,40}?)\s+([a-z0-9][a-z0-9.\-]{2,40})\s+"
        r"(https://opencode\.ai/inference/\S+)", t)
    seen, free = set(), []
    for name, mid, endpoint in pairs:
        if mid in seen:
            continue
        seen.add(mid)
        is_free = mid.endswith("-free") or mid in ZEN_TRAIN_EXCEPTIONS
        if not is_free:
            continue
        note = ZEN_TRAIN_EXCEPTIONS.get(mid)
        free.append({
            "model_id": mid,
            "name": name.strip(),
            "endpoint": endpoint,
            "dataPolicy": note or "제로-retention · 프롬프트 학습 미사용(기본 정책)",
            "trainsOnPrompts": bool(note and mid != "cat-jam-free"),
        })
    return {"url": str(r.url), "freeModels": free}


# --------------------------------------------------------------- 작업3: 결합

EVAL_CACHE_PATH = LOG_DIR / "model_eval_cache.json"

# 임계값 — 이 선을 넘으면 "좋다"로 본다. 데이터가 없으면 판정하지 않는다.
EVAL_RATIO_MIN = 0.6      # 우리 CLI 12문항 중 60% 이상
RETENTION_MIN = 50.0      # 주간 재사용률(%) 50 이상
KILOBENCH_MIN = 40.0      # KiloBench completion(%) 40 이상


def normalize_model(name):
    """소스마다 모델명 표기가 달라 결합 키를 맞춘다.

    검증된 매칭(2026-10-14 실측): space-bunny-free→space-bunny,
    mimo-v2.6-flash-free→mimo-v2.6-flash.
    안 붙는 것도 있다 — KiloBench 의 `Hy3`·`Nemotron 3 Super` 는 Zen 표기와
    어긋나 외부 신호 단독으로 남는다. 억지로 붙이지 않는다(대표님 원칙).
    """
    s = (name or "").strip().lower()
    s = re.sub(r"[:/-]free$", "", s)          # openrouter `:free` / zen `-free`
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)    # kilobench `(free)`·`(50% off)`
    s = re.sub(r"[^a-z0-9.]+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-")


def combine(sources):
    """우리 평가 + 재사용률 + KiloBench + Zen 정책을 모델별로 묶어 종합 판정.

    지시서 작업3 규칙:
      ① CLI 평가 점수 + 재사용률 + KiloBench 점수 → 종합 신뢰도
      ② 신호가 일치하면 강한 추천, 어긋나면 어느 신호가 낮은지 표시
      ③ 데이터가 없는 항목은 표시하지 않는다 — 신호가 하나도 없는 모델은 결과에서 뺀다
         (빈 칸·"미확인" 을 만들지 않는다). zen 단독 항목은 품질 신호가 없으므로
         verdict 키를 아예 넣지 않는다.
    """
    by = {}
    for r in (sources.get("opencode_data") or {}).get("retention") or []:
        by.setdefault(normalize_model(r.get("model")), {})["retention"] = {
            "percent": r.get("retentionPercent"),
            "name": r.get("name"),
            "eligibleUserWeeks": r.get("eligibleUserWeeks"),
        }
    for k in (sources.get("kilobench") or {}).get("free") or []:
        by.setdefault(normalize_model(k.get("model")), {})["kilobench"] = {
            "completionPercent": k.get("completionPercent"),
            "costUsdPerAttempt": k.get("costUsdPerAttempt"),
            "name": k.get("rawName"),
        }
    for z in (sources.get("zen_policy") or {}).get("freeModels") or []:
        by.setdefault(normalize_model(z.get("model_id")), {})["zen"] = {
            "model_id": z.get("model_id"),
            "name": z.get("name"),
            "dataPolicy": z.get("dataPolicy"),
            "trainsOnPrompts": z.get("trainsOnPrompts"),
        }

    cache = {}
    try:
        cache = json.loads(EVAL_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        cache = {}  # 캐시가 없으면 eval 신호만 빠진다 — 나머지 신호는 그대로 쓴다
    for mid, ev in (cache or {}).items():
        if not isinstance(ev, dict) or not ev.get("max_score"):
            continue
        by.setdefault(normalize_model(mid), {})["eval"] = {
            "model_id": mid,
            "score": ev.get("score"),
            "max_score": ev.get("max_score"),
            "source": ev.get("source") or "api",
            "provider": ev.get("provider"),
        }

    models = []
    for key in sorted(by):
        sig = by[key]
        if not sig:
            continue
        votes = []  # (신호이름, 좋은가) — 데이터가 있는 신호만 투표한다
        if "eval" in sig and sig["eval"]["max_score"]:
            votes.append(("eval", sig["eval"]["score"] / sig["eval"]["max_score"] >= EVAL_RATIO_MIN))
        if "retention" in sig and sig["retention"]["percent"] is not None:
            votes.append(("retention", sig["retention"]["percent"] >= RETENTION_MIN))
        if "kilobench" in sig and sig["kilobench"]["completionPercent"] is not None:
            votes.append(("kilobench", sig["kilobench"]["completionPercent"] >= KILOBENCH_MIN))
        entry = {"model": key, "signals": sig}
        if votes:
            if all(v for _, v in votes):
                entry["verdict"] = "강한 추천" if len(votes) >= 2 else f"추천 ({votes[0][0]} 단일 신호)"
            elif not any(v for _, v in votes):
                entry["verdict"] = "비추천"
            else:
                low = [n for n, v in votes if not v]
                entry["verdict"] = f"신호 불일치 ({', '.join(low)} 낮음)"
        models.append(entry)

    return {
        "thresholds": {"evalRatioMin": EVAL_RATIO_MIN,
                       "retentionMin": RETENTION_MIN,
                       "kilobenchMin": KILOBENCH_MIN},
        "models": models,
    }


def main():
    out = {"fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "sources": {}}
    rc = 0
    for key, fn in (("opencode_data", fetch_opencode_data),
                    ("kilobench", fetch_kilobench),
                    ("zen_policy", fetch_zen_policy)):
        try:
            out["sources"][key] = fn()
            n = len(out["sources"][key].get("retention")
                    or out["sources"][key].get("free")
                    or out["sources"][key].get("freeModels") or [])
            log(f"{key}: {n}건")
        except Exception as e:  # 소스 하나가 죽어도 나머지는 간다
            out["sources"][key] = {"error": f"{type(e).__name__}: {e}"}
            log(f"{key}: 실패 — {out['sources'][key]['error']}")
            rc = 1
    out["combined"] = combine(out["sources"])
    log(f"combined: {len(out['combined']['models'])}건")
    os.makedirs(LOG_DIR, exist_ok=True)
    tmp = str(OUT_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, str(OUT_PATH))  # 원자적
    log(f"→ {OUT_PATH}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
