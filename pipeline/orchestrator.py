"""
pipeline/orchestrator.py — PipelineStep 프로토콜 및 PipelineOrchestrator 클래스

PipelineStep: 각 파이프라인 단계가 따라야 할 프로토콜 (name + run() 메서드)
PipelineOrchestrator: 단계를 등록하고 순차 실행하며, 각 단계의 시간/성공여부를 기록

Usage:
    from pipeline.orchestrator import PipelineStep, PipelineOrchestrator

    class MyStep:
        name = "my_step"
        def run(self) -> int:
            print("running...")
            return 0

    orb = PipelineOrchestrator()
    orb.register(MyStep())
    results = orb.run()
"""

import json
import os
import time
import urllib.request
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from pipeline.infra.models import PipelineStepResult
from pipeline.infra.logger import get_pipeline_logger, log_step


@runtime_checkable
class PipelineStep(Protocol):
    """Protocol for pipeline steps.

    Each step must have a name and a run() method that returns
    an integer exit code (0 = success, nonzero = failure).
    """

    name: str

    def run(self) -> int: ...


class PipelineOrchestrator:
    """파이프라인 오케스트레이터 — 단계 등록, 순차 실행, D1 기록, 요약 출력"""

    def __init__(self, run_id: str = ""):
        self._steps: list[PipelineStep] = []
        self.results: list[PipelineStepResult] = []
        self.run_id = run_id or datetime.now().strftime("run_%Y%m%d_%H%M%S")
        self._log = get_pipeline_logger("pipeline.orchestrator", run_id=self.run_id)

    def register(self, step: PipelineStep) -> None:
        """단계를 등록합니다."""
        self._steps.append(step)
        self._log.info(f"Registered step: {step.name}")

    def run(self, dry_run: bool = False) -> list[PipelineStepResult]:
        """등록된 모든 단계를 순차 실행합니다."""
        self.results = []
        all_success = True

        for step in self._steps:
            result = PipelineStepResult(
                step_name=step.name,
                success=False,
                duration_seconds=0.0,
                error=None,
                run_id=self.run_id,
            )

            try:
                with log_step(self._log, step.name):
                    start = time.monotonic()
                    if dry_run:
                        self._log.info(f"[DRY RUN] Would execute: {step.name}")
                        exit_code = 0
                    else:
                        exit_code = step.run()
                    elapsed = time.monotonic() - start

                result.success = exit_code == 0
                result.duration_seconds = elapsed
                if not result.success:
                    result.error = f"exit code {exit_code}"
                    self._log.error(f"Step '{step.name}' failed ({result.error})")
                else:
                    self._log.info(f"Step '{step.name}' completed in {elapsed:.1f}s")

            except Exception as e:
                elapsed = time.monotonic() - start
                result.success = False
                result.duration_seconds = elapsed
                result.error = f"{type(e).__name__}: {e}"
                self._log.exception(f"Step '{step.name}' raised {type(e).__name__}")
                self._send_telegram_failure(result)

            self.results.append(result)
            if not dry_run:
                self._record_to_d1(result)

            if not result.success:
                all_success = False
                self._send_telegram_failure(result)

        self._print_summary()
        return self.results

    def _record_to_d1(self, result: PipelineStepResult) -> None:
        """단계 결과를 D1 pipeline_runs 테이블에 기록 (best-effort).

        SQL 인젝션 방지: 모든 문자열 필드의 작은따옴표를 두 배로 이스케이프.
        """
        from pipeline.infra.d1_client import d1_query

        def esc(s: str) -> str:
            return s.replace("'", "''")

        error_sql = f"'{esc(result.error)}'" if result.error else "NULL"
        status = "success" if result.success else "failure"

        sql = (
            f"INSERT INTO pipeline_runs "
            f"(run_id, step_name, status, duration_seconds, error_message, started_at, completed_at) "
            f"VALUES ("
            f"'{esc(result.run_id)}', '{esc(result.step_name)}', '{status}', "
            f"{result.duration_seconds:.3f}, {error_sql}, "
            f"datetime('now'), datetime('now')"
            f")"
        )
        try:
            d1_query(sql)
        except Exception as e:
            self._log.warning(f"D1 기록 실패: {e}")

    def _send_telegram_failure(self, result: PipelineStepResult) -> None:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not bot_token or not chat_id:
            return

        message = (
            f"❌ <b>Pipeline step failed</b>\n"
            f"Step: {result.step_name}\n"
            f"Error: {result.error or 'exit code != 0'}\n"
            f"Duration: {result.duration_seconds:.1f}s\n"
            f"Run: {result.run_id}"
        )

        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = json.dumps({
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            self._log.info(f"Telegram failure alert sent for step '{result.step_name}'")
        except Exception as e:
            self._log.warning(f"Telegram failure alert failed: {e}")

    def _print_summary(self) -> None:
        """파이프라인 실행 요약을 출력합니다."""
        print("\n" + "=" * 60)
        print(f"  Pipeline Run Summary — {self.run_id}")
        print("=" * 60)
        for r in self.results:
            icon = "✅" if r.success else "❌"
            dur = f"{r.duration_seconds:.1f}s"
            err = f" — {r.error}" if r.error else ""
            print(f"  {icon} {r.step_name}: {dur}{err}")
        total = sum(r.duration_seconds for r in self.results)
        all_ok = all(r.success for r in self.results)
        print(f"\n  {'✅ All steps succeeded' if all_ok else '❌ Some steps failed'}")
        print(f"  Total time: {total:.1f}s")
        print("=" * 60)
