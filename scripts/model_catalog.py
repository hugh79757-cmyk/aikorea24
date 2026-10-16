#!/usr/bin/env python3
"""무료 LLM 모델 카탈로그 수집 · 스냅샷 · diff (AIK24-FREE-PIPE-01 작업 1·2)

매일 1회 실행해 `scripts/logs/model_catalog_YYYY-MM-DD.json` 에 **현재 무료로 쓸 수 있는**
모델만 저장하고, 어제 스냅샷과 비교해 `model_diff_YYYY-MM-DD.json` 에
added / removed / changed 를 남긴다.

수집 대상 4개 프로바이더:
  openrouter — https://openrouter.ai/api/v1/models 에서 id가 ':free' 로 끝나는 것 (키 불필요)
  kilo       — Kilo Gateway models API (작업 1 조사 결과 반영)
  nvidia     — NVIDIA NIM 무료 티어 (작업 1 조사 결과 반영)
  zen        — OpenCode Zen (작업 1 조사 결과 반영)

한 프로바이더가 죽어도 나머지는 진행한다(지시서 작업 1: "작업 중단 금지").
"""
import json
import os
import sys
import time
from pathlib import Path

import httpx

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts", "threads", "v3"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from model_router import load_env  # noqa: E402  (sys.path 삽입 후에만 import 가능)

CATALOG_DIR = PROJECT_DIR / "scripts" / "logs"
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"
KILO_MODELS = "https://api.kilo.ai/api/gateway/models"  # opencode.json 의 provider.kilo.options.baseURL
ZEN_MODELS = "https://opencode.ai/zen/v1/models"
NVIDIA_MODELS = "https://integrate.api.nvidia.com/v1/models"  # 키 불필요, 2026-10-14 실측 80개
HTTP_TIMEOUT = 30


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] [model_catalog] {msg}", flush=True)


def _row(provider, model_id, name, pricing=None, context_length=None):
    """스냅샷 원소. 없는 필드는 null (지시서 작업 1 출력 형식)."""
    return {
        "provider": provider,
        "model_id": model_id,
        "name": name or model_id,
        "pricing": pricing,
        "context_length": context_length,
    }


# --------------------------------------------------------------- 프로바이더


def fetch_openrouter():
    """무료(free variant) 모델 + 전체 id 집합.

    반환: (free_rows, all_ids) — all_ids 는 '무료→유료 전환' 판정에 쓴다
    (무료 variant가 사라졌는데 유료 variant가 남아 있으면 전환으로 본다).
    """
    r = httpx.get(OPENROUTER_MODELS, timeout=HTTP_TIMEOUT)  # API 키 불필요
    r.raise_for_status()
    rows, all_ids = [], set()
    for m in r.json().get("data", []):
        mid = m.get("id") or ""
        if not mid:
            continue
        all_ids.add(mid)
        if not mid.endswith(":free"):
            continue
        p = m.get("pricing") or {}
        try:
            pricing = {"prompt": float(p.get("prompt") or 0), "completion": float(p.get("completion") or 0)}
        except (TypeError, ValueError):
            pricing = None
        rows.append(_row("openrouter", mid, m.get("name"), pricing, m.get("context_length")))
    return rows, all_ids


def fetch_kilo():
    """Kilo Gateway 무료 모델.

    URL 은 `~/.config/opencode/opencode.json` 의 provider.kilo.options.baseURL
    (`https://api.kilo.ai/api/gateway`) 에서 확인했다. 인증 키 불필요(HTTP 200 동일).

    무료 판별은 `:free` 접미사가 아니라 **서버 측 `isFree` 플래그**를 쓴다 —
    접미사만 보면 4건을 놓치고, 가격 0 비교는 2건을 오탐한다(2026-10-14 실측).
    """
    r = httpx.get(KILO_MODELS, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    rows = []
    for m in r.json().get("data", []):
        if m.get("isFree") is not True:
            continue
        p = m.get("pricing") or {}
        try:  # 가격 문자열 포맷이 제각각("0", "0.000000000000")이라 float 변환이 필수
            pricing = {"prompt": float(p.get("prompt") or 0), "completion": float(p.get("completion") or 0)}
        except (TypeError, ValueError):
            pricing = None
        rows.append(_row("kilo", m.get("id"), m.get("name"), pricing, m.get("context_length")))
    return rows, {m.get("id") for m in r.json().get("data", []) if m.get("id")}


def fetch_zen():
    """OpenCode Zen 사용 가능 모델 중 무료.

    공식 문서 https://opencode.ai/docs/zen/ (리다이렉트 후 /v2/docs/console/models/) 에서
    무료 모델 12종을 확인하고, API 응답(`/v1/models`)에 존재하는 것만 포함한다.
    이는 접미사 규칙이 깨져도(예: big-pickle) 무료 목록을 정확히 반영하기 위함이다.
    대표님 원칙: 검증 불가한 항목은 억지로 넣지 않는다.
    """
    # API 응답에서 전체 ID 집합 가져오기
    r = httpx.get(ZEN_MODELS, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    api_ids = {m.get("id") for m in r.json().get("data", []) if m.get("id")}
    # 공식 무료 12종 (화이트리스트)
    ZEN_OFFICIAL_FREE = frozenset([
        "jev-1.13-free",
        "big-pickle",
        "space-bunny-free",
        "cat-jam-free",
        "longcat-2.5-preview-free",
        "step-5-preview-free",
        "exo-free",
        "mimo-v2.6-flash-free",
        "mimo-v2.5-free",
        "nemotron-3-ultra-free",
        "nemotron-3.5-lightning-free",
        "muse-spark-1.3-contributor-free",
    ])
    # 교집합: 공식 목록에 있고 API에 존재하는 모델만
    selected_ids = ZEN_OFFICIAL_FREE & api_ids
    rows = [_row("zen", model_id, model_id) for model_id in selected_ids]
    return rows, api_ids
def fetch_nvidia():
    """NVIDIA NIM — 신규 **감지만** 한다. 무료로 advertise 하지 않는다.

    2026-10-14 실측(PIPE-02 작업1): `https://integrate.api.nvidia.com/v1/models` 는
    80개 모델 id 를 주지만 per-model 키가 created/id/object/owned_by 4개뿐이라
    무료 티어 판별 필드가 없다. `?include=pricing`·`?free=true` 는 무시되고,
    `GET /v1/models/{id}` 는 404, build.nvidia.com 은 SPA 셸이고 `/pricing` 은 404다.
    즉 **API 로 무료 티어 판별 불가 + 공식 무료 모델 목록 URL 도 존재하지 않는다.**

    대표님 원칙("검증 불가한 항목은 억지로 넣지 않는다")에 따라:
      - `rows`(= 무료로 advertise 되는 목록)는 **빈 리스트**로 둔다.
      - `all_ids` 만 실측된 전체 id 집합으로 돌려줘서, NIM 에 새 모델이 올라오면
        detect_new_models.py 가 신규로 잡아 대표님 수동 테스트 대상이 되게 한다.
    shortcut: NIM 무료 티어는 모델 플래그가 아니라 키 크레딧 한도라 모델 단위로
    판별할 수 없다. NVIDIA 가 무료 목록을 공개하면 이 함수를 손봐라.
    """
    r = httpx.get(NVIDIA_MODELS, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    ids = {m.get("id") for m in r.json().get("data", []) if m.get("id")}
    return [], ids


PROVIDERS = {
    "openrouter": fetch_openrouter,
    "kilo": fetch_kilo,
    "nvidia": fetch_nvidia,
    "zen": fetch_zen,
}


# --------------------------------------------------------------- 수집 · diff


def collect():
    """전 프로바이더 수집. 실패한 프로바이더는 건너뛰고 reasons 에 사유를 남긴다.

    반환: (rows, all_ids_by_provider, failed_by_provider)
    """
    rows, all_ids, failed = [], {}, {}
    for name, fn in PROVIDERS.items():
        try:
            r, ids = fn()
        except Exception as e:  # 프로바이더 하나가 죽어도 나머지는 간다
            failed[name] = f"{type(e).__name__}: {e}"
            log(f"{name}: 실패 — {failed[name]}")
            continue
        rows.extend(r)
        all_ids[name] = ids
        log(f"{name}: {len(r)}건")
    return rows, all_ids, failed


def _key(row):
    return (row.get("provider"), row.get("model_id"))


def diff(prev_rows, cur_rows, all_ids=None):
    """어제 스냅샷 vs 오늘 스냅샷.

    added   — 오늘 새로 등장한 무료 모델 (row 그대로)
    removed — 어제 있었는데 오늘 없음. 사유는 '무료→유료 전환' 또는 '단종/제거'
    changed — 둘 다 있으나 pricing / context_length 가 바뀐 것
    """
    all_ids = all_ids or {}
    prev = {_key(r): r for r in prev_rows or []}
    cur = {_key(r): r for r in cur_rows or []}

    added = [cur[k] for k in cur if k not in prev]
    removed = []
    for k in prev:
        if k in cur:
            continue
        base = (k[1] or "").split(":")[0]
        reason = "무료→유료 전환" if base in all_ids.get(k[0] or "", ()) else "단종/제거"
        removed.append({**prev[k], "reason": reason})
    changed = []
    for k in prev:
        if k not in cur:
            continue
        for field in ("pricing", "context_length"):
            if prev[k].get(field) != cur[k].get(field):
                changed.append({
                    "provider": k[0], "model_id": k[1], "field": field,
                    "before": prev[k].get(field), "after": cur[k].get(field),
                })
    return {"added": added, "removed": removed, "changed": changed}


# --------------------------------------------------------------- 저장 · main


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def snapshot_path(day):
    return CATALOG_DIR / f"model_catalog_{day}.json"


def diff_path(day):
    return CATALOG_DIR / f"model_diff_{day}.json"


def latest_snapshot_before(day):
    """day 보다 앞선 가장 최근 스냅샷 경로. 없으면 None."""
    if not CATALOG_DIR.exists():
        return None
    snaps = sorted(p for p in CATALOG_DIR.glob("model_catalog_*.json") if p.name < f"model_catalog_{day}.json")
    return snaps[-1] if snaps else None


# 프로바이더 키 → news 테이블 source / 모델 목록 링크 (PIPE-03 작업 2)
NEWS_SOURCES = {
    "zen": ("OpenCode Zen", "https://opencode.ai/v2/docs/console/models/"),
    "openrouter": ("OpenRouter Free Models", "https://openrouter.ai/models?max_price=0"),
    "kilo": ("Kilo Free Models", "https://api.kilo.ai/api/gateway/models"),
    "nvidia": ("NVIDIA NIM Free", ""),
}


def _news_lit(v):
    """news_collector_v2.save() 의 lit() 과 동일한 이스케이프."""
    return "'" + str(v or "").replace("'", "''")[:500] + "'"


def record_diff_to_news(day, d):
    """diff 의 added/removed 를 news 테이블에 기록한다 (PIPE-03 작업 2).

    브리핑이 이 행들을 '무료 모델 변경' 슬롯으로 집어간다. 같은 날 이미 기록된
    model_id 는 건너뛴다. 반환값은 INSERT 한 건수.
    """
    rows = [("added", r) for r in (d.get("added") or [])] + [("removed", r) for r in (d.get("removed") or [])]
    rows = [(kind, r) for kind, r in rows if r.get("provider") in NEWS_SOURCES]
    if not rows:
        log("news 기록: added/removed 0건 — 스킵")
        return 0

    import cfnew  # 지연 import — D1 미접근 환경에서도 카탈로그 수집은 살아 있게

    cfnew.check_quota()
    sources = [v[0] for v in NEWS_SOURCES.values()]
    existing = cfnew.sql(
        "SELECT title FROM news WHERE DATE(created_at) = %s AND source IN (%s);"
        % (_news_lit(day), ", ".join(_news_lit(s) for s in sources)),
        database_id=cfnew.A24_DB,
    )
    seen = {r.get("title") for r in (existing or [])}
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    stmts = []
    for kind, r in rows:
        source, link = NEWS_SOURCES[r["provider"]]
        mid = r.get("model_id") or ""
        if kind == "added":
            title = f"[신규 무료] {mid} — {source} 무료 목록에 추가"
            tail = "추가"
        else:
            title = f"[제외] {mid} — {source} 무료 목록에서 제외"
            tail = "제외"
        if title in seen:
            continue
        seen.add(title)
        # news.link 는 UNIQUE — 같은 프로바이더의 행이 겹치면 INSERT OR IGNORE 가
        # 조용히 버린다(2026-10-16 실측: kilo added/removed 동시 발생 시 1건 유실).
        url = f"{link or 'https://aikorea24.kr/free-models'}#{mid}"
        stmts.append(
            "INSERT OR IGNORE INTO news "
            "(title, link, description, source, category, pub_date, source_url, original_title, country, v2_pass, v2_tag) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);" % (
                _news_lit(title[:200]), _news_lit(url),
                _news_lit(f"{source} 무료 목록에 {tail} · 12문항 평가 전 — 판단 보류"),
                _news_lit(source), _news_lit("AI"), _news_lit(now), _news_lit(url),
                _news_lit(mid), _news_lit("us"), 1, _news_lit("free-llm")))

    if not stmts:
        log("news 기록: 이미 기록된 항목만 — 스킵")
        return 0
    cfnew.sql(";\n".join(stmts), database_id=cfnew.A24_DB)
    log(f"news 기록: {len(stmts)}건 (무료 목록 변경 → free-llm)")
    return len(stmts)


def run(day=None):
    load_env()  # 프로젝트 .env / ~/.env.common 적재
    day = day or time.strftime("%Y-%m-%d")
    rows, all_ids, failed = collect()

    _write_json(snapshot_path(day), sorted(rows, key=lambda r: (r["provider"] or "", r["model_id"] or "")))

    prev = latest_snapshot_before(day)
    prev_rows = json.loads(prev.read_text(encoding="utf-8")) if prev else []
    d = diff(prev_rows, rows, all_ids)
    d["failed_providers"] = failed  # stdout 로만 남으면 다음 날 어떤 프로바이더가 죽었는지 알 수 없다
    _write_json(diff_path(day), d)

    # PIPE-03 작업 2: 변경 감지를 브리핑으로 잇는다 (실패해도 수집은 계속)
    try:
        record_diff_to_news(day, d)
    except Exception as e:  # noqa: BLE001 — 카탈로그 수집 job 을 죽이지 않는다
        log(f"[경고] news 기록 실패 (수집은 계속): {type(e).__name__}: {e}")

    log(f"스냅샷 {len(rows)}건 → {snapshot_path(day).name}")
    log(f"직전 스냅샷: {prev.name if prev else '없음(첫 실행)'}")
    log(f"diff — added {len(d['added'])} / removed {len(d['removed'])} / changed {len(d['changed'])}")
    if failed:
        log(f"[검증불가] 프로바이더 {len(failed)}건 수집 실패: {', '.join(failed)}")
    return {"snapshot": snapshot_path(day), "diff": diff_path(day), "counts": d, "failed": failed, "total": len(rows)}


if __name__ == "__main__":
    out = run(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps({k: (str(v) if isinstance(v, Path) else v) for k, v in out.items() if k != "counts"}, ensure_ascii=False, indent=2))