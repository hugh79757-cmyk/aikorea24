#!/usr/bin/env python3
"""OpenCode CLI 로 실제 호출 가능한 무료 모델 전수 리스트 (AIK24-EVAL-02 작업 1)

`opencode models` 1줄에 `provider/model` 이 하나씩 나온다(2026-10-14 실측 2049줄).
프로바이더 필터 인자가 없어 전체를 받아 여기서 거른다. 대상은 4개 프로바이더이며,
CLI 표시 provider 이름을 지시서 표기와 맞추기 위해 별칭을 둔다:

  openrouter/ → openrouter   무료 판정: id 가 ':free' 로 끝남
  kilo/       → kilo         무료 판정: id 가 ':free' 로 끝남
  opencode/   → zen          OpenCode Zen 은 config 에 provider 로 안 있고 catalog prefix 가 'opencode'
  nvidia/     → nvidia-nim   무료 판정: id 가 '-free' 로 끝남

후보는 여기서 끝나지 않는다. 각각 `opencode run` 으로 실제로 한 번 울려서 응답이 온 것만
남긴다(지시서 대표님 원칙 1: "OpenCode에서 선택할 수 없는 모델은 테스트 명단에 올리지 않는다").

결과: scripts/logs/free_models_cli.json — model_id / provider / cli_id 만. context_length 는
공개 API 스냅샷에 값이 있을 때만 넣고, 없으면 필드 자체를 뺀다("미공개" 문자열 금지).
"""
import json
import os
import re
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts", "threads", "v3"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_eval  # noqa: E402  (sys.path 삽입 후에만 import 가능)
from model_catalog import CATALOG_DIR, _write_json  # noqa: E402

OUT_PATH = CATALOG_DIR / "free_models_cli.json"

# catalog prefix → (지시서 provider 이름, 무료 접미사)
PROVIDERS = {
    "openrouter": ("openrouter", ":free"),
    "kilo": ("kilo", ":free"),
    "opencode": ("zen", "-free"),
    "nvidia": ("nvidia-nim", "-free"),
}

MODELS_TIMEOUT = 180  # `opencode models` 는 첫 호출에 네트워크 조회를 한다
PROBE_GAP_SEC = 3     # 무료 티어 429 를 피하려고 호출 사이에 간격
PROBE_TIMEOUT = 30    # 살아 있는 모델은 4~16초 만에 답한다. 60초는 실패 항목만 2배로 늦춘다.
PROBE_WORKERS = 4     # 45건 직렬은 20분+. subprocess.run 은 GIL 을 놓으므로 스레드가 유효하다.
# 단, 워커 4개가 무료 티어를 때리면 결정적 오류(404/폐기/미존재)는 그대로 재현되고
# 타임아웃 건만 간헐적으로 바뀔 수 있다. 그 경우 1차 실행 결과와 대조해 기록한다.
PROBE_PROMPT = "한 단어로 대답: PONG"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] [free_models_cli] {msg}", flush=True)


def opencode_models():
    """`opencode models` 1줄에 provider/model 1개. 실패하면 빈 리스트."""
    import subprocess

    try:
        p = subprocess.run(
            ["opencode", "models"], capture_output=True, text=True, timeout=MODELS_TIMEOUT
        )
    except Exception as e:
        log(f"opencode models 실패 — {type(e).__name__}")
        return []
    return [ln.strip() for ln in p.stdout.splitlines() if "/" in ln]


def candidates(lines):
    """(provider, model_id, cli_id) 목록. model_id 는 provider 접두어를 뗀 값 —
    기존 CLI_MODEL_MAP 키(zen 등)와 같은 관례를 유지한다."""
    out = []
    for ln in lines:
        prefix, _, rest = ln.partition("/")
        spec = PROVIDERS.get(prefix)
        if not spec or not rest:
            continue
        provider, suffix = spec
        if rest.endswith(suffix):
            out.append((provider, rest, ln))
    return out


def context_lengths():
    """가장 최근 공개 API 스냅샷의 context_length. 값이 정수인 것만 담는다(공개값만 기록)."""
    snaps = sorted(
        p for p in CATALOG_DIR.glob("model_catalog_*.json")
        if re.fullmatch(r"model_catalog_\d{4}-\d{2}-\d{2}\.json", p.name)
    )
    if not snaps:
        log("공개 스냅샷 없음 → context_length 필드 생략")
        return {}
    try:
        rows = json.loads(snaps[-1].read_text())
    except (OSError, ValueError) as e:
        log(f"스냅샷 읽기 실패({snaps[-1].name}) — {e}")
        return {}
    ctx = {}
    for r in rows if isinstance(rows, list) else []:
        v = r.get("context_length")
        if isinstance(v, int) and v > 0:
            ctx[r.get("model_id")] = v
    return ctx


def probe(provider, model_id, cli_id):
    """1회 호출. 성공하면 reason 이 None, 실패하면 text 가 빈 문자열이다."""
    text, reason = model_eval.cli_call(cli_id, PROBE_PROMPT, timeout=PROBE_TIMEOUT)
    if not text and "타임아웃" in reason:
        # 30초 초과는 무료 티어 혼잡일 수 있다. "선택 불가" 판정 근거로 삼지 말고 한 번만 더 친다.
        time.sleep(15)
        text, reason = model_eval.cli_call(cli_id, PROBE_PROMPT, timeout=PROBE_TIMEOUT)
    return provider, model_id, cli_id, reason, text


def main():
    lines = opencode_models()
    log(f"opencode models {len(lines)}줄")
    cands = candidates(lines)
    per = {}
    for provider, _, _ in cands:
        per[provider] = per.get(provider, 0) + 1
    log(f"무료 후보 {len(cands)}건 — {per}")

    # opencode run 은 현재 폴더를 프로젝트로 본다. 이 저장소에서 돌리면 AGENTS.md 가
    # 컨텍스트에 들어가 호출이 무거워지므로 빈 임시 디렉터리로 옮겨서 친다.
    os.chdir(tempfile.gettempdir())

    ctx = context_lengths()
    verified, dropped = [], []
    with ThreadPoolExecutor(max_workers=PROBE_WORKERS) as ex:
        for i, (provider, model_id, cli_id, reason, text) in enumerate(
            ex.map(lambda c: probe(*c), cands), 1
        ):
            if text:
                row = {"model_id": model_id, "provider": provider, "cli_id": cli_id}
                if model_id in ctx:
                    row["context_length"] = ctx[model_id]
                verified.append(row)
                log(f"[{i}/{len(cands)}] OK {cli_id} — {text[:40]!r}")
            else:
                dropped.append({"cli_id": cli_id, "reason": reason})
                log(f"[{i}/{len(cands)}] 제외 {cli_id} — {reason}")

    verified.sort(key=lambda r: (r["provider"], r["model_id"]))
    _write_json(OUT_PATH, verified)
    log(f"확정 {len(verified)}건 → {OUT_PATH}")
    if dropped:
        log("제외 목록(사유 포함):")
        for d in dropped:
            log(f"  - {d['cli_id']}: {d['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())