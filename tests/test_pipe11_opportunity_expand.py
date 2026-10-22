"""AIK24-PIPE-11 — free-opportunity 항목의 목록 페이지 → 실제 모델 전개.

지시서: 2026-10-22-1205-AIK24-PIPE-11-수집전개-잔존위험해소.md
사고: news 56082 "OpenRouter 무료 모델 (:free 태그)" 의 link 가 openrouter.ai/models?max_price=0
      (목록 페이지) 라 브리핑 1번 슬롯이 "일반론" 항목이 되었고, 그 글이 PIPE-10 사고의
      원인이었다(허위 실측).

여기서는 전개 로직과 구조화 모델 ID 연동을 검증한다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import model_attribution as ma  # noqa: E402
import weekly_opportunity as wo  # noqa: E402


# ── 픽스처 ────────────────────────────────────────────────────────────────
FAKE_MODELS = [
    {"id": "recursive/flint-v1.0:free", "name": "Recursive Flint",
     "description": "무료 코딩 모델", "created": 1792000000,
     "pricing": {"prompt": "0", "completion": "0"}},
    {"id": "nvidia/nemotron-3.5-super-vl:free", "name": "Nemotron",
     "description": "무료 모델", "created": 1791000000,
     "pricing": {"prompt": "0", "completion": "0"}},
    {"id": "paid/model-x", "name": "Paid", "description": "유료",
     "created": 1793000000, "pricing": {"prompt": "0.0001", "completion": "0"}},
]

OPPORTUNITY_ENTRY = {
    "title": "OpenRouter 무료 모델 (:free 태그)",
    "link": "https://openrouter.ai/models?max_price=0&order=newest",
    "description": ":free 태그가 붙은 모델을 무료로 호출",
    "category": "benefit",
    "access": "custom",
    "expires": "2099-12-31",
    "expand": "openrouter_free_models",
}

SERVICE_ENTRY = {
    "title": "Google Cloud 신규 가입 $300 크레딧",
    "link": "https://cloud.google.com/free",
    "description": "신규 고객 크레딧",
    "category": "benefit",
    "access": "custom",
    "expires": "2099-12-31",
}


class TestExpansion:
    """목록 페이지 항목 → 모델별 개별 항목."""

    def test_expand_produces_per_model_items(self, monkeypatch):
        monkeypatch.setattr(wo, "_fetch_openrouter_models_all",
                            lambda: ({m["id"]: m for m in FAKE_MODELS}, None))
        items, notes = wo.expand_entries([OPPORTUNITY_ENTRY])
        assert len(items) == 2, [i["title"] for i in items]
        assert any("전개" in n for n in notes), notes

    def test_expanded_item_has_structured_model_id_and_model_page_link(self, monkeypatch):
        monkeypatch.setattr(wo, "_fetch_openrouter_models_all",
                            lambda: ({m["id"]: m for m in FAKE_MODELS}, None))
        items, _ = wo.expand_entries([OPPORTUNITY_ENTRY])
        first = items[0]
        assert first["model_id"] == "recursive/flint-v1.0:free"
        assert first["link"] == "https://openrouter.ai/recursive/flint-v1.0:free"
        assert first["origin_link"] == "https://openrouter.ai/recursive/flint-v1.0:free"
        # 목록 페이지가 아니라 **모델 페이지**가 표시 링크가 된다
        assert "openrouter.ai/models" not in first["link"]
        # 최신순
        assert first["model_id"] == "recursive/flint-v1.0:free"

    def test_paid_model_is_excluded(self, monkeypatch):
        monkeypatch.setattr(wo, "_fetch_openrouter_models_all",
                            lambda: ({m["id"]: m for m in FAKE_MODELS}, None))
        items, _ = wo.expand_entries([OPPORTUNITY_ENTRY])
        assert all("paid/model-x" not in i["model_id"] for i in items)

    def test_service_entry_passes_through_unchanged(self, monkeypatch):
        monkeypatch.setattr(wo, "_fetch_openrouter_models_all",
                            lambda: ({m["id"]: m for m in FAKE_MODELS}, None))
        items, notes = wo.expand_entries([SERVICE_ENTRY])
        assert len(items) == 1 and items[0]["title"] == SERVICE_ENTRY["title"]
        assert items[0] is SERVICE_ENTRY
        assert not notes

    def test_list_page_without_expand_key_warns(self, monkeypatch):
        entry = dict(OPPORTUNITY_ENTRY)
        entry.pop("expand")
        items, notes = wo.expand_entries([entry])
        assert len(items) == 1
        assert any("expand 키가 없다" in n for n in notes), notes

    def test_expander_failure_keeps_original(self, monkeypatch):
        monkeypatch.setattr(wo, "_fetch_openrouter_models_all",
                            lambda: ({}, "API 실패"))
        items, notes = wo.expand_entries([OPPORTUNITY_ENTRY])
        assert len(items) == 1 and items[0]["title"] == OPPORTUNITY_ENTRY["title"]
        assert any("전개 실패" in n for n in notes), notes

    def test_list_page_detection(self):
        assert wo._looks_like_list_page("https://openrouter.ai/models?max_price=0")
        assert not wo._looks_like_list_page("https://cloud.google.com/free")
        assert not wo._looks_like_list_page("https://docs.github.com/en/copilot")


class TestInsertBuilder:
    """전개 항목의 INSERT 가 model_id + 모델 페이지 link 를 담는지."""

    def test_insert_contains_model_id_and_origin_link(self, monkeypatch):
        monkeypatch.setattr(wo, "_fetch_openrouter_models_all",
                            lambda: ({m["id"]: m for m in FAKE_MODELS}, None))
        items, _ = wo.expand_entries([OPPORTUNITY_ENTRY])
        stmt = wo.build_inserts(items, now=None)[0]
        assert "model_id" in stmt
        assert "origin_link" in stmt
        assert "https://openrouter.ai/recursive/flint-v1.0:free" in stmt
        assert "recursive/flint-v1.0:free" in stmt

    def test_plain_entry_insert_still_works(self):
        stmt = wo.build_inserts([SERVICE_ENTRY], now=None)[0]
        assert "INSERT OR IGNORE INTO news" in stmt
        assert "'Google Cloud 신규 가입 $300 크레딧'" in stmt


class TestStructuredModelIdPriority:
    """규칙: 구조화 model_id 가 최우선, 텍스트 추출은 폴백."""

    def test_model_id_column_wins(self):
        art = {
            "model_id": "recursive/flint-v1.0:free",
            "title": "[무료 LLM] recursive/flint-v1.0:free — OpenRouter 무료 티어",
            "original_title": "recursive/flint-v1.0:free",
        }
        assert ma.source_model_id(art) == "recursive/flint-v1.0:free"

    def test_falls_back_to_original_title(self):
        art = {"title": "[무료 LLM] recursive/flint-v1.0:free — OpenRouter 무료 티어",
               "original_title": "recursive/flint-v1.0:free"}
        assert ma.source_model_id(art) == "recursive/flint-v1.0:free"

    def test_falls_back_to_link(self):
        art = {"title": "일반 뉴스", "link": "https://openrouter.ai/recursive/flint-v1.0:free"}
        assert ma.source_model_id(art) == "recursive/flint-v1.0:free"

    def test_list_page_link_yields_none(self):
        art = {"title": "OpenRouter 무료 모델 (:free 태그)",
               "link": "https://openrouter.ai/models?max_price=0&order=newest"}
        assert ma.source_model_id(art) is None


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
