#!/usr/bin/env python3
"""docs/state.md 감소 가드 — pre-push 훅에서 호출한다. AIK24-STATE-GUARD-01.

목적: state.md 가 통째로 잘린 채 원격에 올라가는 것을 **커밋 이전에** 막는다.
  2026-10-14 f6ed99a8 — 6,559줄 → 25줄 (아무도 눈치채지 못하고 push 됨)
  2026-10-17 02c5da8f — 2,811줄 → 53줄 (같은 형태)

기준선(old) 대비 새 버전(new)이 threshold 줄 이상 줄면 차단한다.
의도적 감소(사고 복구 커밋)는 `ALLOW_STATE_TRUNCATE=1` 로만 우회한다.

사용법
  python3 scripts/state_guard.py                          # origin/main vs HEAD
  python3 scripts/state_guard.py --old HEAD --new f6ed99a8  # 과거 사고 재현 테스트
  python3 scripts/state_guard.py --threshold 0              # 감소하면 무조건 차단

종료 코드
  0 통과(또는 기준선 없음) · 1 감소 감지
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = "docs/state.md"
DEFAULT_THRESHOLD = 100
BYPASS_ENV = "ALLOW_STATE_TRUNCATE"


def count_lines(ref: str, path: str = STATE_PATH, cwd: Path | None = None) -> int | None:
    """해당 ref 의 파일 줄 수. ref/파일이 없으면 None."""
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            capture_output=True,
            text=True,
            cwd=str(cwd or REPO_ROOT),
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return len(result.stdout.splitlines())


def classify(old_lines: int | None, new_lines: int | None, threshold: int = DEFAULT_THRESHOLD):
    """(status, delta) — status: ok | shrink | unknown."""
    if old_lines is None or new_lines is None:
        return "unknown", 0
    delta = new_lines - old_lines
    if delta <= -abs(threshold):
        return "shrink", delta
    return "ok", delta


def is_bypassed(env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    return str(env.get(BYPASS_ENV, "")).strip() not in ("", "0", "false", "False")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="state.md 감소 가드")
    parser.add_argument("--old", default="origin/main", help="기준선 ref (기본 origin/main)")
    parser.add_argument("--new", default="HEAD", help="비교 대상 ref (기본 HEAD)")
    parser.add_argument("--path", default=STATE_PATH, help=f"감시 대상 (기본 {STATE_PATH})")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD, help="차단 임계 줄 수")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    old_lines = count_lines(args.old, args.path)
    new_lines = count_lines(args.new, args.path)
    status, delta = classify(old_lines, new_lines, args.threshold)

    if status == "unknown":
        if not args.quiet:
            print(f"⏭  state.md 가드: 기준선을 찾을 수 없음 ({args.old} 또는 {args.new}) — 통과")
        return 0

    if status == "shrink" and not is_bypassed():
        print(f"\n🚨 {args.path} 가 {abs(delta)}줄 줄었다 — push 중단", file=sys.stderr)
        print(f"   {args.old}: {old_lines}줄 → {args.new}: {new_lines}줄", file=sys.stderr)
        print(
            "\n확인 절차\n"
            f"  1) 무엇이 사라졌는지 확인: git diff {args.old} {args.new} -- {args.path}\n"
            f"  2) 복구: python3 scripts/state_prepend.py --report <(git show {args.old}:{args.path}) --bottom\n"
            f"  3) 의도적 감소였다면: {BYPASS_ENV}=1 git push ...\n"
            "  ※ 2026-10-14(f6ed99a8, 6,550줄)·2026-10-17(02c5da8f, 2,805줄) 두 번 손실이 있었다.",
            file=sys.stderr,
        )
        return 1

    if status == "shrink":
        if not args.quiet:
            print(f"⚠️  state.md {abs(delta)}줄 감소 — {BYPASS_ENV}=1 로 우회 허용됨")
        return 0

    if not args.quiet:
        print(f"✅ state.md 가드: {old_lines} → {new_lines}줄 ({delta:+d}) 정상")
    return 0


if __name__ == "__main__":
    sys.exit(main())
