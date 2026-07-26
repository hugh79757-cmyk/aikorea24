#!/usr/bin/env python3
"""Phase 36 Task 1 — 도입단락 수평선 감지 (fix V3)

정정 포인트:
- 첫 비텍스트 줄이 수평선이면 Pattern 1만 기록
- frontmatter 경계가 아니라 body 첫 비텍스트 HR → 첫 H2까지 영역에서만 Pattern 2를 허용
- 같은 위치의 Pattern 1/2 2중 보고를 제거
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
BLOG_DIRS = [
    PROJECT_DIR / "src" / "content" / "blog",
    PROJECT_DIR / "content" / "blog",
]
HR_PATTERN = re.compile(r"^(-{3,}|\*{3,}|\_{3,}|\*\s+\*\s+\*)\s*$")


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """MD 파일에서 frontmatter와 body 분리"""
    delim_positions = []
    for m in re.finditer(r"^---$", content, re.MULTILINE):
        delim_positions.append(m.start())

    if len(delim_positions) < 2:
        return {}, content

    first_delim = delim_positions[0]
    if first_delim > 0 and content[:first_delim].strip():
        return {}, content

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

    second_delim = delim_positions[1]
    fm_str = content[first_delim + 3 : second_delim].strip()
    body = content[second_delim + 3 :].lstrip("\n")
    return {}, body


def detect_horizontal_rule_intro(body: str) -> list[dict]:
    """도입단락 관련 수평선 패턴 감지 (3종, 중복 제거)"""
    findings: list[dict] = []
    labeled_lines: set[int] = set()
    lines = body.split("\n")

    first_h2_content_pos = None
    for m in re.finditer(r"^##\s+.+$", body, re.MULTILINE):
        first_h2_content_pos = m.start()
        break

    before_h2 = body[:first_h2_content_pos] if first_h2_content_pos is not None else body

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

    claim_a = first_non_text_idx is not None and HR_PATTERN.match(lines[first_non_text_idx].strip())
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


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="도입단락 수평선 감지 (Task 1)")
    parser.add_argument("--all", action="store_true", help="전체 블로그 포스트 검사")
    parser.add_argument("--file", type=str, help="특정 파일만 검사")
    parser.add_argument("--csv", action="store_true", help="탭 구분 요약 출력")
    args = parser.parse_args()

    files: list[Path] = []
    if args.file:
        files = [Path(args.file)]
    elif args.all:
        for d in BLOG_DIRS:
            if d.exists():
                files.extend(sorted(d.glob("*.md")))

    all_findings: list[dict] = []
    total_scanned = 0

    for fpath in files:
        if not fpath.exists():
            continue
        total_scanned += 1
        content = fpath.read_text(encoding="utf-8")
        _, body = parse_frontmatter(content)
        findings = detect_horizontal_rule_intro(body)
        if findings:
            for d in findings:
                d["file"] = fpath.name
                d["path"] = str(fpath)
            all_findings.extend(findings)

    if args.csv:
        rows = ["file\tpattern\tlabel\tline_no\tmatch"]
        rows.extend(
            f"{row['file']}\t{row['pattern']}\t{row['label']}\t{row['line_no']}\t{row['match']}"
            for row in all_findings
        )
        rows.append(
            f"SUMMARY\tPattern1={sum(1 for f in all_findings if f['pattern']==1)}\t"
            f"Pattern2={sum(1 for f in all_findings if f['pattern']==2)}\t"
            f"Pattern3={sum(1 for f in all_findings if f['pattern']==3)}\t"
            f"total={len(all_findings)}"
        )
        print("\n".join(rows))
    else:
        print(f"검사 대상: {len(files)}개 파일\n")

        print(f"{'=' * 60}")
        print(f"도입단락 수평선 감사 결과")
        print(f"{'=' * 60}")
        print(f"총 스캔: {total_scanned}건")
        print(f"감지 건수: {len(all_findings)}건")
        print(f"{'=' * 60}\n")

        for finding in all_findings:
            print(f"📄 {finding['path']}")
            print(f" Pattern {finding['pattern']} ({finding['label']})")
            print(f" 라인: {finding['line_no']} | 매치: {finding['match']}")
            print()

        print(f"{'=' * 60}")
        print(
            f"요약: Pattern 1={sum(1 for f in all_findings if f['pattern']==1)}, "
            f"Pattern 2={sum(1 for f in all_findings if f['pattern']==2)}, "
            f"Pattern 3={sum(1 for f in all_findings if f['pattern']==3)}, "
            f"합계={len(all_findings)}"
        )
        print(f"{'=' * 60}")

    if all_findings:
        sys.exit(1)

if __name__ == "__main__":
    main()
