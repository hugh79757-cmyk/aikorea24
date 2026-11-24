#!/usr/bin/env python3
"""AIK24-MODEL-EVAL-FIX-01 회귀 테스트 — Zen 모델 평가 생략 → 소개글만 발행 버그.

사고 재현(2026-11-24): `qwen4-max-free` 는 models.dev 에서 deprecated 였는데도
OpenRouter 목록에 없다는 이유만으로 "모델 미존재 → 평가 생략" 처리되고 뉴스
소개글로 발행됐다. Zen 모델(hy4-flash-free, beam-free 등)은 전부 같은 경로로
평가를 건너뛰었다.

네트워크 0회 — models.dev / OpenRouter / CLI / LLM 호출은 전부 픽스처·스텁.
사용: pytest tests/test_model_eval_routing_fix.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import blog_draft_generator as bg  # noqa: E402
import model_eval as me  # noqa: E402

ZEN = {
    "qwen4-max-free": {"id": "qwen4-max-free", "status": "deprecated"},
    "hy4-flash-free": {"id": "hy4-flash-free", "status": "active"},
    "beam-free": {"id": "beam-free", "status": "active"},
}
OR = {"liquid/lfm-2.5:free": {"id": "liquid/lfm-2.5:free", "pricing": {"prompt": "0", "completion": "0"}}}


def _article(title, model_id=None):
    a = {
        "title": title,
        "original_title": title,
        "description": "공개 정보 기준 소개",
        "link": "https://example.com/news",
        "source": "테스트",
        "v2_tag": "free-llm",
    }
    if model_id is not None:
        a["model_id"] = model_id
    return a


class _Harness:
    """공통 스텁 — models.dev/OpenRouter 목록, LLM, 로그 캡처."""

    def __init__(self, monkeypatch, capsys):
        self.monkeypatch = monkeypatch
        self.capsys = capsys
        self.calls = []
        monkeypatch.setattr(me, "_fetch_modelsdev_opencode", lambda: dict(ZEN))
        monkeypatch.setattr(me, "_fetch_openrouter_models", lambda: dict(OR))
        monkeypatch.setattr(bg, "chat_completion", self._fake_llm)

    def _fake_llm(self, messages=None, system_prompt=None, **kwargs):
        return "TITLE: 테스트 제목\n---\n본문입니다. 일반 뉴스 경로에서 생성됐습니다."

    def fake_eval_draft(self, keyword, article, model_id, **kwargs):
        self.calls.append(model_id)
        return f"MODEL_EVAL_PATH:{model_id}"

    def logs(self):
        return self.capsys.readouterr().out


def _route(h, title, model_id=None, patch_eval=True):
    if patch_eval:
        h.monkeypatch.setattr(bg, "generate_model_eval_draft", h.fake_eval_draft)
    out = bg.generate_draft("테스트 키워드", [_article(title, model_id)], "A", link_hint=False)
    return out, h.logs()


# ── 1. deprecated ────────────────────────────────────────────────────
def test_deprecated_zen_model_is_skipped(monkeypatch, capsys):
    h = _Harness(monkeypatch, capsys)
    out, logs = _route(h, "[무료 LLM] qwen4-max-free — OpenCode Zen 무료 티어")
    assert out == ""
    assert h.calls == []
    assert "모델 중단됨(deprecated)" in logs
    assert "qwen4-max-free" in logs


# ── 2·3. active Zen 모델은 평가글 경로 ───────────────────────────────
def test_active_zen_hy4_flash_routes_to_eval(monkeypatch, capsys):
    h = _Harness(monkeypatch, capsys)
    out, logs = _route(h, "[무료 LLM] hy4-flash-free — 빠른 무료 모델")
    assert out == "MODEL_EVAL_PATH:opencode/hy4-flash-free"
    assert h.calls == ["opencode/hy4-flash-free"]
    assert "뉴스 블로그 경로" not in logs
    assert bg._LAST_GEN_IS_EVAL is True


def test_active_zen_beam_routes_to_eval(monkeypatch, capsys):
    h = _Harness(monkeypatch, capsys)
    out, _logs = _route(h, "[무료 LLM] beam-free — OpenCode Zen 무료 티어")
    assert out == "MODEL_EVAL_PATH:opencode/beam-free"
    assert h.calls == ["opencode/beam-free"]


# ── 4. OpenRouter :free 기존 동작 보존 ───────────────────────────────
def test_openrouter_free_keeps_existing_route(monkeypatch, capsys):
    h = _Harness(monkeypatch, capsys)
    out, _logs = _route(h, "[무료 LLM] liquid/lfm-2.5:free — OpenRouter 무료 티어")
    assert out == "MODEL_EVAL_PATH:liquid/lfm-2.5:free"
    assert h.calls == ["liquid/lfm-2.5:free"]


# ── 5. 모델 ID 없는 free-llm 일반 뉴스 → 뉴스 경로 ──────────────────
def test_free_llm_news_without_model_id_uses_news_route(monkeypatch, capsys):
    h = _Harness(monkeypatch, capsys)
    out, logs = _route(h, "[무료 LLM] 오픈소스 진영의 새로운 소식")
    assert h.calls == []
    assert out.startswith("TITLE:")
    assert "일반 뉴스 블로그 경로" in logs


# ── 6. 미확인 모델 → 소개글 생성 안 함 ───────────────────────────────
def test_unknown_model_is_skipped(monkeypatch, capsys):
    h = _Harness(monkeypatch, capsys)
    out, logs = _route(h, "[무료 LLM] definitely-not-listed-xyz-free — 신규 모델")
    assert out == ""
    assert h.calls == []
    assert "모델 미확인 — 소개글 작성 안 함" in logs


# ── Part 3: 캐시 우선 · 인라인 평가 실행 안 함 ────────────────────────
def test_eval_block_uses_cache_with_alias(monkeypatch):
    cached = {"label": "12문항 중 10문항 정답", "score": 10, "max_score": 12,
              "failed": 0, "details": []}
    monkeypatch.setattr(me, "cache_get", lambda mid: cached if mid == "hy4-flash-free" else None)
    monkeypatch.setattr(me, "eval_model_cached", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("인라인 평가를 호출하면 안 된다")))
    r = bg._eval_block("opencode/hy4-flash-free")
    assert r is cached


def test_eval_block_pending_when_no_cache(monkeypatch):
    monkeypatch.setattr(me, "cache_get", lambda mid: None)
    monkeypatch.setattr(me, "eval_model_cached", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("인라인 평가를 호출하면 안 된다")))
    monkeypatch.setattr(me, "resolve_cli_model", lambda mid: None)
    r = bg._eval_block("opencode/beam-free")
    assert r["label"] == "평가 대기"
    assert r["failed"] >= r["max_score"]
    assert "cache-miss" in r["pending_reason"]


# ── 모델 평가 생성 실패 시 뉴스 대체 금지 ────────────────────────────
def test_model_eval_failure_does_not_fall_back_to_news(monkeypatch, capsys):
    h = _Harness(monkeypatch, capsys)
    monkeypatch.setattr(bg, "generate_model_eval_draft", lambda *a, **k: "")
    out, logs = _route(h, "[무료 LLM] beam-free — OpenCode Zen 무료 티어", patch_eval=False)
    assert out == ""
    assert "뉴스 경로로 대체" not in logs
    assert "모델 항목 생략" in logs


# ── extract_model_id 하위 호환 ──────────────────────────────────────
def test_extract_model_id_still_returns_string(monkeypatch):
    monkeypatch.setattr(me, "_fetch_modelsdev_opencode", lambda: dict(ZEN))
    monkeypatch.setattr(me, "_fetch_openrouter_models", lambda: dict(OR))
    assert me.extract_model_id(_article("[무료 LLM] hy4-flash-free — 티어")) == "opencode/hy4-flash-free"
    assert me.extract_model_id(_article("[무료 LLM] qwen4-max-free — 티어")) is None
