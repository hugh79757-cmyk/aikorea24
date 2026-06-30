"""
pipeline/steps/step_run_threads.py — Threads 파이프라인 실행 스텝

Strangler Fig 패턴: 기존 scripts/threads/main_v3.py 를 subprocess로 호출.
main_v3.py 는 블랙박스로 유지되며, Phase 4에서 직접 임포트로 전환 예정.
"""

import subprocess
import sys
import time
from pathlib import Path

from pipeline.infra.config import project_root

# 프로젝트 경로 계산
PROJECT_DIR = project_root()
VENV_PYTHON = str(PROJECT_DIR / ".venv" / "bin" / "python3")
OLD_SCRIPT = str(PROJECT_DIR / "scripts" / "threads" / "main_v3.py")


class StepRunThreads:
    """Threads 파이프라인 실행 스텝 — main_v3.py --once 을 subprocess로 호출"""

    name: str = "run_threads"

    def run(self) -> int:
        """main_v3.py --once 를 subprocess로 실행하고 종료 코드 반환"""
        try:
            result = subprocess.run(
                [VENV_PYTHON, OLD_SCRIPT, "--once"],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(PROJECT_DIR),
            )
            # stdout 출력
            if result.stdout:
                print(result.stdout, end="")
            # stderr 출력
            if result.stderr:
                print(result.stderr, file=sys.stderr, end="")
            return result.returncode

        except subprocess.TimeoutExpired:
            print("StepRunThreads: 실행 시간 초과 (600초)", file=sys.stderr)
            return 1

        except Exception as e:
            print(f"StepRunThreads: 예외 발생 — {type(e).__name__}: {e}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    step = StepRunThreads()
    print(f"Running step: {step.name}")
    exit_code = step.run()
    print(f"Step completed with exit code: {exit_code}")
    sys.exit(exit_code)
