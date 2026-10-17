#!/usr/bin/env python3
"""docs/state.md 로테이션 — 오래된 항목을 docs/state-archive/YYYY-MM.md 로 옮긴다. AIK24-STATE-GUARD-01.

목적: state.md 무한 성장 차단. 파일이 커지면
  (a) 전체 재작성만이 prepend 수단이 되고 (사고 원인 관용구가 나오는 환경),
  (b) Read 도구 한계(2,000줄)를 넘어 사람/에이전트가 결과를 검증할 수 없다,
  (c) 잘렸을 때 사고 반경이 커진다.
→ 30일 지난 항목을 월별 아카이브로 내리고 state.md 는 최근 것만 유지한다.

안전 규칙
  - 기본은 dry-run. 실제 이동은 --apply.
  - 헤딩 총집합(집합 아님 — 개수까지) 이 이동 전후 동일하지 않으면 **아무것도 쓰지 않고 중단**.
  - 날짜를 못 읽는 헤딩(예: `## 진행 중 (...)`)은 state.md 에 그대로 둔다.
  - state.md 쓰기 전 자동 백업 (state_prepend.make_backup 재사용).

사용법
  python3 scripts/state_rotate.py --days 30            # 미리보기
  python3 scripts/state_rotate.py --days 30 --apply    # 실제 이동
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from state_prepend import (  # noqa: E402
    ContentLossError,
    headings,
    make_backup,
    read_text,
    write_atomic,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = REPO_ROOT / "docs" / "state.md"
ARCHIVE_DIR = REPO_ROOT / "docs" / "state-archive"
HEADING_RE = re.compile(r"^##\s")
DATE_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})")
POINTER_PREFIX = "<!-- state-archive:"


def split_blocks(text: str) -> tuple[str, list[tuple[str, str]]]:
    """(preamble, [(heading, block)]) — block 은 헤딩 줄부터 다음 헤딩 직전까지."""
    lines = text.splitlines(keepends=True)
    preamble_lines: list[str] = []
    blocks: list[list[str]] = []
    for line in lines:
        if HEADING_RE.match(line):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
        else:
            preamble_lines.append(line)
    return "".join(preamble_lines), [("".join(b).splitlines()[0], "".join(b)) for b in blocks]


def block_date(heading: str) -> str | None:
    match = DATE_RE.match(heading)
    return match.group(1) if match else None


def plan_rotation(
    blocks: list[tuple[str, str]], days: int, today: date | None = None
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """(keep, move) — keep 는 state.md 에 남는 블록."""
    today = today or date.today()
    cutoff = today - timedelta(days=days)
    keep: list[tuple[str, str]] = []
    move: list[tuple[str, str]] = []
    for heading, block in blocks:
        raw = block_date(heading)
        if raw is None:
            keep.append((heading, block))
            continue
        try:
            when = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            keep.append((heading, block))
            continue
        (move if when < cutoff else keep).append((heading, block))
    return keep, move


def pointer_lines(archive_names: list[str], counts: dict[str, int]) -> str:
    out = []
    for name in sorted(archive_names, reverse=True):
        out.append(f"{POINTER_PREFIX} docs/state-archive/{name}.md ({counts.get(name, 0)}개 항목) -->")
    return "\n".join(out)


def strip_pointers(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.startswith(POINTER_PREFIX))


def heading_counter(texts: list[str]) -> Counter:
    counter: Counter = Counter()
    for text in texts:
        counter.update(headings(text))
    return counter


def apply_rotation(target: Path = DEFAULT_TARGET, days: int = 30, apply: bool = False) -> dict:
    state_text = read_text(target)
    if not state_text.strip():
        raise ContentLossError(["(state.md 가 비어 있음 — 로테이션 중단)"])

    preamble, blocks = split_blocks(state_text)
    keep, move = plan_rotation(blocks, days)

    archives: dict[str, list[tuple[str, str]]] = {}
    for heading, block in move:
        raw = block_date(heading) or ""
        archives.setdefault(raw[:7] or "unknown", []).append((heading, block))

    archive_dir = target.parent / "state-archive"
    existing_archive_texts: dict[str, str] = {}
    for month in archives:
        path = archive_dir / f"{month}.md"
        existing_archive_texts[month] = read_text(path)

    # 이동 전후 전체 헤딩 집합 보존 검사 (state.md + 모든 아카이브)
    before = heading_counter([state_text] + list(existing_archive_texts.values()))
    after_texts = [preamble + "".join(block for _, block in keep)]
    for month, items in archives.items():
        after_texts.append("".join(block for _, block in items) + existing_archive_texts[month])
    after = heading_counter(after_texts)
    if before != after:
        missing = before - after
        extra = after - before
        raise ContentLossError(
            [f"헤딩 집합 불일치(사라짐 {sum(missing.values())}건, 늘어남 {sum(extra.values())}건) — 쓰지 않고 중단"]
        )

    archive_counts = {}
    for month, items in archives.items():
        archive_counts[month] = sum(
            1 for ln in existing_archive_texts[month].splitlines() if ln.startswith("## ")
        ) + len(items)

    new_state = strip_pointers(after_texts[0]).rstrip("\n")
    if archives:
        new_state = new_state + "\n\n" + pointer_lines(list(archives), archive_counts) + "\n"
    else:
        new_state = new_state + "\n"

    result = {
        "target": str(target),
        "days": days,
        "keep": len(keep),
        "move": len(move),
        "archives": {month: len(items) for month, items in archives.items()},
        "state_before_lines": len(state_text.splitlines()),
        "state_after_lines": len(new_state.splitlines()),
        "applied": False,
        "backup": None,
    }
    if not apply or not move:
        return result

    archive_dir.mkdir(parents=True, exist_ok=True)
    result["backup"] = str(make_backup(target))
    for month, items in archives.items():
        path = archive_dir / f"{month}.md"
        body = "".join(block for _, block in items) + existing_archive_texts[month]
        write_atomic(path, body)
    write_atomic(target, new_state)
    result["applied"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="state.md 로테이션 (기본 dry-run)")
    parser.add_argument("--days", type=int, default=30, help="이 일수보다 오래된 항목을 아카이브로")
    parser.add_argument("--target", default=str(DEFAULT_TARGET))
    parser.add_argument("--apply", action="store_true", help="실제로 이동 (기본은 미리보기)")
    args = parser.parse_args(argv)

    target = Path(args.target).expanduser()
    if not target.is_absolute():
        target = (REPO_ROOT / target).resolve()

    try:
        result = apply_rotation(target, days=args.days, apply=args.apply)
    except ContentLossError as exc:
        print(f"🚨 로테이션 중단 — {exc}", file=sys.stderr)
        return 2

    print(
        f"{'적용' if result['applied'] else '미리보기'}: {result['target']}\n"
        f"  기준: {result['days']}일 이전\n"
        f"  state.md 유지 {result['keep']}개 / 이동 {result['move']}개\n"
        f"  줄: {result['state_before_lines']} → {result['state_after_lines']}"
    )
    for month, count in sorted(result["archives"].items(), reverse=True):
        print(f"  → docs/state-archive/{month}.md 에 {count}개")
    if result["backup"]:
        print(f"  백업: {result['backup']}")
    if not result["applied"]:
        print("  (dry-run — 파일을 쓰지 않았다. 적용하려면 --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
