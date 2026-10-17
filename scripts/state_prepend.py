#!/usr/bin/env python3
"""state.md 안전 추가 도구 (append-only 보증) — AIK24-STATE-GUARD-01.

배경 — 실측 사고 2건 (같은 원인)
  2026-10-14 f6ed99a8 — docs/state.md 6,559줄 → 25줄 (157개 항목 손실, 미복구)
  2026-10-17 02c5da8f — docs/state.md 2,811줄 → 53줄 (2,805줄, 같은 날 00482ab8 로 복원)

원인 관용구 — 이 한 줄이 전부다.
    open(p, 'w', encoding='utf-8').write(report + open(p, encoding='utf-8').read())
파이썬은 인자를 왼쪽부터 평가한다.
  1) open(p,'w') 가 먼저 파일을 0바이트로 자른다 (O_TRUNC)
  2) 그 다음 인자에서 같은 파일을 읽으므로 '' 를 얻는다
  3) 결과: report 만 저장. exit 0 + "기록 완료" 출력 → 조용한 데이터 손실

이 도구는 그 관용구를 쓰지 않는다.
  read → 합치기 → 쓰기 전 검사 → 원자적 쓰기 → 쓰기 후 재검사 → 실패 시 자동 복원

사용법
  python3 scripts/state_prepend.py --report docs/report.md            # 맨 위에 추가
  python3 scripts/state_prepend.py --report /tmp/old.md --bottom      # 맨 아래에 추가
  cat report.md | python3 scripts/state_prepend.py --report -
  python3 scripts/state_prepend.py --stats
  python3 scripts/state_prepend.py --report x.md --dry-run

종료 코드
  0 성공 · 2 손실 위험으로 거부 · 3 입출력/사용 오류
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = REPO_ROOT / "docs" / "state.md"

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_ERROR = 3


class ContentLossError(Exception):
    """기존 내용이 사라질 수 있어 쓰기를 거부할 때 발생."""

    def __init__(self, lost: list[str]):
        self.lost = lost
        super().__init__(f"기존 내용 손실 위험: {len(lost)}건")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def headings(text: str) -> list[str]:
    """'## ' 로 시작하는 헤딩 줄만 모은다 (순서 유지)."""
    return [ln.strip() for ln in text.splitlines() if ln.startswith("## ")]


def find_duplicate_headings(old_text: str, report_text: str) -> list[str]:
    """이미 있는 헤딩을 보고서가 다시 포함하면 중복 추가 경고 대상."""
    existing = set(headings(old_text))
    return [h for h in headings(report_text) if h in existing]


def assert_no_loss(old_text: str, new_text: str) -> None:
    """쓰기 전/후 공통 검사 — 기존 헤딩이 하나라도 사라지면 거부."""
    missing = sorted(set(headings(old_text)) - set(headings(new_text)))
    if missing:
        raise ContentLossError(missing)
    old_lines = len(old_text.splitlines())
    new_lines = len(new_text.splitlines())
    if old_text.strip() and new_lines < old_lines:
        raise ContentLossError([f"(헤딩은 남았으나 줄 수 감소: {old_lines} → {new_lines})"])


def build(current: str, report: str, bottom: bool = False) -> str:
    """기존 내용 + 새 보고를 합친다. 기존 내용은 항상 전부 보존된다."""
    report = report.strip("\n")
    if not report:
        raise ValueError("빈 보고서는 추가할 수 없다")
    if not current.strip():
        return report + "\n"
    current = current.rstrip("\n") + "\n"
    if bottom:
        return current + "\n" + report + "\n"
    return report + "\n\n" + current


def make_backup(target: Path) -> Path:
    """쓰기 전 백업 — docs/state.md.bak.YYYYMMDD_HHMM (.gitignore:89 에서 무시됨)."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup = target.with_name(target.name + f".bak.{stamp}")
    shutil.copy2(target, backup)
    return backup


def write_atomic(path: Path, text: str) -> None:
    """같은 디렉터리 임시파일 → os.replace 로 원자적 교체."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".state_prepend.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def file_signature(path: Path):
    """동시 수정 감지용 지문 (없으면 None)."""
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    return (st.st_mtime_ns, st.st_size)


def apply_report(
    target: Path,
    report_text: str,
    bottom: bool = False,
    backup: bool = True,
    dry_run: bool = False,
) -> dict:
    """보고서를 state.md 에 안전하게 추가한다. 반환값은 통계 dict."""
    old_text = read_text(target)
    signature = file_signature(target)
    new_text = build(old_text, report_text, bottom=bottom)
    assert_no_loss(old_text, new_text)  # 1차 방어 — 쓰기 전

    stripped_report = report_text.strip("\n").strip()
    if stripped_report and stripped_report not in new_text:
        raise ContentLossError(["(보고서 본문이 결과물에 존재하지 않음 — build 방향 오류)"])

    stats = {
        "target": str(target),
        "before_lines": len(old_text.splitlines()),
        "after_lines": len(new_text.splitlines()),
        "before_headings": len(headings(old_text)),
        "after_headings": len(headings(new_text)),
        "before_bytes": len(old_text.encode("utf-8")),
        "after_bytes": len(new_text.encode("utf-8")),
        "duplicate_headings": find_duplicate_headings(old_text, report_text),
        "backup": None,
        "dry_run": dry_run,
    }

    if dry_run:
        return stats

    # 백업보다 먼저 확인한다 — 외부 변경 뒤에 백업을 뜨면 백업이 오염된다
    if file_signature(target) != signature:
        raise ContentLossError(["(쓰기 직전 파일이 외부에서 변경됨 — 동시 수정 의심)"])

    if backup and target.exists():
        stats["backup"] = str(make_backup(target))

    write_atomic(target, new_text)

    # 2차 방어 — 디스크에 실제로 남았는지 확인, 실패하면 백업으로 복원
    on_disk = read_text(target)
    try:
        assert_no_loss(old_text, on_disk)
    except ContentLossError:
        if stats["backup"] and Path(stats["backup"]).exists():
            shutil.copy2(stats["backup"], target)
        raise
    return stats


def format_stats(stats: dict) -> str:
    arrow = "→"
    lines = [
        f"대상: {stats['target']}",
        f"줄:   {stats['before_lines']} {arrow} {stats['after_lines']} "
        f"(+{stats['after_lines'] - stats['before_lines']})",
        f"헤딩: {stats['before_headings']} {arrow} {stats['after_headings']} "
        f"(+{stats['after_headings'] - stats['before_headings']})",
        f"크기: {stats['before_bytes']:,} {arrow} {stats['after_bytes']:,} bytes",
    ]
    if stats["backup"]:
        lines.append(f"백업: {stats['backup']}")
    if stats["dry_run"]:
        lines.append("dry-run — 파일을 쓰지 않았다")
    if stats["duplicate_headings"]:
        lines.append(
            f"⚠️ 이미 있는 헤딩 {len(stats['duplicate_headings'])}건이 보고서에 다시 포함됨 "
            f"(중복 추가 의심): {stats['duplicate_headings'][0][:60]}"
        )
    return "\n".join(lines)


def stats_only(target: Path) -> dict:
    text = read_text(target)
    return {
        "target": str(target),
        "exists": target.exists(),
        "lines": len(text.splitlines()),
        "headings": len(headings(text)),
        "bytes": len(text.encode("utf-8")),
        "newest": (headings(text) or ["(없음)"])[0],
        "oldest": (headings(text) or ["(없음)"])[-1],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="state.md 안전 추가 도구 (기존 내용 삭제 금지)")
    parser.add_argument("--report", "-r", help="추가할 보고서 파일 ( - 이면 stdin )")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="대상 파일 (기본 docs/state.md)")
    parser.add_argument("--bottom", action="store_true", help="맨 아래에 추가 (과거 기록 복원용)")
    parser.add_argument("--dry-run", action="store_true", help="쓰지 않고 결과만 계산")
    parser.add_argument("--no-backup", action="store_true", help="백업 생략 (권장하지 않음)")
    parser.add_argument("--stats", action="store_true", help="현재 상태만 출력")
    args = parser.parse_args(argv)

    target = Path(args.target).expanduser()
    if not target.is_absolute():
        target = (REPO_ROOT / target).resolve()

    if args.stats:
        info = stats_only(target)
        if not info["exists"]:
            print(f"{info['target']} 없음")
            return EXIT_ERROR
        print(
            f"{info['target']}: {info['lines']}줄 / {info['bytes']:,} bytes / 헤딩 {info['headings']}개\n"
            f"최신: {info['newest'][:80]}\n최고: {info['oldest'][:80]}"
        )
        return EXIT_OK

    if not args.report:
        parser.error("--report 가 필요하다 (또는 --stats)")

    try:
        if args.report == "-":
            report_text = sys.stdin.read()
        else:
            report_path = Path(args.report).expanduser()
            if not report_path.is_absolute():
                report_path = (Path.cwd() / report_path).resolve()
            report_text = report_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"보고서 읽기 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        info = apply_report(
            target,
            report_text,
            bottom=args.bottom,
            backup=not args.no_backup,
            dry_run=args.dry_run,
        )
    except ContentLossError as exc:
        print(f"🚨 쓰기를 거부했다 — {exc}", file=sys.stderr)
        for item in exc.lost[:10]:
            print(f"   손실 예정: {item[:100]}", file=sys.stderr)
        print(
            "\n원인 후보: 보고서로 대상 파일 전체를 넘겼거나, build 결과가 기존 내용을 담고 있지 않다.",
            file=sys.stderr,
        )
        return EXIT_REFUSED
    except (OSError, ValueError) as exc:
        print(f"실행 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(format_stats(info))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
