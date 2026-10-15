#!/usr/bin/env python3
"""무료 모델 리스트 페이지 갱신 · 신규 모델 평가·블로그 발행 (AIK24-FREE-PIPE-01 작업 3·4·5)

`model_catalog.py` 가 만든 오늘 스냅샷과 최근 diff, 모델 리더보드를 읽어
EmDash 고정 슬러그 페이지(free-models)를 **매일 같은 주소로** 갱신한다.

    python3 scripts/free_models_page.py page                 # 리스트 페이지 갱신
    python3 scripts/free_models_page.py page --dry-run       # 마크다운만 stdout
    python3 scripts/free_models_page.py evaluate --limit 1   # 신규 모델 평가 → 블로그 발행
    python3 scripts/free_models_page.py daily                # launchd 진입점 (수집→페이지→평가→링크확인→로그)

카드는 지시서 선정 규칙 그대로만 뽑는다 — ① 현재 무료 ② 리더보드 점수 상위
③ 동점이면 컨텍스트 길이. 무료 모델이 4개 미만이면 있는 만큼만, 채우지 않는다.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts", "threads", "v3"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from model_router import load_env  # noqa: E402

import model_catalog as mc  # noqa: E402
import model_eval  # noqa: E402

PAGE_SLUG = "free-models"
PAGE_URL = f"https://emdash.aikorea24.kr/posts/{PAGE_SLUG}"
CARD_LIMIT = 4
REVIEWS_PATH = mc.CATALOG_DIR / "model_reviews.json"
FAILED_PATH = mc.CATALOG_DIR / "model_eval_failed.json"
ZEN_PENDING_PATH = mc.CATALOG_DIR / "zen_pending.json"

# AIK24-PIPE-01(2026-10-14, 대표님 확정): 무료 모델 자동 평가를 끈다. CLI 라 평가가
# 주니어 머신에 묶여 서버 자동화가 불가해진 현실 + "수동 테스트 → 블로그 업데이트" 정책.
# 수동 평가 경로는 그대로 살아 있다: `python3 scripts/free_models_page.py evaluate --force`
# 또는 `python3 scripts/model_eval.py evaluate --model <id>`.
AUTO_EVAL_ENABLED = False
# 403/401/404 는 키로 접근이 안 되는 상태라 내일도 같다 → 영구 스킵 목록에 적는다.
# 429/타임아웃은 일시적이므로 적지 않는다(내일 다시 시도해야 한다).
PERMANENT_FAIL = ("401", "403", "404")
STATE_PATH = PROJECT_DIR / "docs" / "state.md"
PROVIDER_LABEL = {"openrouter": "OpenRouter", "kilo": "Kilo", "zen": "OpenCode Zen", "nvidia": "NVIDIA NIM"}
# 작업 5: 블로그 리뷰 글 말미에 리스트 페이지로 돌아가는 1줄.
BACKLINK = f"\n\n---\n\n[오늘의 무료 모델 목록 보기]({PAGE_URL})\n"

# EVAL-06: 새로운 데이터 소스 경로
CLI_MODELS_PATH = mc.CATALOG_DIR / "free_models_cli.json"
EXTERNAL_EVALS_PATH = mc.CATALOG_DIR / "external_evals.json"
# EVAL-07: 일일 호출 검증 결과 (호출 검증 시각 + 점검 중 목록)
VERIFY_PATH = mc.CATALOG_DIR / "free_models_verify.json"


def load_verify():
    """EVAL-07 검증 기록 로드. 없으면 빈 dict (페이지 나머지에는 영향 없음)."""
    v = _read_json(VERIFY_PATH, {})
    return v if isinstance(v, dict) else {}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] [free_models] {msg}", flush=True)


# --------------------------------------------------------------- 데이터 읽기 (EVAL-06 신규)


def load_cli_models():
    """EVAL-02 검증 모델 18개 로드 (free_models_cli.json)."""
    return _read_json(CLI_MODELS_PATH, [])


def load_external_evals():
    """EVAL-03 외부 평가 데이터 로드 (external_evals.json)."""
    return _read_json(EXTERNAL_EVALS_PATH, {})


def match_external_data(cli_models, external_evals):
    """CLI 모델에 외부 평가 데이터 결합.
    
    매칭 키:
    - retention: model name 기준 (mimo-v2.6-flash, space-bunny 등)
    - kilobench: rawName 기준 (Hy3, Nemotron 3 Super)
    - zen_policy: model_id 기준 (cat-jam-free, space-bunny-free 등)
    """
    retention_data = {}
    for item in external_evals.get("sources", {}).get("opencode_data", {}).get("retention", []):
        key = item.get("model")
        if key:
            retention_data[key] = item
    
    kilobench_data = {}
    for item in external_evals.get("sources", {}).get("kilobench", {}).get("free", []):
        key = item.get("model")
        if key:
            kilobench_data[key] = item
    
    zen_policy = {}
    for item in external_evals.get("sources", {}).get("zen_policy", {}).get("freeModels", []):
        key = item.get("model_id")
        if key:
            zen_policy[key] = item
    
    # CLI 모델에 매칭
    enriched = []
    for m in cli_models:
        mid = m.get("model_id", "")
        provider = m.get("provider", "")
        cli_id = m.get("cli_id", "")
        
        # retention 매칭용 키 생성
        retention_key = mid.replace(":free", "").replace("-free", "")
        # zen 모델은 opencode/ prefix 제거 후 -free 제거
        if provider == "zen":
            retention_key = mid.replace("-free", "")
        
        enriched_m = dict(m)
        
        # retention 데이터
        if retention_key in retention_data:
            r = retention_data[retention_key]
            enriched_m["retention_percent"] = r.get("retentionPercent")
            enriched_m["retention_eligible_weeks"] = r.get("eligibleUserWeeks")
        
        # kilobench 데이터
        if retention_key in kilobench_data:
            k = kilobench_data[retention_key]
            enriched_m["kilobench_completion"] = k.get("completionPercent")
            enriched_m["kilobench_cost"] = k.get("costUsdPerAttempt")
        
        # zen policy 데이터
        if mid in zen_policy:
            z = zen_policy[mid]
            enriched_m["zen_data_policy"] = z.get("dataPolicy")
            enriched_m["zen_trains_on_prompts"] = z.get("trainsOnPrompts")
        
        enriched.append(enriched_m)
    
    return enriched


# --------------------------------------------------------------- 기존 데이터 읽기


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def leaderboard_scores(qv):
    """{model_id: 최고 점수}. qv 가 다르면 문항이 달라 점수를 비교할 수 없다."""
    rows = _read_json(model_eval.LEADERBOARD_PATH, [])
    best = {}
    for r in rows if isinstance(rows, list) else []:
        if r.get("qv") != qv or not r.get("model_id"):
            continue
        prev = best.get(r["model_id"])
        if prev is None or (r.get("ts") or 0) >= (prev.get("ts") or 0):
            best[r["model_id"]] = r
    return best


def eval_labels():
    """{model_id: 평가 label 한 줄}. 카드의 '한 줄 판단' sourcedb."""
    rows = _read_json(model_eval.CACHE_PATH, {})
    # 캐시 엔트리 안의 키는 'model' 이 아니라 'model_id' 다 (캐시 키가 곧 model_id 라
    # dict 키를 신뢰한다 — 구 포맷 엔트리에는 model_id 가 없을 수 있으므로 엔트리 값을 본다).
    items = rows.items() if isinstance(rows, dict) else ((None, e) for e in rows)
    out = {}
    for mid, e in items:
        if not isinstance(e, dict) or not e.get("label"):
            continue
        out[e.get("model_id") or mid] = e["label"]
    return {k: v for k, v in out.items() if k}


def _fail_reason(res):
    """문항 실패 사유를 한 줄로. failures[{reason}] 을 우선 쓰고 없으면 빈 문자열."""
    reasons = [str((f or {}).get("reason") or "") for f in (res.get("failures") or [])]
    return "; ".join(sorted({r for r in reasons if r}))[:200]


def _is_permanent_fail(res):
    """전 문항 실패 + 사유가 401/403/404 → 내일도 같으므로 영구 스킵."""
    total, mx = res.get("failed") or 0, res.get("max_score") or 0
    if not (mx and total >= mx):
        return False
    return any(code in _fail_reason(res) for code in PERMANENT_FAIL)


def failed_models():
    """이 키로 접근 불가(403/401/404)로 확인된 모델. 카탈로그에 무료로 떠도 호출이 막히면
    매일 같은 모델을 다시 시도하며 평가 자원을 낭비하므로 영구 스킵 목록에 적는다."""
    if not FAILED_PATH.exists():
        return {}
    try:
        return json.loads(FAILED_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def mark_failed(mid, reason):
    d = failed_models()
    if mid in d:
        return
    d[mid] = {"reason": reason, "ts": mc.time.strftime("%Y-%m-%d")}
    FAILED_PATH.parent.mkdir(parents=True, exist_ok=True)
    FAILED_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[free_models] 접근 불가로 기록 — {mid} ({reason})")


def ctx_key(row):
    """정렬용 컨텍스트 길이. 미공개(null)는 0 이라 숫자 모델보다 뒤에 놓인다
    (AIK24-EVAL-ZEN-01 작업 3). null 끼리 동점이면 호출부의 모델 ID 정렬이 결정한다."""
    return row.get("context_length") or 0


def zen_pending():
    """{model_id: 사유}. Zen 은 평가 '실패'가 아니라 '경로 미확보'다 (작업 4)."""
    return _read_json(ZEN_PENDING_PATH, {})


def mark_zen_pending(mid, reason="OpenCode Zen — OpenRouter 경로 없음 · 호출 경로 미확보"):
    d = zen_pending()
    if mid in d:
        return
    d[mid] = {"reason": reason, "ts": mc.time.strftime("%Y-%m-%d")}
    mc._write_json(ZEN_PENDING_PATH, d)


def reviews():
    """{model_id: 발행된 심층 리뷰 URL}. 작업 4 가 발행 직후 기록한다."""
    v = _read_json(REVIEWS_PATH, {})
    return v if isinstance(v, dict) else {}


def pick_cards(rows, scores, labels, revs, limit=CARD_LIMIT):
    """지시서 작업 3 선정 규칙 ①②③. 통과한 모델이 없으면 빈 리스트(채우지 않는다)."""
    free = {r["model_id"]: r for r in rows if r.get("model_id")}
    cands = [(mid, r) for mid, r in free.items() if mid in scores]
    # 정렬 규칙(지시서 작업 3): ① 점수 상위 ② 동점이면 컨텍스트 긴 순(miss 는 0)
    #                            ③ 그것도 같으면 모델 ID 알파벳 순
    cands.sort(key=lambda t: (-scores[t[0]].get("score") or 0, -ctx_key(t[1]), t[0]))
    cards = []
    # EVAL-CLI-01: 카드마다 평가 경로(api/cli)와 실측 컨텍스트를 보여준다. 캐시 엔트리 하나를 재사용.
    cache = _read_json(model_eval.CACHE_PATH, {})
    for mid, r in cands[:limit]:
        ctx = r.get("context_length")
        ev = cache.get(mid) or {}
        mctx = ev.get("measured_context")
        pr = r.get("pricing") or {}
        term = mid.split("/")[0].split(":")[0].replace("-free", "").split(":")[0]
        cards.append({
            "model_id": mid,
            "name": r.get("name") or mid,
            "provider": r.get("provider"),
            "verdict": labels.get(mid) or "판정 없음 (평가는 다음 실행에서 채워집니다)",
            "spec": f"컨텍스트 {ctx:,} 토큰" if ctx else (
                f"≈컨텍스트 {mctx:,} 토큰 (실측)" if mctx else "컨텍스트 길이 미공개"),
            "source": ev.get("source") or "api",
            "price": "무료" if (pr.get("prompt") == 0 and pr.get("completion") == 0) else "가격 미공개",
            "usage": f"OpenCode에서 프로바이더를 {PROVIDER_LABEL.get(r.get('provider'), r.get('provider'))}로 하고 "
                     f"'{term}'를 검색하세요. (모델 ID: {mid})",
            "review": revs.get(mid),
            "score": scores[mid].get("score"),
            "max_score": scores[mid].get("max_score"),
        })
    return cards


def week_changes(days=7):
    """최근 N 일치 diff(added/removed/changed) 집계. 변경 0이면 그 사실을 그대로 쓴다."""
    today = datetime.now()
    rows, seen_added, seen_removed, changes = [], set(), set(), []
    for i in range(days):
        day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        d = _read_json(mc.diff_path(day), None)
        if not isinstance(d, dict):
            continue
        rows.append((day, len(d.get("added") or []), len(d.get("removed") or []), len(d.get("changed") or [])))
        for r in d.get("added") or []:
            seen_added.add(r.get("model_id"))
        for r in d.get("removed") or []:
            seen_removed.add(r.get("model_id"))
        for c in d.get("changed") or []:
            changes.append((day, c))
    total = sum(a + r + c for _, a, r, c in rows)
    return {"rows": rows, "added": sorted(x for x in seen_added if x),
            "removed": sorted(x for x in seen_removed if x),
            "changed": changes, "total": total, "days": days}


# --------------------------------------------------------------- 렌더링 (EVAL-06 신규)


def render_eval06(day, cli_models, wk, failed, verify=None):
    """EVAL-06 지시서에 따른 새 페이지 구조 렌더링.
        
    구조:
    1. 헤더: "무료 AI 모델" + 날짜 + 한 줄 설명
    2. 추천 모델 (Top 3): CLI 평가 점수 + 재사용률 결합
    3. 전체 리스트 (18개): 표 - 모델명, 프로바이더, 컨텍스트, 재사용률, KiloBench, 데이터 정책, 상태
    4. 제외된 모델: Hy3, Groq, Cerebras, NVIDIA NIM
    5. 방법론 (EVAL-07: 호출 검증 시각 + 점검 중)
    """
    verify = verify if verify is not None else load_verify()
    ts = datetime.strptime(day, "%Y-%m-%d")
    today_str = f"{ts.year}년 {ts.month}월 {ts.day}일"
    
    out = [
        f"# 무료 AI 모델 — {today_str}",
        "",
        "> OpenCode에서 실제 동작 확인된 무료 모델만 싣습니다.",
        "",
    ]
    
    # 2. 추천 모델 (Top 3) - retention_percent 높은 순으로 정렬, 평가 점수 있는 모델 우선
    scored_models = []
    for m in cli_models:
        mid = m.get("model_id", "")
        # 리더보드 점수 확인
        scores = leaderboard_scores(model_eval.EVAL_QUESTIONS_VERSION)
        score_info = scores.get(mid)
        retention = m.get("retention_percent")
        
        # 추천 점수 계산: retention(가중치 0.7) + 평가점수 정규화(가중치 0.3)
        rec_score = 0
        if retention is not None:
            rec_score += retention * 0.7
        if score_info and score_info.get("max_score", 0) > 0:
            rec_score += (score_info.get("score", 0) / score_info.get("max_score", 1)) * 100 * 0.3
        
        if retention is not None or score_info:
            m["_rec_score"] = rec_score
            scored_models.append(m)
    
    scored_models.sort(key=lambda x: -x.get("_rec_score", 0))
    top3 = scored_models[:3]
    
    if top3:
        out += ["## 추천 모델 (Top 3)", ""]
        for i, m in enumerate(top3, 1):
            mid = m.get("model_id", "")
            provider = m.get("provider", "")
            cli_id = m.get("cli_id", "")
            ctx = m.get("context_length")
            retention = m.get("retention_percent")
            kilobench = m.get("kilobench_completion")
            zen_policy = m.get("zen_data_policy")
            zen_trains = m.get("zen_trains_on_prompts")
            
            scores = leaderboard_scores(model_eval.EVAL_QUESTIONS_VERSION)
            score_info = scores.get(mid)
            
            # 추천 이유 생성
            reason_parts = []
            if score_info:
                s = score_info.get("score", 0)
                ms = score_info.get("max_score", 0)
                reason_parts.append(f"CLI 평가 {s}/{ms}문항")
            if retention is not None:
                reason_parts.append(f"재사용률 {retention:.1f}%")
            if kilobench is not None:
                reason_parts.append(f"KiloBench {kilobench:.1f}%")
            
            reason = " · ".join(reason_parts) if reason_parts else "데이터 부족"
            
            # 데이터 정책 경고
            warning = ""
            if zen_policy:
                if zen_trains:
                    warning = " ⚠️ **프롬프트가 학습에 사용됨**"
                else:
                    warning = " ✅ 제로-retention (프롬프트 학습 미사용)"
            elif provider in ("kilo", "openrouter"):
                warning = " ℹ️ provider 정책 확인 필요"
            
            out += [
                f"### {i}. {mid} ({PROVIDER_LABEL.get(provider, provider)})",
                "",
                f"- **추천 이유**: {reason}{warning}",
                f"- **컨텍스트**: {f'{ctx:,} 토큰' if ctx else '미공개'}",
                f"- **OpenCode 모델 ID**: `{cli_id}`",
                "",
            ]
    
    # 3. 전체 리스트 (18개) - 표
    out += ["## 전체 리스트 (18개 검증 모델)", ""]
    
    # 헤더: 컨텍스트 있는 것만 표시하라는 지시서에 따라 컬럼 동적 구성
    # 하지만 지시서: "없는 모델은 컬럼 값 비우지 말고 행에서 제외하거나 '—' 대신 아예 표시 안 함"
    # 해석: 컨텍스트가 없는 모델은 컨텍스트 컬럼을 아예 표시하지 않음
    # 전체 표에서는 모든 행 표시, 단 컨텍스트 없는 행은 빈 값 대신 "—" 금지, 아예 표시 안 함
    
    # 표 헤더 구성
    has_context = any(m.get("context_length") for m in cli_models)
    has_retention = any(m.get("retention_percent") is not None for m in cli_models)
    has_kilobench = any(m.get("kilobench_completion") is not None for m in cli_models)
    has_zen_policy = any(m.get("zen_data_policy") for m in cli_models)
    
    headers = ["모델명", "프로바이더"]
    if has_context:
        headers.append("컨텍스트 길이")
    if has_retention:
        headers.append("재사용률")
    if has_kilobench:
        headers.append("KiloBench")
    if has_zen_policy:
        headers.append("데이터 정책")
    headers.append("상태")
    
    out += ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    
    # 정렬: 컨텍스트 있는 것 먼저, 그 다음 재사용률 높은 순
    def sort_key(m):
        ctx = m.get("context_length") or 0
        ret = m.get("retention_percent") or 0
        return (-ctx, -ret)
    
    for m in sorted(cli_models, key=sort_key):
        mid = m.get("model_id", "")
        provider = m.get("provider", "")
        ctx = m.get("context_length")
        retention = m.get("retention_percent")
        kilobench = m.get("kilobench_completion")
        zen_policy = m.get("zen_data_policy")
        zen_trains = m.get("zen_trains_on_prompts")
        
        row = [f"`{mid}`", PROVIDER_LABEL.get(provider, provider)]
        if has_context:
            row.append(f"{ctx:,}" if ctx else "")
        if has_retention:
            row.append(f"{retention:.1f}%" if retention is not None else "")
        if has_kilobench:
            row.append(f"{kilobench:.1f}%" if kilobench is not None else "")
        if has_zen_policy:
            if zen_policy:
                policy_short = zen_policy[:60] + ("..." if len(zen_policy) > 60 else "")
                row.append(policy_short)
            else:
                row.append("")
        # 상태
        status_parts = ["현재 무료"]
        if zen_trains is True:
            status_parts.append("학습 사용")
        elif zen_trains is False:
            status_parts.append("학습 미사용")
        row.append(" · ".join(status_parts))
        
        out.append("| " + " | ".join(row) + " |")
    
    out.append("")
    
    # 4. 제외된 모델
    out += ["## 제외된 모델", ""]
    out += [
        "- **Hy3 (Tencent)**: KiloBench 47.6%로 점수는 좋으나 실제 서비스 안 됨 (Hy3는 무료 티어에서 사용 불가)",
        "- **Groq**: TPM 한도(8,000/min)로 opencode CLI에서 평가 불가 — `gpt-oss` 계열은 직접 API로는 작동하나 opencode 경유 시 요청 크기 초과",
        "- **Cerebras**: 카드 필수로 제외 확정",
        "- **NVIDIA NIM**: 무료 티어 없음 확인 (`GET /v1/models` 80개 중 `-free` 0개)",
        "- **openrouter 직접 경로 8종**: 21:24 이후 4회 연속 전량 타임아웃 — 경로 사용 불가 (kilo 경유로는 동일 모델 정상)",
        "",
        "> 제외 이유: 검증 불가한 항목은 억지로 넣지 않는다 (대표님 원칙 2). 빈 칸·'미확인'·추측 금지.",
        "",
    ]
    
    # 5. 방법론
    out += ["## 방법론", ""]
    out += [
        "- 모든 모델은 OpenCode CLI로 실제 호출해 동작을 확인했습니다 (`opencode run -m <model_id> \"한 단어로 대답: PONG\"`).",
        "- API 문서상 무료라도 실제 동작하지 않으면 제외합니다.",
        f"- 평가: 12문항 4축(지시이행·코딩실무·맥락유지·역할판단) CLI 평가, 리더보드 문항 세트 v{model_eval.EVAL_QUESTIONS_VERSION} 기준.",
        "- 재사용률: OpenCode Data (opencode.ai/data) — eligible user weeks 대비 retained user weeks 비율.",
        "- KiloBench: kilo.ai/kilobench 무료 모델 완주율.",
        "- 데이터 정책: OpenCode Zen 공식 문서 (opencode.ai/v2/docs/console/models/) — 제로-retention 여부.",
        "- 수집 시각: " + datetime.now().strftime('%Y-%m-%d %H:%M') + " · 수집 실패 프로바이더: " + (", ".join(failed) if failed else "없음"),
    ]
    # EVAL-07: 호출 검증 시각 + 점검 중 (FAIL 모델이 있을 때만)
    if verify.get("verified_at"):
        out += [f"- 호출 검증 시각: {verify['verified_at']} (KST)"]
    out += [""]

    fails = verify.get("fail") or []
    if fails:
        out += ["## 점검 중", ""]
        out += ["당일 호출 검증에 실패해 목록에서 제외된 모델입니다. 복구되면 다음 검증에서 복귀합니다.", ""]
        for f in fails:
            out += [f"- `{f.get('model_id') or f.get('cli_id')}` — {f.get('reason') or '호출 실패'}"]
        out += [""]

    return "\n".join(out)


# 기존 render 함수 (하위 호환용 유지)
def render(day, rows, cards, wk, scores, failed):
    ts = datetime.strptime(day, "%Y-%m-%d")
    out = [
        f"# 오늘의 무료 LLM 모델 — {ts.year}년 {ts.month}월 {ts.day}일 {datetime.now().hour}시 기준",
        "",
        f"OpenRouter · Kilo · OpenCode Zen 의 공개 목록에서 **무료로 표시된 모델 {len(rows)}개**를 긁어 모은 스냅샷입니다.",
        f"매일 갱신되며 새로 늘어난 모델은 아래 카드에, 빠진 모델은 '이번 주 변경'에 표시합니다.",
        "",
        "## 오늘의 OpenCode용 무료 모델 %d" % CARD_LIMIT,
        "",
    ]
    if not cards:
        out += [
            "> 아직 이 파이프라인의 12문항 평가를 통과한 무료 모델이 없습니다.",
            "> 카드는 평가 점수가 있는 모델만 오르며, 평가가 끝난 모델부터 채워집니다. 빈자리를 채우려고 모델을 임의로 고르지 않습니다.",
            "",
        ]
    for i, c in enumerate(cards, 1):
        out += [
            f"### {i}. {c['name']} (`{c['model_id']}`)",
            "",
            f"- **한 줄 판단** — {c['verdict']}",
            f"- **점수** — {c['score']}/{c['max_score']}문항 (리더보드 v{model_eval.EVAL_QUESTIONS_VERSION})"
            + (" · CLI 경유 평가" if c.get("source") == "cli" else ""),
            f"- **스펙** — {c['spec']} · 가격 {c['price']}",
            f"- **사용법** — {c['usage']}",
        ]
        if c["review"]:
            out.append(f"- **심층 리뷰** — [12문항 원답 공개 리뷰 보기]({c['review']})")
        out.append("")

    out += ["## 이번 주 변경", ""]
    if not wk["total"]:
        out += [f"오늘 변경 없음 (확인 시각 {datetime.now().strftime('%H:%M')}).", ""]
    else:
        out += ["| 날짜 | 추가 | 제거 | 변경 |", "|---|---|---|---|"]
        for d, a, r, c in wk["rows"]:
            if a or r or c:
                out.append(f"| {d} | {a} | {r} | {c} |")
        out += ["", f"최근 {wk['days']}일 합계 — 추가 {len(wk['added'])} · 제거 {len(wk['removed'])} · 변경 {len(wk['changed'])} (모델 ID 중복 제외 — 위 표는 날짜별 원 건수)", ""]
        if wk["removed"]:
            out += ["무료에서 빠진 모델:", ""] + [f"- `{m}`" for m in wk["removed"][:20]] + [""]
        if wk["changed"]:
            out += ["가격·컨텍스트 변경:", ""] + [f"- `{c.get('model_id')}` {c.get('field')} 변경" for _, c in wk["changed"][:20]] + [""]

    out += [
        "## 무료 모델 전체 목록 (컨텍스트 길이 순)",
        "",
        "| 프로바이더 | 모델 ID | 컨텍스트 |",
        "|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: -ctx_key(x)):  # 미공개는 0 → 맨 뒤
        ctx = f"{r['context_length']:,}" if r.get("context_length") else "미공개"
        out.append(f"| {PROVIDER_LABEL.get(r.get('provider'), r.get('provider'))} | `{r['model_id']}` | {ctx} |")
    out.append("")

    out += [
        "## 판정 기준",
        "",
        f"- 카드는 리더보드 **문항 세트 v{model_eval.EVAL_QUESTIONS_VERSION}** 로만 비교합니다. 문항이 바뀌면 점수를 비교하는 것 자체가 거짓말이라 순위를 초기화합니다.",
        "- 선정 순서는 ① 현재 무료 ② 평가 점수 상위 ③ 동점이면 컨텍스트 길이입니다. 4개가 안 나오면 있는 만큼만 씁니다.",
        "- 판정은 공개 API 응답의 무료 표기 기준입니다. 실제 과금은 provider 별 쿼터 정책이 따릅니다.",
        "",
        f"- 수집 시각 {datetime.now().strftime('%Y-%m-%d %H:%M')} · 수집 실패 프로바이더: "
        + (", ".join(failed) if failed else "없음"),
        "",
    ]
    return "\n".join(out)


# --------------------------------------------------------------- 실행


def cmd_page(day=None, dry_run=False):
    load_env()
    day = day or time.strftime("%Y-%m-%d")
    
    # EVAL-06: 새로운 데이터 소스 사용
    cli_models = load_cli_models()
    if not cli_models:
        log(f"CLI 검증 모델 없음: {CLI_MODELS_PATH} — free_models_cli.py 를 먼저 실행하세요")
        return 1
    
    external_evals = load_external_evals()
    cli_models = match_external_data(cli_models, external_evals)
    
    d = _read_json(mc.diff_path(day), {}) or {}
    wk = week_changes()
    
    # EVAL-06 새 렌더 함수 사용 (EVAL-07: 검증 기록 전달)
    verify = load_verify()
    md = render_eval06(day, cli_models, wk, list(d.get("failed_providers") or {}), verify)
    
    log(f"무료 모델 {len(cli_models)}개 / 이번 주 변경 {wk['total']}건")
    if dry_run:
        print(md)
        return 0
    import emdash_publish

    # title 을 slug 로 쓴다 — EmDash 는 title 을 slugify 해 slug 를 만들고 slug 필드를 받지 않는다.
    # 그래서 제목 대신 한국어 H1 은 본문 첫 줄(# …)이 화면에 뜬다.
    url = emdash_publish.upsert_post(PAGE_SLUG, PAGE_SLUG, md,
                                     excerpt=f"{day} 기준 무료 모델 {len(cli_models)}개")
    if not url:
        log("리스트 페이지 갱신 실패")
        return 1
    log(f"리스트 페이지 갱신 완료: {url}")
    return 0


def split_zen(added):
    """Zen 항목 분리 (AIK24-EVAL-ZEN-01 작업 4).

    model_eval 은 OpenRouter 전용이라 Zen 모델 ID 를 던지면 404 가 난다. 그건 "모델 실패"가
    아니라 "모델 부재"다. mark_failed 로 영구 차단하면 나중에 경로가 확보돼도 재평가할 수 없다.
    반환: (OpenRouter 로 평가할 항목들, zen 대기 대상 model_id 목록)
    """
    zen_ids = [
        t["model_id"] for t in added
        if t.get("provider") == "zen" and t["model_id"] not in model_eval.CLI_MODEL_MAP
    ]
    return [
        t for t in added
        if t.get("provider") != "zen" or t["model_id"] in model_eval.CLI_MODEL_MAP
    ], zen_ids


def cmd_evaluate(day=None, limit=1, dry_run=False):
    """added 중 상위 limit 건을 평가 → 8단 블로그 초안 → EmDash 발행 → 리뷰 URL 기록."""
    load_env()
    day = day or time.strftime("%Y-%m-%d")
    d = _read_json(mc.diff_path(day), {}) or {}
    snap = _read_json(mc.snapshot_path(day), []) or []
    free = {r.get("model_id") for r in snap}
    targets, zen_ids = split_zen([a for a in d.get("added") or [] if a.get("model_id") in free])
    for mid in zen_ids:
        mark_zen_pending(mid)
    # 이미 평가된 모델은 건너뛴다 (무료 티어 429 방지 — 지시서 작업 4)
    done = set(leaderboard_scores(model_eval.EVAL_QUESTIONS_VERSION))
    blocked = failed_models()
    todo = [t["model_id"] for t in targets if t["model_id"] not in done and t["model_id"] not in blocked]
    # 같은 모델 ID 가 여러 프로바이더 목록에 있으면 added 에 중복으로 들어온다 — 한 번만 평가한다.
    todo = list(dict.fromkeys(todo))
    todo.sort(key=lambda m: -next((ctx_key(r) for r in snap if r.get("model_id") == m), 0))
    todo = todo[:limit]
    if blocked:
        log(f"접근 불가 스킵 {len(blocked)}건: {', '.join(sorted(blocked)[:3])}")
    if not todo:
        log("평가 대상 없음 (added 중 미평가 0건)")
        return 0
    log(f"평가 대상 {len(todo)}건: {todo}")

    import blog_draft_generator as bdg

    rc = 0
    for mid in todo:
        try:
            if mid in model_eval.CLI_MODEL_MAP:
                # EVAL-CLI-01: CLI 경유 모델. 모델에 아예 도달 못 하면 점수 0을 남기지 않고 대기 사유만 갱신한다.
                res, blocked_reason = model_eval.eval_model_cli(mid)
                if blocked_reason:
                    mark_zen_pending(mid, blocked_reason)
                    log(f"{mid} — CLI 경유 실패 → 평가 대기: {blocked_reason}")
                    continue
                model_eval.cache_put(mid, res)
            else:
                res = model_eval.eval_model_cached(mid, force=True) or {}
            log(f"{mid} — {res.get('score')}/{res.get('max_score')}")
            if _is_permanent_fail(res):
                mark_failed(mid, _fail_reason(res))
            if dry_run:
                continue
            md = bdg.generate_model_eval_draft({}, {}, mid)  # article 가 None 이면 프롬프트 조립에서 .get() 이 죽는다
            if not md:
                log(f"{mid} — 초안 생성 실패(전 문항 실패)")
                rc = 1
                continue
            # 생성기는 YAML 프론트매터가 아니라 "TITLE: …\n---\n본문" 형식으로 돌려준다.
            # (본문 안에 '---' 가 있으면 split("---", 2) 의 두 번째 조각이 본문 앞부분이 되어
            #  제목이 통째로 사라진다 — 제목은 헤더 한 줄에서 직접 꺼낸다.)
            head, _, body = md.partition("---")
            title = head.strip().removeprefix("TITLE:").strip().strip("[]").strip()
            excerpt = _first_para(body)
            import emdash_publish

            body = body.strip() + BACKLINK  # 작업 5: 리스트 페이지로 돌아가는 링크
            revs = reviews()
            if mid in revs:  # 재발행이면 기존 슬러그를 그대로 물려받아 중복 글을 만들지 않는다
                slug = revs[mid].rstrip("/").split("/")[-1]
                url = emdash_publish.upsert_post(slug, title or mid, body, excerpt=excerpt)
            else:
                url = emdash_publish.publish_post(title or mid, body, excerpt=excerpt)
                revs[mid] = url
                mc._write_json(REVIEWS_PATH, revs)
            if not url:
                log(f"{mid} — 블로그 발행 실패")
                rc = 1
                continue
            log(f"{mid} — 발행 완료: {url}")
        except Exception as e:
            log(f"{mid} — 실패: {type(e).__name__}: {e}")
            rc = 1
    return rc


def cmd_daily(day=None, limit=1):
    """launchd 진입점 (지시서 작업 6 실행 순서).

    수집 → diff → 리스트 페이지 → (added 있으면) 평가·발행 → 상호 연결 확인 → state.md 로그.
    단계 실패는 다음 단계를 막지 않는다 — 하루치 파이프라인이 중간에 죽으면
    아무것도 안 갱신된 채 조용히 넘어가는 것보다 나쁘다.
    """
    day = day or time.strftime("%Y-%m-%d")
    steps = []

    try:
        out = mc.run(day)
        steps.append(f"수집 {out['total']}건 / 실패 프로바이더 {len(out['failed'])} / "
                     f"added {len(out['counts']['added'])} · removed {len(out['counts']['removed'])} · changed {len(out['counts']['changed'])}")
    except Exception as e:
        steps.append(f"수집 실패: {type(e).__name__}: {e}")

    try:
        rc = cmd_page(day)
        steps.append(f"리스트 페이지 {'갱신' if rc == 0 else '실패'} {PAGE_URL}")
    except Exception as e:
        steps.append(f"리스트 페이지 실패: {type(e).__name__}: {e}")

    # AIK24-PIPE-01: 자동 평가를 비활성화했다. CLI 특성상(주니어 Mac 필요) 서버 자동화가 불가해
    # 수동 평가로 전환. 여기서 True 로 되돌리면 다시 자동 평가가 돌아간다.
    # 수집(mc.run)과 리스트 페이지 갱신(cmd_page)은 계속 돈다 — 모델 리스트 파악은 하루 1회 유지.
    if AUTO_EVAL_ENABLED:
        try:
            steps.append(f"평가·발행 rc={cmd_evaluate(day, limit)}")
        except Exception as e:
            steps.append(f"평가 실패: {type(e).__name__}: {e}")
    else:
        steps.append("평가·발행 SKIP (AIK24-PIPE-01 자동 평가 비활성 — 수동 평가로 전환)")

    revs = reviews()
    steps.append(f"심층 리뷰 {len(revs)}건 (리스트 카드 링크 {sum(1 for u in revs.values())}건)")
    line = f"## {day} AIK24-FREE-PIPE-01 일일 실행 — " + " / ".join(steps)
    _prepend_state(line)
    log(line)
    return 0


def _prepend_state(line):
    """state.md 맨 위에 실행 로그 1줄 추가 (기존 내용은 삭제하지 않는다)."""
    try:
        old = STATE_PATH.read_text(encoding="utf-8") if STATE_PATH.exists() else ""
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(line + "\n\n" + old, encoding="utf-8")
    except Exception as e:
        log(f"state.md 기록 실패: {type(e).__name__}: {e}")


def _first_para(body):
    """본문 첫 문단 = 리뷰 요약(excerpt). 제목·목차 줄은 건너뛴다."""
    for line in (body or "").splitlines():
        s = line.strip()
        if not s or s.startswith(("#", ">", "-", "```", "|")):
            continue
        return s[:300]
    return None


def yaml_safe_load(text):
    try:
        import yaml

        return yaml.safe_load(text) or {}
    except Exception:
        return {}


if __name__ == "__main__":
    argv = sys.argv[1:]
    cmd = argv[0] if argv and not argv[0].startswith("-") else "page"
    rest = argv[1:] if cmd == argv[0:1][0] else argv
    # "--limit 3" 과 "--limit=3" 둘 다 받아야 한다. space 형태를 못 읽으면 limit 이 조용히 1 이 된다.
    flags, _i = {}, 0
    while _i < len(rest):
        _a = rest[_i]
        if "=" in _a:
            _k, _v = _a.split("=", 1)
            flags[_k] = _v
        elif _a.startswith("--") and _i + 1 < len(rest) and not rest[_i + 1].startswith("--"):
            flags[_a] = rest[_i + 1]
            _i += 1
        else:
            flags[_a] = True
        _i += 1
    day = flags.get("--day") if isinstance(flags.get("--day"), str) else None
    if cmd == "page":
        sys.exit(cmd_page(day, bool(flags.get("--dry-run"))))
    elif cmd == "evaluate":
        lim = flags.get("--limit")
        sys.exit(cmd_evaluate(day, int(lim) if isinstance(lim, str) else 1, bool(flags.get("--dry-run"))))
    elif cmd == "daily":
        lim = flags.get("--limit")
        sys.exit(cmd_daily(day, int(lim) if isinstance(lim, str) else 1))
    else:
        print(__doc__)
        sys.exit(2)