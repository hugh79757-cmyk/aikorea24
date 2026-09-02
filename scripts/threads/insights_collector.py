#!/Users/twinssn/Projects/aikorea24/.venv/bin/python3
"""insights_collector.py — launchd 일 1회 wrapper (Phase 38-02)

kr.aikorea24.threads-insights.plist가 06:00에 실행.
collect_insights(days=2) → analyze() 순서로 진행, 어느 단계 실패해도 종료 코드 0
(수집 실패는 performance_log.metrics.error에 이미 기록됨 — 알림 불필요, 익일 재수집).
"""
import sys
from datetime import datetime

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))

from performance_log import collect_insights, analyze, _log


def main():
    _log(f'=== insights 수집 시작 {datetime.now().isoformat()} ===')
    try:
        n = collect_insights(days=2)
        _log(f'수집 결과: {n}건')
    except Exception as e:  # noqa: BLE001
        _log(f'❌ 수집 중단 (익일 재시도): {e}')
    try:
        analyze()
    except Exception as e:  # noqa: BLE001
        _log(f'❌ 분석 실패 (익일 재시도): {e}')
    _log('=== 종료 ===')


if __name__ == '__main__':
    main()
