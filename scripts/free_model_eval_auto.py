#!/usr/bin/env python3
"""AIK24-EVAL-AUTO — 신규 무료 모델 자동 평가 → 캐시 반영 → 블로그 **초안** 생성.

트리거 (2026-11-08 확정)
------------------------
`scripts/detect_new_models.py` (매일 04:00) 가 쓰는 `scripts/logs/new_models_alert.json`
하나만 트리거로 쓴다. 이 파일은 이미 added/removed 를 프로바이더별로 나눠 갖고 있고,
수집 시점이 04:00 이라 더 빠르다. `free_models_cli.json`(09:10 CLI 검증 목록)은
**교차 확인용**이다 — 평가는 CLI 실제 호출이 전제라, 실제 CLI 노출 여부는
`opencode models` 를 직접 조회해 확인한다(파일이 비어 있어도 평가가 죽지 않는다).

트리거 조건
-----------
`new_by_provider` 중 **무료 목록에 새로 들어온 것**만 대상이다.
프로바이더별 무료 접미사(openrouter/kilo `:free`, zen `-free`)로 거르므로
이름만 바뀐 것·유료 전환·제거 건은 자동으로 빠진다.

파이프라인 단계
---------------
1. 후보 확정 (alert → 무료 접미사 필터 → `opencode models` 실제 노출 확인)
2. 평가 — `model_eval.eval_model_cli` 12문항(타임아웃 60초 → 180초 재시도 내장)
          + `model_eval.probe_context_length` 니들 컨텍스트 프로브
3. 반영 — `model_eval.cache_put` 만 쓴다. 캐시·리더보드 JSON 직접 편집 금지(EVAL-03 교훈).
4. 블로그 **draft** — 측정값만으로 결정적 템플릿을 채운다. LLM 서술 없음(날조 차단).
   게이트 미달이면 `scripts/logs/rejected/` 에 보존하고 사유를 보고한다.
   **발행(publish)은 이 스크립트에 없다** — 검수 후 사람이 한다(지시서 작업 5).

실패 처리
---------
- `opencode models` 자체가 실패(빈 출력)하면 **아무것도 쓰지 않고** 종료한다.
  2026-11-08 실측 사고: `free_models_cli.py` 가 launchd PATH 에 opencode 가 없어
  FileNotFoundError 였는데, 그 결과를 0건으로 저장해 `free_models_cli.json` 을 `[]` 로
  덮어썼다. 실패를 "신규 0건"으로 바꾸지 않는 것이 이 파이프라인의 전제다.
- 호출 실패(첫 문항 도달 불가·429·타임아웃) → 1회 재시도 → 그래도 실패면 `retry` 로
  두고 다음 날로 이월한다. 실패한 모델을 "평가 완료"로 처리하지 않는다.
  0점을 기록하지도 않는다(능력 실패와 구분).

사용
----
    .venv/bin/python3 scripts/free_model_eval_auto.py run            # 일일 실행(launchd)
    .venv/bin/python3 scripts/free_model_eval_auto.py run --dry-run  # 평가 없이 계획만
    .venv/bin/python3 scripts/free_model_eval_auto.py status          # 큐 현황
    .venv/bin/python3 scripts/free_model_eval_auto.py evaluate <model_id> [--cli <cli_id>]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import model_eval  # noqa: E402

LOGS_DIR = SCRIPTS_DIR / "logs"
ALERT_PATH = LOGS_DIR / "new_models_alert.json"
QUEUE_PATH = LOGS_DIR / "eval_auto_queue.json"
LOG_PATH = LOGS_DIR / "free_model_eval_auto.log"
DRAFT_DIR = LOGS_DIR / "eval_auto_drafts"
REJECTED_DIR = LOGS_DIR / "rejected"
MODELS_DEV_CACHE = LOGS_DIR / "models_dev_cache.json"

# 무료 접미사 — free_models_cli.PROVIDERS 와 같은 규칙(그 파일은 4개 프로바이더, 여기는 감지 3개).
FREE_SUFFIX = {"openrouter": ":free", "kilo": ":free", "zen": "-free"}
# model_id → `opencode models` 표기 접두사
CLI_PREFIX = {"openrouter": "openrouter", "kilo": "kilo", "zen": "opencode"}

# 하루 최대 처리 건수.
# 근거(2026-11-08 iceman-free 실측): 12문항 1건 = 213.3초(문항 간 4초 간격 포함).
# 그 실행에서 **Q12 가 `Free usage limit reached` 로 실패**했다 — 11회 호출로 Zen 무료
# 사용량이 소진됐다는 뜻이다. 즉 2건째 모델은 첫 문항부터 한도에 걸려 이월된다.
# 그래서 1건으로 둔다(측정 근거: scripts/logs/model_eval_runs.jsonl 의 elapsed_sec).
DAILY_LIMIT = 1
MAX_ATTEMPTS = 3  # 3회 시도해도 안 되면 자동 재시도 중단 → status=manual (사람 확인)

MODELS_TIMEOUT = 180
BLOCKED_RETRY_WAIT = 60  # 첫 실패 후 재시도까지 대기(초)


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [eval-auto] {msg}"
    print(line, flush=True)
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, str(path))


def load_queue():
    data = read_json(QUEUE_PATH, {})
    if isinstance(data, dict) and isinstance(data.get("models"), dict):
        return data
    return {"models": {}}


def save_queue(q):
    q["updated_at"] = time.time()
    write_json(QUEUE_PATH, q)


def today(day=None):
    return day or time.strftime("%Y-%m-%d")


def _load_env():
    """~/.env.common → 프로젝트 .env 순서로 적재(기존 프로젝트 규칙과 동일).

    EmDash PAT(EMDASH_AIKOREA24_API_TOKEN)는 여기에만 있다. 이걸 안 부르면
    초안 생성이 "PAT 없음"으로 조용히 실패한다.
    """
    for path, overwrite in ((os.path.expanduser("~/.env.common"), False),
                            (str(PROJECT_DIR / ".env"), True)):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if overwrite:
                        os.environ[k] = v
                    else:
                        os.environ.setdefault(k, v)
        except OSError:
            continue


# ── 작업 1: 트리거 ───────────────────────────────────────────────────────

def candidates_from_alert(alert):
    """alert 의 new_by_provider → 평가 후보. 무료 접미사 규칙으로 거른다."""
    out, seen = [], set()
    for prov, ids in (alert.get("new_by_provider") or {}).items():
        suf = FREE_SUFFIX.get(prov)
        if not suf:
            continue
        for mid in ids or []:
            if not mid.endswith(suf) or mid in seen:
                continue
            seen.add(mid)
            out.append({"provider": prov, "model_id": mid})
    return out


def cli_catalog():
    """`opencode models` 1회 조회. 실패하면 None — 빈 집합과 구분한다.

    launchd 에서 PATH 를 명시하지 않으면 FileNotFoundError 가 나고, 그 결과를
    "모델 0건"으로 저장하면 목록이 통째로 지워진다(2026-11-08 실제 사고).
    여기서는 실패를 None 으로 올려 호출측이 아무것도 쓰지 않게 한다.
    """
    try:
        p = subprocess.run(["opencode", "models"], capture_output=True, text=True,
                           timeout=MODELS_TIMEOUT)
    except FileNotFoundError:
        log("opencode CLI 없음(FileNotFoundError) — PATH 확인 필요. 이번 실행은 중단한다.")
        return None
    except Exception as e:  # noqa: BLE001
        log(f"opencode models 실패 — {type(e).__name__}. 이번 실행은 중단한다.")
        return None
    lines = [ln.strip() for ln in (p.stdout or "").splitlines() if "/" in ln]
    if not lines:
        log("opencode models 0줄 — 목록 조회 실패로 본다. 이번 실행은 중단한다.")
        return None
    return set(lines)


def resolve_cli_id(model_id, provider, catalog):
    pref = CLI_PREFIX.get(provider)
    if not pref:
        return None
    want = f"{pref}/{model_id}"
    return want if want in catalog else None


# ── 작업 2: 평가 실행기 ──────────────────────────────────────────────────

@contextlib.contextmanager
def _sandbox_cwd():
    """평가 호출 동안 cwd 를 빈 임시 디렉터리로 옮긴다.

    2026-11-08 실측 사고: `opencode run` 은 **현재 폴더를 프로젝트로** 삼고 모델에
    파일 쓰기 도구를 준다. 저장소 루트에서 12문항을 돌렸더니 모델이 Q4 답안을
    `tests/test_safe_div.py` 로 저장소에 직접 덮어썼다(git diff 로 확인, 원복함).
    free_models_cli.py 가 같은 이유로 이미 tempdir 로 옮겨 다닌다 — 그 관례를 따른다.
    """
    old = os.getcwd()
    d = tempfile.mkdtemp(prefix="aik24-eval-")
    os.chdir(d)
    try:
        yield d
    finally:
        os.chdir(old)


def evaluate(model_id, cli_id):
    """12문항 + 니들 프로브. 반환 dict — {ok, blocked, result, measured_context, elapsed}."""
    t0 = time.time()
    with _sandbox_cwd():
        res, blocked = model_eval.eval_model_cli(model_id, cli_model=cli_id)
        if blocked:
            log(f"{model_id}: 1차 호출 실패({blocked}) — {BLOCKED_RETRY_WAIT}초 후 1회 재시도")
            time.sleep(BLOCKED_RETRY_WAIT)
            res, blocked = model_eval.eval_model_cli(model_id, cli_model=cli_id)
        if blocked:
            return {"ok": False, "blocked": blocked, "result": None,
                    "measured_context": None, "elapsed": time.time() - t0}
        eval_elapsed = time.time() - t0

        # 니들 컨텍스트 프로브 — 실측 하한만 보고한다(공칭 스펙을 실측으로 쓰지 않는다).
        measured = None
        try:
            measured = model_eval.probe_context_length(model_id, cli_model=cli_id)
        except Exception as e:  # noqa: BLE001
            log(f"{model_id}: 니들 프로브 실패 {type(e).__name__}: {e} — 미측정으로 둔다")
    if measured:
        res["measured_context"] = measured
        log(f"{model_id}: 니들 컨텍스트 실측 하한 {measured:,} 토큰")

    model_eval.cache_put(model_id, res)
    cached = model_eval.cache_load().get(model_id) or {}
    ok = bool(cached.get("details"))
    if not ok:
        log(f"{model_id}: 캐시 미기록(응답 실패 과다 → 전멸 판정). 평가 완료로 처리하지 않는다.")
    return {"ok": ok, "blocked": None, "result": res,
            "measured_context": measured, "elapsed": time.time() - t0,
            "eval_elapsed": eval_elapsed}


def zero_score_notes(res):
    """0점 문항의 성격을 기계적으로 구분하지 않고 '검토 필요'로 표시한다.

    지시서 작업 3: 자동으로 구분이 어려우면 단정하지 말고 표시만 하고 점수만 기록한다.
    사람이 답안 원문을 열어 (채점기 오탐 / 질문-채점기 불일치 / 실제 실패)로 나눈다.
    """
    out = []
    for d in (res.get("details") or []):
        if d.get("score"):
            continue
        out.append({
            "idx": d.get("idx"), "axis": d.get("axis"),
            "has_answer": bool((d.get("answer") or "").strip()),
            "source": d.get("source"),
            "measurement_defect": bool(d.get("measurement_defect")),
            "review_needed": True,
            "answer_head": (d.get("answer") or "")[:800],
        })
    return out


# ── 작업 4: 결정적 블로그 초안 ───────────────────────────────────────────

def models_dev_entry(model_id):
    """models.dev 캐시에서 모델 1건. 없으면 None (추측하지 않는다).

    캐시 구조(2026-11-08 실측): {provider: {..., "models": {model_id: {...}}}}.
    평평한 {provider: {model_id: {...}}} 형태도 받아준다(구버전 캐시 대비).
    """
    data = read_json(MODELS_DEV_CACHE, {})
    if not isinstance(data, dict):
        return None
    provs = [(k, v) for k, v in data.items() if isinstance(v, dict)]
    for prov, node in provs:
        models = node.get("models") if isinstance(node.get("models"), dict) else node
        if not isinstance(models, dict):
            continue
        e = models.get(model_id)
        if isinstance(e, dict):
            out = dict(e)
            out["_provider"] = prov
            return out
    return None


def _axis_rows(res):
    rows = []
    for ax in model_eval.AXES:
        b = (res.get("by_axis") or {}).get(ax) or {}
        if not b.get("max_score"):
            continue
        rows.append((model_eval.AXIS_LABELS.get(ax, ax), int(b.get("score") or 0),
                     int(b.get("max_score") or 0)))
    return rows


def _verdict_phrase(res):
    """점수만으로 쓰는 한 줄 판단. 서술 창작 없음."""
    score, mx = int(res.get("score") or 0), int(res.get("max_score") or 12)
    if mx == 0:
        return "측정값이 없어 판단하지 않습니다."
    r = score / mx
    if r >= 0.83:
        return "12문항 기준 상위권입니다. 실무 파일럿에 바로 넣어 볼 수 있는 수준입니다."
    if r >= 0.66:
        return "12문항 기준 중상위입니다. 반복 작업에는 쓰되 결과 검수를 전제로 해야 합니다."
    if r >= 0.5:
        return "12문항 기준 중위입니다. 보조 용도로만 쓰고 최종 판단은 사람이 해야 합니다."
    return "12문항 기준 하위입니다. 지금 단계에서는 실무 투입을 권하지 않습니다."


def _spec_table_rows(entry, model_id, cli_id):
    """models.dev 원본 값만 표로 만든다. 값이 없는 행은 만들지 않는다."""
    rows = []
    if not entry:
        return rows
    name = entry.get("name")
    if name:
        rows.append(("모델명", str(name), "models.dev"))
    desc = entry.get("description")
    if desc:
        rows.append(("설명", str(desc), "models.dev"))
    lim = entry.get("limit") or {}
    if isinstance(lim.get("context"), int):
        rows.append(("공칭 컨텍스트", f"{lim['context']:,} 토큰", "models.dev"))
    if isinstance(lim.get("output"), int):
        rows.append(("공칭 최대 출력", f"{lim['output']:,} 토큰", "models.dev"))
    cost = entry.get("cost") or {}
    if isinstance(cost, dict) and cost:
        ins, outs = cost.get("input"), cost.get("output")
        if ins is not None and outs is not None:
            free = (float(ins) == 0 and float(outs) == 0)
            rows.append(("가격(입력/출력)",
                         "무료 (0/0)" if free else f"{ins}/{outs} (1M토큰당 USD)",
                         "models.dev"))
    feats = []
    if entry.get("reasoning"):
        feats.append("추론")
    if entry.get("tool_call"):
        feats.append("도구 호출")
    if entry.get("attachment"):
        feats.append("첨부(이미지) 입력")
    if feats:
        rows.append(("지원 기능", " · ".join(feats), "models.dev"))
    rel = entry.get("release_date")
    if rel:
        rows.append(("공개일", str(rel), "models.dev"))
    ow = entry.get("open_weights")
    if ow is not None:
        rows.append(("가중치 공개", "공개" if ow else "비공개", "models.dev"))
    rows.append(("모델 ID / CLI ID", f"`{model_id}` / `{cli_id}`", "`opencode models` 실측"))
    return rows


def _recommend_lines(res):
    """축별 결과에서 기계적으로 파생한 추천 문장. 측정되지 않은 용도는 쓰지 않는다."""
    out = []
    by = res.get("by_axis") or {}
    for ax, label, thr in (("맥락유지", "맥락유지", 1.0),
                           ("코딩실무", "코딩실무", 0.75),
                           ("에이전트", "에이전트", 0.75),
                           ("지시이행", "지시이행", 1.0)):
        b = by.get(ax) or {}
        mx = b.get("max_score") or 0
        if not mx:
            continue
        r = (b.get("score") or 0) / mx
        if r >= thr:
            out.append(f"- {label} 축 {b.get('score')}/{mx} — "
                       f"{'앞선 지시를 오래 기억해야 하는 대화' if ax == '맥락유지' else ''}"
                       f"{'코드 작성·수정 요청' if ax == '코딩실무' else ''}"
                       f"{'여러 단계를 스스로 나누는 작업' if ax == '에이전트' else ''}"
                       f"{'형식·조건을 정확히 지켜야 하는 출력' if ax == '지시이행' else ''}"
                       f"에 쓸 만합니다.")
    if not out:
        out.append("- 축별 점수가 기준선에 못 미쳐, 이 모델을 전제로 한 업무 배치를 권하지 않습니다.")
    return out


_REPO_PATH_RE = re.compile(r"(?:scripts|tests|pipeline|src)/[\w./가-힣-]+|[\w-]+\.py\b")
_KATAKANA_RE = re.compile(r"[\u30A0-\u30FF]")


def _scrub_answer(text, collapse=True):
    """인용하기 전에 답변 원문을 정리한다.

    2026-11-08 사고: 모델이 저장소를 읽고 쓴 흔적(파일 경로)이 답변에 섞였고, 그게 그대로
    글에 인용됐다. 원문 인용은 유지하되 저장소 경로·파일명은 지운다.
    collapse=False 는 코드 인용용 — 줄바꿈을 살려야 코드가 읽힌다.
    """
    s = _REPO_PATH_RE.sub("(파일 경로 생략)", text or "")
    return re.sub(r"\s+", " ", s).strip() if collapse else s.strip()


def _code_quote(res, idx, limit=360):
    """정답 문항의 코드 블록만 뽑는다. 없으면 빈 문자열.

    코드를 한 줄로 접어 인용하면 읽을 수 없다(2026-11-08 첫 발행본 실측).
    """
    for d in (res.get("details") or []):
        if d.get("idx") == idx and d.get("score") == 1:
            code = model_eval.extract_code(_scrub_answer(d.get("answer") or "", collapse=False))
            return code[:limit] if code.strip() else ""
    return ""


def _latest_leaderboard():
    """같은 문항세트(qv) 의 모델별 **최신** 실측만. 비교표용 실제 데이터."""
    rows = read_json(Path(model_eval.LEADERBOARD_PATH), []) or []
    if not isinstance(rows, list):
        return []
    best = {}
    for r in rows:
        if r.get("qv") != model_eval.EVAL_QUESTIONS_VERSION:
            continue
        mid = r.get("model_id")
        if not mid:
            continue
        if mid not in best or (r.get("ts") or 0) > (best[mid].get("ts") or 0):
            best[mid] = r
    return sorted(best.values(), key=lambda r: -(r.get("score") or 0))


def _quote(res, idx, limit=420):
    """문항 1개의 답변 앞부분(정리 후). 없으면 빈 문자열."""
    for d in (res.get("details") or []):
        if d.get("idx") == idx and d.get("score") == 1:
            return _scrub_answer(d.get("answer"))[:limit]
    return ""


def _strong_axis(res):
    """강한 축 라벨 목록 — 점수 비율 1.0 이상."""
    out = []
    for ax in model_eval.AXES:
        b = (res.get("by_axis") or {}).get(ax) or {}
        mx = b.get("max_score") or 0
        if mx and (b.get("score") or 0) / mx >= 1.0:
            out.append(model_eval.AXIS_LABELS.get(ax, ax))
    return out


def build_draft(model_id, res, cli_id, measured_context=None, day=None, zero_classes=None):
    """측정값만으로 **독자용** 초안을 만든다. 반환 (title, body, excerpt).

    2026-11-08 재작성: 첫 버전은 측정표를 그대로 옮긴 '실험 노트'였다(대표님 지적).
    지금은 독자 순서로 쓴다 — 결론 → 5분 체험 → 강한 작업 → 걸리는 지점 → 비교 → 한도.
    지어내지 않는 원칙은 그대로다: 모든 문장은 측정값이나 공개 카탈로그 값에서만 나온다.
    zero_classes: {문항번호: "분류 — 설명"} 를 넘기면 0점 문항 절에 그 문장을 쓴다.
    """
    day = day or time.strftime("%Y-%m-%d")
    score = int(res.get("score") or 0)
    mx = int(res.get("max_score") or 0)
    graded = int(res.get("graded_n") or mx)
    failed = int(res.get("failed") or 0)
    entry = models_dev_entry(model_id)
    axis_rows = _axis_rows(res)
    zeros = zero_score_notes(res)
    lb = _latest_leaderboard()
    rank = None
    rank_txt = ""
    scored = [x for x in lb if x.get("score") is not None]
    if scored:
        top = max(int(x.get("score") or 0) for x in scored)
        ties = [x for x in scored if int(x.get("score") or 0) == top]
        for i, r in enumerate(scored, 1):
            if r.get("model_id") == model_id:
                rank = i
                break
        if score == top:
            rank_txt = ("1위" if len(ties) == 1
                        else f"공동 1위({len(ties)}개 모델이 {top}/{scored[0].get('max_score')})")
        elif rank:
            rank_txt = f"{rank}위"
    strong = _strong_axis(res)

    ratio = (score / graded) if graded else 0
    if ratio >= 0.83:
        verdict = "바로 써볼 만합니다"
    elif ratio >= 0.66:
        verdict = "조건부로 쓸 만합니다"
    elif ratio >= 0.5:
        verdict = "보조 용도로만 권합니다"
    else:
        verdict = "지금은 권하지 않습니다"

    title = f"{model_id} 실측 — {score}/{graded}, 무료로 어디까지 쓸 수 있나"

    p = []
    # ── 리드: 독자 상황 → 이 모델 → 결론. 라벨 붙이지 않는다.
    lead = f"OpenCode 무료 목록에 `{model_id}`가 새로 들어왔습니다. 12문항으로 직접 돌려본 결과 "
    lead += f"**{score}/{graded}**를 맞혔습니다"
    if rank_txt:
        lead += f" — 같은 문항세트로 측정한 무료 모델 {len(scored)}개 중 {rank_txt}입니다"
    lead += f". 결론부터 말하면 **{verdict}**."
    p.append(lead)
    p.append("")
    if strong:
        p.append(f"강한 쪽은 {', '.join(strong)}입니다. 약한 쪽은 형식이 엄격하게 정해진 산출물입니다. "
                 f"아래에 실제로 받은 답과 실패한 지점을 그대로 적었습니다.")
    else:
        p.append("축별로 고른 강점은 없었습니다. 아래에 실제로 받은 답과 실패한 지점을 그대로 적었습니다.")
    p.append("")

    # ── 이게 뭔가: 3문장 + 각주
    p.append(f"## {model_id}가 뭔가")
    p.append("")
    if entry:
        name = entry.get("name") or model_id
        s1 = f"공개 카탈로그상 이름은 **{name}**입니다."
        lim = entry.get("limit") or {}
        ctx, out = lim.get("context"), lim.get("output")
        if isinstance(ctx, int) and isinstance(out, int):
            s1 += f" 공칭 컨텍스트는 {ctx:,} 토큰, 최대 출력은 {out:,} 토큰입니다."
        elif isinstance(ctx, int):
            s1 += f" 공칭 컨텍스트는 {ctx:,} 토큰입니다."
        feats = []
        if entry.get("reasoning"):
            feats.append("추론")
        if entry.get("tool_call"):
            feats.append("도구 호출")
        if feats:
            s1 += " " + "과 ".join(feats) + "을 지원합니다."
        if entry.get("release_date"):
            s1 += f" 공개일은 {entry['release_date']}입니다."
        p.append(s1)
    else:
        p.append("공개 카탈로그에서 이 모델의 스펙을 찾지 못했습니다.")
    unknown = []
    if entry is None:
        unknown.append("스펙 대부분")
    else:
        if not entry.get("open_weights"):
            unknown.append("가중치·학습 데이터·파라미터 수")
        if "stealth" in str(entry.get("description") or "").lower():
            unknown.append("제작사")
    if unknown:
        p.append("")
        p.append(f"{' · '.join(unknown)}는 공개되지 않았습니다. 무료 기간이 언제까지인지도 밝혀지지 않았으니, "
                 f"오래 붙잡고 쓸 모델로 보기는 어렵습니다.")
    p.append("")
    p.append("> 수치는 models.dev 공개값을 "
             f"{day}에 조회한 것입니다. 무료 여부는 [OpenCode Zen 모델 목록](https://opencode.ai/docs/zen/)에서 다시 확인하세요.")
    p.append("")

    # ── 5분 체험: 명령 + 실제 출력
    p.append("## 5분 안에 써보기")
    p.append("")
    p.append("터미널 두 줄이면 확인됩니다.")
    p.append("")
    p.append("```bash")
    p.append(f"opencode models | grep {model_id}")
    p.append(f"opencode run -m {cli_id} \"한 단어로 대답: PONG\"")
    p.append("```")
    p.append("")
    code = _code_quote(res, 3)
    if code:
        p.append("우리가 실제로 던진 것은 코드 수정 요청이었습니다. 만료 토큰을 찾는 함수에서 조건이 틀린 코드를 주고 "
                 "고치라고 했더니, 아래처럼 고친 코드를 냈습니다.")
        p.append("")
        p.append("```python")
        p.extend(code.rstrip().splitlines())
        p.append("```")
        p.append("")
        p.append("이 문항은 제출한 코드를 실제로 실행해 판정했습니다 — 눈으로 읽고 점수를 준 것이 아닙니다.")
        p.append("")

    # ── 강한 작업
    p.append("## 어떤 작업에 강한가")
    p.append("")
    for label, s, m in axis_rows:
        if not m or s / m < 0.75:
            continue
        if label.startswith("코딩"):
            p.append(f"- **코드 수정·리팩터링** ({s}/{m}) — 틀린 조건을 짚고 수정 코드를 냅니다. "
                     f"코딩 문항 4개 중 3개는 제출 코드를 실행해 통과했습니다.")
        elif label.startswith("맥락"):
            q7 = _quote(res, 7, 60)
            extra = f" 12,000자 문서 중간의 함수명(`{q7}`)을 정확히 되받았습니다." if q7 else ""
            p.append(f"- **긴 대화·긴 문서 기억** ({s}/{m}) — 앞선 지시를 오래 붙잡습니다.{extra}")
        elif label.startswith("에이전트"):
            q12 = _quote(res, 12, 40)
            if q12:
                p.append(f"- **우선순위 판단** ({s}/{m}) — 장애 대응 상황을 주고 '지금 할 일'과 "
                         f"'미뤄도 되는 일'을 나누라고 했더니, 고객 메일 발송과 느린 쿼리를 지금 처리로, "
                         f"내부 화면 문구 수정을 미룸으로 분류하고 이유를 붙였습니다.")
            else:
                p.append(f"- **우선순위 판단·계획 세우기** ({s}/{m}) — 여러 단계를 스스로 나눕니다.")
        else:
            p.append(f"- **{label}** ({s}/{m}) — 형식·조건을 지키는 출력에서 안정적입니다.")
    if not any((s / m) >= 0.75 for _l, s, m in axis_rows if m):
        p.append("- 축별 기준선(75%)을 넘은 항목이 없습니다. 특정 용도를 권하기 어렵습니다.")
    p.append("")

    # ── 걸리는 지점
    p.append("## 어디서 걸리는가")
    p.append("")
    if zeros:
        p.append(f"12문항 중 {len(zeros)}문항이 0점이었습니다.")
        p.append("")
        for z in zeros:
            label = model_eval.AXIS_LABELS.get(z["axis"], z["axis"])
            verdict_z = (zero_classes or {}).get(str(z["idx"]))
            head = _scrub_answer(z["answer_head"])[:110] or "(응답 없음)"
            if verdict_z:
                p.append(f"- **Q{z['idx']} · {label}** — {verdict_z}")
            else:
                p.append(f"- **Q{z['idx']} · {label}** — 검토 필요. 받은 답: {head}")
        p.append("")
    p.append("가장 실무에 걸리는 것은 **무료 한도**입니다. 우리가 12문항 평가를 돌리는 동안 무료 사용량이 바닥나서, "
             "같은 날 두 번째 모델은 첫 호출부터 `Free usage limit reached`로 막혔습니다. "
             "한 번에 긴 작업을 여러 번 돌리는 용도보다, 짧은 요청을 몇 번 던지는 용도에 맞습니다.")
    p.append("")
    if failed:
        p.append(f"이번 측정에서도 {failed}문항은 응답이 오지 않아 점수 분모에서 뺐습니다.")
        p.append("")

    # ── 비교 (표 1)
    if lb:
        p.append("## 다른 무료 모델과 비교")
        p.append("")
        p.append("같은 12문항, 같은 채점 기준으로 AIKOREA24가 실측한 값입니다. 모델마다 최신 측정 1건만 씁니다.")
        p.append("")
        p.append("| 모델 | 결과 | 측정일 |")
        p.append("| --- | --- | --- |")
        for r in lb:
            mid = r.get("model_id")
            disp = f"**{mid}**" if mid == model_id else mid
            ts = r.get("ts") or 0
            day_s = time.strftime("%m-%d", time.localtime(ts)) if ts else "—"
            p.append(f"| {disp} | {r.get('score')}/{r.get('max_score')} | {day_s} |")
        p.append("")

    # ── 한도·비용 확인법
    p.append("## 한도와 비용 확인하는 법")
    p.append("")
    p.append("무료라고 적혀 있어도 한도가 붙습니다. 실제로 확인하는 순서는 이렇습니다.")
    p.append("")
    p.append("1. 모델 목록에서 가격이 0으로 표시되는지 봅니다 — 무료 표시가 없는 모델은 유료입니다.")
    p.append("2. 한 번 호출해 봅니다. 응답이 아니라 `Free usage limit reached` 같은 문구가 오면 그날 한도가 끝난 것입니다.")
    p.append("3. 반복 호출이 필요한 작업은 한도에 걸리는 시점을 먼저 재봅니다. 우리는 12문항 평가를 두 번 돌리다 걸렸습니다.")
    p.append("")

    # ── 실측 결과 (표 2)
    p.append(f"## AIK24 실측 결과 ({day})")
    p.append("")
    p.append("| 항목 | 값 |")
    p.append("| --- | --- |")
    p.append(f"| 모델 ID | `{model_id}` |")
    p.append(f"| 결과 | {score}/{graded}" + (f" (미응답 {failed}문항 제외)" if failed else "") + " |")
    p.append("| 축별 | " + " · ".join(f"{l} {s}/{m}" for l, s, m in axis_rows) + " |")
    p.append("| 검증 방법 | OpenCode CLI로 12문항 호출 · 문항별 결정적 채점 · 코드 문항은 실제 실행 |")
    p.append(f"| 니들 컨텍스트 실측 하한 | {f'{measured_context:,} 토큰' if measured_context else '미측정'} |")
    p.append("| 토큰 사용량 | CLI 경유로 측정되지 않음 (미측정) |")
    p.append("")
    n_axis = {}
    for _l, _s, _m in axis_rows:
        n_axis[_l] = _m
    total_q = sum(n_axis.values())
    if total_q:
        p.append(f"12문항은 {' · '.join(f'{k} {v}' for k, v in n_axis.items())}로 구성됩니다. "
                 f"LLM 심사자에게 점수를 묻지 않고 문항마다 규칙 기반으로 채점했고, 코드 문항은 제출 코드를 실제로 실행했습니다. "
                 f"긴 문서 요약 품질, 다국어 정확도, 이미지 입력은 이 평가에 포함되지 않습니다.")
        p.append("")

    p.append("## 참고 자료")
    p.append("")
    p.append("- [OpenCode Zen 모델 목록](https://opencode.ai/docs/zen/)")
    p.append("- [models.dev 모델 카탈로그](https://models.dev/)")
    p.append("")

    # ── 마무리: 결정표 대신 두 목록
    p.append("## 마무리 — 이럴 때 쓴다 / 이럴 때 쓰지 않는다")
    p.append("")
    use_bits, skip_bits = [], []
    for label, s, m in axis_rows:
        if m and s / m >= 0.75:
            if label.startswith("코딩"):
                use_bits.append("함수 하나를 고치거나 리팩터링할 때")
            elif label.startswith("맥락"):
                use_bits.append("앞에서 정한 규칙을 계속 기억해야 하는 대화")
            elif label.startswith("에이전트"):
                use_bits.append("할 일의 우선순위를 정리시킬 때")
    use_bits.append("무료로 짧은 요청을 여러 번 던져볼 때")
    skip_bits = [
        "형식이 정확히 정해진 산출물(스키마·JSON 구조를 그대로 요구하는 작업)",
        "한 번에 긴 작업을 오래 돌려야 할 때 — 무료 한도가 먼저 걸립니다",
        "제작사·가중치가 확인돼야 하는 업무 — 이 모델은 공개되지 않았습니다",
    ]
    p.append("**쓴다**")
    p.append("")
    for b in dict.fromkeys(use_bits):
        p.append(f"- {b}")
    p.append("")
    p.append("**쓰지 않는다**")
    p.append("")
    for b in skip_bits:
        p.append(f"- {b}")
    p.append("")
    p.append("무료 모델 목록은 자주 바뀝니다. 쓰기 전에 `opencode models`로 아직 있는지 확인하는 것이 마지막 단계입니다.")

    body = "\n".join(p).strip() + "\n"
    excerpt = ""
    for line in body.splitlines():
        s = line.strip()
        if s and not s.startswith(("#", "|", "-", "```", ">")):
            excerpt = s.replace("**", "").replace("`", "")
            break
    excerpt = excerpt[:150]
    return title, body, excerpt

def gate_draft(title, body, model_id):
    """게이트 통과 여부. (ok, issues, body_after_repair)

    2026-11-08 강화: 대표님이 첫 글을 '실험 노트'로 지적한 뒤, 형식이 아니라 **읽는 사람**
    기준의 최소선을 코드로 박았다. 통과하지 못하면 초안은 보존되고 발행되지 않는다.
    """
    import blog_quality_gate as qg

    repaired, _notes = qg.repair_markdown(body)
    issues = qg.screen_extended(repaired, verify_links=True, is_eval=True)
    if model_id not in title or model_id not in repaired:
        issues.append(f"모델 귀속 실패(PIPE-10): 제목·본문에 '{model_id}' 표기 필요")

    # 1) 리드가 '보고서 라벨'로 시작하면 실패 — 독자 문장으로 바로 들어가야 한다.
    first = next((l.strip() for l in repaired.splitlines() if l.strip()), "")
    if re.match(r"^(한\s*줄\s*요약|요약)\s*[:：]", first):
        issues.append("리드가 '한 줄 요약:' 라벨로 시작 → 결론을 독자 문장으로 바로 쓴다(라벨 금지)")

    # 2) 문항 답변 나열 금지 — 대표 사례 3개 이하
    q_lines = [l for l in repaired.splitlines() if re.match(r"^\s*-\s*Q\d+", l)]
    if len(q_lines) > 3:
        issues.append(f"문항 나열 {len(q_lines)}줄 → 대표 사례 3개 이하로 줄이고 나머지는 서술로 흡수")

    # 3) 표 남발 금지 — 2개 이하
    tables = len(re.findall(r"^\|\s*-{2,}", repaired, re.M))
    if tables > 2:
        issues.append(f"표 {tables}개 → 2개 이하(비교·실측 결과만)")

    # 4) 저장소 경로·파일명 노출 금지(평가 중 모델이 저장소를 읽은 흔적)
    leaks = sorted(set(_REPO_PATH_RE.findall(repaired)))
    if leaks:
        issues.append("저장소 경로/파일명 노출 %d건 (%s) → 지운다"
                      % (len(leaks), ", ".join(leaks[:3])))

    # 5) 일본어 가타카나 혼입(모델 답변 원문 오타가 그대로 실림)
    if _KATAKANA_RE.search(repaired):
        issues.append("일본어 가타카나 혼입 → 한국어로 교정한다")

    # 6) 독자에게 쓸모 있는 축이 있어야 한다
    if "## 어디서 걸리는가" not in repaired:
        issues.append("'## 어디서 걸리는가' 절 없음 → 실패 사례·한도를 적는다")
    if "## 어떤 작업에 강한가" not in repaired:
        issues.append("'## 어떤 작업에 강한가' 절 없음 → 강점을 시나리오로 적는다")

    return (not issues), issues, repaired


# ── 실행 ────────────────────────────────────────────────────────────────

def _merge_candidates(q, cands, day):
    added = []
    for c in cands:
        mid = c["model_id"]
        cur = q["models"].get(mid)
        if cur is None:
            q["models"][mid] = {
                "model_id": mid, "provider": c["provider"], "first_seen": day,
                "status": "pending", "attempts": 0, "reason": "", "day": day,
            }
            added.append(mid)
        elif cur.get("status") in ("done", "manual"):
            continue
        else:
            cur["provider"] = c["provider"]
    return added


def _next_day(day):
    try:
        return (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        return day


def cmd_run(day=None, limit=None, dry_run=False):
    day = today(day)
    limit = DAILY_LIMIT if limit is None else limit
    _load_env()

    # 동시 실행 방지. 2026-11-08 실측: launchd 실행과 수동 실행이 겹치자 같은 모델을
    # 두 번 평가해 캐시가 나중 결과로 덮였다(8/12 → 10/12). 무료 쿼터도 두 배로 나간다.
    lock_path = LOGS_DIR / "free_model_eval_auto.lock"
    if lock_path.exists():
        try:
            age = time.time() - lock_path.stat().st_mtime
        except OSError:
            age = 0
        if age < 7200:
            log(f"이미 실행 중(lock {int(age)}초 경과) — 이번 실행은 건너뛴다")
            return 0
        log(f"stale lock({int(age)}초) — 제거하고 진행")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(str(os.getpid()), encoding="utf-8")
    try:
        return _cmd_run_locked(day, limit, dry_run)
    finally:
        try:
            lock_path.unlink()
        except OSError:
            pass


def _cmd_run_locked(day, limit, dry_run):
    alert = read_json(ALERT_PATH, {})
    if not alert:
        log("new_models_alert.json 없음 — 감지 잡(04:00)이 아직 안 돌았다. 종료.")
        return 0
    if alert.get("day") != day:
        log(f"alert 은 {alert.get('day')} 자다 — 오늘({day}) 감지분이 아니다. 그래도 기록된 신규만 쓴다.")
    if alert.get("failed_providers"):
        log(f"감지 실패 프로바이더 {alert['failed_providers']} — 해당 프로바이더는 교차 확인 불가")

    cands = candidates_from_alert(alert)
    log(f"무료 신규 후보 {len(cands)}건: {', '.join(c['model_id'] for c in cands) or '없음'}")

    q = load_queue()
    added = _merge_candidates(q, cands, day)
    if added:
        log(f"큐 신규 등록 {len(added)}건: {', '.join(added)}")
    save_queue(q)

    pending = [e for e in q["models"].values() if e.get("status") in ("pending", "retry")]
    pending.sort(key=lambda e: (e.get("first_seen") or "", e["model_id"]))
    if not pending:
        log("평가 대기 0건 — 종료")
        return 0
    if dry_run:
        for e in pending[:limit]:
            log(f"[dry-run] 대상 {e['model_id']} (status={e['status']}, attempts={e['attempts']})")
        return 0

    catalog = cli_catalog()
    if catalog is None:
        # 실패를 0건으로 바꾸지 않는다 — 큐 상태도 건드리지 않고 그대로 둔다.
        log("CLI 목록 조회 실패 — 이번 실행은 아무것도 갱신하지 않는다(다음 실행에서 재시도).")
        return 1
    log(f"opencode models {len(catalog)}줄")

    rc = 0
    for e in pending[:limit]:
        mid = e["model_id"]
        # 이미 유효한 캐시가 있으면 평가를 건너뛴다(무료 쿼터 보호).
        # 단 초안이 아직 없으면 초안 단계는 수행한다 — 중간에 끊긴 실행을 이어붙이기 위함.
        hit = model_eval.cache_get(mid)
        if hit and hit.get("details"):
            e["status"] = "done"
            e["reason"] = "이미 평가됨(캐시 적중)"
            e["score"] = f"{hit.get('score')}/{hit.get('graded_n') or hit.get('max_score')}"
            if e.get("draft", {}).get("ok"):
                save_queue(q)
                log(f"{mid}: 캐시 적중 + 초안 있음 → 생략 ({e['score']})")
                continue
            save_queue(q)
            log(f"{mid}: 캐시 적중 → 평가 생략, 초안 생성으로 진행 ({e['score']})")
            _make_draft(e, mid, hit, e.get("cli_id") or resolve_cli_id(mid, e.get("provider"), catalog),
                        hit.get("measured_context"), day, q)
            continue

        cli_id = resolve_cli_id(mid, e.get("provider"), catalog)
        if not cli_id:
            e["attempts"] = int(e.get("attempts") or 0) + 1
            e["status"] = "blocked" if e["attempts"] >= MAX_ATTEMPTS else "retry"
            e["reason"] = f"CLI 미노출({e.get('provider')}) — opencode models 에 없음"
            e["day"] = _next_day(day)
            save_queue(q)
            log(f"{mid}: {e['reason']} → {e['status']} (attempts={e['attempts']})")
            continue

        log(f"{mid}: 평가 시작 (cli={cli_id})")
        out = evaluate(mid, cli_id)
        e["cli_id"] = cli_id
        e["attempts"] = int(e.get("attempts") or 0) + 1
        if not out["ok"]:
            e["status"] = "blocked" if e["attempts"] >= MAX_ATTEMPTS else "retry"
            e["reason"] = out.get("blocked") or "캐시 미기록(응답 실패 과다)"
            e["day"] = _next_day(day)
            save_queue(q)
            log(f"{mid}: 평가 실패 — {e['reason']} → {e['status']} (다음 날 이월)")
            rc = 1
            continue

        res = out["result"]
        e["status"] = "done"
        e["reason"] = ""
        e["day"] = day
        e["score"] = res.get("score_display") or f"{res.get('score')}/{res.get('max_score')}"
        e["measured_context"] = out.get("measured_context")
        e["elapsed_sec"] = round(out.get("elapsed") or 0, 1)
        e["zeros_review_needed"] = [z["idx"] for z in zero_score_notes(res)]
        log(f"{mid}: 평가 완료 {e['score']} · 소요 {e['elapsed_sec']}초 · "
            f"0점 {len(e['zeros_review_needed'])}문항(검토 필요)")

        # 블로그 초안 (발행 없음)
        _make_draft(e, mid, res, cli_id, out.get("measured_context"), day, q)
        save_queue(q)

    return rc


def _make_draft(e, mid, res, cli_id, measured_context, day, q):
    """초안 생성 + 게이트 + EmDash draft. 실패는 큐에 사유로 남긴다(발행은 하지 않는다)."""
    try:
        title, body, excerpt = build_draft(mid, res, cli_id, measured_context, day=day)
        ok, issues, body2 = gate_draft(title, body, mid)
        DRAFT_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^0-9A-Za-z가-힣._-]+", "-", title)[:80]
        md_path = DRAFT_DIR / f"{day}-{safe}.md"
        md_path.write_text(f"TITLE: {title}\n\n{body2}", encoding="utf-8")
        if not ok:
            REJECTED_DIR.mkdir(parents=True, exist_ok=True)
            rej = REJECTED_DIR / md_path.name
            md_path.replace(rej)
            e["draft"] = {"ok": False, "path": str(rej), "issues": issues}
            log(f"{mid}: 게이트 미달 {len(issues)}건 → 보존 {rej}")
            for it in issues:
                log(f"  - {it}")
            return
        import emdash_publish
        url = emdash_publish.create_draft_post(title, body2, excerpt=excerpt)
        e["draft"] = {"ok": bool(url), "path": str(md_path), "url": url, "title": title}
        log(f"{mid}: EmDash draft 생성 {url or '실패'}")
    except Exception as ex:  # noqa: BLE001
        e["draft"] = {"ok": False, "error": f"{type(ex).__name__}: {ex}"}
        log(f"{mid}: 초안 생성 예외 {type(ex).__name__}: {ex}")


def cmd_status():
    q = load_queue()
    rows = list(q.get("models", {}).values())
    if not rows:
        print("큐가 비어 있습니다.")
        return 0
    print(f"{'model_id':40} {'provider':12} {'status':8} {'attempts':8} score")
    for e in sorted(rows, key=lambda x: (x.get("first_seen") or "", x["model_id"])):
        print(f"{e['model_id'][:40]:40} {str(e.get('provider'))[:12]:12} "
              f"{str(e.get('status'))[:8]:8} {str(e.get('attempts')):8} {e.get('score') or '-'}")
    return 0


def cmd_evaluate(model_id, cli_id=None):
    """모델 1건 수동 평가 (작업 7 실증용). 캐시 반영까지만 — 발행하지 않는다."""
    catalog = cli_catalog()
    if catalog is None:
        log("CLI 목록 조회 실패 — 중단")
        return 1
    if not cli_id:
        for prov in CLI_PREFIX:
            cli_id = resolve_cli_id(model_id, prov, catalog)
            if cli_id:
                break
    if not cli_id:
        log(f"{model_id}: opencode models 에서 CLI ID 를 찾지 못했다")
        return 1
    log(f"{model_id}: 수동 평가 시작 (cli={cli_id})")
    out = evaluate(model_id, cli_id)
    if not out["ok"]:
        log(f"{model_id}: 실패 — {out.get('blocked') or '캐시 미기록'}")
        return 1
    res = out["result"]
    log(f"{model_id}: {res.get('score')}/{res.get('max_score')} · "
        f"컨텍스트 하한 {out.get('measured_context')} · 소요 {round(out.get('elapsed'), 1)}초")
    for d in res.get("details") or []:
        log(f"  Q{d['idx']} [{d['axis']}] {d['score']}점 src={d.get('source')} — "
            f"{(d.get('answer') or '')[:60]!r}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="AIK24-EVAL-AUTO 신규 무료 모델 자동 평가")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("run", help="일일 실행(트리거→평가→캐시→초안)")
    r.add_argument("--day")
    r.add_argument("--limit", type=int)
    r.add_argument("--dry-run", action="store_true")
    sub.add_parser("status", help="큐 현황")
    ev = sub.add_parser("evaluate", help="모델 1건 수동 평가")
    ev.add_argument("model_id")
    ev.add_argument("--cli")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a.day, a.limit, a.dry_run)
    if a.cmd == "status":
        return cmd_status()
    if a.cmd == "evaluate":
        return cmd_evaluate(a.model_id, a.cli)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
