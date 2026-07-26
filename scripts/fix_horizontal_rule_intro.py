#!/usr/bin/env python3
"""Phase 36 Task 1 — 도입단락 수평선 수정 (fix_horizontal_rule_intro.py)

사용법:
  --dry-run [파일경로|--all]  변경사항 미리보기 (파일 미수정)
  --apply  [파일경로|--all]   실제 적용
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Tuple

PROJECT_DIR = Path(__file__).resolve().parent.parent
BLOG_DIRS = [PROJECT_DIR / "src" / "content" / "blog", PROJECT_DIR / "content" / "blog"]

# Markdown HR 패턴 (마크다운 표준 + * * * 스페이스 variants)
HR_PATTERN = re.compile(r"^(-{3,}|\*{3,}|\_{3,}|\*\s+\*\s+\*)\s*$")


def parse_frontmatter(content: str) -> Tuple[dict | None, str]:
    """MD 파일에서 frontmatter와 body를 분리한다.

    규칙:
    - 파일 시작이 `---`로 시작해야 frontmatter로 간주
    - 두 번째 `---`까지를 YAML로 해석
    - yaml.safe_load()로 title/date가 있으면 유효 frontmatter로 판정
    - 파싱 실패 시 가능한 범위까지 탐색한 뒤 body만 반환
    """
    delim_positions = []
    for m in re.finditer(r"^---$", content, re.MULTILINE):
        delim_positions.append(m.start())

    if len(delim_positions) < 2:
        return None, content

    first_delim = delim_positions[0]
    # 파일 시작이 아니라면 frontmatter가 아님
    if first_delim > 0 and content[:first_delim].strip():
        return None, content

    for i in range(1, len(delim_positions)):
        second_delim = delim_positions[i]
        fm_str = content[first_delim + 3 : second_delim].strip()
        body = content[second_delim + 3 :].lstrip("\n")
        try:
            import yaml

            fm = yaml.safe_load(fm_str)
            if isinstance(fm, dict) and "title" in fm and "date" in fm:
                return fm, body
        except Exception:
            continue

    # 마지막 fallback: 두 번째 delimiter 기준
    second_delim = delim_positions[1]
    fm_str = content[first_delim + 3 : second_delim].strip()
    body = content[second_delim + 3 :].lstrip("\n")
    return None, body


def build_frontmatter_block(fm: dict | None) -> str:
    """frontmatter dict를 YAML로 직렬화하여 `---` 감싼 블록으로 반환."""
    import yaml

    if fm is None:
        return ""
    payload = yaml.dump(
        fm,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip("\n")
    return f"---\n{payload}\n---"


def find_intro_horizontal_rules(body: str) -> list[dict]:
    """body 영역에서 도입단락 관련 수평선을 찾는다.

    반환값: [{pattern, label, line_no, match}] (파일 기준 1-indexed)
    pattern: 1 (FM_IMMEDIATE_HR), 2 (INTRO_BEFORE_FIRST_H2_HR), 3 (INTRA_INTRO_HR)
    """
    findings: list[dict] = []
    labeled_lines: set[int] = set()
    lines = body.split("\n")

    first_h2_content_pos = None
    for m in re.finditer(r"^##\s+.+$", body, re.MULTILINE):
        first_h2_content_pos = m.start()
        break

    first_non_empty_idx = None
    first_non_text_idx = None

    for idx, line in enumerate(lines):
        if line.strip():
            if HR_PATTERN.match(line.strip()):
                first_non_text_idx = idx
            else:
                first_non_text_idx = None
            if first_non_empty_idx is None:
                first_non_empty_idx = idx
            if first_non_text_idx is not None:
                break

    claim_a = first_non_text_idx is not None and HR_PATTERN.match(
        lines[first_non_text_idx].strip()
    )
    if claim_a:
        findings.append(
            {
                "pattern": 1,
                "label": "FM_IMMEDIATE_HR",
                "line_no": first_non_text_idx + 1,
                "match": lines[first_non_text_idx].strip(),
            }
        )
        labeled_lines.add(first_non_text_idx)

    if first_non_text_idx is not None and first_h2_content_pos is not None:
        search_start = first_non_text_idx + 1
        for idx in range(search_start, len(lines)):
            if idx in labeled_lines:
                continue
            if lines[idx].strip() == "":
                continue
            if re.match(r"^##\s+.+$", lines[idx]):
                break
            if HR_PATTERN.match(lines[idx].strip()):
                findings.append(
                    {
                        "pattern": 2,
                        "label": "INTRO_BEFORE_FIRST_H2_HR",
                        "line_no": idx + 1,
                        "match": lines[idx].strip(),
                    }
                )
                labeled_lines.add(idx)
                break

    if (
        not findings
        and first_non_empty_idx is not None
        and HR_PATTERN.match(lines[first_non_empty_idx].strip())
    ):
        findings.append(
            {
                "pattern": 3,
                "label": "INTRA_INTRO_HR",
                "line_no": first_non_empty_idx + 1,
                "match": lines[first_non_empty_idx].strip(),
            }
        )

    return findings


def apply_fix(body: str) -> tuple[str, list[dict]]:
    """body에서 제거할 수평선을 찾아 없애고 (수정된 body, 수정 리스트)를 반환."""
    findings = find_intro_horizontal_rules(body)
    if not findings:
        return body, []

    # 중복 라인이 없도록 패턴/라인 번호 기준 정렬 후 제거
    sorted_findings = sorted(findings, key=lambda x: x["line_no"])
    lines = body.split("\n")
    remove_indices = {item["line_no"] - 1 for item in sorted_findings}
    new_lines = [line for idx, line in enumerate(lines) if idx not in remove_indices]
    new_body = "\n".join(new_lines)
    return new_body, sorted_findings


def _preview_lines(text: str, count: int = 5) -> list[str]:
    lines = text.split("\n")
    out = []
    for line in lines:
        if len(out) >= count:
            break
        out.append(line)
    return out


def process_file(path: Path, apply: bool) -> dict:
    raw = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)

    if fm is None:
        return {
            "path": path,
            "skipped": True,
            "reason": "frontmatter not detected",
        }

    new_body, findings = apply_fix(body)
    if not findings:
        return {"path": path, "skipped": True, "reason": "no horizontal rule found"}

    removed = [f"{item['line_no']}: {item['match']}" for item in findings]
    result = {
        "path": path,
        "skipped": False,
        "findings": findings,
        "removed": removed,
        "before_body_preview": _preview_lines(body, 5),
        "after_body_preview": _preview_lines(new_body, 5),
    }

    if apply:
        new_raw = build_frontmatter_block(fm) + "\n\n" + new_body
        path.write_text(new_raw, encoding="utf-8")

    return result


def iter_target_files() -> list[Path]:
    out: list[Path] = []
    for d in BLOG_DIRS:
        if d.exists():
            out.extend(sorted(d.glob("*.md")))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="도입단락 수평선 수정 스크립트")
    parser.add_argument("--dry-run", action="store_true", help="변경 미리보기")
    parser.add_argument("--apply", action="store_true", help="실제 적용")
    parser.add_argument("--all", action="store_true", help="전체 블로그 파일 대상")
    parser.add_argument("file", nargs="?", help="단일 파일 경로")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.error("--dry-run 또는 --apply 중 하나를 지정하세요.")

    mode = "apply" if args.apply else "dry-run"

    if args.file:
        targets = [Path(args.file)]
    elif args.all:
        targets = iter_target_files()
    else:
        parser.error("--all 또는 file 경로를 지정하세요.")

    results: list[dict] = []
    errors: list[dict] = []

    for path in targets:
        if not path.exists():
            errors.append({"path": str(path), "reason": "file not found"})
            continue
        try:
            results.append(process_file(path, apply=args.apply))
        except Exception as exc:  # pragma: no cover -- build failure guard
            errors.append({"path": str(path), "reason": str(exc)})

    modified = [r for r in results if not r.get("skipped")]
    skipped = [r for r in results if r.get("skipped")]

    print("=" * 60)
    print(f"도입단락 수평선 수정 스크립트 — 모드: {mode}")
    print(f"대상 파일 수: {len(targets)}")
    print(f"수정 대상: {len(modified)}건 | 건너뜀: {len(skipped)}건 | 오류: {len(errors)}건")
    print("=" * 60)

    for idx, result in enumerate(modified, start=1):
        print(f"\n[{idx}] {result['path']}")
        for line in result["removed"]:
            print(f"  제거 대상 수평선: {line}")
        print("  [수정 전 body 첫 5줄]")
        for line in result["before_body_preview"]:
            print(f"    {line}")
        print("  [수정 후 body 첫 5줄]")
        for line in result["after_body_preview"]:
            print(f"    {line}")

    if errors:
        print("\n[오류 파일]")
        for item in errors:
            print(f"  {item['path']} — {item['reason']}")

    print("\n" + "=" * 60)
    print(f"완료: {mode} / 변경 {len(modified)}건 / 오류 {len(errors)}건")
    print("=" * 60)


if __name__ == "__main__":
    main()
