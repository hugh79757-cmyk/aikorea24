"""
pipeline/__main__.py — 파이프라인 CLI 진입점 (python -m pipeline)

Usage:
    python -m pipeline                # 전체 파이프라인 실행 (기본값)
    python -m pipeline run            # 전체 파이프라인 실행
    python -m pipeline run --dry-run  # 모의 실행 (step 미실행)
    python -m pipeline status         # 최근 5개 실행 이력
    python -m pipeline status --runs 10  # 최근 10개 실행 이력
"""

import argparse
import sys

from pipeline.infra.d1_client import d1_query
from pipeline.infra.logger import get_scrubbed_logger

logger = get_scrubbed_logger(__name__)


def cmd_status(runs: int = 5) -> None:
    """D1에서 최근 N개 run_id를 조회하여 상태 요약을 출력합니다.

    Args:
        runs: 조회할 실행 수 (기본값: 5)
    """
    from collections import OrderedDict

    sql = (
        f"SELECT run_id, step_name, status, duration_seconds, "
        f"COALESCE(error_message, '') as error_message, started_at "
        f"FROM pipeline_runs "
        f"WHERE run_id IN ("
        f"  SELECT DISTINCT run_id FROM pipeline_runs "
        f"  ORDER BY started_at DESC LIMIT {runs}"
        f") "
        f"ORDER BY started_at DESC"
    )
    rows = d1_query(sql)

    if not rows:
        print("No pipeline runs recorded yet.")
        return

    # run_id 기준 그룹화
    runs_map: dict[str, list[dict]] = OrderedDict()
    for row in rows:
        rid = row["run_id"]
        if rid not in runs_map:
            runs_map[rid] = []
        runs_map[rid].append(row)

    print(f"\n{'=' * 70}")
    print(f"  Pipeline Health — Last {len(runs_map)} Run(s)")
    print(f"{'=' * 70}")
    for run_id, steps in runs_map.items():
        total_ok = sum(1 for s in steps if s["status"] == "success")
        total_fail = sum(1 for s in steps if s["status"] == "failure")
        total_dur = sum(s["duration_seconds"] or 0 for s in steps)
        first_ts = steps[-1]["started_at"][:19] if steps else "?"

        icon = "✅" if total_fail == 0 else "❌"
        print(f"\n  {icon} {run_id}  ({first_ts})")
        print(f"     Steps: {total_ok} OK / {total_fail} Failed  |  Total: {total_dur:.1f}s")
        for s in steps:
            dur = f"{s['duration_seconds']:.1f}s" if s["duration_seconds"] else "-"
            err = f" — {s['error_message'][:60]}" if s["error_message"] else ""
            print(f"       {'✅' if s['status'] == 'success' else '❌'} {s['step_name']:25s} {dur:8s}{err}")
    print()


def cmd_run(dry_run: bool = False) -> None:
    """오케스트레이터를 통해 파이프라인을 실행합니다.

    Args:
        dry_run: True면 단계를 실제로 실행하지 않고 모의 실행
    """
    from pipeline.orchestrator import PipelineOrchestrator

    orchestrator = PipelineOrchestrator()
    # Steps registered here — uncomment when pipeline/steps/ exists
    # orchestrator.register(StepFetchArticles())
    # orchestrator.register(StepGeneratePitches())
    # orchestrator.register(StepWriteThread())
    # orchestrator.register(StepValidate())
    # orchestrator.register(StepPublish())

    results = orchestrator.run(dry_run=dry_run)
    sys.exit(0 if all(r.success for r in results) else 1)


def main() -> None:
    """CLI 메인 함수 — argparse로 명령어를 파싱하고 dispatch합니다."""
    parser = argparse.ArgumentParser(description="aikorea24 Pipeline CLI")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "status"],
        help="Command: run (default) or status",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of runs to show (status command)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate run without executing steps",
    )

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(runs=args.runs)
    elif args.command == "run":
        cmd_run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
