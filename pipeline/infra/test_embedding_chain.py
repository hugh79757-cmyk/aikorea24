#!/usr/bin/env python3
"""CF-MIGRATE-06 결정적 검증 — 임베딩 회전 체인 (live provider 호출 0건).

스킬 llm-fallback-chain-management "Deterministic verification" 절 대응:
  1. 성공 티어가 다음 요청의 front 가 된다
  2. ANY 실패(429 포함)는 티어를 뒤로 보내고 다음 티어를 즉시 호출 — sleep 없음, 제외 없음
  3. 한 패스에 모든 티어가 정확히 1회씩 등장 (균등 회전)
  4. paid/안전망 티어가 항상 마지막
  5. 상태가 새 프로세스(재 import)를 넘어 유지
  6. 타임아웃이 무한 대기를 막는다
  7. 어떤 코드 경로도 티어를 제외·게이트·지연·제거하지 않는다

실행: python3 pipeline/infra/test_embedding_chain.py
"""
import importlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

STATE = os.path.join(tempfile.mkdtemp(prefix="embrot_"), "state.json")
os.environ["EMBEDDING_ROTATION_STATE_PATH"] = STATE
os.environ["OPENAI_API_KEY"] = "test-openai"
os.environ["OPENROUTER_API_KEY"] = "test-openrouter"

import pipeline.infra.vectorize_client as vc  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILURES.append(name)


class FakeResponse:
    def __init__(self, status):
        self.status_code = status


class FakeHTTPError(Exception):
    """requests.HTTPError 흉내 — status_code 속성만 필요."""

    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.response = FakeResponse(code)


class FakeTimeout(Exception):
    pass


class FakeConnError(Exception):
    pass


def install(monkey_behavior, sleeps):
    """monkey_behavior: {tier_name: 'ok' | list | Exception}. 반환: 호출 기록 리스트."""
    hits = []

    def _fake_once(url, model, key, text):
        tier = "openai" if "api.openai.com" in url else "openrouter"
        hits.append(tier)
        item = monkey_behavior.get(tier, "ok")
        if isinstance(item, Exception):
            raise item
        if isinstance(item, type) and issubclass(item, Exception):
            raise item()
        if item != "ok":
            return item
        return [0.1] * vc.EMBEDDING_DIMS

    vc._embed_once = _fake_once
    vc.time = type("T", (), {"monotonic": staticmethod(__import__("time").monotonic),
                             "sleep": lambda s: sleeps.append(s)})()
    return hits


def reset():
    vc._embed_once = _orig_once
    vc.time = _orig_time
    if os.path.exists(STATE):
        os.remove(STATE)


_orig_once = vc._embed_once
_orig_time = vc.time

print("=" * 68)
print("1) 성공 티어가 다음 요청의 front 가 된다")
sleeps = []
calls = install({"openrouter": FakeHTTPError(429)}, sleeps)
vc.get_embedding("가나다 abc")          # pass1: openrouter(429) → openai(성공)
check("1-1 1패스: front 실패 → 다음 티어로 즉시 이동", calls == ["openrouter", "openai"], calls)
check("1-2 sleep 0회", sleeps == [], sleeps)
n1 = len(calls)
vc.get_embedding("다라마 abc")          # pass2: openai 가 front 이므로 그것만 호출
check("1-3 2패스는 성공 티어만 1회 (front 유지)", calls[n1:] == ["openai"], calls[n1:])
reset()

print("2) 429 는 예외가 아니라 회전 신호")
sleeps = []
calls = install({"openai": FakeHTTPError(429)}, sleeps)
vec = vc.get_embedding("테스트")
check("2-1 벡터 반환(None 아님)", isinstance(vec, list) and len(vec) == vc.EMBEDDING_DIMS)
check("2-2 openrouter 로 즉시 회전", calls == ["openrouter"], calls)
check("2-3 sleep 0회 (대기 금지)", sleeps == [], sleeps)
reset()

print("3) 전 티어 실패 시에만 None")
for label, beh in (
    ("401", {"openai": FakeHTTPError(401), "openrouter": FakeHTTPError(401)}),
    ("429", {"openai": FakeHTTPError(429), "openrouter": FakeHTTPError(429)}),
    ("404", {"openai": FakeHTTPError(404), "openrouter": FakeHTTPError(404)}),
    ("timeout", {"openai": FakeTimeout(), "openrouter": FakeTimeout()}),
    ("200+과금본문", {"openai": KeyError("data"), "openrouter": KeyError("data")}),
    ("빈 응답", {"openai": ValueError("빈 응답"), "openrouter": ValueError("빈 응답")}),
):
    sleeps = []
    calls = install(beh, sleeps)
    res = vc.get_embedding("x")
    check(f"3-{label} → None", res is None, res)
    check(f"3-{label} 두 티어 모두 시도", calls == ["openrouter", "openai"], calls)
    check(f"3-{label} 재시도 0회 (429류)", sleeps == [], sleeps)
    reset()

print("4) 균등 회전 — 어떤 티어도 영구 제외되지 않는다")
sleeps = []
for i in range(4):
    reset()          # front 상태 초기화 → 매 패스 openrouter(기본 front) 부터
    calls = install({"openrouter": FakeHTTPError(429), "openai": "ok"}, sleeps)
    vc.get_embedding("x")
    check(f"4-{i+1} 패스: openrouter(실패) → openai 순으로 1회씩",
          calls == ["openrouter", "openai"], calls)
reset()

print("5) 상태가 새 프로세스를 넘어 유지")
sleeps = []
calls = install({"openai": "ok", "openrouter": "ok"}, sleeps)
vc.get_embedding("x")
saved_front = vc._load_tier_order()[0]
del sys.modules["pipeline.infra.vectorize_client"]
os.environ["EMBEDDING_ROTATION_STATE_PATH"] = STATE
vc = importlib.import_module("pipeline.infra.vectorize_client")
_orig_once = vc._embed_once
_orig_time = vc.time
check("5-1 재 import 후 front 유지", vc._load_tier_order()[0] == saved_front, vc._load_tier_order())
reset()

print("6) 체인 예산 — 무한 대기 방지")
sleeps = []
vc.EMBEDDING_CHAIN_BUDGET_SEC = 0.0
calls = install({"openai": "ok", "openrouter": "ok"}, sleeps)
res = vc.get_embedding("x")
check("6-1 예산 0 → None, 호출 0회", res is None and calls == [], (res, calls))
vc.EMBEDDING_CHAIN_BUDGET_SEC = 90.0
reset()

print("7) 대기/제외 로직 0건 — 소스 정적 검사(주석 제외)")
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectorize_client.py")
code_lines = []
for ln in open(src_path, encoding="utf-8"):
    s = ln.split("#")[0] if not ln.lstrip().startswith("#") else ""
    code_lines.append(s)
code = "\n".join(code_lines)
banned = [w for w in ("cooldown", "quota_until", "structural_until", "circuit", "blocked")
          if w in code]
check("7-1 금지 토큰 0건", banned == [], banned)
sleep_args = {ln.split("time.sleep(", 1)[1].rstrip().rstrip(")").strip()
              for ln in code_lines if "time.sleep(" in ln}
allowed = {"EMBEDDING_TIER_RETRY_DELAY", "1.0 * (2.0 ** attempt"}  # 뒤 ')' 는 rstrip 에 제거됨
check("7-2 sleep 은 스킬 허용 형태(5xx 1회 재시도 / CF 요청 재시도)만",
      sleep_args <= allowed, sleep_args)

print("=" * 68)
if FAILURES:
    print(f"FAILED {len(FAILURES)}건: {FAILURES}")
    sys.exit(1)
print("ALL CHECKS PASSED")
