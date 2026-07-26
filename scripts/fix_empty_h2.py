#!/usr/bin/env python3
"""
빈 H2 수정 스크립트 (fix_empty_h2.py)

- Pattern 1, 2: 자동 수정 (빈 H2 라인 삭제 + 주변 빈 줄 정규화)
- Pattern 3: 리포트만 출력, 자동 수정 안 함 (수동 처리 필요)

사용법:
  python3 scripts/fix_empty_h2.py --dry-run      # 미리보기
  python3 scripts/fix_empty_h2.py --apply        # 실제 적용
  python3 scripts/fix_empty_h2.py --file FILE    # 특정 파일만
"""
import re
import sys
import argparse
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
BLOG_DIR = PROJECT_DIR / "src" / "content" / "blog"

# Pattern 3 제외 대상 파일 (수동 처리)
PATTERN3_EXCLUDE = {
    "2026-07-21-010-소재-과학-혁신으로-차세대-ai를-발전시키다-알고리즘-너머의-핵심-동력.md",
    "2026-07-24-007-미국과-주요국들-중국-정상회의에서-강력한-보안-오픈-소스-ai-지지-선언-apec-성명서-분석.md",
    "2026-07-25-005-실리콘밸리는-중국-ai에-대해-완전히-나뉘어-있습니다-대형-스타트업과-소형-기업의-시각-차이-분석.md",
}


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """MD 파일에서 frontmatter와 body 분리"""
    delim_positions = []
    for m in re.finditer(r'^---$', content, re.MULTILINE):
        delim_positions.append(m.start())
    
    if len(delim_positions) < 2:
        return {}, content
    
    first_delim = delim_positions[0]
    if first_delim > 0 and content[:first_delim].strip():
        return {}, content
    
    for i in range(1, len(delim_positions)):
        second_delim = delim_positions[i]
        fm_str = content[first_delim + 3:second_delim].strip()
        body = content[second_delim + 3:].lstrip('\n')
        try:
            import yaml
            fm = yaml.safe_load(fm_str)
            if fm and isinstance(fm, dict) and 'title' in fm and 'date' in fm:
                return fm, body
        except Exception:
            continue
    
    second_delim = delim_positions[1]
    fm_str = content[first_delim + 3:second_delim].strip()
    body = content[second_delim + 3:].lstrip('\n')
    return {}, body


def find_all_h2_positions(body: str) -> list[tuple[int, int, str]]:
    """본문에서 모든 H2 헤딩의 위치와 텍스트 반환"""
    h2_list = []
    for match in re.finditer(r'^##\s+(.+)$', body, re.MULTILINE):
        h2_list.append((match.start(), match.end(), match.group(1).strip()))
    return h2_list


def is_h2_empty(body: str, h2_start: int, h2_end: int, next_h2_start: int | None) -> tuple[bool, int]:
    """
    H2가 빈 H2인지 확인.
    반환: (is_empty, empty_type)
    empty_type: 1=Pattern1(공백만), 2=Pattern2(바로 다음 H2), 0=비어있지 않음
    """
    if next_h2_start is not None:
        between = body[h2_end:next_h2_start]
    else:
        between = body[h2_end:]
    
    stripped = between.strip()
    if not stripped:
        # Pattern 1: 공백만 있음
        return True, 1
    
    # Pattern 2: 공백 문자도 거의 없고 바로 다음 H2
    # (줄바꿈 1개 이하)
    if not re.search(r'\n\s*\n', between) and len(stripped) == 0:
        return True, 2
    
    return False, 0


def fix_empty_h2_in_body(body: str, filename: str) -> tuple[str, list[dict]]:
    """본문에서 빈 H2 수정. 반환: (수정된 본문, 수정 로그 리스트)"""
    h2_list = find_all_h2_positions(body)
    if len(h2_list) < 2:
        return body, []
    
    modifications = []
    new_body = body
    offset = 0  # 삭제로 인한 위치 오프셋
    
    for i, (h2_start, h2_end, h2_text) in enumerate(h2_list):
        adj_start = h2_start + offset
        adj_end = h2_end + offset
        
        next_h2_start = h2_list[i + 1][0] + offset if i + 1 < len(h2_list) else None
        
        is_empty, pattern_type = is_h2_empty(new_body, adj_start, adj_end, next_h2_start)
        
        if is_empty:
            # 빈 H2 라인 찾기 (줄 전체)
            line_start = new_body.rfind('\n', 0, adj_start) + 1
            line_end = new_body.find('\n', adj_end)
            if line_end == -1:
                line_end = len(new_body)
            
            # 빈 H2 라인 삭제
            before = new_body[:line_start]
            after = new_body[line_end:]
            
            # 주변 빈 줄 정규화 (최대 1개 연속)
            combined = before + after
            combined = re.sub(r'\n{3,}', '\n\n', combined)
            
            deleted_text = new_body[line_start:line_end].strip()
            new_body = combined
            offset = len(new_body) - len(body)  # 전체 길이 차이
            
            modifications.append({
                'pattern': pattern_type,
                'empty_h2': deleted_text,
                'next_h2': h2_list[i + 1][2] if i + 1 < len(h2_list) else None,
                'action': 'deleted'
            })
    
    return new_body, modifications


def process_file(filepath: Path, dry_run: bool = False) -> dict:
    """단일 파일 처리"""
    filename = filepath.name
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    fm, body = parse_frontmatter(content)
    
    # Pattern 3 제외 파일 체크
    pattern3_excluded = filename in PATTERN3_EXCLUDE
    
    new_body, modifications = fix_empty_h2_in_body(body, filename)
    
    # Pattern 3 파일인 경우 로그만
    pattern3_logs = []
    if pattern3_excluded:
        h2_list = find_all_h2_positions(body)
        for i, (h2_start, h2_end, h2_text) in enumerate(h2_list):
            if i + 1 < len(h2_list):
                next_h2_start, _, next_h2_text = h2_list[i + 1]
                between = body[h2_end:next_h2_start]
                stripped = between.strip()
                # 수평선 등 비텍스트만 있는지 확인
                if stripped and not re.search(r'[가-힣a-zA-Z0-9]', stripped):
                    pattern3_logs.append({
                        'pattern': 3,
                        'empty_h2': h2_text,
                        'next_h2': next_h2_text,
                        'action': 'skipped (manual required)'
                    })
    
    if not modifications and not pattern3_logs:
        return {'file': filename, 'status': 'skip', 'reason': '빈 H2 없음'}
    
    if dry_run:
        return {
            'file': filename,
            'status': 'dry-run',
            'modifications': modifications,
            'pattern3_logs': pattern3_logs,
        }
    
    # 실제 적용
    new_content = content[:content.index(body)] + new_body + content[content.index(body) + len(body):]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    return {
        'file': filename,
        'status': 'updated' if modifications else 'pattern3-skipped',
        'modifications': modifications,
        'pattern3_logs': pattern3_logs,
    }


def main():
    parser = argparse.ArgumentParser(description='빈 H2 수정')
    parser.add_argument('--dry-run', action='store_true', help='미리보기만 실행')
    parser.add_argument('--apply', action='store_true', help='실제 적용')
    parser.add_argument('--file', type=str, help='특정 파일만 처리')
    parser.add_argument('--all', action='store_true', help='전체 파일 처리')
    args = parser.parse_args()
    
    if not args.dry_run and not args.apply:
        print("에러: --dry-run 또는 --apply 중 하나를 지정하세요")
        sys.exit(1)
    
    if args.file:
        files = [BLOG_DIR / args.file]
    elif args.all:
        files = sorted(BLOG_DIR.glob("*.md"))
    else:
        test_files = [
            "2026-07-25-009-코그니션의-포크-인수-ai-개성이-경쟁-우위가-된-이유를-분석합니다.md",
            "2026-07-25-011-알파폴드-ai가-유전자-편집-단백질을-더-안전하게-재설계하는-방법과-미래-전망.md",
        ]
        files = [BLOG_DIR / f for f in test_files if (BLOG_DIR / f).exists()]
    
    print(f"대상 파일: {len(files)}개 (mode: {'DRY-RUN' if args.dry_run else 'APPLY'})\n")
    
    total_mods = 0
    total_pattern3 = 0
    updated_files = 0
    
    for fpath in files:
        if not fpath.exists():
            print(f"  ⚠️  {fpath.name}: 파일 없음")
            continue
        
        result = process_file(fpath, dry_run=args.dry_run)
        
        if result['status'] == 'skip':
            continue
        
        if result['status'] in ('dry-run', 'updated'):
            updated_files += 1
            for mod in result.get('modifications', []):
                total_mods += 1
                action = "삭제 예정" if args.dry_run else "삭제됨"
                print(f"  🔧 {result['file']}")
                print(f"     Pattern {mod['pattern']}: \"{mod['empty_h2']}\" → {action}")
                if mod['next_h2']:
                    print(f"     다음 H2: \"{mod['next_h2']}\"")
        
        for p3 in result.get('pattern3_logs', []):
            total_pattern3 += 1
            print(f"  ⏭️  {result['file']} (Pattern 3 - 수동 처리 필요)")
            print(f"     빈 H2: \"{p3['empty_h2']}\" → 다음 H2: \"{p3['next_h2']}\"")
    
    print(f"\n{'='*55}")
    print(f"요약: 수정 대상 파일 {updated_files}개, 빈 H2 삭제 {total_mods}건 (Pattern 1,2)")
    if total_pattern3 > 0:
        print(f"       Pattern 3 (수동 처리): {total_pattern3}건")
    print(f"{'='*55}")


if __name__ == '__main__':
    main()