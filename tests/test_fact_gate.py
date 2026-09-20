"""Tests for pipeline.threads.fact_gate — G4 2-layer fact gate."""
import pytest
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "threads"))

SAMPLE_BODY = (
    "2026년 7월 5일, AI 공감 능력 평가 새 방법론이 발표되었습니다. "
    "기존 방법론은 성능 측정에만 의존했지만, 새로운 연구는 100만 건의 "
    "대화 데이터를 분석했습니다. 기존 벤치마크는 72% 정확도에 그쳤지만 "
    "새 시스템은 89% 정확도를 기록했습니다. "
    "새 시스템은 문맥과 대화 흐름을 종합적으로 분석해 더 정확한 결과를 도출했습니다."
)


class TestFactGate:
    """G4 fact gate blocks unsupported claims, allows supported ones."""

    @pytest.mark.unit
    def test_blocks_unsupported_claims(self):
        """slot3_context with numbers not in source → blocked."""
        from pipeline.threads.fact_gate import check_slot3

        unsupported_slot3 = (
            "이 연구는 200만 건의 데이터를 분석했으며, "
            "정확도는 95%를 기록했습니다."
        )
        passed, reason = check_slot3(unsupported_slot3, SAMPLE_BODY)
        assert not passed
        assert "Layer1" in reason or "Layer2" in reason

    @pytest.mark.unit
    def test_allows_supported_claims(self):
        """slot3_context backed by source text → passes."""
        from pipeline.threads.fact_gate import check_slot3

        supported_slot3 = (
            "기존 벤치마크는 72% 정확도에 그쳤지만 "
            "새 시스템은 89% 정확도를 기록했습니다."
        )
        passed, reason = check_slot3(supported_slot3, SAMPLE_BODY)
        assert passed

    @pytest.mark.unit
    def test_blocks_empty_slot3(self):
        from pipeline.threads.fact_gate import check_slot3

        passed, reason = check_slot3("", SAMPLE_BODY)
        assert not passed
        assert "비어있음" in reason

    @pytest.mark.unit
    def test_blocks_empty_body(self):
        from pipeline.threads.fact_gate import check_slot3

        passed, reason = check_slot3("일반적인 주장입니다.", "")
        assert not passed
        assert "crawled_body" in reason

    @pytest.mark.unit
    def test_llm_layer_override(self, monkeypatch):
        """Layer2 LLM blocks → overall block even if Layer1 passes."""
        from pipeline.threads.fact_gate import check_slot3
        import v3.model_router

        supported_slot3 = (
            "기존 벤치마크는 72% 정확도에 그쳤지만 새 시스템은 89% 정확도를 기록했습니다."
        )

        def mock_chat_block(*, system_prompt, messages, temperature, max_tokens, **kwargs):
            if "팩트체크" in (system_prompt or ""):
                return json.dumps({"verdict": "BLOCK", "reason": "소스에 없는 수치"})
            return None

        monkeypatch.setattr(v3.model_router, "chat_completion", mock_chat_block)
        passed, reason = check_slot3(supported_slot3, SAMPLE_BODY)
        assert not passed
        assert "Layer2" in reason
