"""Tests for pipeline.orchestrator — PipelineStep protocol + PipelineOrchestrator."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.orchestrator import PipelineOrchestrator, PipelineStep


class MockSuccessStep:
    name = "mock_success"
    def __init__(self, name="mock_success"):
        self.name = name
    def run(self) -> int:
        return 0


class MockFailureStep:
    name = "mock_failure"
    def __init__(self, name="mock_failure"):
        self.name = name
    def run(self) -> int:
        return 1


class MockExceptionStep:
    name = "mock_exception"
    def __init__(self, name="mock_exception"):
        self.name = name
    def run(self) -> int:
        raise RuntimeError("step crashed")


class TestPipelineOrchestrator:
    @pytest.mark.unit
    def test_empty_orchestrator(self):
        orb = PipelineOrchestrator(run_id="test_empty")
        results = orb.run()
        assert results == []

    @pytest.mark.unit
    def test_single_success_step(self):
        orb = PipelineOrchestrator(run_id="test_single")
        orb.register(MockSuccessStep())
        results = orb.run(dry_run=True)
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].step_name == "mock_success"

    @pytest.mark.unit
    def test_multiple_steps(self):
        orb = PipelineOrchestrator(run_id="test_multi")
        orb.register(MockSuccessStep(name="step_a"))
        orb.register(MockSuccessStep(name="step_b"))
        results = orb.run(dry_run=True)
        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].run_id == results[1].run_id

    @pytest.mark.unit
    def test_steps_executed_in_order(self):
        orb = PipelineOrchestrator(run_id="test_order")
        orb.register(MockSuccessStep(name="first"))
        orb.register(MockSuccessStep(name="second"))
        results = orb.run(dry_run=True)
        assert results[0].step_name == "first"
        assert results[1].step_name == "second"


class TestPipelineOrchestratorFailure:
    @pytest.mark.unit
    def test_failure_propagation(self):
        orb = PipelineOrchestrator(run_id="test_fail")
        orb.register(MockFailureStep())
        results = orb.run(dry_run=False)
        assert len(results) == 1
        assert results[0].success is False
        assert "exit code" in results[0].error

    @pytest.mark.unit
    def test_mixed_steps(self):
        orb = PipelineOrchestrator(run_id="test_mixed")
        orb.register(MockSuccessStep(name="ok"))
        orb.register(MockFailureStep(name="fail"))
        orb.register(MockSuccessStep(name="ok2"))
        results = orb.run(dry_run=False)
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True


class TestPipelineOrchestratorErrorHandling:
    @pytest.mark.unit
    def test_exception_caught(self):
        orb = PipelineOrchestrator(run_id="test_exc")
        orb.register(MockExceptionStep())
        results = orb.run(dry_run=False)
        assert len(results) == 1
        assert results[0].success is False
        assert "RuntimeError" in results[0].error

    @pytest.mark.unit
    def test_d1_failure_swallowed(self, monkeypatch):
        import pipeline.infra.d1_client
        monkeypatch.setattr(pipeline.infra.d1_client, "d1_query", lambda sql: (_ for _ in ()).throw(Exception("D1 down")))
        orb = PipelineOrchestrator(run_id="test_d1_fail")
        orb.register(MockSuccessStep())
        results = orb.run(dry_run=False)
        assert len(results) == 1
        assert results[0].success is True

    @pytest.mark.unit
    def test_dry_run_mode(self):
        orb = PipelineOrchestrator(run_id="test_dry")
        orb.register(MockFailureStep())
        results = orb.run(dry_run=True)
        assert len(results) == 1
        assert results[0].success is True


class TestPipelineStepProtocol:
    @pytest.mark.unit
    def test_protocol_check(self):
        assert isinstance(MockSuccessStep(), PipelineStep)
